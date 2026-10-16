"""The installer brings harness-research as every studio does: pinned, checked, its own installer."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

INSTALLER = Path(__file__).resolve().parents[1] / 'installer'
sys.path.insert(0, str(INSTALLER))
import companions  # noqa: E402


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / 'harness-research-skill'
        (self.repo / 'bootstrap').mkdir(parents=True)
        (self.repo / 'scripts').mkdir()
        (self.repo / 'bootstrap' / 'SKILL.md').write_text('---\nname: harness-research\n---\n')
        (self.repo / 'scripts' / 'install.mjs').write_text('// installs itself\n')
        env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
        for step in (
            ['init', '-q'],
            ['add', '.'],
            ['-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '-qm', 'x'],
        ):
            subprocess.run(['git', *step], cwd=self.repo, check=True, env=env)
        commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=self.repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        tree = self.base / 'tree'
        shutil.copytree(self.repo, tree, ignore=shutil.ignore_patterns('.git'))
        self.pin = {
            'repository': self.repo.as_uri(),
            'version': '0.8.1',
            'commit': commit,
            'sha256': companions.tree_digest(tree),
            'stub': 'bootstrap/SKILL.md',
            'installer': 'scripts/install.mjs',
        }
        self.skills = {
            'codex': self.base / 'home/.agents/skills/blog-studio',
            'claude': self.base / 'home/.claude/skills/blog-studio',
        }

    def test_the_shipped_pin_is_the_one_every_studio_uses(self):
        pins = companions.read_pins()
        self.assertEqual(set(pins), {'harness-research'})
        self.assertEqual(pins['harness-research']['version'], '0.8.1')
        self.assertTrue(pins['harness-research']['commit'].startswith('d58d20d'))

    def test_a_pinned_revision_is_fetched_and_checked(self):
        kept = companions.fetch('harness-research', self.pin, self.base / 'root')
        self.assertTrue((kept / 'scripts' / 'install.mjs').is_file())
        self.assertFalse((kept / '.git').exists())
        self.assertEqual(companions.fetch('harness-research', self.pin, self.base / 'root'), kept)

    def test_anything_but_the_pinned_files_is_refused_and_nothing_kept(self):
        wrong = {**self.pin, 'sha256': '0' * 64}
        with self.assertRaisesRegex(companions.CompanionError, 'file for file'):
            companions.fetch('harness-research', wrong, self.base / 'root')
        self.assertEqual(
            list((self.base / 'root' / 'companions' / 'harness-research').iterdir()), []
        )

    def test_bring_asks_first_needs_node_and_reports(self):
        pins = {'harness-research': self.pin}
        waiting = companions.bring(
            self.base / 'home', self.base / 'root', self.skills, pins, lambda *a: False
        )
        self.assertEqual(waiting['harness-research']['state'], 'waiting')
        self.assertIn('not installed', companions.notes(pins, waiting)[0])
        with mock.patch.object(companions, 'node_version', return_value='v18.0.0'):
            old = companions.bring(
                self.base / 'home', self.base / 'root', self.skills, pins, lambda *a: True
            )
        self.assertIn('Node 20', old['harness-research']['detail'])

        def installed(name, pin, checkout, home, skills):
            for skill in skills.values():
                folder = skill.parent / name
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'package.json').write_text(json.dumps({'version': pin['version']}))
            return {'state': 'installed'}

        with (
            mock.patch.object(companions, 'node_version', return_value='v22.1.0'),
            mock.patch.object(companions, 'run', side_effect=installed),
        ):
            done = companions.bring(
                self.base / 'home', self.base / 'root', self.skills, pins, lambda *a: True
            )
        self.assertEqual(done['harness-research']['state'], 'installed')
        self.assertEqual(
            companions.found(self.skills, 'harness-research'), {'codex': '0.8.1', 'claude': '0.8.1'}
        )
        self.assertEqual(companions.notes(pins, done), [])
        again = companions.bring(
            self.base / 'home', self.base / 'root', self.skills, pins, lambda *a: True
        )
        self.assertEqual(again['harness-research']['state'], 'left alone')

    def test_check_reports_the_pinned_and_found_versions(self):
        result = subprocess.run(
            [
                sys.executable,
                str(INSTALLER / 'install.py'),
                'check',
                '--home',
                str(self.base / 'home'),
                '--json',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)['companions']['harness-research']
        self.assertEqual(row['wanted'], '0.8.1')
        self.assertEqual(set(row['found'].values()), {None})


if __name__ == '__main__':
    unittest.main()
