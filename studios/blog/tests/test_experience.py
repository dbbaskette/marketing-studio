"""User-facing discovery and memory invariants; no live accounts or model calls."""

import base64
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hub_fixtures import SCRIPTS
import experience
import studio


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'writing'

    def cli(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'studio.py'), '--root', str(self.root), *args],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return json.loads(result.stdout) if ok else result.stderr

    def file(self, name, text):
        path = self.base / name
        path.write_text(text)
        return str(path)

    def create(self, title='A useful handoff'):
        self.cli('init')
        return self.cli('article', 'create', '--title', title, '--mode', 'first-draft')['id']

    def test_home_is_read_only_bounded_searchable_and_handles_duplicate_titles(self):
        self.assertEqual(self.cli('home')['workspace_status'], 'new')
        self.assertFalse(self.root.exists())
        first = self.create()
        second = self.create()
        self.cli(
            'article',
            'progress',
            '--id',
            first,
            '--stage',
            'outline',
            '--next-step',
            'Write when asked',
        )
        result = self.cli('home', '--query', 'useful', '--limit', '1')
        self.assertTrue(result['truncated'])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['items'][0]['id'], first)
        self.assertEqual(self.cli('home', '--offset', '1')['items'][0]['id'], second)
        self.assertEqual(self.cli('home', '--query', second)['total'], 1)
        self.assertEqual(self.cli('home', '--stage', 'outline')['total'], 1)
        self.assertEqual(self.cli('home', '--query', 'missing')['items'], [])
        self.cli('home', '--limit', '0', ok=False)
        # An unrelated corrupt article doesn't hide the usable work.
        (self.root / 'articles' / second / 'session.json').write_text('broken')
        result = self.cli('home')
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['problem_count'], 1)

    def test_article_memory_correction_forgetting_history_and_review_freshness(self):
        aid = self.create()
        self.cli(
            'article',
            'save',
            '--id',
            aid,
            '--kind',
            'draft',
            '--file',
            self.file('draft.md', 'A draft.'),
        )
        self.cli(
            'article',
            'review',
            '--id',
            aid,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            self.file('review.json', '{"findings":[]}'),
        )
        self.cli(
            'article',
            'remember',
            '--id',
            aid,
            '--key',
            'audience',
            '--file',
            self.file('memory.md', 'Write for engineers.'),
        )
        context = self.cli('context', '--id', aid)
        self.assertEqual(context['article_memory'][0]['text'], 'Write for engineers.')
        self.assertEqual(context['reviews']['proofread'], 'stale')
        self.cli(
            'article',
            'remember',
            '--id',
            aid,
            '--key',
            'audience',
            '--file',
            self.file('memory.md', 'Write for managers.'),
        )
        self.assertEqual(self.cli('context', '--id', aid)['article_memory'][0]['revision'], 2)
        self.cli('article', 'forget', '--id', aid, '--key', 'audience')
        self.assertEqual(self.cli('context', '--id', aid)['article_memory'], [])
        saved = studio.read_json(self.root / 'articles' / aid / 'session.json')['memory'][
            'audience'
        ]
        self.assertEqual(saved['status'], 'forgotten')
        self.assertEqual(len(saved['history']), 2)
        self.assertEqual(saved['history'][0]['text'], 'Write for engineers.')
        self.assertEqual((self.root / 'articles' / aid / 'DRAFT.md').read_text(), 'A draft.')
        self.cli('article', 'forget', '--id', aid, '--key', 'missing', ok=False)
        self.cli(
            'article',
            'remember',
            '--id',
            aid,
            '--key',
            '../../escape',
            '--file',
            self.file('memory.md', 'x'),
            ok=False,
        )
        self.cli(
            'article',
            'remember',
            '--id',
            aid,
            '--key',
            'large',
            '--file',
            self.file('memory.md', 'x' * 4001),
            ok=False,
        )

    def test_detaching_team_memory_only_changes_selected_article(self):
        aid = self.create()
        path = self.root / 'articles' / aid / 'session.json'
        record = studio.read_json(path)
        record['hub_context'] = {
            'hub': 'h',
            'revision': 'r',
            'selected': [{'item': 'one', 'revision': 'old'}, {'item': 'two', 'revision': 'other'}],
        }
        studio.write_json(path, record)
        self.cli('article', 'detach-context', '--id', aid, '--item', 'one')
        self.assertEqual(
            self.cli('context', '--id', aid)['team_context']['selected'],
            [{'item': 'two', 'revision': 'other'}],
        )
        self.cli('article', 'detach-context', '--id', aid, '--item', 'missing', ok=False)

    def test_readiness_never_exposes_auth_output_and_does_not_mutate_workspace(self):
        secret = 'sensitive@example.invalid SECRET'

        def fake(arguments):
            return subprocess.CompletedProcess(
                arguments,
                0,
                json.dumps({'loggedIn': True, 'email': secret}) if arguments[0] == 'claude' else '',
                'Logged in using ChatGPT ' + secret,
            )

        with (
            patch.object(experience.shutil, 'which', return_value='/fixture/tool'),
            patch.object(experience, 'probe', side_effect=fake),
        ):
            result = experience.readiness(self.root)
        self.assertTrue(
            all(value['status'] == 'signed-in' for value in result['harnesses'].values())
        )
        self.assertNotIn(secret, json.dumps(result))
        self.assertFalse(self.root.exists())
        self.assertEqual(result['google']['status'], 'not-checked')
        # An installed copy is the whole skill plus the manifest setup wrote; a checkout has none.
        package = self.base / 'installed skill'
        shutil.copytree(
            SCRIPTS.parent, package, ignore=shutil.ignore_patterns('__pycache__', '*.pyc')
        )
        version = (SCRIPTS.parent / 'VERSION').read_text().strip()
        self.assertEqual(
            experience.integrity(package),
            {
                'status': 'unverified',
                'version': version,
                'next_step': experience.integrity(package)['next_step'],
            },
        )
        files = {
            p.relative_to(package).as_posix(): studio.digest(p.read_bytes())
            for p in package.rglob('*')
            if p.is_file()
        }
        manifest = package / 'install-manifest.json'
        manifest.write_text(json.dumps({'schema': 1, 'version': version, 'files': files}))
        self.assertEqual(experience.integrity(package), {'status': 'verified', 'version': version})
        for name in ('.DS_Store', 'scripts/.DS_Store'):
            (package / name).write_bytes(b'\0')
        (package / 'config.json').write_text(
            json.dumps({'python': sys.executable, 'runtime_version': version})
        )
        self.assertEqual(experience.integrity(package)['status'], 'verified')
        (package / 'config.json').write_text(
            json.dumps({'python': str(self.base / 'removed/python3'), 'runtime_version': version})
        )
        self.assertEqual(experience.integrity(package)['interpreter'], 'missing')
        (package / 'config.json').unlink()
        (package / 'references/extra.md').write_text('Not in the manifest.')
        self.assertEqual(experience.integrity(package)['status'], 'repair-needed')
        (package / 'references/extra.md').unlink()
        (package / 'SKILL.md').write_text('Changed.')
        self.assertEqual(experience.integrity(package)['status'], 'repair-needed')
        manifest.write_text('{"schema":1,"version":"1.3.0","files":{}}')
        self.assertEqual(experience.integrity(package)['status'], 'repair-needed')
        manifest.write_text('{"schema":1,"version":"' + version + '","files":[]}')
        self.assertEqual(experience.integrity(package)['status'], 'repair-needed')
        with patch.object(experience.shutil, 'which', return_value=None):
            self.assertEqual(experience.auth_status('claude')['status'], 'missing')
        with (
            patch.object(experience.shutil, 'which', return_value='claude'),
            patch.object(
                experience,
                'probe',
                return_value=subprocess.CompletedProcess([], 0, 'unexpected', ''),
            ),
        ):
            self.assertEqual(experience.auth_status('claude')['status'], 'unverified')

    def test_readiness_reports_installed_guidance_without_any_network_or_repository_call(self):
        self.cli('init')
        task = self.root / 'task-context/tasks' / 'a'
        task.mkdir(parents=True)
        pin = task / 'pin.json'
        pin.write_text('{"revision":"old"}')  # left by a 1.x installation
        version = (SCRIPTS.parent / 'VERSION').read_text().strip()
        probes = []

        def fake(arguments):
            probes.append(arguments[0])
            return subprocess.CompletedProcess(arguments, 0, '{"loggedIn":true}', '')

        for online in (False, True):
            with (
                patch.object(experience.shutil, 'which', return_value='/fixture/tool'),
                patch.object(experience, 'probe', side_effect=fake),
                patch.object(experience.subprocess, 'run') as external,
            ):
                result = experience.readiness(self.root, 'claude', online=online)
            external.assert_not_called()
            self.assertEqual(result['guidance']['status'], 'installed')
            self.assertEqual(result['guidance']['version'], version)
            self.assertEqual(result['runtime']['version'], version)
            self.assertNotIn('update_status', result['runtime'])
            self.assertNotIn('approved', json.dumps(result))
        self.assertEqual(set(probes), {'claude'})
        self.assertEqual(pin.read_text(), '{"revision":"old"}')
        self.assertEqual(
            self.cli('readiness', '--harness', 'claude', '--online')['guidance']['version'], version
        )

    def test_symlink_escape_is_not_read_by_discovery_or_context(self):
        self.cli('init')
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'session.json').write_text('{"title":"PRIVATE"}')
        (self.root / 'articles' / 'escape').symlink_to(outside, target_is_directory=True)
        result = self.cli('home')
        self.assertEqual(result['problem_count'], 1)
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.cli('context', '--id', 'escape', ok=False)

    def test_old_reviews_without_memory_fingerprint_remain_current(self):
        aid = self.create()
        self.cli(
            'article',
            'save',
            '--id',
            aid,
            '--kind',
            'draft',
            '--file',
            self.file('draft.md', 'A draft.'),
        )
        self.cli(
            'article',
            'review',
            '--id',
            aid,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            self.file('review.json', '{"findings":[]}'),
        )
        path = self.root / 'articles' / aid / 'session.json'
        record = studio.read_json(path)
        record['reviews']['proofread']['inputs'].pop('memory')
        studio.write_json(path, record)
        self.assertEqual(self.cli('context', '--id', aid)['reviews']['proofread'], 'current')


if __name__ == '__main__':
    unittest.main()
