"""The brand skill's own repository, and installing it from the page: where its main branch
is, fetching main, and running its own installer without letting it move the companions.

The brand repository is a bare one made here, with its release tags. Its installer is a
stand-in that records how it was run, lays the brand skill out as a shared install with a
link for each assistant, and refuses when it is not told to leave harness-research alone.
`gh` is a stand-in too, which serves a ZIP the test made. Nothing real is read, and nothing
is fetched from anywhere but here. The brand is a made-up one, Acme.
"""
import dataclasses
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import helpers
import runner_support  # noqa: F401  puts the runner on the import path
from test_runner_upkeep import UpkeepCase, git

from workspace import WorkspaceError

from runner import brand_source, settings, upkeep

NODE = shutil.which('node')

GITHUB = 'https://github.com/acme/acme-brand.git'
# The brand skill's own command: it lists its brands and says its version, as a real one.
COMMAND = """const [asked] = process.argv.slice(2);
if (asked === 'brands') console.log(JSON.stringify([{ brand: 'acme', name: 'Acme Works',
  variants: ['light'] }]));
else if (asked === 'version') console.log('Acme Brand @VERSION@');
else { console.error('Unknown command'); process.exit(1); }
"""
# The brand skill's own installer, as small as it can be and still do what the real one
# does: one shared copy, `current` pointing at it, and a link for each assistant. It writes
# down how it was run, refuses unless told to leave harness-research alone, can be held
# until the test lets it go, and, when its package says so, meddles with harness-slides.
INSTALLER = """import { cpSync, mkdirSync, symlinkSync, readFileSync, rmSync, lstatSync,
  writeFileSync, existsSync, appendFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
const args = process.argv.slice(2);
const script = fileURLToPath(import.meta.url);
const source = join(dirname(script), '..');
const pkg = JSON.parse(readFileSync(join(source, 'package.json'), 'utf8'));
appendFileSync(process.env.BRAND_STAND_IN_RECORD, JSON.stringify({ script: script.split('/').pop(),
  args, home: homedir(), cwd: process.cwd() }) + '\\n');
if (process.env.BRAND_STAND_IN_HOLD) {
  writeFileSync(process.env.BRAND_STAND_IN_HOLD + '.running', 'yes');
  while (!existsSync(process.env.BRAND_STAND_IN_HOLD)) await new Promise(go => setTimeout(go, 20));
}
const at = args.indexOf('--research');
if (at < 0 || args[at + 1] !== 'skip') {
  console.error('Setup could not finish: it would install harness-research.');
  process.exit(1);
}
if (pkg.refuses) { console.error('Setup could not finish: ' + pkg.refuses); process.exit(1); }
if (pkg.meddles) {
  const slides = join(homedir(), '.agents', 'skills', 'harness-slides');
  rmSync(slides, { recursive: true, force: true });
  mkdirSync(join(slides, 'scripts'), { recursive: true });
  writeFileSync(join(slides, 'package.json'), JSON.stringify({ version: '0.1.0' }));
  writeFileSync(join(slides, 'scripts', 'harness-slides.mjs'), '// its own, older\\n');
}
const shared = join(homedir(), '.local', 'share', 'acme-brand');
const runtime = join(shared, 'versions', pkg.version);
mkdirSync(runtime, { recursive: true });
cpSync(source, runtime, { recursive: true, filter: path => !path.includes('/.git') });
rmSync(join(shared, 'current'), { force: true });
symlinkSync(join('versions', pkg.version), join(shared, 'current'));
for (const folder of ['.agents', '.claude']) {
  const target = join(homedir(), folder, 'skills', 'acme-brand');
  mkdirSync(dirname(target), { recursive: true });
  try { lstatSync(target); } catch { symlinkSync(join(shared, 'current'), target); }
}
console.log('Shared installation installed.');
"""


