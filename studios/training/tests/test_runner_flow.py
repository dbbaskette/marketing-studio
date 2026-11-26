"""The engine after the blueprints: the guide, the brief, the practice scenarios, the Yoodli
scenarios, the copies, the deck that is not made, the index, and research from documents
the person supplies.

Scripted workers hand back the core's own examples. The person's documents, the copies and
the index are small stand-ins that follow the docstrings of the three modules. No agent is
started, nothing is converted and nothing touches the network.
"""
import re
import shutil
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
from runner_support import (BLUEPRINT, BRIEF, DOCUMENT, QUOTE, SCENARIO, YOODLI,
                            NO_BRAND_SKILL, NO_SLIDES, StudioCase, asks, left)

import assess
import desk
import home
import workspace
from runner import engine as engine_module
from runner import page, pipeline
from workspace import WorkspaceError

AVOIDED = re.compile(r'\b(artifacts?|stale|lineage)\b', re.IGNORECASE)
PLAIN = ['research-plan', 'research', 'blueprint', 'document', 'brief', 'scenario:main']
OWN = SCENARIO.replace('Priya Nair', 'Sam Okafor').replace(
    'The zero-downtime objection', 'A restart that dropped requests')
NOTES = ('A platform lead rings after a restart dropped requests.\n\n'
         'She was told rolling restarts mean zero downtime.\n\n'
         'The engineer should explain when capacity holds and agree what happens next.\n')


def other_blueprint() -> str:
    """The example blueprint with one line changed, as a revision would leave it."""
    return BLUEPRINT.replace('A three-instance web app', 'A four-instance web app')


class FlowCase(StudioCase):
    def kinds(self, since: int = 0) -> list[str]:
        """The kind of each job started, after the first `since`."""
        return [kind for kind, _, _ in self.workers.jobs[since:]]

    def review(self, root: Path, name: str) -> str:
        """The last thing written for the person about one file."""
        text = (root / workspace.review_file(name)).read_text()
        return text.rpartition('## Ready for your review')[2]

    def gate(self, root: Path, name: str) -> dict:
        return page.RunnerPage(8765, self.engine).gate(str(root), name)


