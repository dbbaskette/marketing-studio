"""Ready as a deliberate, reversible decision on the Training Studio desk (issue #252).

Mark this level ready is confirmed in a sheet that names each material and what the Document
Library keeps; Undo on its toast and Return to draft on a card bring a material back to
Draft, bound to the version shown, without removing any library revision; an edit to a Ready
material is said before and after; and the topics review is the one thing Home reports
while it is open.

The tests named row_200 to row_204 cover those rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md. Every library is a
disposable folder (STUDIOS_LIBRARY, set by runner_support), every worker is scripted, and the
page journeys run the page's own scripts in page_harness.js against answers the real runner
gave. Nothing reaches Google, an assistant or the network.
"""
import copy
import json
import unittest
from urllib.parse import urlencode

import helpers  # noqa: F401  puts the runner on the import path
import workspace
import test_desk as page_tests
from test_runner_deck import PageCase

from runner import drafts, library
from studio_core import document_library

KEPT = ('document', 'brief')


class ReadyCase(PageCase):
    """A desk training with a plan, a learner guide and a brief, all written and drafts."""

    def setUp(self):
        super().setUp()
        self.root = self.start(materials=['document', 'brief'])
        self.assertEqual(self.to_end(self.root), [])
        self.path = str(self.root)

    def desk(self) -> dict:
        return self.get('drafts', path=self.path)

    def cards(self, desk: dict | None = None) -> dict:
        return {card['name']: card for card in (desk or self.desk())['cards']}

    def approvals(self) -> dict:
        """Each material's approval entry as the session keeps it."""
        session = workspace.load(self.root)
        return {name: copy.deepcopy((session['artifacts'].get(name) or {}).get('approved'))
                for name in workspace.artifact_names(self.root, session)}

    def person(self) -> dict:
        return workspace.person_statuses(self.root, workspace.load(self.root))

    def shelf(self) -> dict:
        """What the shared library holds of this training: each document's title and
        revision, read from the library itself."""
        found = document_library.opened()
        if found is None:
            return {}
        rows = found.catalog(kind='training')['items']
        return {row['title']: row['revision'] for row in rows}

    def seen(self, *names) -> dict:
        cards = self.cards()
        return {name: cards[name]['seen'] for name in names}

    def guide(self) -> str:
        return next(name for name, card in self.cards().items() if card['kind'] == 'document')

    def drafted(self) -> list[str]:
        return [name for name, card in self.cards().items() if card['state'] == 'draft']