class BrandRepository:
    """A stand-in for the brand skill's repository: a bare one, with release tags."""

    def __init__(self, base: Path):
        self.bare, self.work = base / 'acme-brand.git', base / 'acme-brand-work'
        # Its releases are pushed to main, which is its HEAD whatever git's default is here.
        git(base, 'init', '-q', '--bare', '--initial-branch=main', str(self.bare))
        git(base, 'init', '-q', str(self.work))

    def release(self, version: str, slides: str | None = '0.14.1', tag: bool = True,
                **package) -> str:
        """Commit one release, tag it v<version>, and return its commit."""
        files = {
            'package.json': json.dumps({'name': 'acme-brand', 'version': version, **package}),
            'SKILL.md': '---\nname: acme-brand\n---\n\nThe Acme brands.\n',
            'scripts/acme-brand.mjs': COMMAND.replace('@VERSION@', version),
            'scripts/install-mac.mjs': INSTALLER,
            'scripts/install-skill.mjs': INSTALLER,
        }
        if slides:
            files['scripts/lib/harness-install-sources.json'] = json.dumps({
                'slides': {'package': 'harness-slides', 'version': slides},
                'research': {'package': 'harness-research-skill', 'version': '0.8.0'}})
        for name, text in files.items():
            (self.work / name).parent.mkdir(parents=True, exist_ok=True)
            (self.work / name).write_text(text, encoding='utf-8')
        if not slides:
            (self.work / 'scripts' / 'lib' / 'harness-install-sources.json').unlink(
                missing_ok=True)
        git(self.work, 'add', '-A')
        git(self.work, 'commit', '-q', '-m', f'Release {version}')
        if tag:
            git(self.work, 'tag', '-f', f'v{version}')
        git(self.work, 'push', '-q', '-f', '--tags', str(self.bare), 'HEAD:refs/heads/main')
        return git(self.work, 'rev-parse', 'HEAD')

    def archive(self, folder: Path, version: str, prefix: str = '') -> Path:
        """The working copy as a release ZIP, as the brand packs it."""
        path = folder / f'acme-brand-{version}{"-mac" if prefix else ""}.zip'
        with zipfile.ZipFile(path, 'w') as packed:
            for one in sorted(self.work.rglob('*')):
                if one.is_file() and '.git' not in one.relative_to(self.work).parts:
                    packed.write(one, prefix + one.relative_to(self.work).as_posix())
        return path


GH = """#!@PYTHON@
import json, os, shutil, sys
args = sys.argv[1:]
folder = os.environ['GH_STAND_IN']
with open(os.path.join(folder, 'asked.jsonl'), 'a') as kept:
    kept.write(json.dumps(args) + '\\n')
if args[:2] == ['auth', 'status']:
    sys.exit(0 if os.path.exists(os.path.join(folder, 'signed-in')) else 1)
tag = args[2]
release = os.path.join(folder, 'releases', tag)
if args[:2] == ['release', 'view']:
    if not os.path.isdir(release):
        print('release not found', file=sys.stderr)
        sys.exit(1)
    print(json.dumps({'assets': [{'name': name} for name in sorted(os.listdir(release))]}))
    sys.exit(0)
if args[:2] == ['release', 'download']:
    into = args[args.index('--dir') + 1]
    wanted = [args[at + 1] for at, word in enumerate(args) if word == '--pattern']
    for name in wanted:
        shutil.copy(os.path.join(release, name), os.path.join(into, name))
    sys.exit(0)
sys.exit(2)
"""


def settle(keep: upkeep.Upkeep) -> None:
    """Until whatever the keeper started in the background has ended."""
    for thread in list(keep._threads):
        thread.join(120)


