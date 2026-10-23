"""The desk record: a draft as title, opening and sections, with versions."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import unittest

import desk

DRAFT = """# A synthetic title

An opening paragraph.

## First part

First text.

## Second part

Second text.
"""


class SplitJoinTests(unittest.TestCase):
    def test_split_reads_title_opening_and_sections(self):
        found = desk.split(DRAFT)
        self.assertEqual(found['title'], 'A synthetic title')
        self.assertEqual(found['opening'], 'An opening paragraph.')
        self.assertEqual([s['heading'] for s in found['sections']], ['First part', 'Second part'])
        self.assertEqual(found['sections'][1]['text'], 'Second text.')
        self.assertTrue(all(len(s['id']) == 8 for s in found['sections']))
        self.assertEqual(len({s['id'] for s in found['sections']}), 2)

    def test_join_round_trips(self):
        self.assertEqual(desk.join(desk.split(DRAFT)), DRAFT)

    def test_no_headings_is_one_opening(self):
        found = desk.split('Just prose.\n')
        self.assertEqual(found['sections'], [])
        self.assertEqual(found['opening'], 'Just prose.')

    def test_title_may_be_given_when_the_text_has_none(self):
        found = desk.split('## Only\n\nText.\n', title='Given')
        self.assertEqual(found['title'], 'Given')
        self.assertEqual(found['opening'], '')

    def test_a_heading_inside_a_code_block_stays_in_its_section(self):
        text = '# T\n\n## Setup\n\n```sh\n## not a heading\necho hi\n```\n\n## Next\n\nMore.\n'
        found = desk.split(text)
        self.assertEqual([s['heading'] for s in found['sections']], ['Setup', 'Next'])
        self.assertIn('## not a heading', found['sections'][0]['text'])
        self.assertEqual(desk.join(found), text)

    def test_deeper_headings_stay_in_their_section(self):
        found = desk.split('# T\n\n## Part\n\n### Detail\n\nText.\n')
        self.assertEqual(len(found['sections']), 1)
        self.assertEqual(found['sections'][0]['text'], '### Detail\n\nText.')

    def test_windows_line_endings_are_read(self):
        found = desk.split('# T\r\n\r\n## Part\r\n\r\nText.\r\n')
        self.assertEqual(found['sections'][0]['text'], 'Text.')


if __name__ == '__main__':
    unittest.main()