class ToTheEndTests(FlowCase):

    def test_selected_materials_finish_without_unrequested_workers_or_gates(self):
        for materials, gates, writers in (
            (['document'], ['document'], ['document']),
            (['scenario'], ['scenario:main'], ['scenario']),
            (['brief'], ['brief'], ['brief']),
        ):
            with self.subTest(materials=materials):
                start = len(self.workers.jobs)
                root = self.start(title='Only ' + materials[0], materials=materials)
                self.assertEqual(self.to_end(root), [])
                self.all_ready(root)
                kinds = self.kinds(start)
                self.assertEqual([kind for kind in kinds if kind in
                                  ('document', 'brief', 'scenario', 'yoodli')], writers)
                self.assertTrue(self.view(root)['finished']['ready'])
                self.assertEqual(workspace.load(root)['settings']['stages'], materials)
                for stage, file in (('document', 'document.md'), ('brief', 'product-brief.md'),
                                    ('scenario', 'scenario.md')):
                    self.assertEqual((root / file).exists(), stage in materials)

    def test_a_plain_training_goes_from_the_form_to_finished(self):
        self.engine = self.make(at_once=1)
        root = self.start()
        self.assertEqual(self.to_end(root), [])
        self.all_ready(root)
        self.assertEqual(self.kinds(), [
            'research-plan', 'research-result', 'research-result', 'blueprint', 'document',
            'brief', 'scenario'])
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence']), (
            'done', 'This training is finished, with 1 thing left out or limited.'))
        self.assertEqual(view['finished'], {
            'ready': True, 'limitations': ['The deck stage was left out'], 'blocking': [],
            'index': 'README.md', 'yoodli': []})
        self.assertEqual((view['deck_left'], view['documents'], view['copies'], view['problem']),
                         (None, None, [], None))
        self.assertEqual({step['status'] for step in view['steps']}, {'done'})
        self.assertEqual([step['id'] for step in view['steps']][9:], [
            'document', 'gate:document', 'brief', 'gate:brief', 'scenario:main',
            'gate:scenario:main', 'package'])
        status = workspace.status(root)
        self.assertEqual((status['stage'], status['next_step'], status['gate']),
                         ('done', view['sentence'], None))
        self.assertEqual(set(status['artifacts'].values()), {'approved', 'skipped'})
        self.assertEqual((root / 'document.md').read_text(), DOCUMENT)
        self.assertEqual((root / 'product-brief.md').read_text(), BRIEF)
        self.assertEqual((root / 'scenario.md').read_text(), SCENARIO)
        self.assertTrue((root / 'README.md').read_text().startswith('# Rolling restarts\n'))
        self.assertNotIn('README.md', status['files'].values(), 'the index is never saved '
                         'through the core')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_a_finished_training_is_filed_under_finished_by_the_desk(self):
        root = self.start()
        self.to_end(root)
        self.all_ready(root)
        listed = page.RunnerPage(8765, self.engine).trainings()[0]
        self.assertEqual((listed['state'], listed['run']['state'], listed['ready']),
                         ('finished', 'done', True))
        self.assertEqual(self.engine.brief(root)['needs'], False)
        jobs = len(self.workers.jobs)
        self.engine.wake(root)
        self.assertEqual(len(self.workers.jobs), jobs, 'a finished run starts nothing')

    def test_with_levels_everything_after_the_blueprints_is_done_one_level_at_a_time(self):
        root = self.start(levels=['201', '101'])
        self.assertEqual(self.to_end(root), [])
        self.all_ready(root)
        self.assertEqual(self.kinds(3), ['blueprint', 'blueprint', 'document', 'brief',
                                         'scenario', 'document', 'brief', 'scenario'])
        first, second = self.workers.of('document')
        self.assertIn('Write the level 101 learner guide for this training.', first.task)
        self.assertIn('This guide is for level 101.', first.task)
        self.assertEqual(first.guidance, pipeline.briefs.guidance('document', level='101'))
        self.assertIn('Your inputs are "intake", "blueprint", "research findings" and "Shared case for all materials".',
                      first.task)
        self.assertIn('Your inputs are "intake", "blueprint", "research findings", '
                      '"Shared case for all materials" and "earlier levels".', second.task)
        self.assertEqual(self.workers.jobs[-3][2]['inputs'][-1]['name'], 'earlier levels')
        self.assertEqual(self.workers.of('brief')[1].guidance,
                         pipeline.briefs.guidance('brief', level='201', kind='product'))
        for name in ('document.md', 'product-brief.md', 'scenario.md', 'blueprint.md'):
            self.assertTrue((root / '101' / name).is_file() and (root / '201' / name).is_file())
        view = self.view(root)
        self.assertEqual((view['state'], view['finished']['ready']), ('done', True))
        self.assertEqual(workspace.status(root)['level'], '201')

    def test_the_level_being_worked_on_is_recorded_through_the_core(self):
        self.pause_after('document')
        root = self.start(levels=['101', '301'])
        self.assertEqual(workspace.status(root)['level'], '101')
        self.pause_after('document')
        self.engine.act(root, 'resume')
        status = workspace.status(root)
        self.assertEqual((status['level'], status['stage']), ('301', 'document'))

    def test_earlier_levels_are_given_to_a_guide_as_what_to_assume(self):
        root = self.start(levels=['101', '201'])
        found = pipeline.survey(root, self.record(root))
        step = next(step for step in found.steps if step.id == 'document@201')
        given = pipeline.document_work(root, found, step, None, None, []).prepared['inputs']
        self.assertEqual(given['earlier levels'], (
            '## Level 101\n\nAssume the reader can already:\n\n'
            '- Describe what a rolling restart does\n'
            '- Explain when a rolling restart keeps capacity\n'
            '- Handle the objection that rolling restarts guarantee zero downtime\n'))