class SourceCase(unittest.TestCase):
    """A brand repository with releases, and a folder to run git in."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()
        self.place = self.base / 'git-runs-here'
        self.place.mkdir()
        self.brand = BrandRepository(self.base)
        self.address = str(self.brand.bare)


class ReleaseTests(SourceCase):
    def test_a_year_first_version_comes_before_every_other(self):
        for version in ('2026.5.0', '2026.6.0', '2099.0.0'):
            self.assertLess(brand_source.order(version), brand_source.order('0.8.0'))
        self.assertLess(brand_source.order('2026.5.7'), brand_source.order('2026.6.0'))
        self.assertLess(brand_source.order('0.10.2'), brand_source.order('0.13.1'))
        self.assertGreater(brand_source.order('1999.1.0'), brand_source.order('2026.1.0'),
                           'a number before 2000 is a version, not a year')
        self.assertEqual(brand_source.order('not.a.version'), ())

    def test_main_is_what_is_installed_whatever_tags_there_are(self):
        self.brand.release('2026.6.0')
        newer = self.brand.release('0.13.1')
        git(self.brand.work, 'tag', 'not-a-release')
        git(self.brand.work, 'push', '-q', '--tags', str(self.brand.bare))
        found = brand_source.check(self.address, None, self.place)
        self.assertEqual(found['chosen'], {'tag': 'main', 'version': None, 'commit': newer})
        self.assertEqual((found['commit'], found['branch'], found['releases'], found['release']),
                         (newer, 'main', [], None))
        self.assertEqual(brand_source.head(self.address, self.place), newer)

    def test_a_release_named_by_an_older_version_is_not_used(self):
        self.brand.release('0.10.2')
        newer = self.brand.release('0.13.1')
        for asked in ('v0.10.2', '0.10.2', 'v9.9.9'):
            found = brand_source.check(self.address, asked, self.place)
            self.assertEqual((found['release'], found['chosen']['commit']), (None, newer))

    def test_a_repository_that_cannot_be_used_is_refused_in_a_plain_sentence(self):
        with self.assertRaises(WorkspaceError) as refused:
            brand_source.check(self.address, None, self.place)
        self.assertEqual(str(refused.exception), f'{self.address} has no main branch, which '
                         'the brand skill is installed from. Check the address.')
        with self.assertRaises(WorkspaceError) as refused:
            brand_source.check(str(self.base / 'nowhere.git'), None, self.place)
        self.assertTrue(str(refused.exception).startswith(
            "The brand skill's repository could not be read. It was not found ("),
            str(refused.exception))
        for address, says in (
                ('https://pat:secret@example.com/brand.git', 'carries a password or token'),
                ('relative/brand.git', "or a folder's whole path"),
                ('--upload-pack=touch', 'as one address'),
                ('', "Give the brand skill's repository address.")):
            with self.subTest(address=address), self.assertRaises(WorkspaceError) as refused:
                brand_source.check(address, None, self.place)
            self.assertIn(says, str(refused.exception))

    def test_why_git_failed_is_said_as_what_to_do(self):
        self.assertIn('Sign git in with an account that may read it', brand_source.plain(
            "could not read Username for 'https://github.com': terminal prompts disabled"))
        self.assertIn('Sign git in', brand_source.plain(
            'git@github.com: Permission denied (publickey)'))
        self.assertIn('A private repository is not found by someone who may not read it',
                      brand_source.plain('Repository not found'))
        self.assertIn('Check the address and that this computer is online',
                      brand_source.plain("unable to access 'https://example.com/': Could not "
                                         'resolve host: example.com'))


class FetchTests(SourceCase):
    def test_main_is_cloned_with_its_commit_checked(self):
        commit = self.brand.release('0.13.1')
        into = self.base / 'into'
        into.mkdir()
        folder, how = brand_source.fetch(self.address, commit, into)
        self.assertEqual(how, 'main')
        self.assertEqual(json.loads((folder / 'package.json').read_text())['version'], '0.13.1')
        self.assertEqual(brand_source.version_of(folder), '0.13.1')
        self.assertTrue((folder / '.git').is_dir(), 'its installer may ask git which commit')
        again = self.base / 'again'
        again.mkdir()
        with self.assertRaises(WorkspaceError) as refused:
            brand_source.fetch(self.address, '0' * 40, again)
        self.assertIn('main was fetched at another commit than the 000000000000 you were shown',
                      str(refused.exception))

    def test_it_is_cloned_with_the_persons_own_git_and_no_hook_runs(self):
        commit = self.brand.release('0.13.1')
        hooks = self.base / 'hooks'
        hooks.mkdir()
        (hooks / 'post-checkout').write_text('#!/bin/sh\ntouch "$0.ran"\n')
        (hooks / 'post-checkout').chmod(0o755)
        config = helpers.gitconfig(self.base / 'gitconfig',
                                   f'[url "{self.address}"]\n\tinsteadOf = {GITHUB}\n'
                                   f'[core]\n\thooksPath = {hooks}\n')
        into = self.base / 'into'
        into.mkdir()
        with mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(config)}):
            folder, how = brand_source.fetch(GITHUB, commit, into)
        self.assertEqual(how, 'main')
        self.assertTrue((folder / 'scripts' / 'install-skill.mjs').is_file())
        self.assertFalse((hooks / 'post-checkout.ran').exists())


class InstallerTests(SourceCase):
    def test_its_own_installer_is_told_to_leave_harness_research_alone(self):
        folder = self.base / 'release'
        (folder / 'scripts').mkdir(parents=True)
        for name in ('install-mac.mjs', 'install-skill.mjs'):
            (folder / 'scripts' / name).write_text('// its installer\n')
        with mock.patch.object(brand_source, 'PLATFORM', 'darwin'):
            self.assertEqual(brand_source.installer(folder, 'node'), [
                'node', str(folder / 'scripts' / 'install-mac.mjs'), '--yes', '--research',
                'skip'])
        with mock.patch.object(brand_source, 'PLATFORM', 'linux'):
            self.assertEqual(brand_source.installer(folder, 'node'), [
                'node', str(folder / 'scripts' / 'install-skill.mjs'), '--research', 'skip'])
        (folder / 'scripts' / 'install-skill.mjs').unlink()
        with mock.patch.object(brand_source, 'PLATFORM', 'linux'), \
                self.assertRaises(WorkspaceError) as refused:
            brand_source.installer(folder, 'node')
        self.assertIn('no installer Presentation Studio knows how to run', str(refused.exception))

    def test_what_it_brings_when_it_finds_none_is_read_from_its_own_record(self):
        folder = self.base / 'release'
        (folder / 'scripts' / 'lib').mkdir(parents=True)
        self.assertEqual(brand_source.bootstraps(folder), {})
        (folder / brand_source.SOURCES).write_text(json.dumps({
            'slides': {'version': '0.13.1'}, 'research': {'version': '0.8.0'},
            '../odd': {'version': '1.0.0'}, 'other': {'version': 'soon'}}))
        self.assertEqual(brand_source.bootstraps(folder),
                         {'harness-slides': '0.13.1', 'harness-research': '0.8.0'})
        # Harness Brand 1.4.0 and newer name a branch and the oldest version they accept.
        (folder / brand_source.SOURCES).write_text(json.dumps({'slides': {
            'repository': 'https://example.invalid/slides.git', 'branch': 'main',
            'package': 'harness-slides', 'minimumVersion': '0.15.1'}}))
        self.assertEqual(brand_source.bootstraps(folder), {'harness-slides': '0.15.1'})


@unittest.skipUnless(NODE, 'the brand skill and its installer run on Node')
class BrandInstallCase(UpkeepCase):
    """A temporary home with both companions at their pins for both assistants, the
    installer's stand-in beside the runner, and a brand repository with releases."""

    def setUp(self):
        super().setUp()
        self.brand = BrandRepository(self.base)
        self.address = str(self.brand.bare)
        self.record = self.base / 'brand-installer.jsonl'
        patch = mock.patch.dict(os.environ, {'BRAND_STAND_IN_RECORD': str(self.record)})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop('BRAND_SKILL_RUNTIME', None)   # within the patch, so put back after
        self.claude, self.codex = self.skills, self.home / '.agents' / 'skills'
        self.stand_in()
        self.pin()
        for skills in (self.claude, self.codex):
            self.companion('harness-research', '0.8.0', skills)
            self.companion('harness-slides', '0.14.1', skills)
        self.after = []
        self.keep = self.keeper(after=lambda: self.after.append('looked'))
        self.addCleanup(self.keep.close)

    def choose(self, release: str | None = None) -> dict:
        """Name the brand repository in Settings, as the page's save does."""
        found = brand_source.check(self.address, release, self.base)
        settings.save(settings.Settings(brand_repository=found['repository'],
                                        brand_release=found['release']))
        self.keep.remember_brand(found['repository'], found['commit'])
        return found

    def row(self, report: dict | None = None) -> dict:
        report = report or self.keep.report()
        return report['versions']['rows'][-1]

    def ran(self) -> list:
        return [json.loads(line) for line in self.record.read_text().splitlines()] \
            if self.record.is_file() else []

    def install(self, release: str) -> dict:
        shown = self.keep.install_brand(False, release)
        settle(self.keep)
        return shown


