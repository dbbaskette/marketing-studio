"""How often the companions are asked what they are (#513), counted, never timed: the slides
tool's version and what it can do, a brand skill's brands, version and usage, and the skill
folders, each asked or scanned once for a look; a quick question run as one process with no
watcher, while a job that can be stopped keeps its watcher; and the upkeep's background
threads, kept to those still running with one look at a time. Every command line here is a
stand-in, in a home of its own; nothing real is run.
"""
import collections
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401  puts the runner on the import path
from runner_support import LEAVES, still_running, written

from runner import brand as brand_skill, companion, engine as engines, slides, upkeep
from runner import research as research_tool
from studio_core import brand_skills
from workspace import WorkspaceError

LISTED = [{'brand': 'acme', 'name': 'Acme Works', 'variants': ['light']}]


def made(folder: Path, name: str, package: dict | None = None) -> Path:
    """A companion's folder: its entry, its command line and its package.json."""
    (folder / 'scripts').mkdir(parents=True)
    (folder / 'SKILL.md').write_text(f'---\nname: {name}\n---\n')
    (folder / 'scripts' / f'{name}.mjs').write_text('// lists its brands\n')
    (folder / 'package.json').write_text(json.dumps(package or {'name': name}))
    return folder


def later(path: Path) -> None:
    """Change a file's modification time and size, as an update rewriting it does."""
    path.write_text(path.read_text() + '// updated\n')
    stamp = path.stat().st_mtime_ns + 5_000_000_000
    os.utime(path, ns=(stamp, stamp))


class Commands:
    """Every companion's command line, answering as each does, with what was asked of it:
    (script, arguments, 'ask' for a quick question or 'run' for a job)."""

    def __init__(self, version=slides.MINIMUM,
                 listed=('google-preview-pool', *slides.NEEDED, *slides.DESIGN_NEEDED)):
        self.asked, self.version, self.listed = [], version, list(listed)

    def by(self, how):
        def answer(command, cwd=None):
            return self(command, how)
        return answer

    def __call__(self, command, how):
        script, args = Path(command[1]).name, command[2:]
        self.asked.append((script, tuple(args), how))
        if script == 'harness-slides.mjs':
            if args == ['--version']:
                return 0, f'Harness Slides {self.version}\n', ''
            if args == ['version']:
                return 0, json.dumps({'capabilities': self.listed}), ''
            if args == ['drive', 'check']:
                return 0, json.dumps({'account': 'person@example.com'}), ''
            if args[:2] == ['outline', 'contract']:
                return 0, 'An outline holds slides.\n', ''
        if script == 'harness-research.mjs' and args == ['--version']:
            return 0, 'Harness Research 1.5.1\n', ''
        if script == 'acme-brand.mjs':
            if args == ['brands', '--json']:
                return 0, json.dumps(LISTED), ''
            if args == ['version']:
                return 0, 'Acme Brand 1.2.3\n', ''
            if args[0] == 'doctor':
                return 0, json.dumps({'ok': True, 'capabilities': []}), ''
            if args == ['contract']:
                return 0, 'Usage: contract export|check\n', ''
            if args == ['look']:
                return 0, 'Usage: look samples|choose\n', ''
            if args == ['guidance']:
                return 0, 'Usage: guidance start|resume --brand\n', ''
        return 1, '', 'Unknown command/action; run --help\n'

    def times(self) -> collections.Counter:
        return collections.Counter((script, args) for script, args, _ in self.asked)