class WorkerTests(FlowCase):
    """What each of the new jobs is told and given, and that it is given nothing else."""

    def setUp(self):
        super().setUp()
        self.root = self.start(yoodli=True)
        self.to_end(self.root)
        self.briefs_ready(self.root)   # a Yoodli layout waits for the brief's copy
        self.jobs = {kind: (job, spec) for kind, job, spec in self.workers.jobs}

    def given(self, kind: str) -> list[str]:
        return [entry['name'] for entry in self.jobs[kind][1]['inputs']]

    def test_every_job_is_a_writer_with_no_web_and_only_the_worker_tools(self):
        for kind in ('document', 'brief', 'scenario', 'yoodli'):
            job, spec = self.jobs[kind]
            self.assertEqual((job.profile, spec['fetch'], spec['finding'], spec['ask']),
                             ('write', False, None, True), kind)
            self.assertEqual(list(spec['artifacts']), [kind])
            self.assertIn('Topic: Rolling restarts on the platform', job.task)
            self.assertIn(f'with submit_artifact under the name "{kind}".', job.task)
            self.assertNotIn(self.space.repo, job.folder.parents)

    def test_the_guide_is_written_from_the_blueprint_and_the_research(self):
        job, spec = self.jobs['document']
        self.assertEqual(self.given('document'), ['intake', 'blueprint', 'research findings',
                                                 'Shared case for all materials'])
        self.assertEqual(spec['artifacts']['document'], {'kind': 'document',
                                                         'blueprint': BLUEPRINT})
        self.assertEqual(job.guidance, pipeline.briefs.guidance('document'))
        self.assertIn('Write the learner guide for this training.', job.task)

    def test_the_brief_is_written_as_the_kind_the_training_asked_for(self):
        job, spec = self.jobs['brief']
        self.assertEqual(self.given('brief'), ['intake', 'blueprint', 'research findings'])
        self.assertEqual(spec['artifacts']['brief'], {
            'kind': 'brief', 'brief_kind': 'product', 'findings': {
                'availability': 'supported', 'instance-min': 'supported',
                'health-checks': 'supported', 'zero-downtime': 'supported'}})
        self.assertEqual(job.guidance, pipeline.briefs.guidance('brief', kind='product'))
        self.assertIn('Write the brief for this training. It is a product brief.', job.task)

    def test_a_scenario_is_drafted_from_the_practice_plan_the_brief_and_its_mode(self):
        job, spec = self.jobs['scenario']
        self.assertEqual(self.given('scenario'), ['intake', 'blueprint', 'Shared case for all materials', 'brief',
                                                  'mode reference'])
        self.assertEqual(spec['artifacts']['scenario'],
                         {'kind': 'scenario', 'label': 'scenario:main', 'mode': 'roleplay'})
        self.assertEqual(job.guidance, pipeline.briefs.guidance('scenario'))
        self.assertIn('Scenario ID: main\nMode: roleplay\nThe practice plan says of it: '
                      'roleplay. Objectives: O1, O2, O3. A sceptical platform lead', job.task)

    def test_the_yoodli_facts_a_worker_reads_come_from_the_profile(self):
        profile = helpers.SKILL / 'assets' / 'profiles' / 'yoodli.json'
        facts = pipeline.yoodli_facts(home.read_json(profile, None))
        for said in ('Types: Custom, Tutor, Pitch, Objection Handling, Questionnaire, '
                     'Interview.', 'roleplay is Objection Handling',
                     'Persona fields: Name, Role, Demeanor, Background, Behaviors.',
                     'Types that need a persona: Objection Handling, Pitch.',
                     '- Context: 10,000 characters', '- Personas: 3',
                     "- A goal's Explanation: 2,500 characters",
                     'These limits and the field names are provisional.',
                     '- It takes up to 5 files and 1 public address.',
                     '- It cannot create new custom goals.',
                     '- It creates new roleplays only.',
                     '- Custom goals: An organisation on an Enterprise plan.',
                     "- Strict mode uses more of the roleplay's capacity.",
                     '- A PDF can also be shown to the learner.'):
            self.assertIn(said, facts)
        self.assertIn('# Yoodli field data', pipeline.yoodli_facts({}),
                      'a profile that cannot be read still gives the worker a page')


