"""Release archives: reproducible, complete, and installable without the source checkout."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
VERSION = (REPO / 'skills/blog-studio/VERSION').read_text().strip()
spec = importlib.util.spec_from_file_location('build_release', REPO / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name).resolve()
        cls.version, cls.digests = build.build(cls.base / 'build one')

    def test_two_builds_are_byte_identical_and_match_their_checksums(self):
        version, digests = build.build(self.base / 'build two')
        self.assertEqual((version, digests), (VERSION, self.digests))
        self.assertEqual(set(digests), {'blog-studio-installer.zip', 'blog-studio.zip', 'blog-writing-toolkit.zip'})
        for name, digest in digests.items():
            first = (self.base / 'build one' / name).read_bytes()
            self.assertEqual(first, (self.base / 'build two' / name).read_bytes(), name)
            self.assertEqual(hashlib.sha256(first).hexdigest(), digest)
            self.assertEqual((self.base / 'build one' / (name + '.sha256')).read_text(), digest + '  ' + name + '\n')
        # A rebuild replaces its own artifacts and leaves nothing stale behind.
        self.assertEqual(sorted(p.name for p in (self.base / 'build two').iterdir()),
                         sorted([*digests, *(name + '.sha256' for name in digests)]))

    def test_build_does_not_write_into_the_source_tree(self):
        tracked = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--', 'skills', 'installer', 'docs'],
                                 capture_output=True, text=True)
        before = tracked.stdout
        build.check()
        after = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--', 'skills', 'installer', 'docs'],
                               capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertFalse((REPO / 'skills/blog-studio/install-manifest.json').exists())
        self.assertFalse((REPO / 'dist').exists())
        self.assertFalse((REPO / 'bootstrap').exists())

    def test_installer_archive_holds_the_installer_the_whole_skill_and_two_guides_only(self):
        with zipfile.ZipFile(self.base / 'build one/blog-studio-installer.zip') as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertTrue(all(item.date_time == build.TIMESTAMP for item in archive.infolist()))
            self.assertEqual({name.split('/')[1] for name in names}, {'installer', 'skills', 'docs'})
            self.assertEqual(sorted(n for n in names if '/docs/' in n),
                             ['blog-studio-setup/docs/installation.md', 'blog-studio-setup/docs/troubleshooting.md'])
            self.assertTrue(all(n.startswith('blog-studio-setup/skills/blog-studio/') for n in names if '/skills/' in n))
            for name in ('Install Blog Studio.command', 'install.sh', 'google-setup.sh'):
                launcher = archive.getinfo('blog-studio-setup/installer/' + name)
                self.assertTrue((launcher.external_attr >> 16) & 0o111, name)
            for item in archive.infolist():
                relative = item.filename.removeprefix('blog-studio-setup/')
                if relative != 'skills/blog-studio/install-manifest.json':
                    self.assertEqual(archive.read(item), (REPO / relative).read_bytes(), item.filename)
            manifest = json.loads(archive.read('blog-studio-setup/skills/blog-studio/install-manifest.json'))
        self.assertEqual(manifest['version'], VERSION)
        shipped = {n.removeprefix('blog-studio-setup/skills/blog-studio/') for n in names if '/skills/' in n}
        self.assertEqual(shipped - {'install-manifest.json'}, set(manifest['files']))
        tracked = subprocess.run(['git', '-C', str(REPO), 'ls-files', 'skills/blog-studio'], capture_output=True, text=True)
        if tracked.returncode == 0 and tracked.stdout:
            source = {line.removeprefix('skills/blog-studio/') for line in tracked.stdout.splitlines()}
            self.assertEqual(source - set(manifest['files']), set(), 'Every tracked skill file ships.')
        self.assertFalse(any('sync_guidance' in n or 'bootstrap' in n for n in names))

    def test_manual_skill_archive_is_the_same_verified_skill_folder(self):
        with zipfile.ZipFile(self.base / 'build one/blog-studio.zip') as archive, \
                zipfile.ZipFile(self.base / 'build one/blog-studio-installer.zip') as setup:
            for name in archive.namelist():
                self.assertEqual(archive.read(name), setup.read('blog-studio-setup/skills/' + name), name)
            archive.extractall(self.base / 'manual')
        probe = ('import json, sys, pathlib; sys.path.insert(0, sys.argv[1]); import experience; '
                 'print(json.dumps(experience.integrity(pathlib.Path(sys.argv[1]).parent)))')
        scripts = self.base / 'manual/blog-studio/scripts'
        result = subprocess.run([sys.executable, '-B', '-c', probe, str(scripts)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'status': 'verified', 'version': VERSION})

    def test_extracted_installer_sets_up_both_harnesses_and_writes_from_another_directory(self):
        with zipfile.ZipFile(self.base / 'build one/blog-studio-installer.zip') as archive:
            archive.extractall(self.base / 'expanded with spaces')
        setup = self.base / 'expanded with spaces/blog-studio-setup'
        for name in ('Install Blog Studio.command', 'install.sh', 'google-setup.sh'):
            os.chmod(setup / 'installer' / name, 0o755)  # zipfile.extractall drops the mode that unzip keeps
        home = self.base / 'disposable home'
        environment = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', ''),
                           PYTHONDONTWRITEBYTECODE='1')
        def run(*arguments, cwd=self.base):
            result = subprocess.run(list(arguments), capture_output=True, text=True, cwd=cwd, env=environment,
                                    stdin=subprocess.DEVNULL, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        installed = json.loads(run('sh', str(setup / 'installer/install.sh'),
            'install', '--home', str(home), '--target', 'both', '--yes', '--json'))
        self.assertEqual(installed['status'], 'installed')
        self.assertTrue(installed['version'].startswith(VERSION + '-'))
        checked = json.loads(run('sh', str(setup / 'installer/install.sh'), 'check', '--home', str(home), '--json'))
        self.assertEqual(checked['runtime_integrity'], 'verified')
        self.assertEqual(checked['version'], VERSION)
        self.assertEqual(set(checked['targets']), {'codex', 'claude'})
        self.assertIn('files verified', run('bash', str(setup / 'installer/Install Blog Studio.command'), 'check', '--home', str(home)))
        invalid = subprocess.run(['sh', str(setup / 'installer/install.sh'), '--invalid-option'],
            capture_output=True, text=True, cwd=self.base, env=environment, timeout=30)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn('unrecognized arguments', invalid.stderr)
        skill = (home / '.agents/skills/blog-studio').resolve()
        self.assertEqual(skill, (home / '.claude/skills/blog-studio').resolve())
        runtime = skill / 'scripts'
        python = json.loads((skill / 'config.json').read_text())['python']
        # The installed copy is the whole skill: entry file, references and helpers side by side.
        for name in ('SKILL.md', 'VERSION', 'references/entry-flows.md', 'references/modules/blog-deep-research.md',
                     'references/upstream/deep-research/LICENSE', 'scripts/hub.py', 'scripts/google_drive.py', 'scripts/deep_research.py'):
            self.assertTrue((skill / name).is_file(), name)
        self.assertIn('Team Hub', run(python, str(runtime / 'hub.py'), '--help'))
        fresh = self.base / 'not-created'
        self.assertEqual(json.loads(run(python, str(runtime / 'studio.py'), '--root', str(fresh), 'home'))['workspace_status'], 'new')
        self.assertFalse(fresh.exists())
        workspace = self.base / 'writing project/.blog-studio'
        run(python, str(runtime / 'studio.py'), '--root', str(workspace), 'init')
        created = json.loads(run(python, str(runtime / 'studio.py'), '--root',
            str(workspace), 'article', 'create', '--title', 'Portable draft', '--mode', 'outline-only'))
        self.assertEqual(created['guidance'], {'revision': VERSION, 'source': 'installed'})
        shown = json.loads(run(python, str(runtime / 'studio.py'), '--root', str(workspace), 'article', 'show', '--id', created['id']))
        self.assertEqual(shown['guidance']['revision'], VERSION)
        self.assertFalse((workspace / 'task-context').exists())
        removed = json.loads(run('sh', str(setup / 'installer/install.sh'), 'uninstall', '--home', str(home), '--yes', '--json'))
        self.assertEqual(sorted(removed['removed']), ['claude', 'codex'])
        self.assertFalse((home / '.claude/skills/blog-studio').exists())
        self.assertTrue((workspace / 'articles' / created['id']).is_dir())


if __name__ == '__main__':
    unittest.main()
