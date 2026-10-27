"""Whether Presentation Studio and the skills it uses are in place and current. The runner looks
when it starts and when the page checks this computer again.

What a caller needs to know
---------------------------
    keep = upkeep.Upkeep(after=engine.look_again)   # this computer's home and installation
    keep.start()                 # in the background: put back what is safe, then look online
    keep.again()                 # "Check again": the part on this computer now, online after
    keep.check(repair=False)     # the part on this computer only, changing nothing
    keep.report()                # what was found, for the page; never waits, starts nothing
    keep.update(working)         # bring the missing or older companions; refuses in a sentence
    keep.upgrade(working, '0.22.0')   # install that newer Presentation Studio beside this one
    keep.restart(working)        # after an upgrade: stop, so that `studio` starts the new one
    keep.dismiss(key)            # Home stops showing the versions until a newer one is out
    keep.install_brand(working, 'v1.4.0')   # the brand skill, from its repository
    keep.remember_brand(address, listed)    # what Settings' check of that repository found
    keep.close()                 # end an update in hand

- The companions are harness-slides and harness-research (COMPANIONS), the only skills
  Presentation Studio pins. Each is looked for, as the installer places it, in the skills
  folder of each assistant Presentation Studio was installed for (ASSISTANTS; without an
  installer's record, each assistant whose skills folder is here). It is `missing` when
  any of them lacks it, `older` when any copy is older than its pin, and `unread` when a
  copy's version cannot be read. Its version is the one its `package.json` says. Nothing
  is run to look at them. The brand skill is not a
  companion: it is the person's own, installed from the repository they name (see below).
- The pins are `../installer/companions.json`, as the installer writes them: {"schema": 1,
  "companions": {name: {"repository", "version", "commit", ...}}}. A missing file is no
  pins yet, which is no failure: each companion is then `ok` once it is found. A file that
  cannot be read is said as `problem`.
- Updating and upgrading ask the installer beside the runner, `../installer/install.py`,
  when it is there, as is putting back what it placed. Nothing here is a second
  implementation of what the installer does; with no installer, both are refused in a
  sentence and the rest is still looked at.
- What is put back without asking, and only where the installer recorded placing it:
  - the skill link of an assistant Presentation Studio was installed for, when it is missing,
    the copy it points at is whole and the assistant's skill folder is still there;
  - the `current` link, when it is missing or points nowhere;
  - the `studio` and `presentation` commands, when they are missing.

  Anything else in the way, such as a link pointing elsewhere or a real folder, is left
  alone and said. A companion's links belong to its own installer, so a missing one is not
  put back here: it is shown, with Update.
- `update` runs `install.py companions` from the same copy, as a command of its own under
  `companion.supervise`, with UPDATE_SECONDS to finish; `close` ends it.
  - It is refused while a deck on this computer is working, since a step in hand uses
    the companion it found when it started.
  - When it ends, `after` is called, so that the computer is looked at again.
- Online, at most once a day and only while the setting `look_for_updates` is on:
  - It runs `git ls-remote --tags` against Presentation Studio's repository, each
    companion's and the brand skill's when one is named, through `hub.run`, with
    LOOK_SECONDS to answer.
  - Only the tags are kept, in `updates.json` in the data folder, each newest with its
    commit. Whether one is newer is worked out each time it is shown. Nothing is
    downloaded or run.
- The newest Presentation Studio is its newest release tag once there is one, and until then
  the version on `main` when guidance was last fetched. Which companion versions that
  newest one is pinned to is read from its `installer/companions.json` in the guidance
  cache, which holds `main` with its history; a tag is read there only when its commit is
  on `main`. All of that is local. When it cannot be read, it is not guessed.
- `report()['versions']` has a row for Presentation Studio and one for each companion: what is
  installed, the newest, what this version is pinned to and the newest one's pin, a state
  (`current`, `update`, `missing` or `unknown`) and a sentence. A companion released
  beyond its lock is reported only. One that is missing, or older than its >= requirement
  (the lock itself without one), is offered at its exact lock; nothing installs during a
  check.
  Where a companion's tool is found, what it says of itself is said too.
- `upgrade` installs the newest Presentation Studio, the one the person confirmed:
  - the revision, a tag or `main`, is fetched by name into a temporary folder with the
    guidance's own isolated git, and only its plain files are written out;
  - its `VERSION` must be the one shown, and then its own installer runs `install
    --while-open`, which checks it, lays it beside this version and moves `current`;
  - all of it under `companion.supervise`, with UPGRADE_SECONDS to finish.
  This version's folder is left as it is, so the runner keeps running from it. It is
  refused from a checkout, which is upgraded with `git pull`, while a deck is working,
  while anything else is in hand, and when the newest is no longer the one confirmed.
- `restart` is offered once an upgrade is installed. It sets `restarting` to the command
  that opens Presentation Studio, the one the installer wrote, and calls `leave`; `studio
  serve` then stops and runs that command in its place. Without that command, the person
  is told to open Presentation Studio again.
- The report says which guidance a new deck is given: the revision the last guidance
  start resolved, or the copy installed with this version.
- The brand skill has a row of its own, BRAND, last. Its installed version is what the
  brand skill found in this home says of itself, the one chosen in Settings or else the
  first. Its newest is the newest release in the repository named in Settings, looked for
  with the rest, by `brand_source`'s order; `releases` keeps each release's commit, so a
  release chosen in Settings is shown too. With no repository named, a brand skill
  installed by hand is shown and nothing is offered. Its name is the one it gives itself.
- `install_brand` installs the release shown, the one the person confirmed, in the
  background; `versions['brand']` says what it would do and how it went. It is refused
  with no repository named, while a deck is working, while anything else is in hand,
  while a companion is missing or older than its pin, and when the release to install is
  no longer the one shown. Then:
  - the tag must still point at the commit shown, and the release is fetched as
    `brand_source.fetch` says;
  - when its installer would bring its own harness-slides, because the one here is older
    than it records or there is none, nothing is run and that is said;
  - its own installer runs (`brand_source.install`), with BRAND_SECONDS to finish;
  - the companions' links and versions are compared with before it ran, and any change is
    said; and this computer is looked at again, with `after`, so the brand skill is found.
  A brand skill chosen in Settings that was the one upgraded is moved to the new version.
- Ported from Training Studio's runner/upkeep.py. The companions are looked at here rather
  than by the installer, so the brand skill's install reads each assistant's companions
  itself (ASSISTANTS) and needs no installer beside the runner.
"""
from __future__ import annotations