class YoodliTests(FlowCase):
    def test_with_yoodli_each_approved_scenario_is_laid_out_and_put_to_the_person(self):
        root = self.start(yoodli=True)
        self.assertEqual(self.to_end(root), [])
        self.all_ready(root)
        self.assertEqual(self.kinds(4), ['document', 'brief', 'scenario', 'yoodli'])
        ids = [step['id'] for step in self.view(root)['steps']]
        self.assertEqual(ids[9:], [
            'document', 'gate:document', 'brief', 'gate:brief', 'copies:brief',
            'scenario:main', 'gate:scenario:main', 'yoodli:main', 'gate:yoodli:main',
            'copies:yoodli:main', 'package'])
        view = self.view(root)
        self.assertEqual([(entry['artifact'], entry['kind'], entry['state'], entry['link'])
                          for entry in view['copies']], [
            ('brief', 'word', 'made', 'product-brief.docx'),
            ('yoodli:main', 'word', 'made', 'yoodli/main.docx')])
        self.assertEqual(view['finished'], {
            'ready': True, 'limitations': ['The deck stage was left out'], 'blocking': [],
            'index': 'README.md', 'yoodli': [{'artifact': 'yoodli:main',
                'label': workspace.label('yoodli:main'),
                'text': (root / 'yoodli/main.md').read_text()}]})
        self.assertEqual(assess.run_checks(root)['practice']['basis'], 'Yoodli goals')

    def test_a_yoodli_layout_is_written_once_the_brief_has_a_copy_to_name(self):
        # GitHub issue #549: the desk makes a copy of a material only once it is Ready, so a
        # layout written before that was told no copy of the brief existed. It waits for the
        # brief's copy, as it followed the brief's approval and copies in the earlier flow.
        from runner import drafts
        root = self.start(yoodli=True)
        self.assertEqual(self.workers.of('yoodli'), [], 'nothing is laid out yet')
        self.assertFalse((root / 'yoodli' / 'main.md').exists())
        card = next(card for card in drafts.view(self.engine, root)['cards']
                    if card['name'] == 'yoodli:main')
        self.assertEqual((card['state'], card['says']), ('queued', drafts.HANDOFF_WAITS.format(
            brief='the brief')))
        session = workspace.load(root)
        brief = workspace.artifact(root, session, 'brief')['file']
        self.engine.mark_ready(root, 'brief', workspace.sha256_file(root / brief))
        task = self.workers.of('yoodli')[0].task
        self.assertIn('The copy of the brief to upload is its Word file, product-brief.docx.',
                      task)
        self.assertNotIn('No copy of the brief', task)
        self.assertTrue((root / 'yoodli' / 'main.md').is_file())

    def test_a_brief_sent_to_its_copies_lets_the_layout_name_that_copy(self):
        root = self.start(yoodli=True)
        self.engine.send_copy(root, 'brief')
        self.assertIn('The copy of the brief to upload is its Word file, product-brief.docx.',
                      self.workers.of('yoodli')[0].task)

    def test_a_copy_that_cannot_be_made_is_said_to_the_layout_with_why(self):
        # As in the earlier flow: once the brief's copy was tried and could not be made, the
        # layout is written and told why, so the person knows the handoff is incomplete.
        self.copies.refuse['word'] = 'This computer has no converter for Word files.'
        root = self.start(yoodli=True)
        session = workspace.load(root)
        brief = workspace.artifact(root, session, 'brief')['file']
        self.engine.mark_ready(root, 'brief', workspace.sha256_file(root / brief))
        self.assertIn('No copy of the brief is ready to upload: This computer has no '
                      'converter for Word files.', self.workers.of('yoodli')[0].task)

    def test_without_yoodli_no_scenario_is_laid_out(self):
        root = self.start()
        self.to_end(root)
        self.assertEqual(self.workers.of('yoodli'), [])
        self.assertNotIn('yoodli:main', workspace.status(root)['artifacts'])


