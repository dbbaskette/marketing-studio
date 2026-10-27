"""A studio's page may link to the suite's shared page files, and to nothing else.

`studio_core.packaging.shared_link` is the one gate packages, bundles and installs pass
links through: a page file that links to `ui-kit/` under its own name travels as a plain
copy, and any other link stops the package.
"""
import importlib
import tempfile
import unittest
from pathlib import Path

import marketing_studio  # noqa: F401  (puts core/ on the path)

packaging = importlib.import_module('studio_core.packaging')


class SharedLinkTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        # macOS's temporary folder is itself a link: compare against the real path.
        self.root = Path(folder.name).resolve()
        (self.root / 'core/studio_core').mkdir(parents=True)
        (self.root / 'core/studio_core/__init__.py').write_text('')
        (self.root / 'ui-kit').mkdir()
        for name in ('drafting.js', 'style.css', 'markdown.js'):
            (self.root / 'ui-kit' / name).write_text('/* ' + name + ' */\n')
        self.assets = self.root / 'studios/example/assets'
        self.assets.mkdir(parents=True)

    def link(self, name, target):
        path = self.assets / name
        path.symlink_to(Path('../../../ui-kit') / target)
        return path

    def test_the_desk_kit_links_to_ui_kit_under_its_own_name(self):
        self.assertTrue(packaging.shared_link(self.link('drafting.js', 'drafting.js')))

    def test_the_kit_s_name_may_not_point_at_another_ui_kit_file(self):
        self.assertFalse(packaging.shared_link(self.link('drafting.js', 'style.css')))

    def test_another_name_may_not_point_at_the_kit(self):
        self.assertFalse(packaging.shared_link(self.link('other.js', 'drafting.js')))

    def test_the_older_shared_page_files_still_link(self):
        self.assertTrue(packaging.shared_link(self.link('style.css', 'style.css')))
        self.assertTrue(packaging.shared_link(self.link('markdown.js', 'markdown.js')))

    def test_training_studio_s_desk_links_the_kit(self):
        repository = Path(__file__).resolve().parents[1]
        link = repository / 'studios/training/skills/training-studio/scripts/desk/drafting.js'
        self.assertTrue(link.is_symlink())
        self.assertTrue(packaging.shared_link(link))

    def test_a_package_walk_carries_the_kit_as_a_file(self):
        self.link('drafting.js', 'drafting.js')
        found = packaging.files(self.assets)
        self.assertEqual([path.name for path in found], ['drafting.js'])
        self.assertEqual(found[0].read_text(), '/* drafting.js */\n')


if __name__ == '__main__':
    unittest.main()
