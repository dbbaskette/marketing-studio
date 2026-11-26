"""The command line, including the check aggregation and readiness (matrix rows that name check)."""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path

import helpers
from helpers import TrainingCase
import stored_builders
from stored_builders import builder
import gdocs
from test_google import FakeTransport
import training

CLI = helpers.SCRIPTS / 'training.py'


def example(name: str) -> str:
    return (helpers.EXAMPLES / name).read_text(encoding='utf-8')


def levelled(text: str, level: str) -> str:
    return text.replace('Time: 25 min', f'Time: 25 min\nLevel: {level}')


COURSE_BLUEPRINT = (
    example('blueprint.md')
    .replace('\n## M1 —', '### O4 — Describe what a health check reports [recall]\n'
             '### O5 — Explain how health checks pace a restart [explain]\n'
             '### O6 — Choose a health check for a slow-starting app [apply]\n\n## M1 —')
    .replace('\n## Assessment plan\n', '\n## M2 — Health checks (20 min)\n'
             'Objectives: O4, O5, O6\n'
             '- K2.1: A health check reports whether an instance can serve. [R:health-checks]\n'
             '- K2.2: A restart continues only when new instances pass. [R:health-checks]\n'
             'Example: An app that takes ninety seconds to start.\n\n## Assessment plan\n')
    .replace('\n## Practice plan\n', '- O4: Check: What does a health check report? | Observe: '
             'States readiness to serve.\n- O5: Check: How do health checks pace a restart? | '
             'Observe: Links passing checks to the next batch.\n- O6: Check: Which check suits '
             'a slow app? | Observe: Picks one and says why.\n\n## Practice plan\n'))
COURSE_DOCUMENT = (example('document.md')
                   + '\n## Health checks\n\n<!-- covers: O4 O5 O6 K2.1 K2.2 -->\n\nText.\n')


class Flow(TrainingCase):
    """Drives the helper the way the assistant does, in process."""

    def cli(self, *args, expect=0) -> dict:
        """Run the helper. A command that continued a training (they are gone) reaches the
        state it made from its stored copy (`stored_builders.command`)."""
        def run():
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                try:
                    code = training.main(['--dir', str(self.root), *args])
                except SystemExit as stopped:
                    code = stopped.code
            return code, captured.getvalue()
        if args and args[0] in stored_builders.CONTINUING:
            code, output = stored_builders.command(self.root, list(args), run)
        else:
            code, output = run()
        self.assertEqual(code, expect, output)
        return json.loads(output)

    @builder
    def make(self, artifact: str, relative: str, text: str) -> None:
        """Write an artifact's file, save it as built and approve it."""
        self.write(relative, text)
        self.cli('save', artifact, '--built')
        self.cli('approve', artifact)

    @builder
    def research(self, *init_args, yoodli: bool = True, copies=('word',)) -> None:
        helpers.saved_init(self.root, '--title', 'Rolling restarts', *init_args,
                 *(['--yoodli'] if yoodli else []), *(['--copies', *copies] if copies else []))
        self.make('intake', 'intake.md', '# Intake\n\n## Topic\nRolling restarts\n')
        self.make('research-plan', '.training-studio/research-plan.json',
                  json.dumps(helpers.PLAN))
        self.write('.harness-research/research.json', json.dumps(helpers.RESEARCH))
        self.make('research', '.harness-research/research-report.md', '# Research brief\n')

    @builder
    def content(self, level: str | None = None, blueprint: str | None = None,
                document: str | None = None) -> None:
        """Blueprint, document and brief for one level, with the two exports."""
        at = f'@{level}' if level else ''
        folder = f'{level}/' if level else ''
        text = blueprint or example('blueprint.md')
        self.make(f'blueprint{at}', f'{folder}blueprint.md',
                  levelled(text, level) if level else text)
        self.make(f'document{at}', f'{folder}document.md', document or example('document.md'))
        self.make(f'brief{at}', f'{folder}product-brief.md', example('product-brief.md'))
        for name in ('document', 'product-brief'):
            self.write(f'{folder}{name}.docx', f'exported {name}')
        # Named, so pandoc on this computer, or its absence, makes no difference.
        self.cli('export', f'document{at}', '--file', f'{folder}document.docx')
        self.cli('export', f'brief{at}', '--file', f'{folder}product-brief.docx')

    @builder
    def deck(self, level: str | None = None, objectives=('O1', 'O2', 'O3')) -> None:
        at = f'@{level}' if level else ''
        folder = f'{level}/' if level else ''
        self.write(f'{folder}deck.pptx', helpers.DECK)
        coverage = self.root.parent / 'coverage.json'
        coverage.write_text(json.dumps({objective: [2] for objective in objectives}))
        self.cli('save', f'deck{at}', '--built', '--coverage', str(coverage))
        self.cli('approve', f'deck{at}')

    @builder
    def scenario(self, level: str | None = None, yoodli: bool = True) -> None:
        at = f'@{level}' if level else ''
        folder = f'{level}/' if level else ''
        self.make(f'scenario:main{at}', f'{folder}scenario.md', example('scenario.md'))
        if yoodli:
            self.make(f'yoodli:main{at}', f'{folder}yoodli/main.md', example('yoodli.md'))

    @builder
    def complete(self, level: str | None = None) -> None:
        self.content(level)
        self.deck(level)
        self.scenario(level)

    def check(self, *args, expect=0) -> dict:
        return self.cli('check', *args, expect=expect)

    def by_name(self, report: dict) -> dict:
        return {item['check']: item for item in report['checks']}


