"""The Saved runner history card of a deck opened on the desk from the earlier flow: what it
says of a pause, a stop, a failure and a worker's question left unanswered (GitHub issue
#542). The deck is a stored saved deck (tests/fixtures/saved/question) opened on the desk
by the explicit migration; its desk view is then given each saved runner status in turn,
as the migration records it, and the page is drawn by its own scripts."""
import copy

from test_desk_page import DeskPageCase
from runner import desk_chat

QUESTION_KEPT = ('That question is retained in History, unanswered. Conversation editing will '
                 'not answer it, and its step stays unfinished.')


class SavedHistoryCardTests(DeskPageCase):

    def opened(self):
        root = self.load_saved('question')
        preview = desk_chat.migration_preview(self.engine, root)
        self.assertEqual(preview['blockers'], [])
        desk_chat.migrate(self.engine, root, preview['expected'])
        return str(root), self.run_of(str(root))

    def card(self, path, view):
        text = self.open_deck(path, view, [{'snapshot': 'desk'}])['snapshots']['desk']['text']
        self.assertIn('Saved runner history', text)
        return text

    def test_a_worker_question_is_quoted_and_kept_unanswered(self):
        path, view = self.opened()
        asked = view['desk']['saved_question']
        self.assertTrue(asked['text'].endswith('?'))
        text = self.card(path, view)
        self.assertIn(f'A worker asked: “{asked["text"]}”', text)
        self.assertIn(QUESTION_KEPT, text)
        self.assertNotIn('retained in History. Conversation editing will not resume', text)

    def test_a_question_without_its_own_mark_still_reads_as_a_sentence(self):
        path, view = self.opened()
        for text, said in (('Which diagram style', 'A worker asked: “Which diagram style”'),
                           ('', 'A worker asked a question.'),
                           (None, 'A worker asked a question.')):
            with self.subTest(text=text):
                shown = copy.deepcopy(view)
                shown['desk']['saved_question'] = {**shown['desk']['saved_question'], 'text': text}
                drawn = self.card(path, shown)
                self.assertIn(said, drawn)
                self.assertNotIn('A worker asked: a question', drawn)

    def test_a_pause_a_stop_and_a_failure_are_each_said_and_kept(self):
        path, view = self.opened()
        for state, why, word in (('paused', 'Paused on the page.', 'pause'),
                                 ('stopped', None, 'stop'),
                                 ('failed', 'This step did not work in 3 tries.', 'failure')):
            with self.subTest(state):
                shown = copy.deepcopy(view)
                shown['desk']['saved_question'] = None
                shown['desk']['saved_status'] = {'state': state, 'step': 'outline', 'why': why}
                text = self.card(path, shown)
                self.assertIn(why or 'The previous runner stopped.', text)
                self.assertIn(f'That {word} is retained in History. Conversation editing will not '
                              'resume that runner.', text)
                self.assertNotIn('A worker asked', text)

    def test_a_status_and_a_question_share_one_card(self):
        path, view = self.opened()
        shown = copy.deepcopy(view)
        shown['desk']['saved_status'] = {'state': 'paused', 'step': None, 'why': 'Paused on the page.'}
        text = self.card(path, shown)
        self.assertEqual(text.count('Saved runner history'), 1)
        self.assertIn('Paused on the page.', text)
        self.assertIn(QUESTION_KEPT, text)

    def test_no_card_without_a_saved_status_or_question(self):
        path, view = self.opened()
        shown = copy.deepcopy(view)
        shown['desk']['saved_status'] = shown['desk']['saved_question'] = None
        text = self.open_deck(path, shown, [{'snapshot': 'desk'}])['snapshots']['desk']['text']
        self.assertNotIn('Saved runner history', text)