class DeckTests(FlowCase):
    def test_no_deck_on_the_form_leaves_the_deck_out_through_the_core(self):
        root = self.start()
        session = workspace.load(root)
        self.assertNotIn('deck', session['settings']['stages'])
        skipped = [event for event in session['events'] if event['event'] == 'skip']
        self.assertEqual([(event['stage'], event['reason'], event['by']) for event in skipped],
                         [('deck', 'No deck was chosen when this training was started.',
                           'page')])
        self.assertEqual(workspace.status(root)['artifacts']['deck'], 'skipped')
        self.assertNotIn('deck', [step['id'] for step in self.view(root)['steps']])

    def test_a_deck_that_is_there_but_not_approved_is_said_to_need_finishing(self):
        root = self.start(deck_target='pptx')
        self.to_end(root)
        (root / 'deck.pptx').write_bytes(b'PK\x03\x04 a deck made in a conversation\n')
        self.assertEqual(self.view(root)['deck_left']['says'], left(pipeline.DECK_AGAIN))
        self.assertIn('Put that right and check this computer again, or leave the deck out.',
                      left(pipeline.DECK_AGAIN))


class LeftOutTests(FlowCase):

    def test_a_training_whose_blueprint_plans_no_practice_is_not_ready_and_says_why(self):
        self.workers.blueprint_text = BLUEPRINT.partition('## Practice plan')[0] \
            + '## Open gaps' + BLUEPRINT.partition('## Open gaps')[2]
        root = self.start()
        self.assertEqual(self.to_end(root), [])
        self.all_ready(root)
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence']), (
            'done', 'Everything is made, but this training is not ready yet: 1 thing is in '
            'the way.'))
        self.assertEqual((view['finished']['ready'], view['finished']['blocking']),
                         (False, ['No scenario file found.']))
        self.assertEqual(self.workers.of('scenario'), [], 'only a scenario the practice '
                         'plan names is drafted')



class RequestTests(FlowCase):
    """Asking for changes or a rebuild at the new gates works as it does at gates 1 to 3."""

    def test_a_worker_on_a_later_stage_can_ask_the_person_a_question(self):
        self.workers.then('brief', asks('Which product is the brief about?'))
        self.pause_after('brief', later=True)
        root = self.start()
        asked = self.view(root)['question']
        self.assertEqual(asked['from'], 'The worker writing the brief')
        self.engine.answer(root, asked['id'], 'The platform itself.')
        self.assertEqual(self.state(root), 'paused')
        self.assertIn('Answer: The platform itself.', self.workers.of('brief')[1].task)


class LaterChangeTests(FlowCase):
    """An earlier approval that changes, and what is done again because of it."""

    def test_a_setting_that_changes_has_what_uses_it_made_again(self):
        root = self.start()
        self.to_end(root)
        workspace.checkpoint(root, brief_kind='competitive')
        self.assertEqual(workspace.status(root)['artifacts']['brief'], 'not-started')
        self.workers.then('brief', asks('Which two platforms does it compare?'))
        self.engine.wake(root)
        self.assertEqual(self.workers.of('brief')[1].guidance,
                         pipeline.briefs.guidance('brief', kind='competitive'))
        self.assertEqual(self.view(root)['question']['text'],
                         'Which two platforms does it compare?')


class OwnScenarioTests(FlowCase):
    """A scenario file the person wrote: used as it is, and laid out only on request."""

    def own(self, root: Path, text: str = OWN, name: str = 'scenario.md') -> Path:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def test_a_training_with_no_run_cannot_say_whose_a_scenario_is(self):
        self.assertIsNone(self.engine.whose(self.base / 'elsewhere', 'scenario:main'))