import dataclasses  # noqa: F401  read by the shared parts
import importlib.util  # noqa: F401  read by the shared parts
import json
import os
import re
import shlex  # noqa: F401  read by the shared parts
import shutil
import sys  # noqa: F401  read by the shared parts
import tempfile
import threading  # noqa: F401  read by the shared parts
from datetime import datetime, timezone  # noqa: F401  read by the shared parts
from pathlib import Path, PurePosixPath  # noqa: F401  read by the shared parts

import runner  # noqa: F401  puts the core on the import path
import home  # noqa: F401  read by the shared parts
import hub  # noqa: F401  read by the shared parts
import sync_guidance
from studio_core.companions import minimum_version  # noqa: F401  read by the shared parts
from workspace import WorkspaceError

from runner import brand as brand_skill, brand_source, companion, settings  # noqa: F401  read by the shared parts
from runner import research as research_tool, slides as slides_tool

from studio_core import modules
from studio_core.shared_runner import upkeep as _shared
PRODUCT, ITEM, ITEMS = 'Presentation Studio', 'deck', 'decks'
SOURCE_VARIABLE = 'PRESENTATION_STUDIO_SOURCE'   # a source repository to upgrade from
modules.bind(globals(), _shared, _shared.NAMES)

INSTALLER = Path(__file__).resolve().parent.parent / 'installer' / 'install.py'
PINS = 'companions.json'  # beside the installer
COMPANIONS = ('harness-slides', 'harness-research')
NEEDS = {'harness-slides': 'no deck can be made without it',
         'harness-research': 'research cannot run without it'}
VERSION = re.compile(r'^\d+\.\d+\.\d+$')
UNPINNED = ('{path} does not say which companion skills to install, or says it in a way '
            'this version does not read. Get this version again.')
