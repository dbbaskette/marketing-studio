import json
import tempfile
import unittest
from pathlib import Path

import marketing_studio  # noqa: F401  puts the shared core on the import path
from studio_core import critic


class CriticQuestionsTests(unittest.TestCase):
    """The slides tool's own review questions, read from a whole-deck preview."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.folder = Path(holder.name)

    def packet(self, value) -> Path:
        (self.folder / 'critic.json').write_text(json.dumps(value), encoding='utf-8')
        return self.folder

    def test_reads_the_tools_questions(self):
        self.assertEqual(critic.questions(self.packet({'schema': 2, 'questions': ['A?', 'B?']})),
                         ('A?', 'B?'))

    def test_refuses_a_missing_packet(self):
        with self.assertRaises(ValueError) as refused:
            critic.questions(self.folder)
        self.assertEqual(str(refused.exception), critic.MISSING)
        (self.folder / 'critic.json').write_text('{not json', encoding='utf-8')
        with self.assertRaises(ValueError) as refused:
            critic.questions(self.folder)
        self.assertEqual(str(refused.exception), critic.MISSING)

    def test_refuses_a_malformed_packet(self):
        for questions in ('A?', ['A?', ''], ['Q?'] * 13, [], ['A?', 3], None):
            with self.subTest(questions=questions), self.assertRaises(ValueError) as refused:
                critic.questions(self.packet({'schema': 2, 'questions': questions}))
            self.assertEqual(str(refused.exception), critic.MISSING)
        with self.assertRaises(ValueError):
            critic.questions(self.packet(['A?']))

    def test_the_message_says_what_to_do(self):
        self.assertEqual(critic.MISSING, "The slides tool's review questions are not with this "
                         'preview. Put the deck together again.')

    def test_legacy_is_harness_slides_0_16_0s_eight(self):
        self.assertEqual(critic.LEGACY, (
            'After three seconds, is the main point clear, and is it the claim in the title?',
            'Does the eye land first on the element that carries the point?',
            'Is there exactly one emphasis?',
            'Does every element support the title?',
            'Is each label inside or right beside what it names?',
            'Is the space balanced, with nothing stranded or crowded?',
            'Is the slide consistent with its neighbours in style, and different from them in '
            'layout unless they are meant to be compared?',
            'Does every image and icon explain something?'))

    def test_a_round_reads_its_own_questions_or_the_legacy_ones(self):
        self.assertEqual(critic.of_round({'questions': ['A?', 'B?', 'C?']}), ('A?', 'B?', 'C?'))
        self.assertEqual(critic.of_round({}), critic.LEGACY)
        self.assertEqual(critic.of_round({'questions': 'broken'}), critic.LEGACY)
        self.assertEqual(critic.of_round(None), critic.LEGACY)


if __name__ == '__main__':
    unittest.main()
