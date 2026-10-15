"""Synthetic shared-root repositories, driver races, offline queues and shared defaults."""

import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import studio
import studios_config
import blog_runner
import team_workspace as teams
from studio_sync import gitstate, support


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = self.base / 'studios.json'
        self.patch = patch.dict(os.environ, {'STUDIOS_CONFIG': str(self.config)})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_missing_invalid_and_local_override(self):
        self.assertEqual(studios_config.read(), ({}, None))
        studio.initialize(self.base / 'writing')
        root = self.base / 'writing'
        self.config.write_text(
            '{"schema":1,"person":{"name":"Fictional Author"},"assistant":{"agent":"claude","model":"unused"}}'
        )
        defaults = blog_runner.settings(root)
        self.assertEqual(defaults['defaults']['engine'], 'claude')
        self.assertEqual(defaults['defaults']['author'], 'Fictional Author')
        local = {**defaults['defaults'], 'engine': 'codex'}
        blog_runner.settings(root, local)
        self.assertEqual(studios_config.read()[0]['assistant']['agent'], 'claude')
        self.config.write_text('{invalid')
        self.assertEqual(blog_runner.settings(root)['defaults']['engine'], 'codex')
        self.assertTrue(blog_runner.settings(root)['shared_problem'])
        self.assertEqual(self.config.read_text(), '{invalid')

    def test_consent_changes_only_leaves_and_preserves_unknown_bytes(self):
        raw = '{\n "schema": 1, "person": {"name": "Old", "unknown" : [1,  2]},\n "assistant": {"agent":"codex", "model" : "preserve"}, "future" : { "n": 1e3 }\n}\n'
        self.config.write_text(raw)
        studio.initialize(self.base / 'writing')
        old = blog_runner.settings(self.base / 'writing')['defaults']
        blog_runner.settings(
            self.base / 'writing', {**old, 'author': 'New', 'for_all_studios': True}
        )
        self.assertEqual(self.config.read_text(), raw.replace('"Old"', '"New"'))
        studios_config.update(
            {'team': {'repository': 'git@example.test:team/studios.git', 'branch': 'main'}}
        )
        self.assertIn('"future" : { "n": 1e3 }', self.config.read_text())
        self.assertEqual(studios_config.read()[0]['team']['branch'], 'main')

    def test_new_skill_runs_use_defaults_and_existing_runs_keep_their_choices(self):
        root = self.base / 'writing'
        studio.initialize(root)
        self.config.write_text(
            '{"schema":1,"assistant":{"agent":"claude"},"person":{"name":"First Author"}}'
        )
        args = studio.parser().parse_args(
            [
                '--root',
                str(root),
                'run',
                'create',
                '--title',
                'Synthetic defaults',
                '--audience',
                'Authors',
                '--goal',
                'Explain synthetic defaults',
                '--research',
                'none',
                '--stop',
                'outline',
            ]
        )
        first = blog_runner.command(root, args)
        self.assertEqual(first['engine'], 'claude')
        self.assertEqual(studio.item(root, 'articles', first['id'])[1]['author'], 'First Author')
        self.config.write_text(
            '{"schema":1,"assistant":{"agent":"codex"},"person":{"name":"Second Author"}}'
        )
        self.assertEqual(blog_runner.survey(root, first['id'])['engine'], 'claude')
        self.assertEqual(studio.item(root, 'articles', first['id'])[1]['author'], 'First Author')

    def test_credentials_and_invalid_updates_preserve_file(self):
        self.config.write_text('{"schema":1,"future":"kept"}')
        before = self.config.read_bytes()
        for address in (
            'https://token@example.test/repo.git',
            'https://user:secret@example.test/repo',
            'ext::run',
        ):
            with self.assertRaises(ValueError):
                studios_config.update({'team': {'repository': address}})
        self.assertEqual(self.config.read_bytes(), before)
        self.config.write_text('[]')
        with self.assertRaises(ValueError):
            studios_config.update({'person': {'name': 'New'}})
        self.assertEqual(self.config.read_text(), '[]')


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='blog-studios-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'one'),
                'STUDIOS_CONFIG': str(self.base / 'none.json'),
                'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'Synthetic Author',
                'GIT_AUTHOR_EMAIL': 'author@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic Author',
                'GIT_COMMITTER_EMAIL': 'author@example.invalid',
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.remote = self.base / 'team.git'
        subprocess.run(
            ['git', 'init', '--bare', '--initial-branch=main', str(self.remote)],
            check=True,
            capture_output=True,
        )
        seed = self.base / 'seed'
        subprocess.run(
            ['git', 'clone', str(self.remote), str(seed)], check=True, capture_output=True
        )
        (seed / 'trainings/fixture').mkdir(parents=True)
        (seed / 'trainings/hub.json').write_text('{"schema":1,"tool":"training-studio"}')
        (seed / 'trainings/fixture/README.md').write_text('Synthetic training, preserved.\n')
        (seed / 'presentations').mkdir()
        (seed / 'presentations/hub.json').write_text('{"schema":1,"tool":"presentation-studio"}')
        support.git(seed, 'add', '.')
        support.git(seed, 'commit', '-m', 'Synthetic studios fixture')
        support.git(seed, 'push', 'origin', 'main')
        self.root = teams.join(str(self.remote))

    def other(self):
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        return teams.join(str(self.remote))

    def create(self):
        return blog_runner.create(
            self.root,
            {
                'title': 'Fictional launch',
                'goal': 'Explain a fictional service',
                'audience': 'Authors',
                'research': 'none',
                'stop': 'outline',
            },
        )

    def test_side_by_side_claim_handover_takeover_and_no_foreign_commits(self):
        found = self.create()
        ident = found['id']
        self.assertTrue((self.root / ident / 'session.json').is_file())
        self.assertFalse((self.root / 'articles').exists())
        self.assertTrue(teams.driver(self.root, ident)['here'])
        other = self.other()
        self.assertFalse(teams.driver(other, ident)['here'])
        with self.assertRaisesRegex(ValueError, 'another computer'):
            teams.before(other, ident)
        teams.action(other, ident, 'takeover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        with self.assertRaisesRegex(ValueError, 'another computer'):
            teams.before(self.root, ident)
        with self.assertRaises(ValueError):
            studio.atomic(self.root / ident / 'DRAFT.md', b'late worker')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        teams.action(other, ident, 'handover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        teams.action(self.root, ident, 'take')
        self.assertTrue(teams.driver(self.root, ident)['here'])
        changed = support.git(
            self.root.parent, 'diff', '--name-only', 'origin/main~1', 'HEAD'
        ).splitlines()
        self.assertTrue(all(name.startswith('blogs/') for name in changed))
        self.assertEqual(
            (self.root.parent / 'trainings/fixture/README.md').read_text(),
            'Synthetic training, preserved.\n',
        )

    def test_offline_queue_retry_and_manual_sharing(self):
        found = self.create()
        ident = found['id']
        support.git(self.root.parent, 'remote', 'set-url', 'origin', str(self.base / 'missing.git'))
        current = blog_runner.survey(self.root, ident)
        blog_runner.submit(
            self.root,
            ident,
            'outline',
            {'content': '# Synthetic outline', 'notes': ''},
            current['expected'],
        )
        self.assertGreater(len(gitstate.unshared(teams.space(self.root), ident)), 0)
        report = teams.refresh(self.root, push=True)
        self.assertFalse(report['shared'])
        support.git(self.root.parent, 'remote', 'set-url', 'origin', str(self.remote))
        self.assertTrue(teams.refresh(self.root, push=True)['shared'])
        studio.write_json(self.root / '.team-sync.json', {'share': 'asked'})
        current = blog_runner.survey(self.root, ident)
        blog_runner.decide(self.root, ident, current['expected'], 'approve')
        self.assertTrue(gitstate.unshared(teams.space(self.root), ident))
        self.assertTrue(teams.refresh(self.root, push=True)['shared'])

    def test_takeover_keeps_unshared_work_and_requires_online_claim(self):
        found = self.create()
        ident = found['id']
        other = self.other()
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        studio.write_json(self.root / '.team-sync.json', {'share': 'asked'})
        studio.atomic(self.root / ident / 'OUTLINE.md', b'Unshared local writing')
        teams.saved(self.root, ident)
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        teams.action(other, ident, 'takeover')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'one')
        runner = blog_runner.engine(self.root)
        runner.current = ident
        runner.keep_local(ident, {'enabled': True, 'status': 'working'})
        teams.refresh(self.root)
        self.assertTrue(runner.stop.is_set())
        self.assertFalse(runner.local(ident)['enabled'])
        runner.current = None
        blog_runner.ENGINES.pop(str(self.root), None)
        kept = gitstate.kept(teams.space(self.root), ident)
        self.assertTrue(kept)
        self.assertIn(
            'Unshared local writing',
            support.git(self.root.parent, 'show', kept[0] + ':blogs/' + ident + '/OUTLINE.md'),
        )
        support.git(self.root.parent, 'remote', 'set-url', 'origin', str(self.base / 'missing.git'))
        with self.assertRaisesRegex(ValueError, 'Check the team repository'):
            teams.action(self.root, ident, 'takeover')


if __name__ == '__main__':
    unittest.main()


class MigrationTests(unittest.TestCase):
    setUp = TeamTests.setUp

    # Reuse the synthetic repository fixture, with a legacy fake provider kept entirely local.
    def test_selected_migration_is_byte_preserving_and_old_hub_is_unchanged(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        import hub_workspace

        legacy = self.base / 'legacy-writing'
        studio.initialize(legacy)
        provider = FakeProvider(self.base / 'legacy-remotes')
        registry = Registry(self.base / 'legacy-registry', provider)
        hub_id = registry.create('fixture/old-blogs', 'Old blogs')['hub']
        adapter = Workspace(legacy, registry.hub(hub_id))
        source = self.base / 'synthetic.md'
        source.write_text('Synthetic source text.\n')
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'source',
                'add',
                '--name',
                'Synthetic notes',
                '--file',
                str(source),
                '--purpose',
                'reference',
            ]
        )
        reference = studio.source_command(legacy, args)
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'article',
                'create',
                '--title',
                'Migrated fixture',
                '--mode',
                'first-draft',
            ]
        )
        article = studio.article_command(legacy, args)
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'article',
                'attach',
                '--id',
                article['id'],
                '--source',
                reference['id'],
            ]
        )
        studio.article_command(legacy, args)
        source.write_text('# Preserved draft\nSynthetic writing.\n')
        args = studio.parser().parse_args(
            [
                '--root',
                str(legacy),
                'article',
                'save',
                '--id',
                article['id'],
                '--kind',
                'draft',
                '--file',
                str(source),
            ]
        )
        studio.article_command(legacy, args)
        adapter.publish_selected({'articles': [article['id']]})
        old_files = {
            str(p.relative_to(legacy)): p.read_bytes() for p in legacy.rglob('*') if p.is_file()
        }
        old_head = support.git(adapter.hub.repository, 'rev-parse', 'HEAD')
        real_active = hub_workspace.active
        with patch.object(
            hub_workspace,
            'active',
            side_effect=lambda root: (
                adapter if Path(root).resolve() == legacy.resolve() else real_active(root)
            ),
        ):
            result = teams.migrate(self.root, legacy, [article['id']])
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                teams.migrate(self.root, legacy, [article['id']])
        self.assertTrue(result['legacy_unchanged'])
        self.assertEqual((self.root / article['id'] / 'DRAFT.md').read_bytes(), source.read_bytes())
        # Original session and reference files are copied without rewriting their identities.
        self.assertEqual(
            (self.root / article['id'] / 'session.json').read_bytes(),
            (legacy / 'articles' / article['id'] / 'session.json').read_bytes(),
        )
        self.assertEqual(
            studio.item(self.root, 'sources', reference['id'])[0]
            .joinpath('content.md')
            .read_bytes(),
            (legacy / 'sources' / reference['id'] / 'content.md').read_bytes(),
        )
        self.assertEqual(
            {str(p.relative_to(legacy)): p.read_bytes() for p in legacy.rglob('*') if p.is_file()},
            old_files,
        )
        self.assertEqual(support.git(adapter.hub.repository, 'rev-parse', 'HEAD'), old_head)
        self.assertTrue((self.root / result['archive']).is_dir())