UPGRADE_SECONDS = 900     # for a newer Presentation Studio to be checked and installed
SELF = 'presentation-studio'
TOOLS = {'harness-research': (research_tool, 'Harness Research'),
         'harness-slides': (slides_tool, 'Harness Slides')}
COMMANDS = {'command': 'The command that opens Presentation Studio',
            'helper': "The command the skill runs its helper with"}
NO_INSTALLER = ('This copy of the runner has no installer beside it, so the skills cannot be '
                'updated from here. Run the installer again.')
WORKING = ('A deck on this computer is working now, and a step in hand keeps using the '
           'skill it started with. Pause it, or wait until it stops for you, then update.')
NOTHING = 'Every companion skill is already as new as this Presentation Studio was made with.'
STOPPED = 'The update was stopped when Presentation Studio closed. Nothing more was changed.'
UPGRADING = 'Presentation Studio is being upgraded already.'
UPGRADE_WORKING = ('A deck on this computer is working now. Pause it, or wait until it '
                   'stops for you, then upgrade.')
FROM_CHECKOUT = ('This Presentation Studio runs from a copy of its repository, so it is upgraded '
                 'there, with git pull, and not from here.')
NOTHING_NEWER = 'No newer Presentation Studio is known. Check this computer again to look.'
RESTART_WORKING = ('A deck on this computer is working now, and restarting would stop '
                   'its step. Pause it, or wait until it stops for you, then restart.')
UPGRADE_STOPPED = ('The upgrade was stopped when Presentation Studio closed. The version you '
                   'have is still the one in use.')
# The brand skill's installer installs for both assistants: where each keeps its skills.
ASSISTANTS = {'claude': ('Claude Code', ('.claude', 'skills')),
              'codex': ('Codex', ('.agents', 'skills'))}
NO_BRAND_REPOSITORY = ("Name the brand skill's repository in Settings first. Presentation "
                       'Studio installs it from there.')
BRAND_WORKING = ('A deck on this computer is working now, and a step in hand keeps using '
                 'the brand skill it started with. Pause it, or wait until it stops for you, '
                 'then install.')
NO_BRAND_SKILL = ('No brand skill is installed, so a deck stops where it first needs your '
                  'brand.')
BRAND_STOPPED = 'The install was stopped when Presentation Studio closed.'


def read_pins(path: Path) -> tuple[dict, str | None]:
    """The pinned companions, {name: pin}, and a sentence when the file cannot be read. A
    file that is not there is no pins yet: ({}, None)."""
    try:
        kept = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError):
        return {}, UNPINNED.format(path=path)
    pins = kept.get('companions') if isinstance(kept, dict) else None
    if not isinstance(kept, dict) or kept.get('schema') != 1 or not isinstance(pins, dict) \
            or not all(isinstance(pin, dict) and isinstance(pin.get('repository'), str)
                       and isinstance(pin.get('commit'), str)
                       and VERSION.match(str(pin.get('version'))) for pin in pins.values()):
        return {}, UNPINNED.format(path=path)
    return pins, None


