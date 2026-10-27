"""Finishing's proposals: kept on this computer, then applied or skipped by the person."""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from drafting_fixtures import FolderStore, draft, make
from studio_core.drafting import proposals, record
from studio_core.drafting.proposals import Proposals, read_result

TOOLS = {'finish-humanize': 'humanize', 'finish-headline': 'headline', 'finish-copyedit': 'copyedit'}
JOB, OTHER = 'a' * 32, 'b' * 32


class ProposalCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = FolderStore(folder.name)
        self.desk = record.Desk(self.store)
        make(self.store, 'one', draft())
        self.kept = Proposals(self.store, self.desk, TOOLS)

    def offer(self, items, job=JOB, kind='finish-humanize', **extra):
        return self.kept.keep('one', job, kind, items, **extra)

    def swap(self, before, after, part='bbbbbbbb', **extra):
        return {'part': part, 'before': before, 'after': after, **extra}


class KeepTests(ProposalCase):
    def test_a_set_waits_on_this_computer_not_in_the_item(self):
        made = self.offer([self.swap('Second text.', 'Two.'), self.swap('Second', 'Next')])
        self.assertTrue(self.store.local('one', JOB + '.json').is_file())
        self.assertEqual(sorted(p.name for p in self.store.folder('one').iterdir()), ['draft.json'])
        self.assertEqual([(i['id'], i['state']) for i in made['items']], [('p1', 'open'), ('p2', 'open')])
        self.assertEqual(made['item'], 'one')
        self.assertEqual(self.kept.read('one', JOB)['kind'], 'finish-humanize')
        with self.assertRaisesRegex(ValueError, 'Choose a finishing tool.'):
            self.offer([], kind='finish-unknown')
        with self.assertRaisesRegex(ValueError, 'Choose a set of suggestions on this item.'):
            self.kept.read('one', '../x')

    def test_the_newest_set_per_tool_is_read_without_reading_every_set(self):
        self.offer([self.swap('Second text.', 'Two.')])
        self.offer([self.swap('Second text.', 'Deux.')], job=OTHER)
        with patch.object(Proposals, 'sets', side_effect=AssertionError('read every set')):
            shown = self.kept.summary('one', self.desk.read('one'))
        self.assertEqual(shown['humanize']['job'], OTHER)
        self.assertTrue(shown['humanize']['items'][0]['present'])

    def test_an_older_set_is_let_go_once_nothing_in_it_is_open(self):
        self.offer([self.swap('Second text.', 'Two.')])
        self.kept.skip('one', JOB, ['p1'])
        self.offer([self.swap('Second text.', 'Deux.')], job=OTHER)
        self.assertFalse(self.store.local('one', JOB + '.json').exists())

    def test_an_open_older_set_is_let_go_after_a_day(self):
        self.offer([self.swap('Second text.', 'Two.')])
        old = time.time() - proposals.DAY - 10
        os.utime(self.store.local('one', JOB + '.json'), (old, old))
        self.offer([self.swap('Second text.', 'Deux.')], job=OTHER)
        self.assertFalse(self.store.local('one', JOB + '.json').exists())

    def test_sets_keyed_by_the_owner_word_are_read(self):
        blog = Proposals(self.store, self.desk, TOOLS, owner='blog')
        made = blog.keep('one', JOB, 'finish-humanize', [self.swap('Second text.', 'Two.')])
        self.assertEqual(made['blog'], 'one')
        self.assertEqual(blog.read('one', JOB)['job'], JOB)
        with self.assertRaisesRegex(ValueError, 'no longer here'):
            Proposals(self.store, self.desk, TOOLS, owner='deck').read('one', JOB)
        self.assertEqual(Proposals(self.store, self.desk, TOOLS, owner='deck').sets('one'), [])

    def test_forget_lets_the_item_s_sets_go(self):
        self.offer([self.swap('Second text.', 'Two.')])
        self.kept.forget('one')
        self.assertFalse(self.store.local('one').exists())