class ReadyTests(ReadyCase):

    def test_row_200_marking_a_level_marks_only_the_versions_named(self):
        before = self.approvals()
        names = self.drafted()
        self.assertTrue(any(name.startswith('blueprint') for name in names))
        marked = self.post('drafts/level-ready', {'path': self.path, 'level': '',
                                                  'seen': self.seen(*names)})
        self.assertEqual(sorted(marked['marked']), sorted(names))
        self.assertIsNone(marked['stopped'])
        self.assertEqual({card['state'] for card in marked['cards']}, {'ready'})
        # The guide and the brief are kept in the library, each as revision 1.
        self.assertEqual(sorted(self.shelf().values()), [1, 1])
        self.assertEqual({marked['library'][name]['state'] for name in marked['library']},
                         {'kept'})
        # Each Ready card now offers its way back.
        self.assertTrue(all('draft' in card['actions'] for card in marked['cards']))

    def test_row_200_a_material_whose_version_was_not_named_is_not_marked(self):
        before = self.approvals()
        plan = next(name for name in self.drafted() if name.startswith('blueprint'))
        marked = self.post('drafts/level-ready', {'path': self.path, 'level': '',
                                                  'seen': self.seen(plan)})
        self.assertEqual(marked['marked'], [plan])
        self.assertIn('has changed since it was opened', marked['stopped']['said'])
        self.assertEqual({name for name, entry in self.approvals().items()
                          if entry != before[name]}, {plan})
        self.assertEqual(self.shelf(), {})

    def test_row_201_undo_restores_the_earlier_states_exactly(self):
        before, statuses, names = self.approvals(), self.person(), self.drafted()
        seen = self.seen(*names)
        self.post('drafts/level-ready', {'path': self.path, 'level': '', 'seen': seen})
        kept = self.shelf()
        self.assertEqual(len(kept), 2)
        undone = self.post('drafts/draft', {'path': self.path, 'seen': seen})
        self.assertEqual(sorted(undone['returned']), sorted(names))
        # Every approval and every state is what it was before Mark ready.
        self.assertEqual(self.approvals(), before)
        self.assertEqual(self.person(), statuses)
        self.assertEqual({card['state'] for card in undone['cards']}, {'draft'})
        # The library keeps both revisions, and the desk says so of each.
        self.assertEqual(self.shelf(), kept)
        for name in names:
            if name.partition('@')[0].partition(':')[0] in KEPT:
                self.assertEqual(undone['library'][name], {'state': 'earlier', 'revision': 1})
        # Marked ready again with the same words, no revision is added.
        again = self.post('drafts/level-ready', {'path': self.path, 'level': '', 'seen': seen})
        self.assertEqual(sorted(again['marked']), sorted(names))
        self.assertEqual(self.shelf(), kept)
        self.assertIn('Rolling restarts: return 3 materials to draft', self.log())

    def test_row_202_return_to_draft_is_bound_to_the_version_shown(self):
        guide = self.guide()
        seen = self.seen(guide)
        self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': seen[guide]})
        kept = self.shelf()
        commits = self.log()
        # Another version than the one shown, or one that is not Ready, changes nothing.
        refused = self.post('drafts/draft', {'path': self.path, 'seen': {guide: 'f' * 64}},
                            expect=409)
        self.assertIn('has changed since it was opened', refused['error'])
        plan = next(name for name in self.drafted() if name.startswith('blueprint'))
        refused = self.post('drafts/draft', {'path': self.path, 'seen': {
            guide: seen[guide], **self.seen(plan)}}, expect=409)
        self.assertIn('is a draft already', refused['error'])
        self.post('drafts/draft', {'path': self.path, 'seen': 'not a map'}, expect=400)
        self.assertEqual(self.cards()[guide]['state'], 'ready')
        self.assertEqual(self.log(), commits)
        # The version shown returns to draft; the library keeps revision 1 and says so.
        returned = self.post('drafts/draft', {'path': self.path, 'seen': seen})
        card = self.cards(returned)[guide]
        self.assertEqual((card['state'], 'draft' in card['actions'], 'ready' in card['actions']),
                         ('draft', False, True))
        self.assertEqual(returned['library'][guide], {'state': 'earlier', 'revision': 1})
        self.assertEqual(self.shelf(), kept)
        self.assertEqual(self.log()[-1], 'Rolling restarts: return the learner guide to draft')
        # Its review file says what was decided.
        reviews = (self.root / workspace.review_file(guide)).read_text(encoding='utf-8')
        self.assertIn('Decision: returned to draft on the page', reviews)

    def test_row_202_a_name_that_is_not_a_desk_material_refuses_before_any_change(self):
        guide = self.guide()
        seen = self.seen(guide)
        self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': seen[guide]})
        session = workspace.load(self.root)
        intake = workspace.sha256_file(
            self.root / workspace.artifact(self.root, session, 'intake')['file'])
        approvals, commits = self.approvals(), self.log()
        refused = self.post('drafts/draft', {'path': self.path, 'seen': {
            guide: seen[guide], 'intake': intake}}, expect=409)
        self.assertEqual(refused['error'], drafts.NOTHING_TO_RETURN)
        self.assertEqual(self.cards()[guide]['state'], 'ready')
        self.assertEqual(self.approvals(), approvals)
        self.assertEqual(self.log(), commits)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_return_to_draft_without_the_mark_it_undoes_stays_accepted_on_the_desk(self):
        guide = self.guide()
        seen = self.seen(guide)
        self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': seen[guide]})
        record = self.record(self.root)
        record['drafts'].pop('marked')
        (self.root / '.training-studio' / 'run.json').write_text(json.dumps(record))
        self.post('drafts/draft', {'path': self.path, 'seen': seen})
        approved = self.approvals()[guide]
        self.assertEqual((approved['by'], approved['sha256']), ('desk', seen[guide]))
        self.assertEqual(self.person()[guide], 'draft')
        # What is built from it is not held: an edit leaves it the same way.
        self.assertFalse(any(card['state'] == 'held' for card in self.desk()['cards']))

    def test_row_203_an_edit_to_a_ready_guide_keeps_the_library_wording_true(self):
        guide = self.guide()
        seen = self.seen(guide)
        self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': seen[guide]})
        self.assertEqual(self.desk()['library'][guide], {'state': 'kept', 'revision': 1})
        shown = self.get('drafts/card', path=self.path, name=guide)
        part = shown['sections'][0]
        saved = self.post('drafts/save', {'path': self.path, 'name': guide, 'part': part['id'],
                                          'seen': shown['revision'],
                                          'text': part['text'] + '\n\nOne more line.\n'})
        desk = saved['desk']
        self.assertEqual(self.cards(desk)[guide]['state'], 'draft')
        self.assertEqual(desk['library'][guide], {'state': 'earlier', 'revision': 1})
        self.assertEqual(list(self.shelf().values()).count(1), 1)
        # Marked ready again, the changed words are a new revision; the first is kept too.
        now = self.cards()[guide]['seen']
        ready = self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': now})
        self.assertEqual(ready['library'][guide], {'state': 'kept', 'revision': 2})
        held = document_library.opened()
        kept = library.status(self.root)['materials'][guide]
        self.assertEqual(held.describe(kept['document'])['revision'], 2)
        self.assertEqual(held.preview(kept['document'], revision=1)['text'].count('One more line.'),
                         0)