class CopiesTests(FlowCase):
    def shown(self, root: Path) -> dict:
        return {(entry['artifact'], entry['kind']): entry
                for entry in self.view(root)['copies']}

    def test_a_training_that_asked_for_no_copies_has_no_copies_steps(self):
        root = self.start()
        self.to_end(root)
        self.assertEqual((self.view(root)['copies'], self.copies.calls), ([], 0))
        self.assertEqual([step for step in self.steps(root) if step.startswith('copies:')],
                         [])

    def test_a_copy_that_cannot_be_made_says_why_and_never_holds_the_run_up(self):
        self.copies.refuse.update(
            google='Google access is not set up on this computer.',
            word='This computer has no converter for Word files.')
        root = self.start(copies=['google', 'word'])
        self.all_ready(root)
        made = self.shown(root)
        self.assertEqual((made['document', 'google']['state'],
                          made['document', 'google']['problem'],
                          made['document', 'word']['state'],
                          made['document', 'word']['problem']),
                         ('not-made', 'Google access is not set up on this computer.',
                          'not-made', 'This computer has no converter for Word files.'))
        self.assertEqual(self.steps(root)['copies:document']['status'], 'done')
        self.assertEqual(self.record(root)['copies']['problems'],
                         {'document': 'Google access is not set up on this computer.',
                          'brief': 'Google access is not set up on this computer.'})
        self.assertEqual((self.state(root), self.view(root)['problem']), ('done', None))
        calls = self.copies.calls
        self.engine.wake(root)
        self.assertEqual(self.copies.calls, calls, 'it is not tried again until asked')
        self.to_end(root)
        view = self.view(root)
        self.assertEqual((view['state'], view['finished']['ready']), ('done', True))
        self.assertIn('The learner guide is not in a Google Doc',
                      view['finished']['limitations'])

    def test_trying_the_copies_again_makes_those_that_were_not_made(self):
        self.copies.refuse['google'] = 'Google access is not set up on this computer.'
        root = self.start(copies=['google'])
        self.to_end(root)
        self.all_ready(root)
        self.assertEqual({entry['state'] for entry in self.view(root)['copies']},
                         {'not-made'})
        self.assertNotIn('docs.example.com', (root / 'README.md').read_text())
        self.copies.refuse.clear()
        after = self.engine.copies_again(root)
        self.assertEqual([(entry['state'], entry['problem']) for entry in after['copies']],
                         [('made', None), ('made', None)])
        self.assertEqual(after['finished']['limitations'], ['The deck stage was left out'])
        self.assertEqual(after['sentence'],
                         'This training is finished, with 1 thing left out or limited.')
        self.assertIn('docs.example.com', (root / 'README.md').read_text(),
                      'the index lists the copies, so it is written again')
        self.assertEqual(self.log()[-1],
                         'Rolling restarts: make the copies again, as asked on the page')
        self.assertEqual(self.git('status', '--porcelain'), '')
        with self.assertRaisesRegex(WorkspaceError, 'No run is driving this training'):
            self.engine.copies_again(self.base / 'elsewhere')


