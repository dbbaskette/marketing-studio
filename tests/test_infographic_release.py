"""Fourth-studio integration and pinned renderer packaging, fully offline."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from marketing_studio import catalog, control, cli
from studio_core import bundles, infographic_renderer, offline_install

ROOT = Path(__file__).resolve().parents[1]


class InfographicReleaseTests(unittest.TestCase):
    def test_catalog_control_flags_and_minimal_companion_subsets(self):
        self.assertEqual(catalog.STUDIOS['infographic'][0], 'Infographic Studio')
        self.assertTrue(control.valid({'command': 'start', 'studio': 'infographic'}))
        self.assertEqual(cli.parser().parse_args(['start', '--is']).selected, ['infographic'])
        self.assertEqual(offline_install.names(['infographic']), [])
        self.assertEqual(offline_install.names(['blog', 'infographic']), ['harness-research'])
        self.assertEqual(offline_install.names(['training', 'infographic']), ['harness-research', 'harness-slides'])

    def test_renderer_is_only_in_subsets_that_need_it(self):
        with tempfile.TemporaryDirectory(prefix='infographic-inventory-') as temp:
            source = Path(temp) / 'source'; bundles.materialize(ROOT, source, ['blog', 'infographic'])
            renderer = source / 'runtime/renderer/fixture'; renderer.parent.mkdir(parents=True); renderer.write_bytes(b'fake renderer')
            self.assertIn('runtime/renderer/fixture', bundles.inventory(source, ['infographic']))
            self.assertNotIn('runtime/renderer/fixture', bundles.inventory(source, ['blog']))

    def archive(self, root, path='shell/headless', payload=b'synthetic binary'):
        archive = root / 'renderer.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            info = zipfile.ZipInfo(path); info.external_attr = 0o100755 << 16; zipped.writestr(info, payload)
            zipped.writestr('shell/LICENSE', b'synthetic license')
        pin = {'url': 'https://example.invalid/pinned.zip', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
               'executable': 'shell/headless', 'executable_sha256': hashlib.sha256(payload).hexdigest()}
        (root / 'pins').mkdir(); (root / 'pins/infographic-renderer.json').write_text(json.dumps({'version': 'synthetic-v1', 'platforms': {'macos-arm64': pin}}))
        runtime = root / 'runtime'; runtime.mkdir()
        return archive, runtime

    def test_pinned_renderer_extracts_regular_executable_and_license_and_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix='infographic-render-package-') as temp:
            root = Path(temp); archive, runtime = self.archive(root)
            with mock.patch.object(infographic_renderer, 'download', return_value=archive) as download:
                with self.assertRaises(ValueError): infographic_renderer.prepare(root, runtime, 'linux-arm64', root / 'cache')
                download.assert_not_called()
                record = infographic_renderer.prepare(root, runtime, 'macos-arm64', root / 'cache')
            self.assertEqual(record['version'], 'synthetic-v1')
            executable = runtime / 'renderer/shell/headless'
            self.assertEqual(executable.read_bytes(), b'synthetic binary')
            self.assertTrue(executable.stat().st_mode & 0o111)
            self.assertTrue((runtime / 'renderer/shell/LICENSE').is_file())
            self.assertFalse(any(p.is_symlink() for p in (runtime / 'renderer').rglob('*')))

    def test_escaping_renderer_archive_never_writes_outside_its_directory(self):
        with tempfile.TemporaryDirectory(prefix='infographic-render-boundary-') as temp:
            root = Path(temp); archive, runtime = self.archive(root, path='../escape')
            with mock.patch.object(infographic_renderer, 'download', return_value=archive), self.assertRaises(ValueError):
                infographic_renderer.prepare(root, runtime, 'macos-arm64', root / 'cache')
            self.assertFalse((runtime / 'escape').exists())
