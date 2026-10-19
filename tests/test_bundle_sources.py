"""Packaging source configuration and Git snapshots use disposable repositories only."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import marketing_studio
from studio_core import bundle_sources, companions, distribution

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_builder', ROOT / 'scripts/build_presentation_bundle.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BundleSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='bundle-sources-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        home = self.root / 'home'
        home.mkdir()
        self.env = {'HOME': str(home), 'PATH': os.environ['PATH'],
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_AUTHOR_NAME': 'Packaging Test', 'GIT_AUTHOR_EMAIL': 'packaging@example.invalid',
                    'GIT_COMMITTER_NAME': 'Packaging Test', 'GIT_COMMITTER_EMAIL': 'packaging@example.invalid'}
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git('init', '-q')
        (self.source / 'package.json').write_text('{"version":"9.0.0"}')
        (self.source / 'tracked.txt').write_text('committed')
        (self.source / 'delete.txt').write_text('remove me')
        (self.source / '.gitignore').write_text('.env\nnode_modules/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial fixture')
        self.initial = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'init.templateDir=', *args],
                              cwd=self.source, env=self.env, capture_output=True,
                              text=True, check=True, timeout=30).stdout.strip()

    def config(self, sources):
        path = self.root / 'sources.json'
        path.write_text(json.dumps({'schema': 1, 'sources': sources}))
        return path

    def test_config_supports_relative_paths_urls_refs_and_string_shorthand(self):
        path = self.config({'brand': {'path': 'source'},
                            'harness-slides': {'git': 'https://example.test/slides.git', 'ref': 'v1.2.3'},
                            'harness-research': 'git@example.test:team/research.git'})
        sources = bundle_sources.load_config(path)
        self.assertEqual(sources['brand'], {'path': str(self.source)})
        self.assertEqual(sources['harness-slides']['ref'], 'v1.2.3')
        self.assertEqual(sources['harness-research']['ref'], 'HEAD')

    def test_config_rejects_ambiguous_sources_credentials_and_unknown_names(self):
        invalid = [{'brand': {'path': 'source', 'git': 'https://example.test/source.git'}},
                   {'brand': {'path': 'source', 'ref': 'main'}},
                   {'brand': {'git': 'https://user:fixture@example.test/source.git'}},
                   {'brand': {'git': 'ext::unsafe'}},
                   {'brand': {'git': 'https://example.test/source.git', 'ref': '--upload-pack=unsafe'}},
                   {'brand': {'git': 'https://example.test/source.git', 'ref': 'main', 'ignored_typo': True}},
                   {'harness-unknown': 'source'}]
        for sources in invalid:
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                bundle_sources.load_config(self.config(sources))

    def test_local_snapshot_keeps_tracked_edits_additions_and_deletions_without_private_files(self):
        (self.source / 'tracked.txt').write_text('local changes')
        (self.source / 'new file.txt').write_text('staged addition')
        self.git('add', 'new file.txt')
        self.git('rm', '-q', 'delete.txt')
        (self.source / '.env').write_text('fixture-private-data')
        (self.source / 'untracked-notes.txt').write_text('exclude untracked')
        before = self.git('status', '--porcelain')
        snapshot, metadata = bundle_sources.snapshot({'path': str(self.source)}, self.root / 'snapshot', self.env)
        self.assertEqual((snapshot / 'tracked.txt').read_text(), 'local changes')
        self.assertTrue((snapshot / 'new file.txt').is_file())
        self.assertFalse((snapshot / 'delete.txt').exists())
        self.assertFalse((snapshot / '.env').exists())
        self.assertFalse((snapshot / 'untracked-notes.txt').exists())
        self.assertEqual(metadata['commit'], self.initial)
        self.assertTrue(metadata['modified'])
        self.assertNotIn(str(self.source), json.dumps(metadata))
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.initial)
        shutil.rmtree(snapshot / '.git')
        self.assertEqual(metadata['sha256'], companions.tree_digest(snapshot))

    def test_git_source_resolves_selected_tag_without_working_tree_edits(self):
        self.git('tag', 'v9.0.0')
        (self.source / 'tracked.txt').write_text('newer commit')
        self.git('commit', '-qam', 'Newer fixture')
        (self.source / 'tracked.txt').write_text('uncommitted')
        snapshot, metadata = bundle_sources.snapshot({'git': self.source.as_uri(), 'ref': 'v9.0.0'},
                                                      self.root / 'snapshot', self.env)
        self.assertEqual((snapshot / 'tracked.txt').read_text(), 'committed')
        self.assertEqual(metadata['commit'], self.initial)
        self.assertEqual(metadata['kind'], 'git')
        self.assertFalse(metadata['modified'])

    def test_tracked_links_are_rejected(self):
        (self.source / 'link').symlink_to(self.source / 'tracked.txt')
        self.git('add', 'link')
        with self.assertRaisesRegex(ValueError, 'links or submodules'):
            bundle_sources.snapshot({'path': str(self.source)}, self.root / 'snapshot', self.env)

    def test_init_config_does_not_overwrite_existing_files_or_links(self):
        example = self.config({'brand': {'path': '../brand'}})
        target = self.root / 'new-config.json'
        bundle_sources.init_config(target, example)
        original = target.read_bytes()
        with self.assertRaises(FileExistsError):
            bundle_sources.init_config(target, example)
        self.assertEqual(target.read_bytes(), original)
        target.unlink()
        target.symlink_to(self.root / 'missing.json')
        with self.assertRaises(FileExistsError):
            bundle_sources.init_config(target, example)
        self.assertTrue(target.is_symlink())

    def test_companion_snapshot_has_an_exact_local_lock_without_changing_defaults(self):
        (self.source / 'scripts').mkdir()
        (self.source / 'scripts/install.mjs').write_text('// fixture')
        (self.source / 'bootstrap').mkdir()
        (self.source / 'bootstrap/SKILL.md').write_text('---\nname: harness-slides\n---\n')
        self.git('add', '.')
        source, metadata = bundle_sources.snapshot({'path': str(self.source)}, self.root / 'snapshot', self.env)
        original = companions.read_pins(ROOT / 'pins/companions.json')['harness-slides']
        pin = bundle_sources.companion_pin('harness-slides', source, metadata, original)
        self.assertEqual(pin['commit'], self.initial)
        self.assertEqual(pin['sha256'], metadata['sha256'])
        self.assertEqual(pin['repository'], 'local:harness-slides')
        self.assertNotIn('requirement', pin)
        self.assertIn('requirement', original)
        self.assertNotIn(str(self.source), json.dumps(pin))

    def test_wrong_companion_skill_is_rejected(self):
        (self.source / 'scripts').mkdir()
        (self.source / 'scripts/install.mjs').write_text('// fixture')
        (self.source / 'bootstrap').mkdir()
        (self.source / 'bootstrap/SKILL.md').write_text('---\nname: harness-research\n---\n')
        pin = companions.read_pins(ROOT / 'pins/companions.json')['harness-slides']
        with self.assertRaisesRegex(ValueError, 'different skill'):
            bundle_sources.companion_pin('harness-slides', self.source, {}, pin)

    def test_plan_reports_git_sources_without_fetching_or_building(self):
        config = self.config({'brand': {'git': 'https://example.test/brand.git', 'ref': 'release'},
                              'harness-slides': {'git': 'https://example.test/slides.git'}})
        output = io.StringIO()
        with mock.patch.object(bundle_sources, 'snapshot', side_effect=AssertionError('Fetched source')), \
                mock.patch.object(builder, 'build', side_effect=AssertionError('Started build')), \
                contextlib.redirect_stdout(output):
            code = builder.main(['--config', str(config), '--plan', '--output', str(self.root / 'output')])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report['brand_source'], 'https://example.test/brand.git')
        self.assertIsNone(report['brand_version'])
        self.assertIsNone(report['companions']['harness-slides']['version'])
        self.assertFalse((self.root / 'output').exists())

    def test_distribution_rejects_a_changed_override_before_downloads_or_installers(self):
        destination = self.root / 'stage'
        (destination / 'pins').mkdir(parents=True)
        shutil.copy2(ROOT / 'pins/companions.json', destination / 'pins/companions.json')
        with mock.patch.object(distribution, 'download', side_effect=AssertionError('Downloaded tools')), \
                mock.patch.object(distribution, 'fetch_companion', side_effect=AssertionError('Fetched companion')):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                distribution.prepare(ROOT, destination, 'macos-arm64', self.root / 'cache', ['presentation'],
                                     companion_sources={'harness-slides': self.source})

    def test_prerelease_versions_use_semantic_order(self):
        ordered = ['1.0.0', '1.0.1-alpha.2', '1.0.1-alpha.10', '1.0.1-beta', '1.0.1', '1.0.2-alpha']
        self.assertEqual(sorted(reversed(ordered), key=companions.version_key), ordered)


if __name__ == '__main__':
    unittest.main()
