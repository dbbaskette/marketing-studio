"""The words a desk job is asked with: the edit rule, the actions and the author's note."""

import unittest

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core.drafting import prompts

# Blog Studio's references/modules/desk-edit.md, word for word, as it was when it moved here.
DESK_EDIT = """# Desk edits

You are editing one part of a blog draft for its author.

- Change only what the author's note requires. Reproduce every part the note does not
  require changing verbatim, word for word.
- Do not restructure, reorder, rephrase, tighten or otherwise improve parts the note does
  not mention. Keep the part's length and shape unless the note requires otherwise.
- Keep facts, numbers, names, quotations and links. Never invent experience, customers or
  results. Where the note asks for something the sources cannot support, write what they
  support and add the gap to gaps.
- Return only the rewritten part in `content`: no heading, no commentary, no source IDs,
  no editorial placeholders. Put each thing the author must supply before publishing in
  `gaps`, and each material claim with its source ID and exact passage in `evidence`.
"""


class PromptTests(unittest.TestCase):
    def test_the_edit_rule_for_a_blog_draft_is_the_desk_edit_guide(self):
        self.assertEqual(prompts.edit_rule('blog draft'), DESK_EDIT.rstrip())

    def test_the_edit_rule_names_the_thing_edited(self):
        self.assertIn('one part of a training guide for its author', prompts.edit_rule('training guide'))
        self.assertNotIn('blog', prompts.edit_rule('training guide'))

    def test_the_author_s_words_are_fenced_and_name_the_product(self):
        said = prompts.request('NOTE FOR THIS SECTION', 'Add one.', prompts.SURGICAL,
                               'Presentation Studio')
        self.assertIn(
            'AUTHOR’S NOTE FOR THIS SECTION, from the author through Presentation Studio. ', said
        )
        self.assertIn(prompts.SURGICAL, said)
        self.assertTrue(said.endswith('\n"""\nAdd one.\n"""'))
        self.assertTrue(said.startswith('\n\nAUTHOR’S '))

    def test_the_actions_are_rephrase_shorten_expand_and_fix(self):
        self.assertEqual(sorted(prompts.ACTIONS), ['expand', 'fix', 'rephrase', 'shorten'])
        self.assertEqual(prompts.ASK, 'Do what the author asks below with the passage.')

    def test_a_passage_task_says_to_return_only_the_replacement(self):
        self.assertEqual(
            prompts.passage_task('Fix it.'),
            '\n\nAct on the passage only: Fix it. Return only the replacement for passage in '
            'content; around is its context and is not returned.\n\n',
        )


if __name__ == '__main__':
    unittest.main()