class TopicsTests(PageCase):
    def test_row_204_home_reports_only_the_topics_decision(self):
        self.engine.plan_first = True
        root = self.begin(flow='desk')
        told = drafts.standing(self.engine, root)
        self.assertEqual(told['next']['kind'], 'plan')
        self.assertEqual(told['sentence'], drafts.PLAN_WAITS)
        self.assertNotIn('mark ready', told['sentence'])
        item = next(item for item in self.get('trainings')['trainings']
                    if item['path'] == str(root))
        self.assertEqual((item['sentence'], item['to_review']), (drafts.PLAN_WAITS, 0))


# --- the page, run for real against the runner's own answers ---------------------------

class RunnerAnswers(page_tests.ScriptedPage):
    """The page's answers read from the real runner page, as `ScriptedPage.read` asks."""

    origin = f'http://127.0.0.1:{PageCase.PORT}'

    def answer(self, method, target, body=None, **options):
        status, _, reply = self.ask(method, target, None if body is None else json.loads(body))
        return status, reply, None

    def screens(self, **more) -> dict:
        """What every screen of the runner's page asks for first."""
        listed = self.read('trainings')
        return {'GET /api/capabilities': [page_tests.RUNNER],
                'GET /api/setup': [page_tests.ok(page_tests.SET_UP)],
                'GET /api/trainings': [listed], 'GET /api/computer': [self.read('computer')],
                'GET /api/agents': [page_tests.ok(page_tests.AGENTS_FOUND)],
                **page_tests.MODELS, **more}


@unittest.skipUnless(page_tests.NODE, 'Node is needed to run the page scripts')
class TopicsJourneyTests(RunnerAnswers, PageCase):
    def test_row_204_home_names_the_training_and_says_only_the_topics_decision(self):
        self.engine.plan_first = True
        first = self.begin(flow='desk')
        second = self.begin(flow='desk', title='Capacity planning')
        self.root = first   # the page's plan is written beside it
        listed = {item['path']: item for item in self.get('trainings')['trainings']}
        self.assertEqual({listed[str(root)]['state'] for root in (first, second)}, {'needs-you'})
        result = self.run_page(self.screens(), [{'snapshot': 'home'}])
        home = result['snapshots']['home']
        self.assertEqual(len(home['filled']), 1)
        self.assertRegex(home['filled'][0],
                         r'^Review the teaching plan for (Rolling restarts|Capacity planning)$')
        self.assertEqual(home['text'].count(drafts.PLAN_WAITS), 2)
        self.assertNotIn('to mark ready', home['text'])


