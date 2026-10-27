"""Blog Studio's desk runs on the shared desk parts in studio_core.drafting."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import unittest

import desk
from studio_core.drafting import parts


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


if __name__ == '__main__':
    unittest.main()