class ApplyTests(ProposalCase):
    def test_one_proposal_that_no_longer_fits_changes_nothing(self):
        self.offer([self.swap('Second text.', 'Two.')])
        self.desk.save('one', 1, 'bbbbbbbb', 'Typed meanwhile.')
        self.store.written.clear()
        with self.assertRaisesRegex(ValueError, '^' + proposals.GONE + '$'):
            self.kept.apply('one', 2, JOB, [{'id': 'p1'}])
        self.assertEqual(self.store.written, [])

    def test_apply_all_applies_what_fits_and_counts_the_rest(self):
        self.offer([self.swap('Second text.', 'Two.'), self.swap('Nowhere', 'X', part='aaaaaaaa')])
        done = self.kept.apply('one', 1, JOB, [{'id': 'p1'}, {'id': 'p2'}])
        self.assertEqual(done, {'applied': 1, 'left': ['p2']})
        self.assertEqual(self.store.read('one')['sections'][1]['text'], 'Two.')
        kept = self.desk.versions.versions('one', 'bbbbbbbb')
        self.assertEqual([(v['source'], v['text']) for v in kept], [('finishing', 'Second text.')])
        self.assertEqual(self.kept.read('one', JOB)['items'][0]['state'], 'applied')

    def test_a_part_a_job_is_working_on_is_refused(self):
        self.offer([self.swap('Second text.', 'Two.'), self.swap('A synthetic', 'One', part='title')])
        with self.assertRaisesRegex(ValueError, 'A desk job is working on this part.'):
            self.kept.apply('one', 1, JOB, [{'id': 'p1'}], working={'sections'})
        done = self.kept.apply('one', 1, JOB, [{'id': 'p1'}], working=lambda: {'title'})
        self.assertEqual(done['applied'], 1)

    def test_choosing_one_alternative_skips_the_others_in_its_group(self):
        whole = {'part': 'title', 'before': 'A synthetic title', 'whole': True, 'group': 'title'}
        self.offer([{**whole, 'after': 'One'}, {**whole, 'after': 'Two'}], kind='finish-headline')
        self.kept.apply('one', 1, JOB, [{'id': 'p1'}])
        states = [item['state'] for item in self.kept.read('one', JOB)['items']]
        self.assertEqual(states, ['applied', 'skipped'])
        self.assertEqual(self.store.read('one')['title'], 'One')

    def test_proposals_are_marked_applied_only_once_the_item_is_written(self):
        self.offer([self.swap('Second text.', 'Two.')])
        with patch.object(FolderStore, 'write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.kept.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertEqual(self.kept.read('one', JOB)['items'][0]['state'], 'open')

    def test_two_suggestions_over_the_same_words_never_both_land_and_one_retires_the_other(self):
        self.offer([self.swap('Second text.', 'Two.')])
        self.offer([self.swap('Second', 'Next')], job=OTHER, kind='finish-copyedit')
        together = Proposals(self.store, self.desk, TOOLS,
                             together=('finish-humanize', 'finish-copyedit'))
        together.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertEqual(together.read('one', OTHER)['items'][0]['state'], 'retired')
        with self.assertRaisesRegex(ValueError, proposals.RETIRED):
            together.apply('one', 2, OTHER, [{'id': 'p1'}])

    def test_accept_all_leaves_what_a_flagged_suggestion_still_waits_on(self):
        self.offer([self.swap('Second text.', 'Twenty.', flag='Check the facts.')])
        self.offer([self.swap('Second', 'Next')], job=OTHER, kind='finish-copyedit')
        together = Proposals(self.store, self.desk, TOOLS,
                             together=('finish-humanize', 'finish-copyedit'))
        done = together.apply('one', 1, OTHER, [{'id': 'p1'}], every=True)
        self.assertEqual(done, {'applied': 0, 'left': ['p1']})
        self.assertEqual(self.store.written, [])

    def test_an_alternative_is_chosen_by_its_place(self):
        self.offer([self.swap('Second text.', 'Two.', alternatives=[{'after': 'Deux.', 'flag': ''}])])
        self.kept.apply('one', 1, JOB, [{'id': 'p1', 'alternative': 0}])
        self.assertEqual(self.store.read('one')['sections'][1]['text'], 'Deux.')

    def test_empty_words_and_the_same_text_are_refused(self):
        self.offer([self.swap('Second text.', 'Two.')])
        with self.assertRaisesRegex(ValueError, 'not applied empty'):
            self.kept.apply('one', 1, JOB, [{'id': 'p1', 'after': '  '}])
        with self.assertRaisesRegex(ValueError, 'Nothing would change'):
            self.kept.apply('one', 1, JOB, [{'id': 'p1', 'after': 'Second text.'}])

    def test_a_studio_s_own_fit_decides_what_a_proposal_writes(self):
        fitted = Proposals(
            self.store, self.desk, TOOLS,
            fit=lambda value, item, after, text: text + ' ' + after,
            present=lambda value, item: False,
        )
        fitted.keep('one', JOB, 'finish-humanize', [self.swap('Second text.', 'Added.')])
        fitted.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertEqual(self.store.read('one')['sections'][1]['text'], 'Second text. Added.')
        shown = fitted.summary('one', self.store.read('one'))
        self.assertEqual([i['present'] for i in shown['humanize']['items']], [False])

    def test_a_studio_may_act_on_a_proposal_that_is_not_a_text_swap(self):
        # A deck's review finding is applied as a note on its slide, not as a text change.
        acted = []

        class Notes(Proposals):
            def act(self, ident, job, found, draft, picks, every, named, left=()):
                acted.append((ident, job, [(item['id'], after) for item, after in picks]))
                return {'applied': len(picks), 'left': []}

        notes = Notes(self.store, self.desk, TOOLS)
        notes.keep('one', JOB, 'finish-humanize', [self.swap('Nowhere at all', 'A note.')])
        self.assertEqual(notes.apply('one', 1, JOB, [{'id': 'p1'}]), {'applied': 1, 'left': []})
        self.assertEqual(acted, [('one', JOB, [('p1', 'A note.')])])
        self.assertEqual(self.store.written, [])
        # The request is still checked first: an outdated form never reaches `act`.
        self.desk.save('one', 1, 'bbbbbbbb', 'Typed meanwhile.')
        with self.assertRaisesRegex(ValueError, 'changed since you opened it'):
            notes.apply('one', 1, JOB, [{'id': 'p1'}])
        self.assertEqual(len(acted), 1)

    def test_skip_counts_only_what_was_open(self):
        self.offer([self.swap('Second text.', 'Two.'), self.swap('Second', 'X')])
        self.assertEqual(self.kept.skip('one', JOB, ['p1', 'p1']), {'skipped': 1})
        self.assertEqual(self.kept.skip('one', JOB, ['p1']), {'skipped': 0})
        with self.assertRaisesRegex(ValueError, 'Choose suggestions from this set.'):
            self.kept.skip('one', JOB, ['p9'])


class ReadingTests(unittest.TestCase):
    def test_a_result_in_fences_is_read_and_another_shape_is_refused(self):
        self.assertEqual(read_result('```json\n{"a": 1}\n```', 'X'), {'a': 1})
        self.assertEqual(read_result(' [1] ', 'X'), [1])
        with self.assertRaisesRegex(ValueError, '^X$'):
            read_result('nope', 'X')

    def test_rows_keep_only_rows_of_the_asked_shape(self):
        found = {'rows': [{'a': 'x'}, {'a': 1}, 'no']}
        self.assertEqual(proposals.rows(found, 'rows', ('a',), 'X'), ([{'a': 'x'}], 2))
        with self.assertRaisesRegex(ValueError, 'X'):
            proposals.rows({'rows': [{'a': 1}]}, 'rows', ('a',), 'X')
        with self.assertRaisesRegex(ValueError, 'X'):
            proposals.rows(json.loads('{}'), 'rows', ('a',), 'X')

    def test_a_passage_is_located_only_where_it_occurs_once(self):
        value = draft()
        self.assertEqual(proposals.located(value, 'aaaaaaaa', ' First text. '), 'First text.')
        self.assertIsNone(proposals.located(value, 'aaaaaaaa', 't'))
        self.assertIsNone(proposals.located(value, 'cccccccc', 'First'))


if __name__ == '__main__':
    unittest.main()
