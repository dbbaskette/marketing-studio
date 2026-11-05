"""First-pass bounds and cheap author preflight, with synthetic evidence only."""
import copy
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_quality as quality, research_session as session, research_sections


class QualityTests(unittest.TestCase):
    def test_only_whole_placeholder_blocks_are_rejected(self):
        for text in ('test', ' TEST. ', 'TODO', 'TBD', 'Placeholder', 'Lorem ipsum', 'Insert text here'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'placeholder'):
                quality.prose({'brief': [{'blocks': [{'text': text}]}]})
        quality.prose({'sections': [{'blocks': [{'text': 'Test the restore procedure before relying on it.'}]}]})

    def test_evidence_bounds_reject_without_truncating(self):
        value = {'schema': 2, 'sources': [], 'facts': [{'id': str(i)} for i in range(9)]}
        before = copy.deepcopy(value)
        with self.assertRaisesRegex(ValueError, 'at most 8 facts'):
            session.preparation(value, {'research_mode': 'evidence', 'research_policy': quality.FOCUSED})
        self.assertEqual(value, before)
        quality.evidence(value, None)  # Existing tasks do not gain new limits.
        with self.assertRaisesRegex(ValueError, 'at most 5 sources'):
            quality.evidence({'sources': [{}] * 6}, quality.FOCUSED)

    def test_bounded_prose_preserves_original_and_legacy_policy(self):
        value = {'sections': [{'blocks': [{'text': 'word ' * 501}]}]}
        with self.assertRaisesRegex(ValueError, '500 words'):
            quality.prose(value, quality.FOCUSED)
        self.assertEqual(len(value['sections'][0]['blocks'][0]['text'].split()), 501)
        quality.prose(value)

    def test_final_placeholder_is_refused_before_assembly(self):
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            research_sections.prepared({'schema': 2, 'sections': [],
                'brief': [{'blocks': [{'text': 'test'}]}]}, {'research_mode': 'compose-final'})

    def test_malformed_prose_is_a_repairable_validation_error(self):
        for value in ({'sections': ['bad']}, {'brief': [{'blocks': ['bad']}]}, {'sections': 'bad'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                quality.prose(value)

    def test_policy_tampering_is_not_a_silent_increase(self):
        self.assertTrue(quality.valid_policy(dict(quality.FOCUSED)))
        self.assertFalse(quality.valid_policy({**quality.FOCUSED, 'schema': True}))
        with self.assertRaisesRegex(ValueError, 'Restore'):
            quality.evidence({}, {**quality.FOCUSED, 'facts_per_area': 100})

    def test_training_resources_share_budget_and_permissions(self):
        self.assertIn('same source and fact budget', quality.FOCUSED_GUIDANCE)
        self.assertIn('when web research is allowed', quality.FOCUSED_GUIDANCE)
        self.assertIn('Attribute sources', quality.FOCUSED_GUIDANCE)

    def test_incomplete_is_not_claimed_to_be_incorrect(self):
        coverage = quality.coverage({'originals': [{'read_original': True}, {'read_original': False}]})
        self.assertEqual(coverage, {'read': 1, 'total': 2, 'unread': 1})
        self.assertIn('Unread does not mean incorrect', str(quality.IncompleteCheck(coverage)))
