"""Real, synthetic brand commands and release repositories; no provider or private content."""

import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import brand_skill as brands
import blog_runner
import management
import studio
from studio_brand import source

NODE = shutil.which('node')
COMMAND = r"""import fs from 'node:fs';
import path from 'node:path';
const args = process.argv.slice(2);
const get = key => args[args.indexOf(key) + 1];
if (args[0] === 'version') console.log('Synthetic Brand VERSION');
else if (args[0] === 'brands') console.log(JSON.stringify([
  {brand:'fictional',name:'Fictional identity',variants:['light','dark']}
]));
else if (args[0] === 'contract' && args[1] === 'export') {
  if (get('--medium') !== 'blog' || args.includes('--delivery')) process.exit(2);
  const folder = get('--output'); fs.mkdirSync(folder, {recursive:true});
  fs.writeFileSync(path.join(folder,'brand-contract.json'), JSON.stringify({
    schema:1, medium:'blog',brand:get('--brand'),variant:get('--variant'),revision:'synthetic-v1'}));
  fs.writeFileSync(path.join(folder,'VOICE.md'),'Name the organisation Fictional Labs.');
  fs.writeFileSync(path.join(folder,'DESIGN.md'),'Synthetic visual guide, not an author voice.');
  console.log('{}');
} else process.exit(1);
"""
INSTALLER = r"""import fs from 'node:fs';
import path from 'node:path';
const folder = path.join(process.env.HOME,'.agents','skills','synthetic-brand');
fs.mkdirSync(path.join(folder,'scripts'),{recursive:true});
for (const name of ['SKILL.md','package.json','scripts/synthetic-brand.mjs'])
  fs.copyFileSync(new URL('../'+name,import.meta.url),path.join(folder,name));
fs.writeFileSync(path.join(process.env.HOME,'brand-installer-ran'),'synthetic only');
"""


