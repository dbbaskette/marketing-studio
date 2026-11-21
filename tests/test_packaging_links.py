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


class OneVersionTests(unittest.TestCase):
    """The rule every installer shares: one version folder, named through `current`."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.versions = self.root / 'tool/versions'
        for name in ('1.0.0-old', '2.0.0-new'):
            (self.versions / name / 'scripts').mkdir(parents=True)
            (self.versions / name / 'scripts/run.py').write_text(name)
        (self.root / 'tool/current').symlink_to(self.versions / '2.0.0-new')

    def test_every_other_child_goes_and_the_kept_version_is_untouched(self):
        (self.versions / '.pending-0123abcd/half').mkdir(parents=True)
        (self.versions / 'stray.txt').write_text('a stray file')
        cleaned = packaging.prune(self.versions, '2.0.0-new')
        self.assertEqual(cleaned, {'removed': [str(self.versions / name) for name in
                                               ('.pending-0123abcd', '1.0.0-old', 'stray.txt')],
                                   'retained': []})
        self.assertEqual([path.name for path in self.versions.iterdir()], ['2.0.0-new'])
        self.assertEqual((self.versions / '2.0.0-new/scripts/run.py').read_text(), '2.0.0-new')

    def test_a_link_is_unlinked_and_what_it_points_at_survives(self):
        outside = self.root / 'elsewhere'
        (outside / 'deep').mkdir(parents=True)
        (outside / 'deep/mine.txt').write_text('kept')
        (self.versions / 'linked').symlink_to(outside, target_is_directory=True)
        (self.versions / 'dangling').symlink_to(self.root / 'nowhere')
        # A link inside a real folder is removed with it, and is not followed either.
        (self.versions / '1.0.0-old/inside').symlink_to(outside, target_is_directory=True)
        cleaned = packaging.prune(self.versions, '2.0.0-new')
        self.assertEqual(sorted(Path(path).name for path in cleaned['removed']),
                         ['1.0.0-old', 'dangling', 'linked'])
        self.assertEqual(cleaned['retained'], [])
        self.assertEqual((outside / 'deep/mine.txt').read_text(), 'kept')

    def test_a_child_that_cannot_be_removed_is_reported_and_the_rest_still_go(self):
        stuck = self.versions / '1.0.0-old'
        (self.versions / '0.9.0-older').mkdir()
        for path in (stuck / 'scripts', stuck):
            path.chmod(0o555)
        self.addCleanup(lambda: [path.chmod(0o755) for path in (stuck, stuck / 'scripts')])
        cleaned = packaging.prune(self.versions, '2.0.0-new')
        self.assertEqual(cleaned['removed'], [str(self.versions / '0.9.0-older')])
        self.assertEqual([kept['path'] for kept in cleaned['retained']], [str(stuck)])
        self.assertTrue(cleaned['retained'][0]['reason'])
        self.assertEqual((stuck / 'scripts/run.py').read_text(), '1.0.0-old')

    def test_a_child_something_still_runs_from_stays_and_is_reported_with_its_reason(self):
        (self.versions / '0.9.0-older').mkdir()
        cleaned = packaging.prune(self.versions, '2.0.0-new', {'1.0.0-old': 'A studio still opens with it.'})
        self.assertEqual(cleaned, {'removed': [str(self.versions / '0.9.0-older')],
                                   'retained': [{'path': str(self.versions / '1.0.0-old'),
                                                 'reason': 'A studio still opens with it.'}]})
        self.assertEqual((self.versions / '1.0.0-old/scripts/run.py').read_text(), '1.0.0-old')

    def test_nothing_is_removed_from_a_linked_or_unexpected_versions_folder(self):
        elsewhere = self.root / 'elsewhere'
        self.versions.rename(elsewhere)
        self.versions.symlink_to(elsewhere, target_is_directory=True)
        cleaned = packaging.prune(self.versions, '2.0.0-new')
        self.assertEqual(cleaned['removed'], [])
        self.assertEqual([kept['path'] for kept in cleaned['retained']], [str(self.versions)])
        self.assertIn('link', cleaned['retained'][0]['reason'])
        self.assertEqual(sorted(path.name for path in elsewhere.iterdir()), ['1.0.0-old', '2.0.0-new'])
        # The version to keep is not there: this is not the folder it was taken for.
        absent = packaging.prune(elsewhere, '3.0.0-absent')
        self.assertEqual(absent['removed'], [])
        self.assertEqual([kept['path'] for kept in absent['retained']], [str(elsewhere)])
        self.assertEqual(sorted(path.name for path in elsewhere.iterdir()), ['1.0.0-old', '2.0.0-new'])
        self.assertEqual(packaging.prune(self.root / 'no such folder', 'any'), {'removed': [], 'retained': []})

    def test_a_path_inside_the_current_version_is_said_through_current(self):
        inside = self.versions / '2.0.0-new/runtime/python/bin/python3'
        self.assertEqual(packaging.stable_address(inside),
                         self.root / 'tool/current/runtime/python/bin/python3')
        self.assertEqual(packaging.stable_address(self.versions / '2.0.0-new'), self.root / 'tool/current')
        # A version that `current` does not name, and any other path, is said as it is.
        for other in (self.versions / '1.0.0-old/scripts/run.py', self.root / 'elsewhere/bin/python3',
                      Path('/usr/bin/python3')):
            self.assertEqual(packaging.stable_address(other), other)

    def test_a_saved_path_into_a_removed_version_is_said_through_current(self):
        # Row 243: a settings value, a job spec or a pin saved before an update names a
        # version folder the update removed; it is re-derived through `current`.
        import shutil
        shutil.rmtree(self.versions / '1.0.0-old')
        saved = self.versions / '1.0.0-old/scripts/run.py'
        self.assertEqual(packaging.stable_address(saved, saved=True), self.root / 'tool/current/scripts/run.py')
        self.assertEqual(packaging.stable_address(saved, saved=True).read_text(), '2.0.0-new')
        self.assertEqual(packaging.stable_address(self.versions / '1.0.0-old', saved=True), self.root / 'tool/current')
        # Without `current` beside it, or outside any `versions/`, a path is said as it is.
        for other in (self.root / 'loose/versions/1.0.0/scripts/run.py', self.root / 'elsewhere/run.py'):
            self.assertEqual(packaging.stable_address(other, saved=True), other)

    def test_a_place_found_through_any_link_is_said_through_current(self):
        skills = self.root / 'skills'
        skills.mkdir()
        (skills / 'tool').symlink_to(self.root / 'tool/current')
        (skills / 'pinned').symlink_to(self.versions / '2.0.0-new')
        for place in (self.root / 'tool/current', skills / 'tool', skills / 'pinned', self.versions / '2.0.0-new'):
            with self.subTest(place=place):
                self.assertEqual(packaging.stable_place(place), self.root / 'tool/current')
        checkout = self.root / 'checkout'
        checkout.mkdir()
        (skills / 'dev').symlink_to(checkout)
        self.assertEqual(packaging.stable_place(skills / 'dev'), skills / 'dev')   # not a version: as named

    def test_only_a_link_into_versions_names_a_version_folder(self):
        current = self.root / 'tool/current'
        self.assertEqual(packaging.version_target(current, str(self.versions / '1.0.0-old')),
                         self.versions / '1.0.0-old')
        self.assertEqual(packaging.version_target(current, 'versions/1.0.0-old'), self.versions / '1.0.0-old')
        self.assertIsNone(packaging.version_target(self.root / 'skills/tool', str(current)))


if __name__ == '__main__':
    unittest.main()
