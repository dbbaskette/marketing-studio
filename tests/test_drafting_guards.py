"""Whether a rewrite changes a fact or the part's structure, said in one line."""

import unittest

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core.drafting import guards

NUMBER = 'Check the facts: this changes a number.'
NAME = 'Check the facts: this changes a name.'


class GuardTests(unittest.TestCase):
    def test_a_changed_number_link_quote_or_dropped_name_is_named(self):
        self.assertEqual(guards.changes_facts('In 2024 Ada wrote.', 'In 2025 Ada wrote.'), NUMBER)
        self.assertEqual(guards.changes_facts('We asked Ada today.', 'We asked her today.'), NAME)
        self.assertEqual(guards.changes_facts('In 2024 Ada wrote.', 'In 2024 Ada wrote.'), '')
        self.assertIn('a link', guards.changes_facts('See https://a.example.', 'See it.'))

    def test_anywhere_lets_a_name_move_but_not_go(self):
        self.assertEqual(guards.changes_facts('We met Ada today.', 'Ada met us today.', True), '')
        self.assertEqual(guards.changes_facts('We met Ada today.', 'We met today.', True), NAME)

    def test_code_and_shape_are_kept(self):
        self.assertEqual(guards.changes_structure('A.\n\n```\nx\n```', 'A.\n\n```\ny\n```'),
                         guards.STRUCTURE)
        self.assertEqual(guards.changes_structure('Use `a` here.', 'Use `b` here.'),
                         guards.STRUCTURE)
        self.assertEqual(guards.changes_structure('One.\n\nTwo.', 'One. Two.'), guards.STRUCTURE)
        self.assertEqual(guards.changes_structure('One.\n\nTwo.', 'One. Two.', paragraphs=False),
                         '')

    def test_an_image_reference_is_structure_not_a_name(self):
        before = 'Intro.\n\n![Chart][image1]\n\nThat is all.'
        self.assertEqual(guards.changes_structure(before, before.replace('Chart', 'Graph')),
                         guards.STRUCTURE)
        self.assertEqual(guards.names('Ask Acme ![Diagram][image1] Then more'), {'Acme'})

    def test_flags_join_both_lines(self):
        flag = guards.flags('In 2024 run `a`.', 'In 2025 run `b`.')
        self.assertEqual(flag, NUMBER + ' ' + guards.STRUCTURE)
        self.assertEqual(guards.flags('Same words.', 'Same words.'), '')


if __name__ == '__main__':
    unittest.main()
