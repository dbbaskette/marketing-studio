import os
import tempfile
import unittest
from pathlib import Path

import marketing_studio  # noqa: F401  puts the shared core on the import path
from studio_core import brand_guidance


class ReviewTextsTests(unittest.TestCase):
    """The brand's review checklist, read from the path its `guidance start` answer names."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name).resolve()
        self.checklist = self.base / 'slide-review.md'
        self.checklist.write_text('# Brand checklist\n\nUse the Brand checklist.\n',
                                  encoding='utf-8')

    @staticmethod
    def answer(review) -> dict:
        return {'brand': {'review': review}}

    def test_an_absolute_markdown_file_is_read(self):
        self.assertEqual(brand_guidance.review_texts(self.answer(str(self.checklist))),
                         {'brand review checklist': '# Brand checklist\n\nUse the Brand '
                                                    'checklist.\n'})

    def test_anything_else_is_ignored(self):
        text = self.base / 'slide-review.txt'
        text.write_text('Not Markdown.\n', encoding='utf-8')
        folder = self.base / 'folder.md'
        folder.mkdir()
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: (outside / 'secret.md').unlink(missing_ok=True)
                        or outside.rmdir())
        (outside / 'secret.md').write_text('Not the brand.\n', encoding='utf-8')
        link = self.base / 'linked.md'
        os.symlink(outside / 'secret.md', link)
        relative = os.path.relpath(self.checklist)
        for review in (relative, str(text), str(folder), str(link), None, 7,
                       str(self.base / 'missing.md')):
            with self.subTest(review=review):
                self.assertEqual(brand_guidance.review_texts(self.answer(review)), {})
        for answer in (None, {}, {'brand': None}, {'brand': 'x'}):
            self.assertEqual(brand_guidance.review_texts(answer), {})

    def test_a_long_checklist_is_cut_at_the_most_a_worker_is_handed(self):
        self.checklist.write_text('x' * (brand_guidance.READ_MOST + 10), encoding='utf-8')
        found = brand_guidance.review_texts(self.answer(str(self.checklist)))
        self.assertEqual(len(found['brand review checklist']), brand_guidance.READ_MOST)


if __name__ == '__main__':
    unittest.main()