@unittest.skipUnless(page_tests.NODE, 'Node is needed to run the page scripts')
class ReadyJourneyTests(RunnerAnswers, ReadyCase):
    """Each journey reads the desk from the real runner, runs the page in page_harness.js,
    then makes the same requests of the runner that the page made and checks what the
    Document Library holds. A journey's answers are what the runner gave for them."""

    def card_answers(self) -> dict:
        """Each material's editor, by the address the page asks it at."""
        found = {}
        for name in self.cards():
            address = '/api/drafts/card?' + urlencode({'path': self.path, 'name': name})
            found['GET ' + address] = [self.read('drafts/card', path=self.path, name=name)]
        return found

    def shell(self, **more) -> dict:
        return self.screens(**{'GET /api/run': [self.read('run', path=self.path)],
                               'GET /api/drafts': [self.read('drafts', path=self.path)],
                               **self.card_answers(), **more})

    def journey(self, answers, steps, **plan):
        return self.run_page(answers, steps, state={'screen': 'run', 'path': self.path}, **plan)

    def posts(self, result) -> list:
        return [(request['address'], request['body']) for request in result['requests']
                if request['method'] == 'POST']

    def test_row_200_the_sheet_names_each_material_and_cancel_changes_nothing(self):
        commits, shelf = self.log(), self.shelf()
        result = self.journey(self.shell(), [
            {'click': 'Mark every material ready'}, {'snapshot': 'sheet'},
            {'click': 'Cancel'}, {'snapshot': 'cancelled'},
            # Read here, the guide is opened in the version shown; Escape changes nothing too.
            {'click': 'Guide · Draft'}, {'click': 'Mark every material ready'},
            {'snapshot': 'read'}, {'key': 'Escape'}, {'snapshot': 'escaped'}])
        sheet = result['snapshots']['sheet']
        self.assertIn('Mark every material ready?', sheet['sheet'])
        self.assertIn('Ready is your approval of the version you read.', sheet['sheet'])
        # The plan is shown when the desk opens; the guide and brief are not.
        for words in ('Plan\nOpened', 'Guide\nNot opened yet', 'Brief\nNot opened yet',
                      'Not opened yet: Guide and Brief.',
                      'Guide and Brief are kept in the Document Library as Markdown'):
            self.assertIn(words, sheet['sheet'])
        self.assertEqual(sheet['filled'], ['Mark 3 materials ready'])
        buttons = sheet['buttons']
        self.assertEqual(buttons[buttons.index('Mark 3 materials ready') + 1], 'Cancel')
        cancelled = result['snapshots']['cancelled']
        self.assertEqual(cancelled['sheet'], '')
        self.assertEqual(cancelled['focus'], 'Mark every material ready')
        read = result['snapshots']['read']['sheet']
        for words in ('Guide\nOpened', 'Not opened yet: Brief.'):
            self.assertIn(words, read)
        self.assertEqual(result['snapshots']['escaped']['sheet'], '')
        self.assertEqual(result['snapshots']['escaped']['focus'], 'Mark every material ready')
        self.assertEqual(self.posts(result), [])
        self.assertEqual((self.log(), self.shelf()), (commits, shelf))

    def test_row_201_confirm_then_undo_restores_everything_and_keeps_the_library(self):
        before, names = self.approvals(), self.drafted()
        seen = self.seen(*names)
        sent = {'path': self.path, 'level': '', 'seen': seen}
        # What the runner answers to exactly what the page sends, made before it runs.
        answers = self.shell()
        answers['POST /api/drafts/level-ready'] = [self.read_post('drafts/level-ready', sent)]
        kept = self.shelf()
        answers['POST /api/drafts/draft'] = [self.read_post('drafts/draft',
                                                            {'path': self.path, 'seen': seen})]
        # On a phone the toolbar's words are short, and the name says what it marks.
        result = self.journey(answers, [
            {'click': 'Mark all ready'}, {'click': 'Mark 3 materials ready'},
            {'snapshot': 'marked'}, {'click': 'Undo'}, {'snapshot': 'undone'},
            # The toast's leaving, later, never takes the focus Undo put back.
            {'timer': 'gone'}, {'snapshot': 'gone'}], narrow=True)
        self.assertEqual(self.posts(result), [('/api/drafts/level-ready', sent),
                                              ('/api/drafts/draft', {'path': self.path,
                                                                     'seen': seen})])
        shot = result['snapshots']['marked']
        self.assertIn('3 materials are marked ready. Guide and Brief are kept in the Document '
                      'Library. Undo', shot['toasts'])
        self.assertNotIn('Mark all ready', shot['buttons'])
        self.assertEqual(shot['focus'], 'Undo')
        shot = result['snapshots']['undone']
        self.assertIn('Undone. 3 materials are drafts again. The Document Library keeps '
                      'revision 1 of Guide until you mark it ready again. The Document Library '
                      'keeps revision 1 of Brief until you mark it ready again.', shot['toasts'])
        self.assertIn('Mark all ready', shot['buttons'])
        self.assertEqual(shot['focus'], 'Mark all ready')
        self.assertEqual(result['snapshots']['gone']['focus'], 'Mark all ready')
        self.assertEqual(self.approvals(), before)
        self.assertEqual(self.shelf(), kept)
        self.assertEqual(len(kept), 2)

    def test_row_201_undo_leaves_with_its_desk(self):
        seen = self.seen(*self.drafted())
        answers = self.shell()
        answers['POST /api/drafts/level-ready'] = [self.read_post(
            'drafts/level-ready', {'path': self.path, 'level': '', 'seen': seen})]
        result = self.journey(answers, [
            {'click': 'Mark every material ready'}, {'click': 'Mark 3 materials ready'},
            {'snapshot': 'marked'}, {'click': 'Home'}, {'snapshot': 'home'}])
        self.assertIn('Undo', result['snapshots']['marked']['buttons'])
        self.assertNotIn('Undo', result['snapshots']['home']['buttons'])
        # Leaving the desk shares what was typed, as always; nothing returns to draft.
        self.assertEqual([address for address, _ in self.posts(result)],
                         ['/api/drafts/level-ready', '/api/drafts/share'])

    def test_row_202_return_to_draft_on_a_card_says_what_the_library_keeps(self):
        guide = self.guide()
        seen = self.seen(guide)
        self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': seen[guide]})
        kept = self.shelf()
        answers = self.shell()
        answers['POST /api/drafts/draft'] = [self.read_post('drafts/draft',
                                                            {'path': self.path, 'seen': seen})]
        result = self.journey(answers, [
            {'click': 'Guide · Ready'}, {'snapshot': 'ready'}, {'click': 'Return to draft'},
            {'snapshot': 'returned'}], narrow=True)
        shot = result['snapshots']['ready']
        self.assertIn('Kept in the Document Library as Markdown, revision 1. Return to draft '
                      'leaves that revision in the library.', shot['text'])
        self.assertEqual(self.posts(result), [('/api/drafts/draft',
                                               {'path': self.path, 'seen': seen})])
        shot = result['snapshots']['returned']
        said = 'The Document Library keeps revision 1 of this guide until you mark it ready again.'
        self.assertIn('Guide is a draft again. ' + said, shot['toasts'])
        self.assertIn(said, shot['text'])
        self.assertIn('Guide · Draft', shot['buttons'])
        self.assertEqual(shot['focus'], 'Mark ready')
        self.assertEqual(self.shelf(), kept)

    def test_row_203_editing_a_ready_guide_warns_first_and_says_it_is_a_draft_after(self):
        guide = self.guide()
        seen = self.seen(guide)
        self.post('drafts/ready', {'path': self.path, 'name': guide, 'seen': seen[guide]})
        shown = self.get('drafts/card', path=self.path, name=guide)
        # The part the editor shows first: the opening, where the guide has one.
        part = ({'id': 'opening', 'heading': 'Opening', 'text': shown['opening']}
                if shown.get('opening') else shown['sections'][0])
        typed = part['text'] + ' And more.'
        answers = self.shell()
        saved = self.read_post('drafts/save', {
            'path': self.path, 'name': guide, 'part': part['id'], 'seen': shown['revision'],
            'text': typed, 'session': 'journey'})
        answers['POST /api/drafts/save'] = [saved]
        result = self.journey(answers, [
            {'click': 'Guide · Ready'}, {'click': 'Edit Guide'}, {'snapshot': 'editing'},
            {'fill': 'Text of ' + part['heading'], 'value': typed}, {'timer': 'save'},
            {'snapshot': 'saved'}])
        warning = ('Saving a change returns this guide to Draft. The Document Library keeps '
                   'revision 1 until you mark it ready again.')
        self.assertIn(warning, result['snapshots']['editing']['text'])
        self.assertEqual(result['snapshots']['editing']['posts'], 0)
        shot = result['snapshots']['saved']
        self.assertEqual([address for address, _ in self.posts(result)], ['/api/drafts/save'])
        self.assertIn('Guide is back to Draft. Mark it ready again once you have read it. The '
                      'Document Library keeps revision 1 of this guide until you mark it ready '
                      'again.', shot['toasts'])
        self.assertNotIn(warning, shot['text'])
        self.assertIn('Guide · Draft', shot['buttons'])
        self.assertEqual(shot['fields']['Text of ' + part['heading']], typed)
        self.assertEqual(self.cards()[guide]['state'], 'draft')
        self.assertEqual(sorted(self.shelf().values()), [1])

    def read_post(self, endpoint, sent) -> dict:
        """The runner's answer to one change, as the page would be given it."""
        return self.captured('POST', f'/api/{endpoint}', sent)