class TeamPageTests(unittest.TestCase):
    setUp = TeamTests.setUp
    create = TeamTests.create

    def test_page_joins_and_switches_workspace_with_driver_controls(self):
        import http.client
        import threading
        import management
        from urllib.parse import urlsplit

        local = self.base / 'local-page'
        studio.initialize(local)
        httpd, url = management.server(local)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        token = urlsplit(url).fragment
        try:
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
            connection.request(
                'POST',
                '/api/team-join',
                json.dumps(
                    {
                        'repository': str(self.remote),
                        'branch': 'main',
                        'share': 'asked',
                        'for_all_studios': False,
                    }
                ),
                {'X-Blog-Studio-Token': token, 'Content-Type': 'application/json'},
            )
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 200, result)
            self.assertEqual(result['share'], 'asked')
            connection.close()
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
            connection.request('GET', '/api/run-settings', headers={'X-Blog-Studio-Token': token})
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(result['workspace'], str(self.root))
            connection.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            blog_runner.engine(self.root).close()
            from hub_store import release_lock

            if getattr(httpd, 'team_runner_lock', None) is not None:
                release_lock(httpd.team_runner_lock)

    def test_fetch_does_not_hold_the_workspace_files_lock(self):
        import threading
        import time

        entered, release = threading.Event(), threading.Event()
        original = support.run
        failures = []

        def run(repo, *args, **kwargs):
            if args[:1] == ('fetch',):
                entered.set()
                release.wait(5)
            return original(repo, *args, **kwargs)

        def refresh():
            try:
                teams.refresh(self.root)
            except Exception as exc:
                failures.append(str(exc))

        with patch.object(support, 'run', side_effect=run):
            thread = threading.Thread(target=refresh)
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                started = time.monotonic()
                with studio.locked(self.root):
                    self.assertTrue((self.root / 'hub.json').is_file())
                self.assertLess(time.monotonic() - started, 1)
            finally:
                release.set()
                thread.join(timeout=10)
        self.assertFalse(failures)

    def test_google_linked_documents_follow_the_same_driver(self):
        import google_drive

        found = self.create()
        ident = found['id']
        folder, record = studio.item(self.root, 'articles', ident)
        record['google'] = {
            'baselines': {'draft': {'document': {'document_id': 'SyntheticDocument'}}}
        }
        studio.persist(folder, 'articles', record)
        teams.saved(self.root, ident)
        self.assertIn('SyntheticDocument', google_drive.linked_documents(self.root))
        google_drive.require_linked(self.root, 'SyntheticDocument')
        os.environ['BLOG_STUDIO_DATA'] = str(self.base / 'two')
        other = teams.join(str(self.remote))
        with self.assertRaisesRegex(ValueError, 'another computer'):
            google_drive.require_linked(other, 'SyntheticDocument')

    def test_external_edits_are_preserved_and_publication_requires_approval(self):
        found = self.create()
        ident = found['id']
        with self.assertRaisesRegex(ValueError, 'Approve every'):
            teams.action(self.root, ident, 'publish')
        draft = self.root / ident / 'OUTLINE.md'
        draft.write_text('Uncommitted synthetic writing.\n')
        with self.assertRaisesRegex(ValueError, 'no local work was overwritten'):
            teams.refresh(self.root, push=True)
        self.assertEqual(draft.read_text(), 'Uncommitted synthetic writing.\n')
