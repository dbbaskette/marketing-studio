"""Synthetic image markup is omitted only from display, with code and prose retained."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
from manuscript_preview import fields, text_only


class ManuscriptPreviewTests(unittest.TestCase):
    def test_reference_images_and_embedded_data_are_omitted_without_losing_prose_or_links(self):
        source = '# Synthetic title\n\nBefore ![chart][IMAGE 1] after.\n\n[image 1]: <data:image/png;base64,AAAA>\n\n[read more](https://example.invalid/reference)\n\nLast paragraph.\n'
        shown = text_only(source)
        self.assertIn('Before  after.', shown)
        self.assertIn('[read more](https://example.invalid/reference)', shown)
        self.assertIn('Last paragraph.', shown)
        self.assertNotIn('data:image', shown)
        self.assertNotIn('image 1', shown.lower())
        self.assertEqual(fields(source), {'preview_content': shown, 'images_omitted': True})

    def test_inline_collapsed_shortcut_and_html_images_are_omitted(self):
        source = 'Before ![alt](https://example.invalid/chart(v2).png "Chart") after.\n![chart][]\n![shortcut]\n<img src="data:image/png;base64,AAAA">\n\n[chart]: https://example.invalid/chart.png\n[shortcut]: <https://example.invalid/photo.png>\n'
        self.assertEqual(text_only(source), 'Before  after.\n\n\n\n\n')

    def test_fenced_and_inline_code_and_escaped_examples_are_retained(self):
        source = 'Example `![alt](diagram.png)` and `<img src="sample.png">`.\n\\![literal]\n\n```markdown\n![chart][image1]\n[image1]: <data:image/png;base64,AAAA>\n```\n'
        self.assertEqual(text_only(source), source)
        self.assertEqual(fields(source), {})

    def test_wrapped_data_definition_is_hidden_and_following_text_remains(self):
        source = 'Text.\n\n![chart][image1]\n\n[image1]: <data:image/png;base64,\n    AAAA\n    BBBB>\n\nFollowing paragraph.\n'
        self.assertEqual(text_only(source), 'Text.\n\n\n\n\nFollowing paragraph.\n')


if __name__ == '__main__':
    unittest.main()
