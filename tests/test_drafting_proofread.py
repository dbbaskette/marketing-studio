"""The in-process mechanical checks: findings in their parts, with the sentence Fix rewrites."""

import unittest

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core.drafting import proofread


def draft(*texts, opening='An opening.'):
    return {
        'title': 'A title',
        'opening': opening,
        'sections': [
            {'id': 'aaaaaaa' + str(n), 'heading': 'Part ' + str(n), 'brief': '', 'text': text}
            for n, text in enumerate(texts)
        ],
        'revision': 3,
    }


class ProofreadTests(unittest.TestCase):
    def test_a_dash_is_found_in_its_part_with_its_sentence(self):
        found = proofread.check(draft('Plain.', 'One — two. Three.'), {'no_em_dashes': True},
                                [], 'one')
        self.assertEqual(found['id'], 'one')
        self.assertEqual(found['revision'], 3)
        [hit] = found['findings']
        self.assertEqual((hit['part'], hit['rule'], hit['sentence']),
                         ('aaaaaaa1', 'em-dash', 'One — two.'))

    def test_indented_code_is_never_read_as_prose(self):
        text = 'Text.\n\n    x — y\n'
        masked = proofread.mask_indented(text)
        self.assertEqual(len(masked), len(text))
        self.assertNotIn('—', masked)
        self.assertEqual(proofread.check(draft(text), {'no_em_dashes': True}, [], 'x')['findings'],
                         [])

    def test_a_listed_opener_and_a_repeated_start_are_found(self):
        found = proofread.repetition('p', 'Moreover, it works. It runs. It stops.', ['Moreover'])
        self.assertEqual({hit['rule'] for hit in found}, {'ai-starter', 'repeated-start'})

    def test_two_sections_opening_alike_are_named(self):
        same = 'This is how we built the thing for you.'
        found = proofread.openers(draft(same, same + ' Again.'))
        self.assertEqual([(hit['rule'], hit['part']) for hit in found],
                         [('echoed-opener', 'aaaaaaa1')])

    def test_findings_are_capped_and_counted(self):
        found = proofread.check(draft('A — b. ' * 301), {'no_em_dashes': True}, [], 'x')
        self.assertEqual(len(found['findings']), 300)
        self.assertEqual(found['more'], 1)
        self.assertEqual(found['limitations'], proofread.LIMITATIONS)

    def test_a_finding_s_place_follows_the_draft_s_heading_level(self):
        deeper = draft('One — two.')
        deeper['sections'][0]['level'] = 3
        [hit] = proofread.check(deeper, {'no_em_dashes': True}, [], 'x')['findings']
        self.assertEqual((hit['part'], hit['at']), ('aaaaaaa0', 4))


if __name__ == '__main__':
    unittest.main()
