"""The research stop reads verified output, never judges evidence itself."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_view as view


from synthesis_fixture import published_bundle as bundle


class AccountTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name) / 'research'

    def test_the_account_leads_with_the_brief_and_the_check_s_word(self):
        bundle(self.folder)
        found = view.account(self.folder)
        self.assertEqual(found['brief'], '# Prioritized handoff\n')
        self.assertEqual(found['check']['said'], view.CHECKED)
        self.assertEqual(found['check']['note'], 'An honest account.')

    def test_every_gap_is_listed_once_in_order(self):
        bundle(self.folder, findings=[dict(id='one', gaps=[dict(text='Unknown range.')]),
                                     dict(id='two', gaps=[dict(text='Unknown  range.')])],
               sections=[dict(blocks=[dict(kind='gap', text='No comparison.')])],
               brief=[dict(blocks=[dict(kind='gap', text='No comparison.')])])
        self.assertEqual(view.account(self.folder)['gaps'], ['Unknown range.', 'No comparison.'])

    def test_sources_are_counted_by_permission_and_partial_ones_named(self):
        bundle(self.folder, sources=[dict(id='a', permission='selected'), dict(id='b', permission='selected'),
               dict(id='c', permission='public', title='Public page', context='partial', context_note='Pages 1 to 4 only.')])
        found = view.account(self.folder)
        self.assertEqual(found['read'], '3 sources: 2 of yours, 1 public.')
        self.assertEqual(found['sources']['partial'], [dict(title='Public page', note='Pages 1 to 4 only.')])
        bundle(self.folder, sources=[dict(id='a', permission='selected')])
        self.assertEqual(view.account(self.folder)['read'], '1 source: 1 of yours.')

    def test_findings_answer_the_question_their_id_begins_with(self):
        bundle(self.folder, findings=[dict(id=i) for i in ('instance-min--capacity', 'instance--count', 'instance-minimum', 'other')])
        found = view.account(self.folder, [dict(id='instance-min', question='Minimum?'), dict(id='instance', question='Count?')])
        self.assertEqual(found['questions'][0]['findings'], ['instance-min--capacity'])
        self.assertEqual(found['questions'][1]['findings'], ['instance--count'])
        self.assertEqual(found['unplanned'], ['instance-minimum', 'other'])
        self.assertEqual(view.answered_by('instance-min', ['instance-min']), 'instance-min')
        self.assertEqual(view.answered_by('a--b--c', ['a', 'a--b']), 'a--b')

    def test_an_unread_original_remains_blocked(self):
        review = dict(accepted=False, digest='synthetic-digest', originals=[dict(source='a', read_original=False, access_error='Not served.')])
        bundle(self.folder, review=review)
        self.assertIsNone(view.account(self.folder))

    def test_no_account_without_a_readable_complete_bundle(self):
        self.assertIsNone(view.account(self.folder))
        bundle(self.folder)
        (self.folder / 'brief.md').write_text('Changed')
        self.assertIsNone(view.account(self.folder))
        facts, manifest = bundle(self.folder)
        facts['status'] = manifest['status'] = 'draft'
        (self.folder / 'facts.json').write_text(json.dumps(facts))
        manifest['artifacts'] = [dict(file=e['file'], sha256=hashlib.sha256((self.folder / e['file']).read_bytes()).hexdigest()) for e in manifest['artifacts']]
        (self.folder / 'output.json').write_text(json.dumps(manifest))
        self.assertIsNone(view.account(self.folder))

    def test_the_price_names_rounds_cost_and_what_is_made_again(self):
        attempts = {'research:author-1': [dict(started_at='2026-10-22T10:00:00Z', seconds=1800, dollars=6)],
                    'research:review-1': [dict(started_at='2026-10-22T10:30:00Z', seconds=1080, dollars=3.8)]}
        self.assertEqual(view.price(attempts, ('the outline', 'the look samples'))['words'],
                         'Asking for changes runs the research again from its last report: up to 3 rounds of writing and checking. Its last try took 48 minutes and $9.80. Then it makes again: the outline and the look samples.')

    def test_a_price_with_nothing_recorded_says_so(self):
        self.assertEqual(view.price({})['words'], 'Asking for changes runs the research again from its last report: up to 3 rounds of writing and checking. No time or money was recorded for its last try.')
        self.assertTrue(view.price({}, drafted=False)['words'].startswith('Asking for changes runs the research again:'))
        found = view.price({'research:author-1': [dict(seconds=120, dollars=None)]})['words']
        self.assertIn('Its last try took 2 minutes.', found)
        self.assertNotIn('$', found)
