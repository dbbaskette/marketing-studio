"""A desk item's parts: split from Markdown and joined back, and the codec that reads them."""

import re
import unittest

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core.drafting import parts
from studio_core.drafting.parts import MARKDOWN, Codec

DRAFT = '# T\n\nOpen.\n\n## One\n\nA.\n\n## Two\n\nB.\n'


class PartsTests(unittest.TestCase):
    def test_a_draft_splits_into_title_opening_and_sections_and_joins_back(self):
        draft = parts.split(DRAFT)
        self.assertEqual(draft['title'], 'T')
        self.assertEqual(draft['opening'], 'Open.')
        self.assertEqual([s['heading'] for s in draft['sections']], ['One', 'Two'])
        self.assertEqual([s['text'] for s in draft['sections']], ['A.', 'B.'])
        for section in draft['sections']:
            self.assertRegex(section['id'], r'^[a-f0-9]{8}$')
        self.assertEqual(parts.join(draft), DRAFT)
        self.assertNotIn('images', draft)

    def test_a_heading_in_a_fence_is_text(self):
        text = 'Before.\n\n```\n## Not a section\n```\n'
        draft = parts.split(text)
        self.assertEqual(draft['sections'], [])
        self.assertIn('## Not a section', draft['opening'])
        self.assertFalse(parts.has_heading(draft['opening']))
        self.assertTrue(parts.has_heading('## Yes'))

    def test_sections_start_at_the_shallowest_heading_level(self):
        draft = parts.split('# T\n\n### One\n\nA.\n\n#### Inside\n\n### Two\n\nB.')
        self.assertEqual([s['heading'] for s in draft['sections']], ['One', 'Two'])
        self.assertEqual(parts.level(draft), 3)
        self.assertEqual(parts.limit(draft), 3)
        self.assertEqual(parts.join(draft), '# T\n\n### One\n\nA.\n\n#### Inside\n\n### Two\n\nB.\n')

    def test_an_outline_needs_two_sections(self):
        found = parts.outline_from('# T\n\n- One: do a\n- Two')
        self.assertEqual([s['heading'] for s in found['sections']], ['One', 'Two'])
        self.assertEqual(found['sections'][0]['brief'], 'do a')
        self.assertIsNone(parts.outline_from('- One'))

    def test_a_split_may_take_something_out_of_the_body_first(self):
        draft = parts.split('# T\n\nOpen. X\n', take=lambda body: (body.replace(' X', ''), {'x': 1}))
        self.assertEqual(draft, {'title': 'T', 'opening': 'Open.', 'sections': [], 'images': {'x': 1}})
        self.assertEqual(parts.join(draft, ['[x]: y']), '# T\n\nOpen.\n\n[x]: y\n')

    def test_a_codec_finds_a_part_and_refuses_one_it_does_not_have(self):
        draft = parts.split(DRAFT)
        ident = draft['sections'][1]['id']
        self.assertEqual(MARKDOWN.text_of(draft, 'opening'), 'Open.')
        MARKDOWN.set_text(draft, ident, '  x  ')
        self.assertEqual(draft['sections'][1]['text'], 'x')
        self.assertIsNone(MARKDOWN.section(draft, 'title'))
        with self.assertRaisesRegex(ValueError, r'^Choose a part of this draft\.$'):
            MARKDOWN.section(draft, 'abcdef12')
        self.assertTrue(MARKDOWN.known('title'))
        self.assertTrue(MARKDOWN.known(ident))
        self.assertFalse(MARKDOWN.known('../x'))

    def test_a_codec_says_what_heading_would_start_a_section(self):
        self.assertTrue(MARKDOWN.breaks('## New'))
        self.assertFalse(MARKDOWN.breaks('### Inside'))
        self.assertTrue(MARKDOWN.breaks('### Inside', 3))
        self.assertEqual(
            MARKDOWN.break_message(2),
            'A ## heading would start a new section. Use ### for a heading inside this part.',
        )
        self.assertEqual(
            MARKDOWN.break_message(6),
            'A heading would start a new section. Add sections on the Outline tab.',
        )
        self.assertEqual(
            MARKDOWN.added_message('##'),
            'The rewrite added a ## section heading, so it was not applied. Run it again.',
        )

    def test_a_codec_with_no_fixed_parts_names_slides(self):
        deck = Codec(fixed=(), single=(), part=re.compile(r's-[0-9]{1,3}'), thing='deck',
                     noun='slide')
        self.assertFalse(deck.known('title'))
        self.assertTrue(deck.known('s-4'))
        with self.assertRaisesRegex(ValueError, r'^Choose a part of this deck\.$'):
            deck.section({'sections': [{'id': 's-1', 'text': ''}]}, 's-4')


if __name__ == '__main__':
    unittest.main()