class BrandRowTests(BrandInstallCase):
    def test_a_brand_skill_installed_by_hand_is_shown_and_nothing_is_offered(self):
        self.keep.check(repair=False)
        row = self.row()
        self.assertEqual((row['name'], row['kind'], row['state'], row['installed']),
                         ('brand skill', 'brand', 'unknown', None))
        self.assertEqual(row['says'], 'No brand skill is installed, so a deck stops where it '
                         'first needs your brand. Name its repository in Settings to install '
                         'and update it from here.')
        self.brand.release('0.13.1')
        folder = self.base / 'by-hand'
        # By its tag: the bare repository's HEAD is whatever branch git makes by default here.
        # By its tag, so the branch git makes by default on this computer does not matter.
        git(self.base, 'clone', '-q', '--branch', 'v0.13.1', self.address, str(folder))
        (self.claude / 'acme-brand').symlink_to(folder)
        self.keep.check(repair=False)
        shown = self.keep.report()['versions']
        self.assertEqual((self.row()['installed'], self.row()['state']), ('0.13.1', 'unknown'))
        self.assertEqual(self.row()['says'], 'Acme Brand 0.13.1 is installed. Name its '
                         'repository in Settings to install and update it from here.')
        self.assertFalse(shown['brand']['offered'])
        self.assertIsNone(shown['key'], 'Home says nothing of it')

    def test_with_a_repository_named_home_tells_of_a_missing_brand_skill_or_a_moved_main(self):
        self.brand.release('2026.6.0')
        commit = self.brand.release('0.13.1')
        self.choose()
        self.keep.check(repair=False)
        shown = self.keep.report()['versions']
        row = shown['rows'][-1]
        self.assertEqual((row['state'], row['newest'], row['target'], row['release'],
                          row['commit']), ('missing', None, 'main', 'main', commit[:12]))
        self.assertEqual(row['says'], 'No brand skill is installed, so a deck stops where it first needs your brand. '
                         f'Its main branch, at {commit[:12]}, can be installed from {self.address}.')
        self.assertEqual(shown['key'], 'brand skill main')
        self.assertEqual(shown['brand'], {
            'offered': True, 'action': 'Install', 'repository': self.address,
            'release': 'main', 'version': 'main', 'commit': commit[:12],
            'installed': None, 'state': None, 'since': None, 'says': None})

        self.install('main')
        self.keep.check(repair=False)
        row = self.row()
        self.assertEqual((row['state'], row['installed'], row['target']), ('current', '0.13.1', None))
        self.assertEqual(row['says'], 'Acme Brand 0.13.1 is installed from main, as it is now.')
        self.assertFalse(self.keep.report()['versions']['brand']['offered'])
        newer = self.brand.release('0.14.0')
        with mock.patch.object(upkeep.Upkeep, 'due', return_value=True):
            self.keep.look()
        self.keep.check(repair=False)
        shown = self.keep.report()['versions']
        row = shown['rows'][-1]
        self.assertEqual((row['state'], row['installed'], row['target'], row['commit']),
                         ('update', '0.13.1', 'main', newer[:12]))
        self.assertEqual(row['says'], 'The main branch of Acme Brand has moved on, to '
                         f'{newer[:12]}, since it was installed here.')
        self.assertEqual((shown['brand']['action'], shown['key']), ('Upgrade', 'brand skill main'))

    def test_one_installed_by_hand_with_a_repository_named_can_take_main(self):
        commit = self.brand.release('0.13.1')
        folder = self.base / 'by-hand'
        git(self.base, 'clone', '-q', '--branch', 'v0.13.1', self.address, str(folder))
        (self.claude / 'acme-brand').symlink_to(folder)
        self.choose()
        self.keep.check(repair=False)
        row = self.row()
        self.assertEqual((row['state'], row['target']), ('current', 'main'))
        self.assertEqual(row['says'], 'Acme Brand 0.13.1 is installed. Its main branch, at '
                         f'{commit[:12]}, can be installed from here.')