class Home(unittest.TestCase):
    """A home of its own, with the slides tool, Harness Research and one brand skill, and
    every command line replaced by `self.tool`."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()
        self.home = self.base / 'home'
        self.runtime = made(self.base / 'harness-slides', 'harness-slides',
                            {'name': 'harness-slides', 'version': slides.MINIMUM})
        self.research = made(self.home / '.claude' / 'skills' / 'harness-research',
                             'harness-research', {'name': 'harness-research',
                                                  'version': '1.5.1'})
        self.skill = made(self.home / '.claude' / 'skills' / 'acme-brand', 'acme-brand')
        self.tool = Commands()
        patches = [
            mock.patch.dict(os.environ, {'TRAINING_STUDIO_DATA': str(self.base / 'data'),
                                         'STUDIOS_CONFIG': str(self.base / 'config.json'),
                                         slides.VARIABLE: str(self.runtime)}),
            mock.patch.object(Path, 'home', return_value=self.home),
            mock.patch('shutil.which', lambda name, *rest, **named: f'/usr/bin/{name}'),
            mock.patch.object(slides, 'run_command', self.tool.by('run')),
            mock.patch.object(slides, 'ask_command', self.tool.by('ask')),
            mock.patch.object(brand_skill, 'run_command', self.tool.by('run')),
            mock.patch.object(brand_skill, 'ask_command', self.tool.by('ask')),
            mock.patch.object(research_tool, 'run_command', self.tool.by('run'))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        for name in (brand_skill.VARIABLE, research_tool.VARIABLE):
            os.environ.pop(name, None)


class SlidesProbeTests(Home):
    def test_nothing_is_run_when_it_is_made(self):
        slides.Slides()
        self.assertEqual(self.tool.asked, [])

    def test_its_version_and_what_it_can_do_are_asked_once_each_as_quick_questions(self):
        tool = slides.Slides()
        for _ in range(3):
            self.assertEqual(tool.version(), slides.MINIMUM)
            self.assertTrue(tool.has('google-preview-pool'))
        tool.outline_contract(Path('/d/brand.json'))
        self.assertEqual(self.tool.asked, [
            ('harness-slides.mjs', ('--version',), 'ask'),
            ('harness-slides.mjs', ('version',), 'ask'),
            ('harness-slides.mjs', ('outline', 'contract', '--brand', '/d/brand.json'), 'run')])

    def test_an_updated_tool_is_asked_again_without_a_restart(self):
        tool = slides.Slides()
        tool.version(), tool.capabilities()
        self.tool.version, self.tool.listed = '9.9.9', ['assets']
        later(self.runtime / 'package.json')
        self.assertEqual((tool.version(), tool.capabilities()), ('9.9.9', frozenset({'assets'})))
        later(self.runtime / slides.SCRIPT)
        tool.version(), tool.capabilities()
        self.assertEqual(self.tool.times()[('harness-slides.mjs', ('--version',))], 3)
        self.assertEqual(self.tool.times()[('harness-slides.mjs', ('version',))], 3)

    def test_a_tool_replaced_behind_its_link_is_asked_again(self):
        current = self.base / 'current'
        current.symlink_to(self.runtime)
        tool = slides.Slides(runtime=current)
        tool.version()
        newer = made(self.base / 'newer', 'harness-slides')
        current.unlink()
        current.symlink_to(newer)
        tool.version()
        self.assertEqual(self.tool.times()[('harness-slides.mjs', ('--version',))], 2)


class BrandProbeTests(Home):
    def test_a_brand_found_by_a_look_is_asked_nothing_more(self):
        listed = brand_skill.found()
        self.assertEqual([entry['runtime'] for entry in listed], [str(self.skill)])
        before = len(self.tool.asked)
        chosen = brand_skill.Brand(found=listed)
        named = brand_skill.Brand(runtime=self.skill, found=listed)
        for skill in (chosen, named):
            self.assertEqual((skill.name, skill.version, skill.runtime),
                             ('Acme Brand', '1.2.3', self.skill))
            self.assertEqual(skill.brands(), LISTED)
        self.assertEqual(len(self.tool.asked), before, 'nothing is asked again')
        self.assertEqual(chosen.brands(), LISTED)
        self.assertEqual(self.tool.asked[-1], ('acme-brand.mjs', ('brands', '--json'), 'ask'),
                         'after the first, the skill is asked')
        with self.assertRaisesRegex(WorkspaceError, 'No brand skill was found'):
            brand_skill.Brand(found=[])

    def test_a_skill_the_scan_knew_only_by_its_links_name_is_still_chosen(self):
        kit = self.base / 'Kit'
        made(kit / 'versions' / '1.0', 'acme-brand', {'version': '1.0.0'})   # no name
        (kit / 'current').symlink_to(Path('versions') / '1.0')
        self.skill.rename(self.base / 'elsewhere')
        self.skill.symlink_to(kit / 'current')
        listed = brand_skill.found()
        self.assertEqual([entry['name'] for entry in listed], ['Acme Brand'])
        chosen = brand_skill.Brand(found=listed)
        self.assertEqual((chosen.name, chosen.script.name), ('Acme Brand', 'acme-brand.mjs'))

    def test_the_scan_asks_quick_questions_only(self):
        brand_skill.found()
        self.assertEqual({how for _, _, how in self.tool.asked}, {'ask'})

    def test_what_its_usage_says_is_asked_once_for_each_copy(self):
        skill = brand_skill.Brand(runtime=self.skill)
        for _ in range(3):
            self.assertTrue(skill.contracts())
            self.assertTrue(skill.looks())
            self.assertEqual(skill.guides(), 'brand')
        times = self.tool.times()
        self.assertEqual([times[('acme-brand.mjs', (question,))]
                          for question in ('contract', 'look', 'guidance')], [1, 1, 1])
        later(self.skill / 'scripts' / 'acme-brand.mjs')
        skill.contracts(), skill.looks(), skill.guides()
        times = self.tool.times()
        self.assertEqual([times[('acme-brand.mjs', (question,))]
                          for question in ('contract', 'look', 'guidance')], [2, 2, 2],
                         'an updated skill is asked again')
        self.assertEqual({how for _, args, how in self.tool.asked
                          if args in (('contract',), ('look',), ('guidance',))}, {'ask'})


class LookTests(Home):
    def engine(self):
        made = engines.Engine.__new__(engines.Engine)
        made._looked, made._looking = None, threading.Lock()
        made.slides, made.brand = slides.Slides, brand_skill.Brand
        return made

    def test_one_look_asks_each_question_once_and_scans_the_skills_once(self):
        scans = []
        real = brand_skills.installed
        with mock.patch.object(brand_skills, 'installed',
                               lambda *given: scans.append(1) or real(*given)):
            found = self.engine()._look(fresh=True)
        self.assertIsNone(found['tool'])
        self.assertEqual(found['version'], slides.MINIMUM)
        self.assertTrue(found['pool'])
        self.assertEqual((found['brand']['found'], found['brand']['name']),
                         (True, 'Acme Brand'))
        self.assertEqual(found['brand']['brands'], [{'brand': 'acme', 'name': 'Acme Works',
                                                     'variants': ['light']}])
        self.assertEqual((found['needs'], found['design_needs'], found['contracts']),
                         ([], [], True))
        self.assertEqual([entry['runtime'] for entry in found['skills']], [str(self.skill)])
        self.assertEqual(len(scans), 1, 'the skill folders are scanned once')
        times = self.tool.times()
        self.assertEqual(max(times.values()), 1, times)
        for asked in (('harness-slides.mjs', ('--version',)),
                      ('harness-slides.mjs', ('version',)),
                      ('acme-brand.mjs', ('brands', '--json')),
                      ('acme-brand.mjs', ('version',))):
            self.assertEqual(times[asked], 1, asked)
        self.assertEqual({how for _, args, how in self.tool.asked
                          if args in (('--version',), ('version',), ('brands', '--json'))},
                         {'ask'}, 'each a quick question, with no watcher')

    def test_a_tool_too_old_is_still_said_as_the_slides_tools_problem(self):
        self.tool.version = '0.9.0'
        found = self.engine()._look(fresh=True)
        self.assertIn('harness-slides 0.9.0 is installed, and a deck needs', found['tool'])
        self.assertEqual(found['version'], '0.9.0')
        self.assertEqual(self.tool.times()[('harness-slides.mjs', ('--version',))], 1)

    def test_a_brand_named_in_settings_is_taken_from_the_scan(self):
        from runner import settings
        with mock.patch.object(settings, 'load', return_value=SimpleNamespace(
                brand_skill=str(self.skill), previews='local')):
            found = self.engine()._look(fresh=True)
        self.assertEqual(found['brand']['name'], 'Acme Brand')
        self.assertEqual(self.tool.times()[('acme-brand.mjs', ('version',))], 1)
        self.assertEqual(self.tool.times()[('acme-brand.mjs', ('brands', '--json'))], 1)


class UpkeepToolsTests(Home):
    def test_each_companion_is_asked_each_question_once(self):
        keep = upkeep.Upkeep(home_dir=self.home, root=self.base / 'root',
                             installer=self.base / 'installer' / 'install.py')
        said = keep._tools()
        self.assertTrue(said['harness-slides'].startswith(
            f'The tool in use says it is {slides.MINIMUM}, and that it can do: '))
        self.assertEqual(said['harness-research'], 'The tool in use says it is 1.5.1.')
        times = self.tool.times()
        self.assertEqual(times[('harness-slides.mjs', ('--version',))], 1)
        self.assertEqual(times[('harness-slides.mjs', ('version',))], 1)


class QuickQuestionTests(unittest.TestCase):
    """A quick question is one process with no watcher; a job keeps its watcher."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()
        self.pids = self.base / 'pids'
        self.started = []
        real = subprocess.Popen

        def counted(command, *given, **named):
            self.started.append(list(command))
            return real(command, *given, **named)

        patch = mock.patch.object(companion.subprocess, 'Popen', counted)
        patch.start()
        self.addCleanup(patch.stop)

    def watchers(self) -> list:
        return [command for command in self.started
                if command[:4] == [sys.executable, '-I', '-S', '-c']]

    def test_a_quick_question_starts_one_process_and_no_watcher(self):
        self.assertEqual(companion.ask([sys.executable, '-c', 'print("1.2.3")'], None,
                                       'The tool'), (0, '1.2.3\n', ''))
        self.assertEqual(len(self.started), 1)
        self.assertEqual(self.watchers(), [])

    def test_a_quick_question_that_overruns_is_ended_with_everything_it_started(self):
        for seconds in (3, 60):   # a busy computer may not have started it in 3 seconds
            with self.assertRaisesRegex(WorkspaceError, 'did not answer in'):
                companion.ask(['sh', '-c', LEAVES, 'sh', str(self.pids)], None, 'The tool',
                              seconds=seconds)
            if self.pids.exists():
                break
        self.assertEqual(self.watchers(), [])
        self.assertEqual(still_running(written(self.pids)), [])

    def test_a_job_that_can_be_stopped_keeps_its_watcher_and_is_stopped_with_its_group(self):
        stop = threading.Event()

        def stops():
            written(self.pids, seconds=60)
            stop.set()

        stopping = threading.Thread(target=stops)
        stopping.start()
        self.addCleanup(stop.set)
        with companion.stopping(stop), self.assertRaises(companion.Stopped):
            companion.run_command(['sh', '-c', LEAVES, 'sh', str(self.pids)], None, 120,
                                  'The tool')
        stopping.join()
        self.assertEqual(len(self.watchers()), 1, 'the job is watched')
        self.assertEqual(still_running(written(self.pids)), [])

    def test_the_slides_tools_quick_questions_are_asked_this_way(self):
        asked = []
        with mock.patch.object(companion, 'run_command',
                               lambda *given, **named: asked.append(named) or (0, '', '')):
            slides.ask_command(['node', 'script', '--version'])
            brand_skill.ask_command(['node', 'script', 'brands', '--json'])
            slides.run_command(['node', 'script', 'compose', 'render'])
            brand_skill.run_command(['node', 'script', 'contract', 'export'])
        self.assertEqual([named.get('watch', True) for named in asked],
                         [False, False, True, True])


class UpkeepThreadTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()
        patch = mock.patch.dict(os.environ, {
            'TRAINING_STUDIO_DATA': str(self.base / 'data'),
            'STUDIOS_CONFIG': str(self.base / 'config.json')})
        patch.start()
        self.addCleanup(patch.stop)
        self.keep = upkeep.Upkeep(home_dir=self.base / 'home', root=self.base / 'root',
                                  installer=self.base / 'installer' / 'install.py')

    def settle(self):
        for thread in list(self.keep._threads):
            thread.join(30)

    def test_threads_that_have_ended_are_let_go(self):
        for _ in range(50):
            self.keep._background(lambda: None, 'nothing')
            time.sleep(0.001)
        self.settle()
        self.keep._background(lambda: None, 'nothing')
        self.settle()
        self.assertLessEqual(len(self.keep._threads), 1)

    def test_check_again_runs_off_the_callers_thread_and_once_at_a_time(self):
        let, ran = threading.Event(), []

        def local(keep, repair):
            ran.append(threading.current_thread())
            let.wait(30)
            return keep._blank(None)

        with mock.patch.object(upkeep.Upkeep, '_local', local), \
                mock.patch.object(upkeep.Upkeep, 'look', lambda keep: False):
            self.assertTrue(self.keep.again())
            self.assertFalse(self.keep.again(), 'a second is not started')
            self.assertFalse(self.keep.start())
            self.assertTrue(self.keep.report()['checking'], 'nothing was found yet')
            let.set()
            self.settle()
            self.assertEqual(len(ran), 1)
            self.assertIsNot(ran[0], threading.current_thread())
            self.assertFalse(self.keep.report()['checking'])
            let.clear()
            self.assertTrue(self.keep.again(), 'once it is done, another may start')
            self.assertFalse(self.keep.report()['checking'],
                             'what was found last is shown meanwhile')
            let.set()
            self.settle()
        self.assertEqual(len(ran), 2)


if __name__ == '__main__':
    unittest.main()
