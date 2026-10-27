"""Blog Studio's desk runs on the shared desk parts in studio_core.drafting."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import unittest
from unittest.mock import patch

import desk
import desk_finish
import desk_images
from studio_core.drafting import guards, parts, proofread, record, versions
from test_desk import DeskCase


class SharedCodecTests(unittest.TestCase):
    def test_the_desk_uses_the_shared_codec(self):
        self.assertIs(desk._divide, parts.divide)
        self.assertIs(desk.has_heading, parts.has_heading)
        self.assertIs(desk.outline_from, parts.outline_from)
        self.assertIs(desk.SECTION, parts.SECTION)
        self.assertEqual(desk.PARTS, ('title', 'opening'))
        self.assertIs(desk.PART, parts.MARKDOWN.part)
        self.assertEqual(desk.CODEC.fixed, parts.MARKDOWN.fixed)
        # Blog's split and join keep images beside the text: the shared ones, with its hooks.
        found = desk.split('# T\n\nOpen.\n\n## One\n\nA.\n')
        self.assertEqual(list(found), ['title', 'opening', 'sections', 'images'])
        self.assertEqual(desk.join(found), '# T\n\nOpen.\n\n## One\n\nA.\n')


class SharedChecksTests(unittest.TestCase):
    def test_finishing_checks_with_the_shared_guards_and_proofread(self):
        self.assertIs(desk_finish.STRUCTURE, guards.STRUCTURE)
        self.assertIs(desk_finish._mask_indented, proofread.mask_indented)
        self.assertIs(desk_finish._sentences, proofread.sentences)
        self.assertEqual(desk_images.REFERENCE.pattern, guards.REFERENCE.pattern)
        self.assertEqual(
            desk_finish.changes_facts('In 2024.', 'In 2025.'),
            'Check the facts: this changes a number.',
        )


class SharedRecordTests(DeskCase):
    def test_the_desk_record_is_the_shared_one_with_blog_s_store(self):
        made = self.make()
        kept = desk._drafting(self.root)
        self.assertIsInstance(kept, record.Desk)
        self.assertEqual((kept.store.product, kept.store.word), ('Blog Studio', 'blog'))
        self.assertEqual(desk.SOURCES, versions.SOURCES + ('chat', 'google'))
        self.assertEqual(kept.store.folder(made['id']), self.folder(made['id']) / 'desk')

    def test_a_save_still_reaches_blog_s_own_write(self):
        made = self.make()
        part = made['sections'][0]['id']
        with patch('desk._write', side_effect=OSError('Synthetic disk failure')) as write:
            with self.assertRaisesRegex(OSError, 'Synthetic disk failure'):
                desk.save(self.root, made['id'], 1, part, 'New first text.')
        self.assertEqual(write.call_args.args[3], [part])
        self.assertEqual(desk.read(self.root, made['id'])['revision'], 1)

    def test_a_title_holding_an_image_is_refused_by_blog_s_own_rule(self):
        made = self.make()
        with self.assertRaisesRegex(ValueError, desk.TITLE_IMAGE):
            desk.save(self.root, made['id'], 1, 'title', 'A ![x](data:image/png;base64,AAAA) title')


if __name__ == '__main__':
    unittest.main()