class ContractTests(TrainingCase):
    """The promises every command keeps, checked in a real subprocess."""

    def run_cli(self, *args, expect=0):
        done = subprocess.run([sys.executable, str(CLI), *args], cwd=self.root,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, expect, done.stdout + done.stderr)
        return json.loads(done.stdout)

    def test_public_init_refuses_without_writes(self):
        home = self.root.parent / 'home'
        home.mkdir()
        (home / 'keep.txt').write_text('Synthetic existing home content.\n')
        with mock.patch.dict(os.environ, {'HOME': str(home)}):
            target = self.root.parent / 'new-training'
            roots = [self.root.parent, Path(os.environ['TRAINING_STUDIO_DATA']),
                     Path(os.environ['HOME']), Path(os.environ['STUDIOS_CONFIG']).parent]
            def contents():
                return [{p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                        for root in roots]
            before = contents()
            for directory in (target, self.root):
                result = self.run_cli('--dir', str(directory), 'init', '--title', 'Topic', expect=2)
                self.assertIn('desk', result['error'].lower())
                self.assertEqual(before, contents())
            self.assertFalse(target.exists())

    def test_status_before_init_is_a_refusal_with_exit_code_2(self):
        self.assertEqual(self.run_cli('status', expect=2),
                         {'error': 'No training in this directory. Use checked desk commands for new work.'})

    def test_saved_fixture_retains_levels_and_brief(self):
        report = helpers.saved_init(self.root, '--title', 'Valkey', '--levels', '301,101',
                              '--brief-kind', 'competitive')
        self.assertEqual(report['levels'], ['101', '301'])
        self.assertEqual(report['files']['brief@101'], '101/competitive-brief.md')
        self.assertEqual(report['artifacts']['blueprint@301'], 'not-started')

    def test_row_35_a_broken_record_is_a_structured_error(self):
        helpers.saved_init(self.root, '--title', 'Topic')
        record = self.root / '.training-studio' / 'session.json'
        record.write_text('{not json')
        for command in (('status',), ('check',)):
            self.assertIn('not valid JSON', self.run_cli(*command, expect=2)['error'])
        self.assertEqual(record.read_text(), '{not json')

    def test_a_command_that_continued_a_training_answers_that_it_ended_and_changes_nothing(self):
        """GitHub issue #547: nothing continues a training a conversation made. Each command
        that did answers one plain sentence, with what to do instead, and changes nothing."""
        helpers.saved_init(self.root, '--title', 'Topic')
        self.write('intake.md', '# Intake\n')
        def files():
            return {path.relative_to(self.root): path.read_bytes()
                    for path in self.root.rglob('*') if path.is_file()}
        before = files()
        for command in (('save', 'intake', '--built'), ('approve', 'intake'),
                        ('skip', 'deck', '--reason', 'Later'), ('checkpoint', '--stage', 'done'),
                        ('pin', 'harness-research', '--task', 't-1'),
                        ('export', 'document', '--unavailable', '--reason', 'None'),
                        ('research-import', '--case', str(self.root.parent))):
            with self.subTest(command=command[0]):
                self.assertEqual(self.run_cli(*command, expect=2), {'error': training.ENDED})
        self.assertEqual(set(training.ENDED_COMMANDS),
                         {'save', 'approve', 'skip', 'checkpoint', 'pin', 'export',
                          'research-import'})
        self.assertEqual(files(), before)

    def test_status_says_a_conversation_training_is_a_saved_record(self):
        """GitHub issue #547: status says what such a training is and its way on."""
        import workspace
        helpers.saved_init(self.root, '--title', 'Topic')
        self.assertEqual(self.run_cli('status')['saved_record'],
                         {'said': workspace.CONVERSATION_SAID,
                          'next': workspace.CONVERSATION_NEXT})

    def test_usage_errors_are_json_too(self):
        self.assertIn('unrecognized', self.run_cli('check', '--soon', expect=2)['error'])
        self.assertIn('invalid choice', self.run_cli('publish', expect=2)['error'])


class FoundationTests(TrainingCase):
    """Command plug-ins and the list of trainings on this computer."""

    def run_at(self, script, *args, cwd=None, expect=0):
        done = subprocess.run([sys.executable, str(script), *args], cwd=cwd or self.root,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, expect, done.stdout + done.stderr)
        return json.loads(done.stdout)

    def test_a_cmd_module_beside_the_helper_adds_its_commands(self):
        import shutil
        scripts = self.root.parent / 'scripts'
        shutil.copytree(helpers.SCRIPTS, scripts, ignore=shutil.ignore_patterns('__pycache__'))
        (scripts / 'cmd_hello.py').write_text(
            'def register(commands):\n'
            "    hello = commands.add_parser('hello')\n"
            "    hello.add_argument('--name', default='you')\n"
            '    hello.set_defaults(handler=lambda args, root: '
            "{'hello': args.name, 'root': root.name})\n")
        self.assertEqual(self.run_at(scripts / 'training.py', 'hello', '--name', 'there'),
                         {'hello': 'there', 'root': self.root.name})
        self.assertIn('No training', self.run_at(scripts / 'training.py', 'status',
                                                 expect=2)['error'])

    def test_list_names_the_trainings_on_this_computer(self):
        other = self.root.parent / 'another'
        other.mkdir()
        helpers.saved_init(self.root, '--title', 'First training')
        helpers.saved_init(other, '--title', 'Second', '--levels', '101')
        listed = {item['path']: item for item in self.run_at(CLI, 'list')['trainings']}
        self.assertEqual(listed[str(self.root)]['title'], 'First training')
        self.assertEqual(listed[str(other)]['levels'], ['101'])

    def test_list_forgets_a_training_whose_directory_no_longer_holds_one(self):
        import shutil
        helpers.saved_init(self.root, '--title', 'Short lived')
        shutil.rmtree(self.root / '.training-studio')
        paths = [item['path'] for item in self.run_at(CLI, 'list')['trainings']]
        self.assertNotIn(str(self.root), paths)

    def test_status_says_which_guidance_a_training_follows(self):
        report = helpers.saved_init(self.root, '--title', 'Topic')
        self.assertIn('guidance', report)
        self.assertEqual(self.run_at(CLI, 'status')['guidance'], report['guidance'])



class CheckTests(Flow):
    def test_row_32_a_blueprint_alone_passes_its_checks_but_is_not_ready(self):
        self.research()
        self.make('blueprint', 'blueprint.md', example('blueprint.md'))
        report = self.check()
        self.assertTrue(report['checks_passed'])
        self.assertFalse(report['ready'])
        self.assertEqual((report['passed'], report['checks']), (5, []))
        for reason in ('document is not-started', 'brief is not-started',
                       'deck is not-started', 'No scenario file found.'):
            self.assertIn(reason, report['blocking'])
        self.check('--complete', expect=1)

    def test_check_before_a_blueprint_reports_what_is_missing(self):
        helpers.saved_init(self.root, '--title', 'Rolling restarts')
        report = self.check()
        self.assertEqual((report['checks_passed'], report['ready'], report['passed']),
                         (True, False, 0))
        self.assertIn('intake is not-started', report['blocking'])

    def test_a_scenario_is_checked_before_any_blueprint_exists(self):
        helpers.saved_init(self.root, '--title', 'Rolling restarts')
        self.write('scenario.md', example('scenario.md').replace('## Opening', '## Start'))
        report = self.check(expect=1)
        self.assertEqual(self.by_name(report)['scenario:main.sections']['problems'],
                         ['Section "Opening" is missing or empty.'])

    def test_a_lesson_reaches_ready(self):
        self.research()
        self.complete()
        report = self.check('--complete')
        self.assertEqual((report['checks_passed'], report['ready'], report['blocking']),
                         (True, True, []))
        self.assertEqual(report['passed'], 13)
        self.assertEqual(report['checks'], [])
        self.assertEqual(report['limitations'], ['yoodli:main has no export'])
        self.assertEqual(report['practice'], {'basis': 'Yoodli goals',
                                              'exercised': ['O1', 'O2', 'O3'],
                                              'not_exercised': []})
        self.assertEqual(len(report['warnings']), 1)
        self.assertIn('provisional', report['warnings'][0])
        everything = self.check('--all')
        self.assertEqual(len(everything['checks']), 13)
        self.assertEqual(self.by_name(everything)['document.coverage']['basis'], 'declared')

    def test_a_two_module_course_reaches_ready(self):
        self.research()
        self.content(blueprint=COURSE_BLUEPRINT, document=COURSE_DOCUMENT)
        self.deck(objectives=('O1', 'O2', 'O3', 'O4', 'O5', 'O6'))
        self.scenario()
        report = self.check('--complete')
        self.assertTrue(report['ready'], report['blocking'])
        self.assertEqual(self.cli('status')['sizing'][''],
                         {'size': 'course', 'modules': ['m1', 'm2']})
        self.assertEqual(report['practice']['not_exercised'], ['O4', 'O5', 'O6'])

    def test_a_failed_check_blocks_and_sets_the_exit_code(self):
        self.research()
        broken = example('blueprint.md').replace('[R:health-checks]', '[R:made-up]')
        self.write('blueprint.md', broken)
        self.cli('save', 'blueprint', '--built')
        report = self.check(expect=1)
        self.assertFalse(report['checks_passed'])
        self.assertEqual([item['check'] for item in report['checks']], ['blueprint.citations'])
        self.assertIn('blueprint.citations failed', report['blocking'])

    def test_a_check_that_cannot_run_blocks_readiness(self):
        helpers.saved_init(self.root, '--title', 'Rolling restarts')
        self.write('blueprint.md', example('blueprint.md'))
        report = self.check()
        self.assertTrue(report['checks_passed'])
        self.assertTrue(any(reason.startswith('blueprint.citations could not run')
                            for reason in report['blocking']))

    def test_row_20_replacing_the_deck_voids_its_coverage_review(self):
        self.research()
        self.complete()
        self.write('deck.pptx', helpers.DECK + 'a different deck')
        self.cli('save', 'deck', '--built')
        report = self.check()
        self.assertEqual(self.by_name(report)['deck.coverage']['status'], 'unavailable')
        self.assertFalse(report['ready'])

    def test_row_21_changing_the_blueprint_voids_the_coverage_review(self):
        self.research()
        self.complete()
        self.write('blueprint.md', example('blueprint.md') + '\nA note.\n')
        self.assertEqual(self.by_name(self.check())['deck.coverage']['status'], 'unavailable')

    def test_row_25_an_unavailable_brief_export_is_a_limitation(self):
        self.research()
        self.complete()
        self.cli('export', 'brief', '--unavailable', 'No converter on this machine')
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertIn('Yoodli handoff incomplete: no export of brief', report['limitations'])

    def test_a_missing_brief_export_blocks_when_scenarios_are_wanted(self):
        self.research()
        self.complete()
        (self.root / 'product-brief.docx').unlink()
        report = self.check('--complete', expect=1)
        self.assertEqual(report['blocking'], ['brief has no export, and the Yoodli scenario '
                                              'names it as the file to upload'])

    def test_an_outdated_export_blocks(self):
        self.research()
        self.complete()
        self.write('document.docx', 'someone re-exported an older draft')
        self.assertIn('The export of document is out of date', self.check()['blocking'])

    def test_row_27_a_deleted_file_is_not_ready(self):
        self.research()
        self.complete()
        (self.root / 'document.md').unlink()
        report = self.check('--complete', expect=1)
        self.assertIn('document is not-started', report['blocking'])

    def test_row_28_the_done_marker_does_not_override_readiness(self):
        self.research()
        self.complete()
        self.cli('checkpoint', '--stage', 'done')
        self.assertTrue(self.check()['ready'])
        self.write('product-brief.md', example('product-brief.md') + '\nA late edit.\n')
        report = self.check('--complete', expect=1)
        self.assertIn('brief is draft', report['blocking'])
        self.assertIn('yoodli:main is stale', report['blocking'])
        self.assertEqual(self.cli('status')['stage'], 'done')

    def test_row_31_an_unavailable_deck_is_a_limitation_not_a_blocker(self):
        self.research()
        self.cli('skip', 'deck', '--unavailable', '--reason', 'harness-slides is not installed')
        self.content()
        self.scenario()
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertIn('deck unavailable: harness-slides is not installed',
                      report['limitations'])

    def test_skipped_stages_are_limitations(self):
        self.research(yoodli=False)
        self.cli('skip', 'scenario', '--reason', 'Later')
        self.cli('skip', 'brief', '--reason', 'Later')
        self.cli('skip', 'deck', '--reason', 'Later')
        self.make('blueprint', 'blueprint.md', example('blueprint.md'))
        self.make('document', 'document.md', example('document.md'))
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertEqual(report['limitations'][:3],
                         ['brief was skipped', 'deck was skipped', 'scenario was skipped'])
        self.assertEqual(report['practice'], {})


class OptionalYoodliTests(Flow):
    """Yoodli is an optional stage, off unless asked for (matrix rows 58 to 62)."""

    @builder
    def without_yoodli(self) -> None:
        self.research(yoodli=False)
        self.content()
        self.deck()
        self.scenario(yoodli=False)

    def test_row_61_a_training_is_complete_without_yoodli(self):
        self.without_yoodli()
        report = self.check('--complete')
        self.assertEqual((report['ready'], report['blocking'], report['limitations']),
                         (True, [], []))
        self.assertEqual(report['passed'], 10)
        self.assertEqual(report['warnings'], [])
        self.assertEqual(report['practice'], {'basis': 'practice plan',
                                              'exercised': ['O1', 'O2', 'O3'],
                                              'not_exercised': []})
        status = self.cli('status')
        self.assertFalse(any(name.startswith('yoodli:') for name in status['artifacts']))
        self.assertEqual(status['settings']['stages'], ['document', 'brief', 'deck', 'scenario'])

    def test_without_yoodli_a_missing_brief_export_does_not_block(self):
        self.without_yoodli()
        (self.root / 'product-brief.docx').unlink()
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertEqual(report['limitations'], ['brief has no export'])

    def test_row_62_turning_yoodli_on_later_reopens_the_training(self):
        self.without_yoodli()
        self.cli('skip', 'yoodli', '--clear')
        report = self.check('--complete', expect=1)
        self.assertEqual(report['blocking'], ['yoodli:main is not-started'])
        self.make('yoodli:main', 'yoodli/main.md', example('yoodli.md'))
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertEqual(report['practice']['basis'], 'Yoodli goals')

    def test_turning_yoodli_off_again_hides_it(self):
        self.research()
        self.complete()
        self.cli('skip', 'yoodli', '--reason', 'Not using Yoodli after all')
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertFalse(any('yoodli' in text.lower() for text in report['limitations']))
        self.assertTrue((self.root / 'yoodli' / 'main.md').is_file())


class CopiesTests(Flow):
    """Word copies and Google Docs are kept only when asked for (matrix rows 64, 67 and 68)."""

    @builder
    def built(self, *copies: str) -> None:
        """Everything approved, Yoodli off, and no copy of anything made yet."""
        self.research(yoodli=False, copies=copies)
        for name, file in (('blueprint', 'blueprint.md'), ('document', 'document.md'),
                           ('brief', 'product-brief.md')):
            self.make(name, file, example(file))
        self.deck()
        self.scenario(yoodli=False)

    def test_row_64_a_training_with_no_copies_is_ready_and_reports_none(self):
        self.built()
        report = self.check('--complete')
        self.assertEqual((report['ready'], report['blocking'], report['limitations']),
                         (True, [], []))
        status = self.cli('status')
        self.assertEqual((status['settings']['copies'], status['exports'],
                          status['google_docs']), ([], {}, {}))

    def test_row_67_a_wanted_google_doc_that_is_not_made_is_a_limitation(self):
        self.built('google')
        self.assertEqual(self.cli('status')['google_docs'],
                         {'brief': 'missing', 'document': 'missing'})
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertEqual(report['limitations'], ['document is not in a Google Doc',
                                                 'brief is not in a Google Doc'])

    def test_row_68_a_google_doc_behind_its_file_blocks(self):
        self.built('google')
        drive = FakeTransport()
        for name in ('document', 'brief'):
            gdocs.push(self.root, name, drive)
        self.assertEqual(self.cli('status')['google_docs'],
                         {'brief': 'current', 'document': 'current'})
        self.assertEqual(self.check('--complete')['limitations'], [])
        self.write('document.md', example('document.md') + '\nOne more line.\n')
        self.cli('approve', 'document')
        self.assertEqual(self.cli('status')['google_docs']['document'], 'outdated')
        report = self.check('--complete', expect=1)
        self.assertIn('The Google Doc of document is behind its file', report['blocking'])
        gdocs.push(self.root, 'document', drive)
        self.assertNotIn('The Google Doc of document is behind its file',
                         self.check()['blocking'])

    @builder
    def with_yoodli_and_google_docs(self) -> None:
        """Everything approved with Yoodli on and Google Docs kept, and no Doc made yet."""
        self.research(copies=('google',))
        for name, file in (('blueprint', 'blueprint.md'), ('document', 'document.md'),
                           ('brief', 'product-brief.md')):
            self.make(name, file, example(file))
        self.deck()
        self.scenario()

    def test_row_71_yoodli_needs_the_briefs_google_doc_when_no_word_copy_is_kept(self):
        self.with_yoodli_and_google_docs()
        self.assertEqual(self.cli('status')['exports'], {})
        report = self.check('--complete', expect=1)
        self.assertEqual(report['blocking'], ['brief is not in a Google Doc, and the Yoodli '
                                              'scenario names it as the file to upload'])
        self.assertEqual(report['limitations'], ['document is not in a Google Doc'])

    def test_row_72_with_the_docs_made_a_yoodli_training_is_ready_without_word(self):
        self.with_yoodli_and_google_docs()
        drive = FakeTransport()
        for name in ('document', 'brief'):
            gdocs.push(self.root, name, drive)
        report = self.check('--complete')
        self.assertEqual((report['ready'], report['blocking'], report['limitations']),
                         (True, [], []))
        self.assertFalse(list(self.root.rglob('*.docx')))

    def test_with_both_kinds_kept_the_word_copy_is_the_upload(self):
        self.research(copies=('google', 'word'))
        self.complete()
        report = self.check('--complete')
        self.assertTrue(report['ready'])
        self.assertEqual(report['limitations'], ['yoodli:main has no export',
                                                 'document is not in a Google Doc',
                                                 'brief is not in a Google Doc'])

    def test_a_linked_doc_is_not_tracked_unless_google_copies_were_asked_for(self):
        self.built()
        gdocs.push(self.root, 'document', FakeTransport())
        self.write('document.md', example('document.md') + '\nOne more line.\n')
        self.cli('approve', 'document')
        self.assertEqual(self.cli('status')['google_docs'], {})
        self.assertFalse(any('Google Doc' in text for text in self.check()['blocking']))


class DryRunFindingTests(Flow):
    """Behaviour added after an assistant followed the guidance end to end."""

    def test_row_51_a_pending_question_blocks_readiness(self):
        self.research()
        self.complete()
        self.cli('checkpoint', '--question', 'Is the client timeout section right?')
        report = self.check('--complete', expect=1)
        self.assertEqual(report['blocking'], ['A question is waiting on the user: '
                                              'Is the client timeout section right?'])
        self.cli('checkpoint', '--no-question')
        self.assertTrue(self.check('--complete')['ready'])

    def test_row_52_an_accepted_stale_artifact_is_listed_as_a_limitation(self):
        self.research()
        self.complete()
        self.write('blueprint.md', example('blueprint.md') + '\nA note.\n')
        self.cli('approve', 'blueprint')
        for name in ('document', 'brief'):
            self.cli('approve', name, '--accept-stale', 'The note changes nothing taught')
        report = self.check()
        self.assertIn('document was accepted as it was after its inputs changed: '
                      'The note changes nothing taught', report['limitations'])

    def test_row_53_an_invalid_research_plan_fails_its_check(self):
        helpers.saved_init(self.root, '--title', 'Rolling restarts')
        self.make('intake', 'intake.md', 'v1\n')
        plan = dict(helpers.PLAN, input_files=['intake.md'],
                    items=[{'id': 'Q0', 'question': ''}])
        self.write('.training-studio/research-plan.json', json.dumps(plan))
        failed = self.by_name(self.check(expect=1))['research-plan.items']
        self.assertEqual(len(failed['problems']), 3)
        self.write('.training-studio/research-plan.json', '{not json')
        failed = self.by_name(self.check(expect=1))['research-plan.items']
        self.assertEqual(failed['problems'], ['The plan is not valid JSON.'])

    def test_row_57_scenario_files_that_were_passed_over_are_named(self):
        self.research('--levels', '101')
        self.write('scenarios/keys-quiz.md', example('scenario.md'))
        warnings = self.check()['warnings']
        self.assertTrue(any(text.startswith('scenarios/keys-quiz.md is not used as a scenario')
                            for text in warnings), warnings)

    def test_a_scenario_whose_mode_differs_from_the_practice_plan_is_flagged(self):
        self.research()
        self.content(blueprint=example('blueprint.md').replace('- main: roleplay.',
                                                               '- main: tutor.'))
        self.scenario()
        warnings = self.check()['warnings']
        self.assertIn('The practice plan lists scenario:main as tutor; its scenario file '
                      'says roleplay. The scenario file decides.', warnings)

    def test_status_summarises_the_approved_research(self):
        helpers.saved_init(self.root, '--title', 'Rolling restarts')
        self.assertIsNone(self.cli('status')['research'])
        self.cli('skip', 'deck', '--unavailable', '--reason', 'Not installed')
        self.research_only()
        report = self.cli('status')
        self.assertEqual(report['research']['findings'],
                         {'supported': 5, 'insufficient': 1, 'pending': 1, 'contradicted': 1})
        self.assertEqual(report['research']['run'], 'run-1')
        self.assertTrue(report['research']['approved_at'])
        self.assertEqual(report['unavailable_stages'], {'deck': 'Not installed'})

    def test_row_73_research_is_summarised_before_it_is_approved(self):
        counts = {'supported': 5, 'insufficient': 1, 'pending': 1, 'contradicted': 1}
        helpers.saved_init(self.root, '--title', 'Rolling restarts')
        self.make('intake', 'intake.md', 'v1\n')
        self.make('research-plan', '.training-studio/research-plan.json',
                  json.dumps(helpers.PLAN))
        self.write('.harness-research/research.json', json.dumps(helpers.RESEARCH))
        self.write('.harness-research/research-report.md', '# Research brief\n')
        self.cli('save', 'research', '--built')
        waiting = self.cli('status')
        self.assertEqual(waiting['artifacts']['research'], 'draft')
        self.assertEqual(waiting['research'],
                         {'approved_at': None, 'run': 'run-1', 'findings': counts})
        self.cli('approve', 'research')
        self.assertTrue(self.cli('status')['research']['approved_at'])
        answered = json.loads(json.dumps(helpers.RESEARCH))
        answered['results']['rollback'] = {'status': 'supported'}
        self.write('.harness-research/research.json', json.dumps(answered))
        changed = self.cli('status')
        self.assertEqual(changed['artifacts']['research'], 'draft')
        self.assertEqual(changed['research'], {
            'approved_at': None, 'run': 'run-1',
            'findings': {'supported': 6, 'insufficient': 1, 'contradicted': 1}})

    def research_only(self) -> None:
        self.make('intake', 'intake.md', 'v1\n')
        self.make('research-plan', '.training-studio/research-plan.json',
                  json.dumps(helpers.PLAN))
        self.write('.harness-research/research.json', json.dumps(helpers.RESEARCH))
        self.make('research', '.harness-research/research-report.md', '# Research brief\n')



class LevelCheckTests(Flow):
    def test_row_48_one_unfinished_level_blocks_the_training(self):
        self.research('--levels', '101,301')
        self.complete('101')
        report = self.check('--complete', expect=1)
        self.assertTrue(report['checks_passed'])
        self.assertIn('blueprint@301 is not-started', report['blocking'])
        self.assertIn('No scenario file found for level 301.', report['blocking'])
        self.assertFalse(any('@101' in reason for reason in report['blocking']))
        self.assertEqual(report['practice'], {'101': {
            'basis': 'Yoodli goals', 'exercised': ['O1', 'O2', 'O3'], 'not_exercised': []}})

    def test_both_levels_complete_is_ready(self):
        self.research('--levels', '101,301')
        self.complete('101')
        self.complete('301')
        report = self.check('--complete', '--all')
        self.assertTrue(report['ready'], report['blocking'])
        self.assertIn('yoodli:main.mapping@301', self.by_name(report))

    def test_row_49_repeated_objectives_across_levels_are_a_warning(self):
        self.research('--levels', '101,301')
        self.make('blueprint@101', '101/blueprint.md', levelled(example('blueprint.md'), '101'))
        self.make('blueprint@301', '301/blueprint.md', levelled(example('blueprint.md'), '301'))
        report = self.check()
        self.assertTrue(report['checks_passed'])
        overlap = [text for text in report['warnings'] if text.startswith('Levels 101 and 301')]
        self.assertEqual(len(overlap), 3)

    def test_row_50_a_blueprint_in_the_wrong_folder_fails(self):
        self.research('--levels', '101,301')
        self.write('301/blueprint.md', levelled(example('blueprint.md'), '201'))
        report = self.check(expect=1)
        failed = self.by_name(report)['blueprint.structure@301']
        self.assertEqual(failed['problems'],
                         ['The frame must say "Level: 301", the level of its folder.'])



class HelpTests(unittest.TestCase):
    """--help lists every value a flag takes and says what every flag is for."""

    def everything(self, parser, path=('training.py',)):
        """Every argument of every command, plug-ins included, with the command it is in."""
        for action in parser._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            if isinstance(action, argparse._SubParsersAction):
                helped = {choice.dest: choice.help for choice in action._choices_actions}
                for name, sub in action.choices.items():
                    yield (*path, name), f'the {name} command', helped.get(name)
                    yield from self.everything(sub, (*path, name))
                continue
            yield path, '/'.join(action.option_strings) or action.dest, action.help

    def test_every_flag_and_command_has_one_line_of_help(self):
        found = list(self.everything(training.parser()))
        self.assertGreater(len(found), 60)
        for path, name, text in found:
            with self.subTest(command=' '.join(path), argument=name):
                self.assertTrue(text and text.strip(), 'no help')
                self.assertNotIn('\n', text)

    def help_of(self, *command) -> str:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), self.assertRaises(SystemExit):
            training.main([*command, '--help'])
        return ' '.join(printed.getvalue().split())

    def test_help_lists_the_values_each_flag_takes(self):
        import workspace
        text = self.help_of('init')
        for values in (workspace.BRIEF_KINDS, workspace.DECK_TARGETS, workspace.COPIES,
                       workspace.LEVELS, workspace.APPROVAL):
            self.assertIn('{' + ','.join(values) + '}', text)

    def test_an_unknown_value_is_refused_by_the_command_line(self):
        for flag, value in (('--brief-kind', 'battlecard'), ('--deck-target', 'keynote')):
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed), self.assertRaises(SystemExit):
                training.main(['init', '--title', 'Topic', flag, value])
            self.assertIn('invalid choice', json.loads(printed.getvalue())['error'])
