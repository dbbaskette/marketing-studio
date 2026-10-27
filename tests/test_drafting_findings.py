"""Review findings as proposals: kept on this computer, applied as a note on their part."""

import tempfile
import unittest

from drafting_fixtures import FolderStore, draft, make
from studio_core.drafting import findings, record
from studio_core.drafting.findings import Noted

TOOLS = {'finish-review': 'review'}
JOB = 'c' * 32
FOUND = [
    {'slide': 'bbbbbbbb', 'number': 3, 'severity': 'major', 'about': 'drawing',
     'note': 'The diagram reads backwards.', 'fix': 'Draw it left to right.'},
    {'slide': 'aaaaaaaa', 'number': 2, 'severity': 'minor', 'about': 'content',
     'note': 'The source line is long.', 'fix': None},
    {'slide': None, 'number': None, 'severity': 'minor', 'note': 'The deck runs long.'},
]


class NotedCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = FolderStore(folder.name)
        self.desk = record.Desk(self.store)
        make(self.store, 'one', draft())
        self.notes, self.told, self.gone = [], [], set()
        self.kept = Noted(self.store, self.desk, TOOLS, self.note, owner='deck',
                          present=lambda draft, item: item['part'] not in self.gone,
                          noted=lambda ident, applied: self.told.append(
                              (ident, [item['id'] for item in applied])))

    def note(self, ident, item, words):
        if item['part'] == 'refused':
            raise ValueError('That part is being redrawn now.')
        self.notes.append((ident, item['part'], words))

    def offer(self, found=FOUND):
        return self.kept.keep('one', JOB, 'finish-review', findings.items(found, 'slide'))


class ItemTests(NotedCase):
    def test_each_finding_on_a_part_is_a_proposal_whose_after_is_its_note_and_fix(self):
        made = self.offer()
        self.assertEqual([(item['id'], item['part'], item['after']) for item in made['items']],
                         [('p1', 'bbbbbbbb', 'The diagram reads backwards. Draw it left to right.'),
                          ('p2', 'aaaaaaaa', 'The source line is long.')])
        self.assertEqual(made['items'][0]['severity'], 'major')
        self.assertNotIn('fix', made['items'][1])
        self.assertEqual(made['deck'], 'one')
        # Waiting on this computer only: the item's own folder holds its draft alone.
        self.assertTrue(self.store.local('one', JOB + '.json').is_file())
        self.assertEqual(sorted(p.name for p in self.store.folder('one').iterdir()), ['draft.json'])

    def test_a_studio_says_what_note_a_finding_makes_and_what_else_it_keeps(self):
        found = [{'slide': 's1', 'says': 'Text runs off the slide.', 'kind': 'blocker',
                  'code': 'OUT_OF_BOUNDS'}]
        made = findings.items(found, 'slide', fields=('kind', 'says'),
                              words=lambda one: "The brand's check: " + one['says'])
        self.assertEqual(made[0]['after'], "The brand's check: Text runs off the slide.")
        self.assertEqual((made[0]['kind'], made[0]['says']), ('blocker', 'Text runs off the slide.'))
        self.assertNotIn('code', made[0])
        # Only the fields a studio names are kept beside the shared ones.
        self.assertNotIn('kind', findings.items(found, 'slide')[0])

    def test_the_part_a_finding_names_is_said_by_the_studio(self):
        with self.assertRaises(TypeError):
            findings.items(FOUND)  # pylint: disable=no-value-for-parameter
        made = findings.items([{'section': 'aaaaaaaa', 'note': 'Too long.'}], 'section')
        self.assertEqual(made[0]['part'], 'aaaaaaaa')


class ApplyTests(NotedCase):
    def test_apply_notes_the_part_and_changes_no_text(self):
        self.offer()
        before = self.desk.read('one')
        done = self.kept.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertEqual(done, {'applied': 1, 'left': []})
        self.assertEqual(self.notes, [('one', 'bbbbbbbb',
                                       'The diagram reads backwards. Draw it left to right.')])
        self.assertEqual(self.told, [('one', ['p1'])])
        self.assertEqual(self.desk.read('one'), before)
        self.assertEqual(self.store.written, [])
        self.assertEqual([item['state'] for item in self.kept.read('one', JOB)['items']],
                         ['applied', 'open'])

    def test_the_person_s_own_words_are_the_note(self):
        self.offer()
        self.kept.apply('one', 1, JOB, [{'id': 'p2', 'after': '  Cut the source   line. '}])
        self.assertEqual(self.notes, [('one', 'aaaaaaaa', 'Cut the source line.')])

    def test_one_that_cannot_be_noted_is_refused_and_nothing_is_marked(self):
        self.offer([{**FOUND[0], 'slide': 'refused'}])
        with self.assertRaisesRegex(ValueError, 'being redrawn now'):
            self.kept.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertEqual(self.told, [])
        self.assertEqual(self.kept.read('one', JOB)['items'][0]['state'], 'open')

    def test_several_at_once_note_what_can_be_and_leave_the_rest(self):
        self.offer([FOUND[0], {**FOUND[1], 'slide': 'refused'}])
        done = self.kept.apply('one', 1, JOB, [{'id': 'p1'}, {'id': 'p2'}])
        self.assertEqual(done, {'applied': 1, 'left': ['p2']})
        self.assertEqual([item['state'] for item in self.kept.read('one', JOB)['items']],
                         ['applied', 'open'])

    def test_a_part_no_longer_there_is_refused(self):
        self.offer()
        self.gone.add('bbbbbbbb')
        with self.assertRaisesRegex(ValueError, 'This section changed since this was found, so '
                                                'it was not noted. Skip it.'):
            self.kept.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertFalse(self.kept.summary('one', self.desk.read('one'))['review']['items'][0][
            'present'])

    def test_an_empty_note_is_refused(self):
        self.offer()
        with self.assertRaisesRegex(ValueError, findings.EMPTY):
            self.kept.apply('one', 1, JOB, [{'id': 'p1', 'after': '   '}])

    def test_an_outdated_form_is_refused_for_the_part_it_notes(self):
        self.offer()
        held = self.desk.read('one')
        held['revision'], held['changed'] = 3, {'bbbbbbbb': 3}
        make(self.store, 'one', held)
        with self.assertRaisesRegex(ValueError, 'changed since you opened it'):
            self.kept.apply('one', 2, JOB, [{'id': 'p1'}])
        self.assertEqual(self.kept.apply('one', 2, JOB, [{'id': 'p2'}])['applied'], 1)

    def test_skip_keeps_a_finding_as_read_and_notes_nothing(self):
        self.offer()
        self.assertEqual(self.kept.skip('one', JOB, ['p1']), {'skipped': 1})
        self.assertEqual(self.notes, [])
        self.assertEqual(self.kept.read('one', JOB)['items'][0]['state'], 'skipped')
        with self.assertRaisesRegex(ValueError, 'already applied or skipped'):
            self.kept.apply('one', 1, JOB, [{'id': 'p1'}])


if __name__ == '__main__':
    unittest.main()