@unittest.skipUnless(NODE and shutil.which('git'), 'brand commands need Node and Git')
class BrandSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='blog-brand-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        self.home.mkdir()
        self.root = self.base / 'writing'
        self.data = self.base / 'data'
        self.config = self.base / 'studios.json'
        self.environment = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.data),
                'STUDIOS_CONFIG': str(self.config),
                'BRAND_SKILL_RUNTIME': '',
                'HARNESS_SLIDES_RUNTIME': str(self.base / 'no-slides'),
                'HARNESS_RESEARCH_RUNTIME': str(self.base / 'no-research'),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.mock_home = patch.object(brands, 'home', return_value=self.home)
        self.mock_home.start()
        self.addCleanup(self.mock_home.stop)
        brands._CACHE.clear()
        brands._JOB = None
        studio.initialize(self.root)

    def skill(self, folder=None, version='1.2.0'):
        folder = folder or self.home / '.agents/skills/synthetic-brand'
        (folder / 'scripts').mkdir(parents=True)
        (folder / 'SKILL.md').write_text('# Synthetic brand fixture\n')
        (folder / 'package.json').write_text('{"name":"synthetic-brand"}')
        (folder / 'scripts/synthetic-brand.mjs').write_text(COMMAND.replace('VERSION', version))
        return folder

    def git(self, folder, *args):
        return subprocess.check_output(
            ['git', '-C', str(folder), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()

    def repository(self, bootstrap=False):
        folder = self.skill(self.base / 'release')
        (folder / 'scripts/install-skill.mjs').write_text(INSTALLER)
        if bootstrap:
            (folder / 'scripts/lib').mkdir()
            (folder / 'scripts/lib/harness-install-sources.json').write_text(
                '{"slides":{"version":"0.13.1"}}'
            )
        self.git(folder, 'init', '-b', 'main')
        self.git(folder, 'config', 'user.name', 'Synthetic Fixture')
        self.git(folder, 'config', 'user.email', 'fixture@example.invalid')
        self.git(folder, 'add', '.')
        self.git(folder, 'commit', '-m', 'Synthetic brand fixture')
        for tag in ('v1.1.0', 'v1.2.0', 'v2026.6.0'):
            self.git(folder, 'tag', '-a', tag, '-m', 'Synthetic release')
        return folder

    def checked(self, bootstrap=False):
        folder = self.repository(bootstrap)
        found = management.dispatch(
            self.root, 'brand-configure', {'repository': str(folder), 'release': ''}
        )
        self.assertEqual(found['checked']['tag'], 'v1.2.0')
        return folder, found

    def confirm(self, found):
        return {
            'confirmed': True,
            'repository': found['repository'],
            'tag': found['checked']['tag'],
            'commit': found['checked']['commit'],
        }

    def wait(self):
        deadline = time.monotonic() + 15
        while brands._JOB['status'] == 'working' and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertNotEqual(brands._JOB['status'], 'working', 'synthetic install timed out')
        return brands._JOB

    def test_select_installed_skill_and_pin_blog_contract_separately_from_author_voice(self):
        first = self.skill(version='1.1.0')
        second = self.skill(self.home / '.claude/skills/another-brand')
        found = brands.status()
        self.assertEqual(len(found['skills']), 2)
        brands.configure({'runtime': str(second)})
        run = blog_runner.create(
            self.root,
            {
                'title': 'Synthetic article',
                'goal': 'Explain a fictional system',
                'audience': 'Authors',
                'research': 'none',
                'tone': 'Plain and personal',
                'brand': 'fictional',
                'variant': 'dark',
            },
        )
        self.assertEqual(run['brand']['version'], '1.2.0')
        directory, record, kept = blog_runner.load(self.root, run['id'])
        saved = (directory / blog_runner.STATE).read_bytes()
        self.assertNotIn(str(self.home), json.dumps(kept['brand']))
        _, payload, _ = blog_runner.job(self.root, run['id'])
        self.assertEqual(payload['brand']['voice'], 'Name the organisation Fictional Labs.')
        self.assertEqual(payload['voice'], record['voice'])
        self.assertIn('Plain and personal', json.dumps(payload['voice']))
        brands.configure({'runtime': str(first)})
        shutil.rmtree(second)
        self.assertEqual((directory / blog_runner.STATE).read_bytes(), saved)
        self.assertEqual(blog_runner.survey(self.root, run['id'])['expected'], run['expected'])
        self.assertEqual(blog_runner.job(self.root, run['id'])[1]['brand'], payload['brand'])
        other = self.base / 'another-computer'
        shutil.copytree(self.root, other)
        self.assertEqual(blog_runner.job(other, run['id'])[1]['brand'], payload['brand'])

    def test_no_brand_keeps_writing_available_and_shared_default_is_optional(self):
        self.assertIsNone(brands.snapshot(''))
        self.assertEqual(brands.defaults(), {'brand': '', 'variant': ''})
        self.config.write_text('{"schema":1,"brand":{"brand":"fictional","variant":"dark"}}')
        self.assertEqual(brands.defaults(), {'brand': '', 'variant': ''})
        self.skill()
        brands.installed(refresh=True)
        self.assertEqual(brands.defaults(), {'brand': 'fictional', 'variant': 'dark'})
        run = blog_runner.create(
            self.root,
            {
                'title': 'Shared brand',
                'goal': 'A fixture',
                'audience': 'Authors',
                'research': 'none',
            },
        )
        self.assertEqual(run['brand']['variant'], 'dark')
        plain = blog_runner.create(
            self.root,
            {
                'title': 'Plain',
                'goal': 'A fixture',
                'audience': 'Authors',
                'research': 'none',
                'brand': '',
            },
        )
        self.assertIsNone(plain['brand'])

    def test_real_skill_cli_accepts_the_brand_input(self):
        folder = self.skill()
        command = [
            sys.executable,
            str(Path(studio.__file__)),
            '--root',
            str(self.root),
            'run',
            'create',
            '--title',
            'CLI brand fixture',
            '--goal',
            'A fixture',
            '--audience',
            'Authors',
            '--research',
            'none',
            '--brand',
            'fictional',
            '--variant',
            'dark',
        ]
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env={**os.environ, 'HOME': str(self.home), 'BRAND_SKILL_RUNTIME': str(folder)},
            timeout=20,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        made = json.loads(done.stdout)
        self.assertEqual(made['brand']['brand'], 'fictional')
        self.assertEqual(made['brand']['variant'], 'dark')

    def test_checks_repository_before_save_and_preserves_previous_on_refusal(self):
        folder, found = self.checked()
        saved = brands._path().read_bytes()
        for values in (
            {'repository': str(folder), 'release': 'v9.9.9'},
            {'repository': str(self.base / 'missing'), 'release': ''},
            {'repository': 'https://token@example.invalid/private.git', 'release': ''},
        ):
            with self.assertRaises(ValueError):
                brands.configure(values)
            self.assertEqual(brands._path().read_bytes(), saved)
        self.assertFalse((self.home / 'brand-installer-ran').exists())
        pinned = brands.configure({'repository': str(folder), 'release': '1.1.0'})
        self.assertEqual(pinned['release'], 'v1.1.0')
        self.assertEqual(found['checked']['commit'], self.git(folder, 'rev-parse', 'HEAD'))
        brands.configure({'repository': '', 'release': ''})
        self.assertIsNone(brands.status()['checked'])

    def test_only_listed_skills_and_brands_are_accepted(self):
        self.skill()
        for runtime in ('/unlisted', 123):
            with self.assertRaises(ValueError):
                brands.configure({'runtime': runtime})
        for identity, variant in (('unknown', 'light'), ('fictional', 'unknown'), ('', 'light')):
            with self.assertRaises(ValueError):
                brands.snapshot(identity, variant)
        self.assertEqual(brands.snapshot('fictional')['variant'], 'light')

    def test_brand_source_lives_only_in_shared_config_and_refreshes_on_next_read(self):
        import studios_config

        _, shown = self.checked()
        private = studio.read_json(brands._path())
        self.assertNotIn('repository', private)
        self.assertNotIn('release', private)
        self.assertEqual(studios_config.read()[0]['brand']['repository'], shown['repository'])
        studios_config.update({'brand': {'release': 'v1.1.0'}})
        fresh = brands.status()
        self.assertEqual(fresh['release'], 'v1.1.0')
        self.assertIsNone(fresh['checked'])
        with self.assertRaisesRegex(ValueError, 'changed in another studio'):
            brands.configure(
                {
                    'repository': shown['repository'],
                    'release': '',
                    'shared_before': shown['shared_before'],
                }
            )
        self.assertEqual(studios_config.read()[0]['brand']['release'], 'v1.1.0')

    def test_local_skill_choice_preserves_unmigrated_values_when_shared_file_is_invalid(self):
        folder = self.skill()
        legacy = {'repository': 'https://example.invalid/legacy-brand.git', 'release': 'v1.4.0'}
        studio.write_json(brands._path(), legacy)
        self.config.write_text('{invalid')
        brands.configure({'runtime': str(folder)})
        saved = studio.read_json(brands._path())
        self.assertEqual(saved['repository'], legacy['repository'])
        self.assertEqual(saved['release'], legacy['release'])
        self.assertEqual(saved['runtime'], str(folder))
        self.assertEqual(self.config.read_text(), '{invalid')

    def test_confirmed_install_runs_real_release_installer_in_synthetic_home(self):
        _, found = self.checked()
        with self.assertRaises(ValueError):
            brands.install({**self.confirm(found), 'confirmed': False})
        with brands.using():
            with self.assertRaisesRegex(ValueError, 'blog is working'):
                brands.install(self.confirm(found))
        brands.install(self.confirm(found))
        self.assertEqual(self.wait()['status'], 'complete')
        self.assertTrue((self.home / 'brand-installer-ran').is_file())
        self.assertEqual(brands.status()['version'], '1.2.0')
        self.assertEqual(brands.snapshot('fictional', 'light')['version'], '1.2.0')

    def test_moved_tag_and_companion_bootstrap_are_refused_before_installer_runs(self):
        folder, found = self.checked(bootstrap=True)
        brands.install(self.confirm(found))
        self.assertEqual(self.wait()['status'], 'failed')
        self.assertIn('harness-slides', brands._JOB['message'])
        self.assertFalse((self.home / 'brand-installer-ran').exists())
        (folder / 'change.txt').write_text('Synthetic tag movement')
        self.git(folder, 'add', '.')
        self.git(folder, 'commit', '-m', 'Synthetic tag movement')
        self.git(folder, 'tag', '-f', 'v1.2.0')
        brands.install(self.confirm(found))
        self.assertIn('tag moved', self.wait()['message'])
        self.assertFalse((self.home / 'brand-installer-ran').exists())

    def test_installation_blocks_new_writing_until_finished(self):
        _, found = self.checked()
        run = blog_runner.create(
            self.root,
            {
                'title': 'Waiting blog',
                'goal': 'A fixture',
                'audience': 'Authors',
                'research': 'none',
                'brand': '',
            },
            'page',
        )
        worker = unittest.mock.Mock(return_value={'content': '# Synthetic outline', 'notes': ''})
        engine = blog_runner.Engine(self.root, worker)
        engine.control(run['id'], 'resume')
        entered, finish = threading.Event(), threading.Event()

        def held(*args):
            entered.set()
            finish.wait(5)
            return 1, False, 'Synthetic refusal'

        with patch.object(source, 'install', side_effect=held):
            brands.install(self.confirm(found))
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaisesRegex(ValueError, 'being installed'):
                    with brands.using():
                        self.fail('Installation must hold the writing lease')
                with brands.using(quiet=True) as available:
                    self.assertFalse(available)
                engine.once(run['id'])
                worker.assert_not_called()
                self.assertTrue(engine.local(run['id'])['enabled'])
            finally:
                finish.set()
                self.wait()
        engine.once(run['id'])
        worker.assert_called_once()

    def test_zip_paths_cannot_escape_release_folder(self):
        archive = self.base / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as packed:
            packed.writestr('../escaped.txt', 'Synthetic malicious path')
        with self.assertRaisesRegex(ValueError, 'cannot be placed'):
            source.unpack(archive, self.base / 'unpacked')
        self.assertFalse((self.base / 'escaped.txt').exists())

    def test_authenticated_page_brand_inputs_use_local_state(self):
        self.skill()
        server, url = management.server(self.root, 0)
        token = urlsplit(url).fragment
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        self.addCleanup(connection.close)
        connection.request('GET', '/api/brand', headers={'X-Blog-Studio-Token': token})
        response = connection.getresponse()
        found = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(found['brands'][0]['brand'], 'fictional')
        connection.request(
            'POST',
            '/api/brand-configure',
            json.dumps({'runtime': found['runtime']}),
            {'Content-Type': 'application/json', 'X-Blog-Studio-Token': token},
        )
        response = connection.getresponse()
        self.assertEqual(response.status, 200, response.read())
        self.assertTrue(brands._path().is_file())
        self.assertFalse(list(self.root.rglob('brand.json')))


if __name__ == '__main__':
    unittest.main()
