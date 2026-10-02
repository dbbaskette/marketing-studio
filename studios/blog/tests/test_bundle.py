"""Standalone installer distribution works without the source checkout."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]

class BundleTests(unittest.TestCase):
    def test_extracted_bundle_installs_and_pins_an_article_from_another_directory(self):
        bundle = REPO / 'dist/blog-studio-installer.zip'
        expected = bundle.with_suffix('.zip.sha256').read_text().split()[0]
        self.assertEqual(hashlib.sha256(bundle.read_bytes()).hexdigest(), expected)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            with zipfile.ZipFile(bundle) as archive:
                for item in archive.infolist():
                    source = REPO / item.filename.removeprefix('blog-studio-setup/')
                    self.assertEqual(archive.read(item), source.read_bytes(), item.filename)
                launcher = archive.getinfo('blog-studio-setup/installer/Install Blog Studio.command')
                self.assertTrue((launcher.external_attr >> 16) & 0o111)
                archive.extractall(base / 'expanded with spaces')
            setup = base / 'expanded with spaces/blog-studio-setup'
            home = base / 'disposable home'
            def run(*arguments, cwd=base):
                result = subprocess.run(list(arguments), capture_output=True, text=True, cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout
            installed = json.loads(run(sys.executable, str(setup / 'installer/install.py'),
                'install', '--home', str(home), '--target', 'both', '--offline', '--yes', '--json'))
            self.assertEqual(installed['status'], 'installed')
            runtime = (home / '.agents/skills/blog-studio/scripts').resolve()
            self.assertIn('Team Hub',run(sys.executable,str(runtime/'hub.py'),'--help'))
            for helper in ('hub_store.py','hub_workspace.py','google_workflow.py'):
                self.assertTrue((runtime/helper).is_file())
            self.assertIn('prepare',run(sys.executable,str(runtime/'studio.py'),'--root',str(base/'unused'),'google','--help'))
            self.assertEqual(runtime, (home / '.claude/skills/blog-studio/scripts').resolve())
            remote = base / 'fixture repository'
            remote.mkdir()
            run('git', 'init', '-b', 'main', cwd=remote)
            (remote / 'guidance').mkdir()
            (remote / 'guidance/manifest.json').write_text(json.dumps({'schema': 1,
                'minimum_runtime': '1.0.0', 'entry': 'skills/blog-studio/SKILL.md',
                'content_root': 'skills/blog-studio'}))
            entry = remote / 'skills/blog-studio/SKILL.md'
            entry.parent.mkdir(parents=True)
            entry.write_text('Fixture instructions.')
            run('git', 'add', '.', cwd=remote)
            run('git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-qm', 'Disposable guidance', cwd=remote)
            spec = importlib.util.spec_from_file_location('bundle_sync', runtime / 'sync_guidance.py')
            sync = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sync)
            workspace = base / 'writing project/.blog-studio'
            pin = sync.start(workspace, source=str(remote))
            self.assertEqual(pin['runtime'], str(runtime))
            self.assertLess(len(json.dumps(pin)), 900)
            run(sys.executable, str(runtime / 'studio.py'), '--root', str(workspace), 'init')
            created = json.loads(run(sys.executable, str(runtime / 'studio.py'), '--root',
                str(workspace), 'article', 'create', '--title', 'Portable draft', '--mode', 'outline-only'))
            article_id = created['id']
            attached = json.loads(run(sys.executable, str(runtime / 'studio.py'), '--root',
                str(workspace), 'article', 'guidance', '--id', article_id, '--task', pin['task']))
            self.assertEqual(attached['guidance']['revision'], pin['revision'])
            self.assertEqual(attached['guidance']['runtime'], str(runtime))
            resumed = json.loads(run(sys.executable, str(runtime / 'sync_guidance.py'), 'resume',
                '--workspace', str(workspace), '--task', pin['task']))
            self.assertEqual(resumed['fresh'], 'pinned')
            self.assertEqual(resumed['revision'], pin['revision'])

if __name__ == '__main__':
    unittest.main()
