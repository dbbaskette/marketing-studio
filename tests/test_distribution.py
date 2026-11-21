"""Release preparation and offline install contracts; no network or real user state."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import marketing_studio
from studio_core import bundles, distribution, offline_install, runtime

ROOT = Path(__file__).resolve().parents[1]


def installer():
    spec = importlib.util.spec_from_file_location('release_installer', ROOT / 'installer/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-release-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def archive(self, entries):
        path = self.root / 'input.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, data, link in entries:
                member = tarfile.TarInfo(name)
                member.mode = 0o755
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = link
                    archive.addfile(member)
                else:
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
        return path

    def test_private_runtime_links_are_flattened_and_licenses_kept(self):
        archive = self.archive([('python/bin/python3.13', b'python', None),
                                ('python/bin/python3', b'', 'python3.13'),
                                ('python/LICENSE', b'license', None)])
        output = self.root / 'python'
        distribution.unpack(archive, output)
        self.assertFalse((output / 'bin/python3').is_symlink())
        self.assertEqual((output / 'bin/python3').read_bytes(), b'python')
        self.assertTrue(os.access(output / 'bin/python3', os.X_OK))
        self.assertEqual((output / 'LICENSE').read_bytes(), b'license')

    def test_python_sources_ship_without_mutable_bytecode_caches(self):
        archive = self.archive([
            ('python/lib/python3.13/encodings/__init__.py', b'# source', None),
            ('python/lib/python3.13/encodings/__pycache__/__init__.cpython-313.pyc', b'cache', None),
            ('python/lib/python3.13/legacy.pyc', b'cache', None),
            ('python/lib/python3.13/legacy.pyo', b'cache', None),
        ])
        output = self.root / 'python'
        distribution.unpack(archive, output)
        self.assertEqual([p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()],
                         ['lib/python3.13/encodings/__init__.py'])

    def test_archive_escape_and_cyclic_links_are_refused(self):
        for index, entries in enumerate([
            [('python/../../outside', b'bad', None)],
            [('python/bin/python3', b'', '../../../outside')],
            [('python/a', b'', 'b'), ('python/b', b'', 'a')],
        ]):
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):
                    distribution.unpack(self.archive(entries), self.root / str(index))
        self.assertFalse((self.root / 'outside').exists())

    def test_cached_runtime_is_verified_before_use(self):
        cache = self.root / 'cache'
        cache.mkdir()
        sha = hashlib.sha256(b'expected').hexdigest()
        (cache / sha).write_bytes(b'damaged')
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('Network used')):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                distribution.download({'sha256': sha, 'url': 'https://example.com/runtime'}, cache)

    def test_node_bundle_contains_runtime_and_license_without_npm(self):
        archive = self.archive([('node/bin/node', b'node', None), ('node/LICENSE', b'license', None),
                                ('node/lib/node_modules/npm/index.js', b'not a runtime dependency', None)])
        output = self.root / 'node'
        distribution.unpack(archive, output, node=True)
        self.assertEqual(sorted(p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()),
                         ['LICENSE', 'bin/node'])

    def test_linux_terminal_database_is_not_needed_in_browser_studio_bundle(self):
        archive = self.archive([('python/bin/python3', b'python', None),
                                ('python/share/terminfo/a/ansi', b'unused', None),
                                ('python/share/terminfo/a/ANSI', b'unused', None)])
        output = self.root / 'python'
        distribution.unpack(archive, output)
        self.assertTrue((output / 'bin/python3').is_file())
        self.assertFalse((output / 'share/terminfo').exists())

    def test_installer_honors_shared_assistant_before_detecting_other_clis(self):
        config = self.root / 'shared.json'
        config.write_text('{"schema":1,"assistant":{"agent":"claude"}}')
        with mock.patch.dict(os.environ, {'STUDIOS_CONFIG': str(config)}), mock.patch('shutil.which', return_value='/synthetic/codex'):
            self.assertEqual(runtime.assistant_target(self.root), 'claude')

    def test_a_companion_installers_answer_names_the_version_folder_new_style_or_old(self):
        shared = self.root / 'shared'
        folder = shared / 'versions' / ('1.3.0-' + 'c' * 20)
        folder.mkdir(parents=True)
        (shared / 'current').symlink_to('versions/' + folder.name)
        # Harness Research 1.3.0 and later: `runtime` is the stable link, the folder is named.
        newer = {'runtime': str(shared / 'current'), 'id': folder.name, 'versionDirectory': str(folder)}
        # Earlier releases: `runtime` is the version folder itself, and nothing else is said.
        older = {'runtime': str(folder)}
        # A release that answers with the link but does not name the folder is still read.
        linked = {'runtime': str(shared / 'current')}
        for answer in (newer, older, linked):
            with self.subTest(answer=sorted(answer)):
                found = distribution.installed_version(answer)
                self.assertEqual(found, folder)
                self.assertNotEqual(found.name, 'current')
                self.assertFalse(found.is_symlink())
                self.assertRegex(found.name, r'^1\.3\.0-[a-f0-9]{20}$', 'what offline_install.plan accepts')
        for answer in ({'runtime': str(shared)}, {'runtime': str(shared / 'current'), 'id': 'current'},
                       {'runtime': str(shared / 'versions/absent')}):
            with self.subTest(answer=answer), self.assertRaisesRegex(ValueError, 'version folder'):
                distribution.installed_version(answer)

    def test_release_preparation_records_the_folder_name_and_copies_its_files(self):
        """A stand-in companion installer that answers as 1.3.0 does; no network, no npm."""
        root, destination, cache = self.root / 'checkout', self.root / 'staged', self.root / 'cache'
        (root / 'pins').mkdir(parents=True)
        (destination / 'pins').mkdir(parents=True)
        package = self.root / 'harness-research'
        (package / 'scripts').mkdir(parents=True)
        (package / 'SKILL.md').write_text('Synthetic companion')
        (package / 'package.json').write_text('{"version":"1.3.0"}')
        (package / 'scripts/install.mjs').write_text('// stand-in\n')
        answers = []

        def stand_in(command, **options):
            shared = Path(command[command.index('--shared') + 1])
            folder = shared / 'versions' / ('1.3.0-' + 'd' * 20)
            shutil.copytree(package, folder)
            (shared / 'current').symlink_to('versions/' + folder.name)
            answers.append({'runtime': str(shared / 'current'), 'id': folder.name, 'versionDirectory': str(folder)})
            return subprocess.CompletedProcess(command, 0, json.dumps(answers[-1]), '')

        pin = {'version': '1.3.0', 'commit': 'e' * 40, 'sha256': distribution.tree_digest(package),
               'installer': 'scripts/install.mjs', 'repository': 'https://example.invalid/research.git',
               'stub': 'SKILL.md'}
        runtimes = {'platforms': {'macos-arm64': {'python': {}, 'node': {}}}, 'python_notices': {}}
        (root / 'pins/runtimes.json').write_text(json.dumps(runtimes))
        with mock.patch.object(distribution, 'read_pins', return_value={'harness-research': pin}), \
                mock.patch.object(distribution, 'download', side_effect=lambda pin, cache: cache), \
                mock.patch.object(distribution, 'unpack'), mock.patch.object(distribution, 'python_notices'), \
                mock.patch.object(distribution.subprocess, 'run', side_effect=stand_in), \
                mock.patch('urllib.request.urlopen', side_effect=AssertionError('Network used')):
            record = distribution.prepare(root, destination, 'macos-arm64', cache, ['blog'],
                                          {'harness-research': package})
        self.assertEqual(answers[0]['runtime'].rsplit('/', 1)[1], 'current')
        self.assertEqual(record['companions']['harness-research']['id'], '1.3.0-' + 'd' * 20)
        self.assertEqual((destination / 'companions/harness-research/package.json').read_text(), '{"version":"1.3.0"}')
        self.assertFalse(any(path.is_symlink() for path in (destination / 'companions').rglob('*')))

    def test_private_path_precedes_host_tools_in_generated_launchers(self):
        private = self.root / 'runtime'
        (private / 'node/bin').mkdir(parents=True)
        (private / 'node/bin/node').touch()
        (private / 'platform').write_text(distribution.host_platform())
        with mock.patch.object(runtime.sys, 'executable', str(private / 'python/bin/python3')):
            path = runtime.shell_path()
        self.assertIn(str(private / 'node/bin'), path)
        self.assertTrue(path.endswith(':"$PATH"\n'))

    def test_a_private_runtime_inside_an_installed_version_is_named_through_current(self):
        data = self.root / 'marketing-studio'
        private = data / 'versions/4.0.0-abcdef012345/runtime'
        (private / 'node/bin').mkdir(parents=True)
        (private / 'node/bin/node').touch()
        (private / 'platform').write_text(distribution.host_platform())
        (data / 'current').symlink_to(private.parent)
        # However the interpreter says where it is: through the link, or resolved past it.
        for executable in (private / 'python/bin/python3', data / 'current/runtime/python/bin/python3'):
            with self.subTest(executable=executable), mock.patch.object(runtime.sys, 'executable', str(executable)):
                path = runtime.shell_path()
            self.assertEqual(path, 'export PATH=' + str(data / 'current/runtime/python/bin') + ':'
                             + str(data / 'current/runtime/node/bin') + ':"$PATH"\n')


class OfflineInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='marketing-offline-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source, self.home = self.root / 'source', self.root / 'home'
        self.home.mkdir()
        bundles.materialize(ROOT, self.source, ['presentation'])
        for relative in ('runtime/python/bin/python3', 'runtime/node/bin/node'):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        (self.source / 'runtime/platform').write_text(distribution.host_platform())
        self.record = {'schema': 1, 'platform': distribution.host_platform(), 'companions': {}}
        for name in ('harness-research', 'harness-slides'):
            folder = self.source / 'companions' / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('Synthetic companion')
            (folder / 'package.json').write_text('{"version":"1.0.0"}')
            self.record['companions'][name] = {'version': '1.0.0', 'id': '1.0.0-' + 'a' * 20}
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        self.module = installer()
        self.data = self.home / '.local/share/marketing-studio'

    def install(self):
        with mock.patch.object(self.module, 'run_native', return_value={'installed': True}):
            return self.module.install(self.source, self.home, self.data, ['presentation'], 'codex', 'install')

    def update(self, name='harness-slides', version='1.1.0'):
        """The same download with a newer prepared companion, as a later release has."""
        self.record['companions'][name] = {'version': version, 'id': version + '-' + 'b' * 20}
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        (self.source / 'companions' / name / 'package.json').write_text(json.dumps({'version': version}))

    def command(self, *arguments):
        """The installer's command line against the disposable home: (exit code, stderr)."""
        said = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(said):
            code = self.module.main([*arguments, '--home', str(self.home), '--yes', '--json'])
        return code, said.getvalue()

    def keep_from_removal(self, folder):
        """Make a folder one that cannot be removed, and put that right when the test ends."""
        folders = [folder, *(path for path in folder.rglob('*') if path.is_dir())]
        for path in folders:
            path.chmod(0o555)
        self.addCleanup(lambda: [path.chmod(0o755) for path in folders if path.is_dir()])

    def versions(self, name):
        return sorted(path.name for path in (offline_install.shared_root(self.home, name) / 'versions').iterdir())

    def test_offline_install_has_no_fetch_npm_or_provider_calls(self):
        with mock.patch('subprocess.run', side_effect=AssertionError('External command used')):
            self.install()
        current = self.home / '.agents/skills/harness-slides'
        self.assertEqual(json.loads((current / 'package.json').read_text())['version'], '1.0.0')
        launcher = (self.data / 'marketing-studio').read_text()
        # The private runtime is named through `current`, which the next update moves.
        self.assertIn('export PATH=' + str(self.data / 'current/runtime/python/bin') + ':'
                      + str(self.data / 'current/runtime/node/bin') + ':', launcher)
        self.assertIn('exec ' + str(self.data / 'current/runtime/python/bin/python3') + ' ', launcher)
        self.assertNotIn('versions/', launcher)
        self.assertNotIn(str(self.source), launcher)
        self.assertFalse((self.home / '.claude/skills/harness-slides').exists())

    def test_wrong_platform_and_unrelated_skills_fail_before_installing(self):
        self.record['platform'] = 'unsupported-platform'
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'another platform'):
            self.install()
        self.assertFalse(self.data.exists())
        self.record['platform'] = distribution.host_platform()
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        skill = self.home / '.agents/skills/harness-slides'
        skill.mkdir(parents=True)
        sentinel = skill / 'keep'
        sentinel.write_text('preserved')
        with self.assertRaisesRegex(ValueError, 'unmanaged path|unrelated skill|unmanaged folder'):
            self.install()
        self.assertEqual(sentinel.read_text(), 'preserved')
        self.assertFalse((self.data / 'current').exists())

    def late_failure(self):
        """Fail at the last step that can: writing the record, after every pointer has moved."""
        original, failed = self.module.atomic, []
        def fail(path, data, mode=0o600):
            if path == self.data / 'installation.json' and not failed:
                failed.append(path)   # once: putting the old record back must then succeed
                raise OSError('Synthetic late failure')
            return original(path, data, mode)
        return mock.patch.object(self.module, 'atomic', side_effect=fail)

    def test_failure_restores_all_companion_and_suite_pointers(self):
        with self.late_failure():
            with self.assertRaisesRegex(OSError, 'late failure'):
                self.install()
        for path in offline_install.managed_paths(self.home, ['presentation'], 'codex'):
            self.assertFalse(path.exists() or path.is_symlink(), str(path))
        self.assertFalse((self.data / 'installation.json').exists())
        self.assertFalse((self.data / 'current').is_symlink())

    def test_a_failed_update_restores_the_old_pointers_and_keeps_the_old_versions(self):
        self.install()
        pointers = {path: os.readlink(path) for path in
                    [self.data / 'current', *offline_install.managed_paths(self.home, ['presentation'], 'codex')]}
        record = (self.data / 'installation.json').read_bytes()
        launcher = (self.data / 'marketing-studio').read_bytes()
        kept = {name: self.versions(name) for name in ('harness-research', 'harness-slides')}
        self.update()
        (self.source / 'VERSION').write_text('9.9.9\n')
        with self.late_failure():
            with self.assertRaisesRegex(OSError, 'late failure'):
                self.install()
        for path, target in pointers.items():
            self.assertEqual(os.readlink(path), target, str(path))
            self.assertTrue(path.resolve().is_dir(), 'the version it names was not removed: ' + str(path))
        self.assertEqual((self.data / 'installation.json').read_bytes(), record)
        self.assertEqual((self.data / 'marketing-studio').read_bytes(), launcher)
        self.assertEqual(self.versions('harness-research'), kept['harness-research'])
        self.assertTrue(set(kept['harness-slides']) < set(self.versions('harness-slides')),
                        'the old version stays beside the one the failed update staged')
        self.assertEqual(json.loads((self.home / '.agents/skills/harness-slides/package.json').read_text())['version'], '1.0.0')

    def test_a_source_install_is_not_run_with_the_private_python_an_update_removes(self):
        self.install()
        pointer, record = os.readlink(self.data / 'current'), (self.data / 'installation.json').read_bytes()
        (self.source / 'distribution.json').unlink()   # a checkout: no private runtime of its own
        (self.source / 'VERSION').write_text('9.9.9\n')
        # As `marketing-studio update --from <checkout>` would run it: with the installed runtime.
        private = self.data / 'current/runtime/python/bin/python3'
        with mock.patch.object(self.module.sys, 'executable', str(private)), \
                mock.patch.object(self.module, 'run_native', side_effect=AssertionError('Installed a studio')):
            with self.assertRaisesRegex(self.module.InstallError, 'your own Python'):
                self.module.install(self.source, self.home, self.data, ['presentation'], 'codex', 'skip')
        self.assertEqual(os.readlink(self.data / 'current'), pointer)
        self.assertEqual((self.data / 'installation.json').read_bytes(), record)
        self.assertEqual(len(list((self.data / 'versions').iterdir())), 1)

    def test_a_source_install_that_would_strand_a_studio_on_the_private_runtime_is_refused(self):
        self.install()
        # Training Studio was installed from the same download, and opens with its private Python.
        state = json.loads((self.data / 'installation.json').read_text())
        state['studios'] = ['presentation', 'training']
        (self.data / 'installation.json').write_text(json.dumps(state))
        opener = self.home / '.local/share/training-studio/studio'
        opener.parent.mkdir(parents=True)
        opener.write_text('#!/bin/sh\nexec ' + str(self.data / 'current/runtime/python/bin/python3') + ' studio.py\n')
        pointer, record = os.readlink(self.data / 'current'), (self.data / 'installation.json').read_bytes()
        (self.source / 'distribution.json').unlink()   # a checkout: no private runtime of its own
        (self.source / 'VERSION').write_text('9.9.9\n')
        with mock.patch.object(self.module, 'run_native', side_effect=AssertionError('Installed a studio')):
            with self.assertRaisesRegex(self.module.InstallError, 'Training Studio open with the private Python'):
                self.module.install(self.source, self.home, self.data, ['presentation'], 'codex', 'skip')
        self.assertEqual(os.readlink(self.data / 'current'), pointer)
        self.assertEqual((self.data / 'installation.json').read_bytes(), record)
        self.assertTrue((self.data / 'current/runtime/python/bin/python3').is_file())

    def test_uninstall_keeps_the_private_runtime_the_studios_open_with(self):
        self.install()
        code, said = self.command('uninstall')
        self.assertEqual(code, 0, said)
        for path in (self.data / 'installation.json', self.data / 'marketing-studio',
                     self.home / '.local/bin/marketing-studio', self.home / 'Applications/Open Marketing Studio.command'):
            self.assertFalse(path.exists() or path.is_symlink(), str(path))
        # A studio's launcher names this Python through `current`, and still finds it.
        self.assertTrue((self.data / 'current/runtime/python/bin/python3').is_file())
        self.assertTrue((self.data / 'current/runtime/node/bin/node').is_file())
        # Installing again afterwards is an ordinary install.
        self.assertEqual(self.install()['action'], 'install')

    def test_newer_independent_companions_are_kept(self):
        current = offline_install.shared_root(self.home, 'harness-slides') / 'current'
        newer = current.parent / 'versions/2.0.0-newer'
        newer.mkdir(parents=True)
        (newer / 'package.json').write_text('{"version":"2.0.0"}')
        current.symlink_to('versions/2.0.0-newer')
        # Whatever else its own installer left there is its own to remove, not this one's.
        beside = current.parent / 'versions/1.9.0-earlier'
        beside.mkdir()
        (beside / 'package.json').write_text('{"version":"1.9.0"}')
        result = self.install()
        self.assertEqual(current.resolve(), newer)
        self.assertEqual((self.home / '.agents/skills/harness-slides').resolve(), newer)
        self.assertEqual(self.versions('harness-slides'), ['1.9.0-earlier', '2.0.0-newer'])
        left = result['results']['companions']['harness-slides']
        self.assertEqual((left['state'], left['removed'], left['retained']), ('left alone', [], []))
        self.assertEqual(result['results']['companions']['harness-research']['state'], 'installed')

    def test_an_update_keeps_one_version_of_each_bundled_companion_and_of_the_suite(self):
        first = self.install()
        name = 'harness-slides'
        root = offline_install.shared_root(self.home, name)
        old = (root / 'current').resolve()
        # What an interrupted install and someone's own link can leave beside the versions.
        outside = self.root / 'kept elsewhere'
        outside.mkdir()
        (outside / 'mine.txt').write_text('Not the installer\'s.')
        (root / 'versions/linked').symlink_to(outside, target_is_directory=True)
        (root / 'versions/.bundle-stale/runtime').mkdir(parents=True)
        (self.data / 'versions/.pending-0123abcdef01').mkdir()
        self.update()
        (self.source / 'VERSION').write_text('9.9.9\n')
        second = self.install()
        installed = second['results']['companions'][name]
        # The companion's own pointer stays the relative link its installer requires.
        self.assertRegex(os.readlink(root / 'current'), r'^versions/1\.1\.0-b{20}-bundle-[a-f0-9]{12}$')
        self.assertEqual(self.versions(name), [(root / 'current').resolve().name])
        self.assertEqual(sorted(installed['removed']),
                         sorted(str(root / 'versions' / item) for item in (old.name, 'linked', '.bundle-stale')))
        self.assertEqual(installed['retained'], [])
        self.assertEqual((installed['runtime'], installed['id'], installed['versionDirectory']),
                         (str(root / 'current'), (root / 'current').resolve().name, str((root / 'current').resolve())))
        self.assertEqual((outside / 'mine.txt').read_text(), "Not the installer's.", 'a link is never followed')
        self.assertEqual(json.loads((self.home / '.agents/skills' / name / 'package.json').read_text())['version'], '1.1.0')
        # The untouched companion keeps the version it has, and the suite keeps one too.
        self.assertEqual(second['results']['companions']['harness-research']['removed'], [])
        self.assertEqual(len(self.versions('harness-research')), 1)
        self.assertEqual([path.name for path in (self.data / 'versions').iterdir()], [second['id']])
        self.assertEqual(sorted(second['removed']), sorted(str(self.data / 'versions' / item)
                                                           for item in (first['id'], '.pending-0123abcdef01')))
        self.assertEqual((second['runtime'], second['versionDirectory']),
                         (str(self.data / 'current'), str(self.data / 'versions' / second['id'])))
        # The launchers written by the first install still open the second.
        self.assertNotIn('versions/', (self.data / 'marketing-studio').read_text())
        self.assertTrue((self.data / 'current/runtime/python/bin/python3').is_file())
        state = json.loads((self.data / 'installation.json').read_text())
        self.assertEqual(state['current'], second['id'])
        self.assertNotIn('versions/', json.dumps({key: value for key, value in state.items() if key != 'previous'}))

    def test_a_companion_version_that_cannot_be_removed_is_reported_and_the_install_succeeds(self):
        self.install()
        root = offline_install.shared_root(self.home, 'harness-slides')
        old = (root / 'current').resolve()
        self.keep_from_removal(old)
        self.update()
        result = self.install()
        installed = result['results']['companions']['harness-slides']
        self.assertEqual(installed['state'], 'installed')
        self.assertEqual(installed['removed'], [])
        self.assertEqual([kept['path'] for kept in installed['retained']], [str(old)])
        self.assertTrue(installed['retained'][0]['reason'])
        self.assertEqual(json.loads((self.home / '.agents/skills/harness-slides/package.json').read_text())['version'], '1.1.0')

    def prerelease(self):
        name, version = 'harness-research', '1.0.1-alpha.1'
        self.record['companions'][name] = {'version': version, 'id': version + '-' + 'b' * 20}
        (self.source / 'companions' / name / 'package.json').write_text(json.dumps({'version': version}))
        (self.source / 'distribution.json').write_text(json.dumps(self.record))
        return name, version

    def test_configured_prerelease_installs_offline(self):
        name, version = self.prerelease()
        self.install()
        current = self.home / '.agents/skills' / name
        self.assertEqual(json.loads((current / 'package.json').read_text())['version'], version)

    def test_stable_install_is_preserved_over_a_prerelease_of_the_same_version(self):
        name, _ = self.prerelease()
        current = offline_install.shared_root(self.home, name) / 'current'
        stable = current.parent / 'versions/1.0.1-stable'
        stable.mkdir(parents=True)
        (stable / 'package.json').write_text('{"version":"1.0.1"}')
        current.symlink_to('versions/' + stable.name)
        self.install()
        self.assertEqual(current.resolve(), stable)

    def test_existing_upstream_lock_refuses_changes_and_is_preserved(self):
        root = offline_install.shared_root(self.home, 'harness-research')
        root.mkdir(parents=True)
        lock = root / '.install-lock'
        lock.write_text('another installer')
        with self.assertRaisesRegex(ValueError, 'in progress'):
            self.install()
        self.assertEqual(lock.read_text(), 'another installer')
        self.assertFalse((self.data / 'current').exists())

    def test_same_upstream_revision_without_dependencies_is_replaced_by_the_bundled_copy(self):
        name = 'harness-slides'
        root = offline_install.shared_root(self.home, name)
        previous = root / 'versions' / self.record['companions'][name]['id']
        previous.mkdir(parents=True)
        (previous / 'package.json').write_text('{"version":"1.0.0"}')
        (root / 'current').symlink_to('versions/' + previous.name)
        # It is never written over: the prepared tree gets a folder of its own, and the
        # upstream one is still there if this install fails.
        with self.late_failure():
            with self.assertRaisesRegex(OSError, 'late failure'):
                self.install()
        self.assertEqual(os.readlink(root / 'current'), 'versions/' + previous.name)
        self.assertEqual((previous / 'package.json').read_text(), '{"version":"1.0.0"}')
        result = self.install()
        self.assertNotEqual((root / 'current').resolve(), previous)
        self.assertIn('-bundle-', (root / 'current').resolve().name)
        # Once the install has succeeded one version is kept, as the companion's own installer keeps one.
        self.assertFalse(previous.exists())
        self.assertIn(str(previous), result['results']['companions'][name]['removed'])

    def test_rollback_after_an_update_refuses_and_changes_nothing(self):
        self.install()
        current = offline_install.shared_root(self.home, 'harness-slides') / 'current'
        self.update()
        self.install()
        pointers = {path: os.readlink(path) for path in (current, self.data / 'current')}
        record = (self.data / 'installation.json').read_bytes()
        launcher = (self.data / 'marketing-studio').read_bytes()
        code, said = self.command('rollback')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(said.splitlines()[-1]), {'error': (
            'The earlier version is no longer on this computer: an update keeps only the newest. '
            'Install the version you want from its repository instead. Nothing was changed.')})
        self.assertEqual({path: os.readlink(path) for path in pointers}, pointers)
        self.assertEqual((self.data / 'installation.json').read_bytes(), record)
        self.assertEqual((self.data / 'marketing-studio').read_bytes(), launcher)
        self.assertFalse((current.parent / '.install-lock').exists(), 'the companion lock was not left behind')

    def test_rollback_restores_companion_versions_that_are_still_there(self):
        self.install()
        current = offline_install.shared_root(self.home, 'harness-slides') / 'current'
        before, suite = os.readlink(current), os.readlink(self.data / 'current')
        for folder in (current.resolve(), Path(suite)):
            self.keep_from_removal(folder)
        self.update()
        result = self.install()
        self.assertEqual([kept['path'] for kept in result['retained']], [suite])
        self.assertNotEqual(os.readlink(current), before)
        code, said = self.command('rollback')
        self.assertEqual(code, 0, said)
        self.assertEqual(os.readlink(current), before)
        self.assertEqual(os.readlink(self.data / 'current'), suite)
        self.assertEqual(json.loads((self.home / '.agents/skills/harness-slides/package.json').read_text())['version'], '1.0.0')

    def test_tampered_runtime_is_rejected_by_bundle_manifest(self):
        archive = self.root / 'archive'
        result = bundles.build(self.source, archive, selection=['presentation'])
        import zipfile
        with zipfile.ZipFile(archive / next(iter(result))) as source:
            source.extractall(self.root / 'unpacked')
        unpacked = self.root / 'unpacked/marketing-studio-setup'
        (unpacked / 'runtime/node/bin/node').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'bundle changed'):
            self.module.verify_bundle(unpacked)


if __name__ == '__main__':
    unittest.main()