class BrandInstallTests(BrandInstallCase):
    def test_the_release_is_fetched_and_its_own_installer_run_then_the_computer_looked_at(self):
        commit = self.brand.release('0.13.1')
        self.choose()
        self.keep.check(repair=False)
        going = self.base / 'go'
        with mock.patch.dict(os.environ, {'BRAND_STAND_IN_HOLD': str(going)}):
            shown = self.keep.install_brand(False, 'main')
            brand = shown['versions']['brand']
            self.assertEqual((brand['state'], brand['offered']), ('running', False))
            self.assertEqual(brand['says'], f'Fetching main from {self.address} and running '
                             'its own installer. This can take a few minutes.')
            self.wait_for(going.with_name('go.running'))
            for refused, says in ((lambda: self.keep.install_brand(False, 'main'),
                                   upkeep.BRAND_INSTALLING),
                                  (lambda: self.keep.update(False), upkeep.BRAND_INSTALLING)):
                with self.assertRaises(WorkspaceError) as caught:
                    refused()
                self.assertEqual(str(caught.exception), says)
            self.assertFalse(self.keep.report()['update']['offered'])
            going.write_text('go\n')
            settle(self.keep)
        (asked,) = self.ran()
        script = 'install-mac.mjs' if sys.platform == 'darwin' else 'install-skill.mjs'
        self.assertEqual(asked['script'], script)
        self.assertEqual(asked['args'], ['--yes', '--research', 'skip']
                         if sys.platform == 'darwin' else ['--research', 'skip'])
        self.assertEqual(Path(asked['home']).resolve(), self.home)
        brand = self.keep.report()['versions']['brand']
        self.assertEqual(brand['state'], 'done')
        self.assertEqual(brand['says'], f'Acme Brand 0.13.1 is installed, from {self.address} '
                         f'at main (revision {commit[:12]}). New decks can use it.')
        self.assertEqual(self.after, ['looked'], 'the computer is looked at again')
        self.assertEqual((self.row()['state'], self.row()['installed']), ('current', '0.13.1'))
        self.assertTrue((self.claude / 'acme-brand' / 'SKILL.md').is_file())
        for skills in (self.claude, self.codex):
            self.assertEqual(json.loads((skills / 'harness-slides' / 'package.json')
                                        .read_text())['version'], '0.14.1')

    def test_it_is_refused_before_anything_is_fetched_or_run(self):
        commit = self.brand.release('0.13.1')
        self.keep.check(repair=False)
        cases = [(lambda: self.keep.install_brand(False, 'main'),
                  upkeep.NO_BRAND_REPOSITORY)]
        for refused, says in cases:
            with self.assertRaises(WorkspaceError) as caught:
                refused()
            self.assertEqual(str(caught.exception), says)
        self.choose()
        for release, working, says in (
                ('v0.10.0', False, f'The main branch is now at {commit[:12]}, not v0.10.0. Look '
                                   'at it again before you install.'),
                ('main', True, upkeep.BRAND_WORKING)):
            with self.assertRaises(WorkspaceError) as caught:
                self.keep.install_brand(working, release)
            self.assertEqual(str(caught.exception), says)
        shutil.rmtree(self.codex / 'harness-slides')
        self.keep.check(repair=False)
        with self.assertRaises(WorkspaceError) as caught:
            self.keep.install_brand(False, 'main')
        self.assertEqual(str(caught.exception), 'Update the companion skills first '
                         "(harness-slides). The brand skill's installer brings its own "
                         'harness-slides when it finds none it can use, and Presentation '
                         "Studio's are the ones to keep.")
        self.assertEqual(self.ran(), [])

    def test_a_release_that_would_replace_harness_slides_is_not_run(self):
        self.brand.release('0.13.1', slides='0.15.0')
        self.choose()
        self.keep.check(repair=False)
        self.install('main')
        brand = self.keep.report()['versions']['brand']
        self.assertEqual(brand['state'], 'failed')
        self.assertEqual(brand['says'], 'The brand skill main was not installed: its '
                         'installer would replace harness-slides 0.14.1 with its own 0.15.0 for '
                         'Claude Code and Codex, in place of the one Presentation Studio is '
                         'made with. Upgrade Presentation Studio first. Nothing was run.')
        self.assertEqual(self.ran(), [], 'its installer was never run')
        self.assertFalse(os.path.lexists(self.claude / 'acme-brand'))

    def test_a_companion_it_would_bring_that_is_not_here_stops_it(self):
        folder = self.base / 'release'
        (folder / 'scripts' / 'lib').mkdir(parents=True)
        (folder / brand_source.SOURCES).write_text(json.dumps({
            'slides': {'version': '0.14.1'}, 'research': {'version': '9.9.9'},
            'diagrams': {'version': '1.0.0'}}))
        self.assertEqual(self.keep._would_change(folder), 'its installer would put in its own '
                         'harness-diagrams 1.0.0, as none is installed here. Update the skills '
                         'first.')

    def test_a_change_its_installer_made_to_a_companion_is_said(self):
        self.brand.release('0.13.1', meddles=True)
        self.choose()
        self.keep.check(repair=False)
        self.install('main')
        brand = self.keep.report()['versions']['brand']
        self.assertEqual(brand['state'], 'changed')
        self.assertIn('Its installer also changed harness-slides at '
                      f"{self.codex / 'harness-slides'}, from 0.14.1 to 0.1.0. Presentation "
                      "Studio's pins are the ones to use: Update the skills puts back any that "
                      'is now older.', brand['says'])
        self.assertTrue(self.keep.report()['update']['offered'], 'Update puts it back')

    def test_what_its_installer_says_when_it_fails_is_shown(self):
        self.brand.release('0.13.1', refuses='Existing skill folders need migration.')
        self.choose()
        self.keep.check(repair=False)
        self.install('main')
        brand = self.keep.report()['versions']['brand']
        self.assertEqual((brand['state'], brand['says']), (
            'failed', 'The brand skill main was not installed: Setup could not finish: '
                      'Existing skill folders need migration.'))
        self.assertEqual(self.after, ['looked'])

    def test_main_moved_since_it_was_shown_is_not_installed(self):
        self.brand.release('0.13.1')
        self.choose()
        self.keep.check(repair=False)
        moved = self.brand.release('0.13.2')   # main moves on
        self.install('main')
        brand = self.keep.report()['versions']['brand']
        self.assertEqual(brand['state'], 'failed')
        self.assertIn(f'main now points at {moved[:12]}, not the', brand['says'])
        self.assertEqual(self.ran(), [])

    def test_a_chosen_brand_skill_is_kept_by_its_stable_address_through_an_update(self):
        self.brand.release('0.13.1')
        self.choose()
        self.keep.check(repair=False)
        self.install('main')
        installed = self.keep.check(repair=False)['brands'][0]['runtime']
        self.assertTrue(installed.endswith('current'), installed)
        self.brand.release('0.14.0')
        self.choose()
        settings.save(dataclasses.replace(settings.load(), brand_skill=installed))
        self.keep.check(repair=False)
        self.install('main')
        self.assertEqual(settings.load().brand_skill, installed)
        self.assertEqual(self.row()['installed'], '0.14.0')

    def test_closing_ends_an_install_in_hand(self):
        self.brand.release('0.13.1')
        self.choose()
        self.keep.check(repair=False)
        going = self.base / 'go'
        with mock.patch.dict(os.environ, {'BRAND_STAND_IN_HOLD': str(going)}):
            self.keep.install_brand(False, 'main')
            self.wait_for(going.with_name('go.running'))
            self.keep.close()
        brand = self.keep.report()['versions']['brand']
        self.assertEqual((brand['state'], brand['says']), ('failed', upkeep.BRAND_STOPPED))

    def wait_for(self, path: Path) -> None:
        """Until the stand-in says it is running: it then waits to be let go."""
        clock = time.monotonic() + 60
        while not path.exists():
            self.assertLess(time.monotonic(), clock, 'the installer never started')
            time.sleep(0.02)


if __name__ == '__main__':
    unittest.main()