def _package(folder: Path) -> dict:
    try:
        found = json.loads((folder / 'package.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


class Upkeep:
    """What the runner knows about the skills on this computer, and the one update in hand."""

    # --- in the background ---------------------------------------------------------------


    # --- on this computer ----------------------------------------------------------------

    def pins(self) -> tuple[dict, str | None]:
        """The companions this version is pinned to; see `read_pins`."""
        return read_pins(self.installer.parent / PINS)

    def _local(self, repair: bool) -> dict:
        install = self.module()
        pins, problem = self.pins()
        if install is None:
            companions = [self._companion(name, pins.get(name), self._assistants(None))
                          for name in COMPANIONS]
            return {**self._blank(problem or NO_INSTALLER), 'companions': companions,
                    'main': self._main_version(), 'newest': self._newest(None),
                    'tools': self._tools(), 'brands': self._brands()}
        try:
            state = install.read_state(self.root)
        except install.InstallError as refusal:
            state, problem = None, problem or str(refusal)
        repaired = self._current(install, state) if state and repair else []
        chosen = list(state.get('links', {})) if state else install.found_harnesses(self.home)
        companions = [self._companion(name, pins.get(name), self._assistants(state))
                      for name in COMPANIONS]
        links = [self._link(install, state, harness, repair) for harness in chosen]
        repaired += [link['says'] for link in links if link['state'] == 'repaired']
        if state and repair:
            repaired += self._commands(install, state)
        return {'at': _now(), 'installer': True, 'mode': (state or {}).get('mode'),
                'links': links, 'repaired': repaired, 'problem': problem,
                'companions': companions,
                'main': self._main_version(), 'newest': self._newest(install),
                'tools': self._tools(), 'target': self._target(state),
                'brands': self._brands()}

    def _assistants(self, state: dict | None) -> list[str]:
        """The assistants whose companions are looked at: those Presentation Studio was
        installed for, as the installer recorded, else each whose skills folder is here."""
        if state and state.get('links'):
            return [name for name in ASSISTANTS if name in state['links']]
        return [name for name, (_, parts) in ASSISTANTS.items()
                if self.home.joinpath(*parts).is_dir()]

    def _companion(self, name: str, pin: dict | None, chosen: list[str]) -> dict:
        """One companion, for each assistant Presentation Studio is installed for, against
        its pin when there is one. Only the copy in each assistant's skills folder is looked
        at: that is the one its installer places."""
        found = self._assistant_versions(name, chosen)
        wanted, need = (pin or {}).get('version'), NEEDS[name]
        floor = _floor(pin) if pin else None
        short = [assistant for assistant, version in found.items()
                 if version is None or (floor and version
                                        and _version(version) < _version(floor))]
        unread = [ASSISTANTS[assistant][0] for assistant, version in found.items()
                  if version == '']
        who = _who([ASSISTANTS[assistant][0] for assistant in short])
        made = f' This Presentation Studio was made with {wanted}.' if wanted else ''
        if short and all(found[assistant] is None for assistant in short):
            state, says = 'missing', f'{name} is not installed for {who}, and {need}.{made}'
        elif short:
            state, says = 'older', (f'{name} for {who} is older than the {wanted} this '
                                    'Presentation Studio was made with.')
        elif unread:
            state, says = 'unread', (f'{name} is there for {_who(unread)}, but not as its '
                                     'own installer leaves it, so its version could not be '
                                     'read. It was left alone.')
        elif not chosen:
            state, says = 'missing', f'{name} cannot be looked for: no assistant was found.'
        else:
            having = sorted({version for version in found.values() if version}, key=_version)
            state = 'ok'
            says = f"{name} {', '.join(having)}, for " + _who(
                [ASSISTANTS[assistant][0] for assistant in found]) + '.' + (
                '' if wanted else ' No version is pinned for it yet.')
        return {'name': name, 'wanted': wanted, 'state': state, 'says': says,
                'found': {ASSISTANTS[assistant][0]: version
                          for assistant, version in found.items()},
                'repository': pin['repository'].removesuffix('.git') if pin else None,
                'commit': pin['commit'][:12] if pin else None,
                'note': (pin or {}).get('note'),
                **({'requirement': pin['requirement'], 'locked': pin['version']} if pin and pin.get('requirement') else {})}

    @staticmethod
    def _pins_at(install, commit: str | None) -> dict | None:
        """The companion versions Presentation Studio was pinned to at a commit, {name:
        version}, read from the guidance cache when that commit is on the source branch
        there. None when it cannot be read here: nothing is fetched for it."""
        cache = sync_guidance.guidance_root() / 'cache.git'
        if not isinstance(commit, str) \
                or not sync_guidance.COMMIT.fullmatch(commit) or not sync_guidance.ours(cache) \
                or not sync_guidance.on_main(commit, cache):
            return None
        try:
            text = sync_guidance.git('cat-file', 'blob', f"{commit}:{'pins/companions.json' if sync_guidance.source().get('manifest', '').startswith('studios/') else 'installer/companions.json'}",
                                     repo=cache)
            with tempfile.TemporaryDirectory() as holder:
                kept = Path(holder) / PINS
                kept.write_bytes(text)
                pins, problem = read_pins(kept)
        except (sync_guidance.SyncError, OSError):
            return None
        return None if problem else {name: pin['version'] for name, pin in pins.items()}

    # --- online --------------------------------------------------------------------------

    def repositories(self) -> dict:
        """Where each release is looked for: Presentation Studio's repository and each
        companion's, as its pin names it."""
        found = {SELF: sync_guidance.source()['repository']}
        found.update({name: pin['repository'] for name, pin in self.pins()[0].items()})
        brand, _ = settings.brand_source()
        if brand:
            found[BRAND] = brand
        return found

    # --- the update ----------------------------------------------------------------------

    def update(self, working: bool) -> dict:
        """Bring each companion that is missing or older than its pin, through the
        installer's own checked install, in the background. Refused, in a sentence, while a
        deck is working, while an update is in hand, and when there is nothing to do."""
        with self._lock:
            found = self._found
            self._refuse_busy()
        if found is None:
            found = self.check(repair=False)
        if not found['installer']:
            raise WorkspaceError(NO_INSTALLER)
        names = [entry['name'] for entry in found['companions']
                 if entry['state'] in ('missing', 'older') and entry['wanted']]
        if not names:
            raise WorkspaceError(NOTHING)
        if working:
            raise WorkspaceError(WORKING)
        with self._lock:
            self._refuse_busy()
            self._update = {'state': 'running', 'since': _now(), 'names': names,
                            'says': f'Bringing {_who(names)}. This can take a few minutes.'}
        self._background(lambda: self._bring(names), 'updating the skills')
        return self.report()

    # --- the upgrade ---------------------------------------------------------------------


    def _install(self, newest: dict, target: str | None) -> None:
        """Fetch the newest revision and run its own installer, beside this version."""
        version, state, says, commit = newest['version'], 'failed', None, None
        holder = Path(tempfile.mkdtemp(prefix='presentation-studio-upgrade-'))
        try:
            repository = str(sync_guidance.source()['repository'])
            tree, commit = fetch_tree(repository, newest['ref'], holder)
            found = (tree / 'VERSION').read_text(encoding='utf-8').strip() \
                if (tree / 'VERSION').is_file() else None
            if found != version:
                raise WorkspaceError(f"{repository} has version {found or 'unknown'} at "
                                     f"{newest['ref']}")
            state, says = self._run_installer(tree, version, target)
        except (sync_guidance.SyncError, WorkspaceError, OSError) as refusal:
            says = f'Presentation Studio {version} was not installed: {str(refusal).rstrip(".")}.'
        except Exception as failure:  # said on the page; the runner keeps serving
            says = f'The upgrade could not be run ({type(failure).__name__}: {failure}).'
        finally:
            shutil.rmtree(holder, ignore_errors=True)
        if self._stop.is_set() and state != 'restart':
            says = UPGRADE_STOPPED
        with self._lock:
            self._upgrade = {**(self._upgrade or {}), 'state': state, 'says': says,
                             'ended': _now(), 'commit': commit and commit[:12]}

    # --- the brand skill ------------------------------------------------------------------


    def _brand_target(self, online: dict) -> tuple[str | None, dict | None]:
        """The brand skill's repository, and the release to install from it as last known:
        the one chosen in Settings, else the newest. {'tag', 'version', 'commit'} or None."""
        repository, release = settings.brand_source()
        if not repository or online.get('repository') != repository:
            return repository, None
        known = {tag: {'tag': tag, 'version': tag.removeprefix('v'), 'commit': commit}
                 for tag, commit in (online.get('releases') or {}).items()
                 if isinstance(commit, str)}
        if release:
            return repository, known.get(release)
        return repository, brand_source.newest(known)

    def install_brand(self, working: bool, release: str) -> dict:
        """Install `release` of the brand skill from its repository, with its own installer,
        in the background. Refused, in a sentence, with no repository named, while a deck
        is working, while anything else is in hand, while a companion waits for Update, and
        when `release` is not the one known to install."""
        with self._lock:
            found = self._found
            self._refuse_busy()
        if found is None:
            found = self.check(repair=False)
        repository, target = self._brand_target(self._saved().get('found', {}).get(BRAND)
                                                or {})
        if not repository:
            raise WorkspaceError(NO_BRAND_REPOSITORY)
        if target is None:
            raise WorkspaceError(f'Which releases {repository} has is not known here yet. Save '
                                 'the repository in Settings again to look.')
        if target['tag'] != str(release):
            raise WorkspaceError(f"The release to install is now {target['tag']}, not "
                                 f'{release}. Look at it again before you install.')
        if working:
            raise WorkspaceError(BRAND_WORKING)
        waiting = [entry['name'] for entry in found['companions']
                   if entry['state'] in ('missing', 'older')]
        if waiting:
            raise WorkspaceError(f'Update the companion skills first ({_who(waiting)}). The '
                                 "brand skill's installer brings its own harness-slides when "
                                 "it finds none it can use, and Presentation Studio's are the "
                                 'ones to keep.')
        before = self._the_brand(found.get('brands') or [])
        with self._lock:
            self._refuse_busy()
            self._brand = {'state': 'running', 'since': _now(), 'release': target['tag'],
                           'says': f"Fetching {target['tag']} from {repository} and running "
                                   'its own installer. This can take a few minutes.'}
        self._background(lambda: self._bring_brand(repository, target, before),
                         'installing the brand skill')
        return self.report()

    def _bring_brand(self, repository: str, target: dict, before: dict | None) -> None:
        """Fetch the release, check it leaves the companions alone, run its own installer,
        then look again."""
        tag, commit, version = target['tag'], target['commit'], target['version']
        holder = Path(tempfile.mkdtemp(prefix='presentation-studio-brand-'))
        state, says = 'failed', None
        try:
            now = brand_source.releases(repository, holder).get(tag)
            if now is None or now['commit'] != commit:
                raise WorkspaceError(f"{tag} now points at "
                                     f"{now['commit'][:12] if now else 'nothing'}, not the "
                                     f'{commit[:12]} you were shown. Look at it again before '
                                     'you install')
            folder, _ = brand_source.fetch(repository, tag, commit, holder, self._stop)
            changes = self._would_change(folder)
            if changes:
                raise WorkspaceError(f'{changes} Nothing was run')
            kept = self._companion_links()
            code, late, said = brand_source.install(folder, self.home, BRAND_SECONDS,
                                                    self._stop)
            moved = self._moved(kept, self._companion_links())
            if late:
                says = (f'The brand skill {tag} was not installed: its installer did not '
                        f'finish in {BRAND_SECONDS // 60} minutes, so it was ended.')
            elif code != 0:
                says = f'The brand skill {tag} was not installed: {said}.'
            else:
                state, says = self._brand_installed(repository, target, before)
            if moved:
                state = 'changed'
                says = (f"{says} Its installer also changed {'; '.join(moved)}. Presentation "
                        "Studio's pins are the ones to use: Update the skills puts back any "
                        'that is now older.')
        except companion.Stopped:
            says = BRAND_STOPPED
        except (WorkspaceError, OSError) as refusal:
            says = f'The brand skill {tag} was not installed: {str(refusal).rstrip(".")}.'
        except Exception as failure:  # said on the page; the runner keeps serving
            says = (f'The brand skill could not be installed ({type(failure).__name__}: '
                    f'{failure}).')
        finally:
            shutil.rmtree(holder, ignore_errors=True)
        with self._lock:
            self._brand = {**(self._brand or {}), 'state': state, 'says': says,
                           'ended': _now(), 'commit': commit[:12], 'version': version}
        self.check(repair=False)
        if self.after is not None:
            try:
                self.after()
            except Exception:  # a look that fails is the next look's to say
                pass

    def _assistant_versions(self, name: str, chosen=None) -> dict:
        """The version of a companion each assistant (each of `chosen`, else both) has in
        its skills folder: None when it has none, '' when one is there whose version cannot
        be read."""
        found = {}
        for assistant in chosen if chosen is not None else ASSISTANTS:
            parts = ASSISTANTS[assistant][1]
            skill = self.home.joinpath(*parts) / name
            if not os.path.lexists(skill):
                found[assistant] = None
                continue
            version = _package(skill).get('version')
            found[assistant] = version if isinstance(version, str) \
                and VERSION.match(version) else ''
        return found

    def _would_change(self, folder: Path) -> str | None:
        """What the release's installer would change of the companions, said in a sentence;
        None when it would leave them alone. It brings its own copy of each it records,
        unless every one installed here is at least that version and one is there."""
        for name, wanted in brand_source.bootstraps(folder).items():
            if name in brand_source.SKIPPED:
                continue
            found = self._assistant_versions(name)
            having = [version for version in found.values() if version]
            short = [ASSISTANTS[assistant][0] for assistant, version in found.items()
                     if version == '' or (version and _version(version) < _version(wanted))]
            if not having:
                return (f"its installer would put in its own {name} {wanted}, as none is "
                        'installed here. Update the skills first.')
            if short:
                return (f"its installer would replace {name} {', '.join(sorted(set(having)))} "
                        f"with its own {wanted} for {_who(short)}, in place of the one "
                        'Presentation Studio is made with. Choose an older release in '
                        'Settings, or upgrade Presentation Studio first.')
        return None

    def _companion_links(self) -> dict:
        """Where each companion is in this home, for each assistant and in its installer's
        own folder: {path: (its name, where it leads, its version)}."""
        found = {}
        for name, (module, title) in TOOLS.items():
            places = [self.home.joinpath(*parts) / name for _, parts in ASSISTANTS.values()]
            places += [place for place in companion.locations(module.VARIABLE, name, title,
                                                               home=self.home)
                       if place.name == 'current']
            for place in places:
                if not os.path.lexists(place):
                    found[str(place)] = (name, None, None)
                    continue
                version = _package(place).get('version')
                found[str(place)] = (name, os.path.realpath(place),
                                     version if isinstance(version, str) else None)
        return found

    def _brand_row(self, found: dict | None, online: dict) -> dict:
        """The brand skill's row, with what an install would do. It names the brand skill
        as the brand skill names itself."""
        repository, target = self._brand_target(online)
        skill = self._the_brand((found or {}).get('brands') or [])
        installed = skill and skill.get('version')
        known = online if online.get('repository') == repository else {}
        latest = known.get('latest') if repository else None
        row = {'name': BRAND, 'kind': 'brand', 'installed': installed, 'newest': latest,
               'pinned': None, 'next': None, 'target': None, 'beyond': None,
               'reports': (f"The brand skill in use is {skill['name']}, at {skill['runtime']}."
                           if skill else None),
               'known_at': known.get('known_at'), 'repository': repository,
               'release': target and target['tag'],
               'commit': target and target['commit'][:12]}
        named = skill['name'] if skill else 'The brand skill'
        if not repository:
            first = (NO_BRAND_SKILL if not skill
                     else f'{named} {installed} is installed.' if installed
                     else f'{named} is installed.')
            return {**row, 'state': 'unknown', 'says': f'{first} Name its repository in '
                    'Settings to install and upgrade it from here.'}
        if target is None:
            _, release = settings.brand_source()
            return {**row, 'state': 'unknown', 'says': (
                f'{repository} has no release {release}, as last looked.' if release
                and known.get('releases') is not None else
                f'Which releases {repository} has is not known yet. It is looked for once a '
                'day, and when the repository is saved in Settings.')}
        wanted = target['version']
        if skill is None:
            return {**row, 'state': 'missing', 'target': wanted, 'says': (
                f"{NO_BRAND_SKILL} {target['tag']} can be "
                f'installed from {repository}.')}
        if installed is None:
            return {**row, 'state': 'unknown', 'target': wanted, 'says': (
                f"{named} does not say which version it is. {target['tag']} can be installed "
                f'from {repository}.')}
        if brand_source.order(wanted) > brand_source.order(installed):
            return {**row, 'state': 'update', 'target': wanted, 'says': (
                f'{named} {wanted} is out, and this computer has {installed}.')}
        _, chosen = settings.brand_source()
        if wanted != installed and chosen:
            return {**row, 'state': 'current', 'target': wanted, 'says': (
                f'{named} {installed} is installed, newer than {chosen}, the release chosen '
                'in Settings. That one can be installed from here.')}
        return {**row, 'state': 'current', 'says': (
            f'{named} {installed} is the release chosen in Settings.' if chosen else
            f'{named} {installed} is the newest release.')}

    @staticmethod
    def _brand_offer(row: dict, busy: bool, brand: dict | None) -> dict:
        """What installing the brand skill would do, for the page's sheet."""
        return {'offered': bool(row['target'] and row['repository'] and not busy),
                'action': 'Upgrade' if row['installed'] else 'Install',
                'repository': row['repository'], 'release': row['release'],
                'version': row['target'], 'commit': row['commit'],
                'installed': row['installed'],
                'state': brand and brand['state'], 'since': brand and brand['since'],
                'says': brand and brand['says']}

    # --- what is said ----------------------------------------------------------------------


    @staticmethod
    def _companion_row(entry: dict, online: dict, newest: dict | None, pins: dict | None,
                       reports: str | None) -> dict:
        """One companion's row. `newest` is the newer Presentation Studio, when there is one,
        and `pins` what it is pinned to, when that could be read."""
        name, pinned = entry['name'], entry.get('locked', entry['wanted'])
        having = sorted((version for version in entry['found'].values() if version),
                        key=_version)
        installed = having[0] if having else None
        following = (pins or {}).get(name)
        latest = online.get('latest')
        line = max((version for version in (pinned, following) if version), key=_version,
                   default=None)
        row = {'name': name, 'installed': installed, 'newest': latest, 'pinned': pinned,
               'next': following, 'target': None, 'reports': reports,
               'known_at': online.get('known_at'),
               'beyond': (f'{name} {latest} is out, newer than Presentation Studio supports yet. '
                          'It is offered once a Presentation Studio made with it is out.')
               if latest and line and _version(latest) > _version(line) else None}
        if entry['state'] in ('missing', 'older'):
            return {**row, 'state': 'missing' if entry['state'] == 'missing' else 'update',
                    'target': entry['wanted'], 'says': entry['says']}
        if pinned is None and installed is not None:
            return {**row, 'state': 'current', 'says': entry['says']}
        if entry['state'] == 'unread' or installed is None:
            return {**row, 'state': 'unknown', 'says': entry['says']}
        if following and _version(installed) < _version(following):
            return {**row, 'state': 'update', 'target': following, 'says': (
                f"{name} {following} comes with Presentation Studio {newest['version']}, which "
                f'is made with it. This computer has {installed}.')}
        if newest and pins is None:
            return {**row, 'state': 'current', 'says': (
                f'{name} {installed} is what this Presentation Studio is made with. Which version '
                f"Presentation Studio {newest['version']} is made with is not known here yet.")}
        return {**row, 'state': 'current', 'says': (
            f'{name} {installed} is what this Presentation Studio is made with.'
            if installed == pinned else
            f'{name} {installed}, newer than the {pinned} this Presentation Studio is made with.')}

    def report(self) -> dict:
        """Everything found, in the shape the page reads. Starts nothing and never waits."""
        with self._lock:
            found = self._found
            update = dict(self._update) if self._update else None
            upgrade = dict(self._upgrade) if self._upgrade else None
            brand = dict(self._brand) if self._brand else None
        wanted = [entry for entry in (found or {}).get('companions', [])
                  if entry['state'] in ('missing', 'older') and entry['wanted']]
        busy = bool(update and update['state'] == 'running') \
            or bool(upgrade and upgrade['state'] in ('running', 'restart', 'restarting')) \
            or bool(brand and brand['state'] == 'running')
        return {'checking': found is None, 'checked_at': found and found['at'],
                'version': self.version(),
                'mode': found and found['mode'],
                'problem': found and found['problem'],
                'links': list((found or {}).get('links', [])),
                'repaired': list((found or {}).get('repaired', [])),
                'companions': list((found or {}).get('companions', [])),
                # Marketing Studio installs and updates a suite's companions too.
                'update': {'offered': bool(wanted and found['installer'] and not busy
                                           and not self.suite_managed()),
                           'state': update and update['state'],
                           'since': update and update['since'],
                           'says': update and update['says']},
                'guidance': self.guidance(), 'releases': self.releases(),
                'versions': self.versions(found, upgrade, busy, brand)}


modules.bind(globals(), _shared, methods={'Upkeep': _shared.METHODS['Upkeep']})