class DocumentTests(FlowCase):
    """Research from documents the person supplies."""

    def test_a_training_from_the_persons_documents_waits_for_them_first(self):
        root = self.start(source_scope='supplied-only')
        view = self.view(root)
        self.assertEqual((view['state'], view['sentence'], self.workers.jobs), (
            'waiting', 'Add your documents, then say that is all of them. Nothing is '
            'researched until you do. This training is researched from them alone.', []))
        self.assertEqual(view['documents'], {
            'waiting': True, 'added': [],
            'types': ['.txt', '.md', '.html', '.htm', '.docx'],
            'limits': {'bytes': 8_000_000, 'files': 40},
            # Where documents are kept is the page's to say; this is only what it cannot know.
            'note': 'This computer cannot read a PDF: save it as text or as a Word file '
                    'first.'})
        step = view['steps'][1]
        self.assertEqual((step['id'], step['kind'], step['status'], step['label']),
                         ('documents', 'gate', 'waiting', 'Add your documents'))
        self.assertEqual(self.engine.brief(root)['needs'], True)
        self.assertIn('## Source scope\n\nYour documents only\n',
                      (root / 'intake.md').read_text())
        self.assertEqual(self.record(root)['documents'],
                         {'scope': 'supplied-only', 'done': None, 'count': 0})
        self.engine.wake(root)
        self.assertEqual(self.workers.jobs, [])

    def test_a_training_from_the_public_web_takes_no_documents(self):
        root = self.start()
        self.assertIsNone(self.view(root)['documents'])
        self.assertIsNone(self.record(root)['documents'])
        with self.assertRaisesRegex(WorkspaceError, engine_module.NO_DOCUMENTS):
            self.send(root, 'handbook.txt')
        with self.assertRaisesRegex(WorkspaceError, 'A document can be: add, remove, done, update'):
            self.engine.supply(root, 'replace', 'handbook.txt')
        with self.assertRaisesRegex(WorkspaceError, 'No run is driving this training'):
            self.engine.supply(self.base / 'elsewhere', 'done')

    def test_documents_are_added_shown_and_removed_until_the_person_says_that_is_all(self):
        root = self.start(source_scope='supplied-only')
        after = self.send(root, 'handbook.txt')
        self.assertEqual(after['documents']['added'], [
            {'name': 'handbook.txt', 'bytes': 60, 'readable': True, 'problem': None}])
        after = self.send(root, 'slides.docx')
        self.assertEqual(after['documents']['added'][1], {
            'name': 'slides.docx', 'bytes': 60, 'readable': False,
            'problem': 'slides.docx could not be read. Save it as text and add it again.'})
        for name, said in (('handbook.txt', 'was already added'),
                           ('notes.pdf', 'not a kind of document that can be read here'),
                           ('../outside.txt', 'a plain file name')):
            with self.assertRaisesRegex(WorkspaceError, said):
                self.send(root, name)
        self.assertEqual(self.git('status', '--porcelain'), '',
                         'the documents themselves are never shared')
        after = self.engine.supply(root, 'remove', 'slides.docx')
        self.assertEqual([entry['name'] for entry in after['documents']['added']],
                         ['handbook.txt'])
        self.assertEqual((after['documents']['waiting'], after['state'], self.workers.jobs),
                         (True, 'waiting', []))

        self.pause_after('research-result')
        done = self.engine.supply(root, 'done')
        self.assertEqual((done['documents']['waiting'], done['state'], done['sentence']),
                         (False, 'paused', 'Paused. Nothing new starts until you resume.'))
        self.assertEqual(self.steps(root)['documents']['status'], 'done')
        self.assertIn('Rolling restarts: the documents are all added: 1 to research from',
                      self.log())
        with self.assertRaisesRegex(WorkspaceError, 'cannot be removed now'):
            self.engine.supply(root, 'remove', 'handbook.txt')
        with self.assertRaisesRegex(WorkspaceError, 'all added already'):
            self.engine.supply(root, 'done')

    def test_the_writers_of_a_blueprint_are_offered_the_documents_and_a_guide_is_not(self):
        root = self.start(source_scope='supplied-only')
        self.send(root, 'handbook.txt')
        self.engine.supply(root, 'done')
        jobs = {kind: (job, spec) for kind, job, spec in self.workers.jobs}
        job, spec = jobs['blueprint']
        self.assertIn(pipeline.DOCUMENTS + pipeline.SPECIFICS, job.task)
        job, spec = jobs['document']
        self.assertNotIn(pipeline.DOCUMENTS, job.task)

    def test_a_web_only_training_still_takes_no_documents(self):
        root = self.start()
        with self.assertRaises(WorkspaceError) as refused:
            self.send(root, 'more.txt')
        self.assertEqual(str(refused.exception), engine_module.NO_DOCUMENTS)

    def test_research_from_documents_alone_needs_one_that_can_be_read(self):
        root = self.start(source_scope='supplied-only')
        self.send(root, 'slides.docx')
        with self.assertRaisesRegex(WorkspaceError, 'Add at least one document that can be '
                                    'read first. This training is researched from your '
                                    'documents only.'):
            self.engine.supply(root, 'done')
        self.assertEqual((self.view(root)['documents']['waiting'], self.workers.jobs),
                         (True, []))

    def test_with_the_web_as_well_no_document_at_all_is_an_answer(self):
        root = self.start(source_scope='both')
        self.pause_after('research-plan')
        done = self.engine.supply(root, 'done')
        self.assertEqual((done['documents']['waiting'], done['state']), (False, 'paused'))
        self.assertIn('Sources that may be used: the public web.\n',
                      self.workers.jobs[0][1].task)
        self.assertIn('Rolling restarts: no documents were added; research uses the public '
                      'web', self.log())

    def test_a_computer_that_can_read_a_pdf_takes_one(self):
        self.documents.pdf = True
        root = self.start(source_scope='both')
        shown = self.view(root)['documents']
        self.assertIn('.pdf', shown['types'])
        self.assertNotIn('PDF', shown['note'])


if __name__ == '__main__':
    import unittest
    unittest.main()
