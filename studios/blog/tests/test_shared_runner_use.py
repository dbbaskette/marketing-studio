"""Blog Studio takes the shared runner's whole modules from the core.

Each module Blog Studio takes is the core's file, one object under Blog Studio's own name
and in `sys.modules`, with Blog Studio's values, and with Blog Studio's own modules standing
in for the host modules the shared code names: Blog Studio has no `runner` package, and its
`hub` is the Team Hub registry, not the Git primitives the shared code calls `hub`.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

from studio_core import shared_runner
from studio_sync import support

SHARED = Path(__file__).resolve().parents[3] / 'core' / 'studio_core' / 'shared_runner'
# Blog Studio's module, the shared runner's module it is, and the modules it was given.
TAKEN = {
    'studio_sync.team': (
        'team',
        {
            'home': 'studio_sync.support',
            'hub': 'studio_sync.support',
            'workspace': 'studio_sync.support',
            'gitstate': 'studio_sync.gitstate',
        },
    ),
    'studio_brand.companion': ('companion', {'workspace': 'studio_sync.support'}),
    'studio_brand.source': (
        'brand_source',
        {
            'hub': 'studio_sync.support',
            'workspace': 'studio_sync.support',
            'companion': 'studio_brand.companion',
            'settings': 'studio_brand.settings',
        },
    ),
}


class SharedRunnerUseTests(unittest.TestCase):
    def test_the_shared_runner_is_the_core_s(self):
        self.assertEqual(Path(shared_runner.__file__).resolve().parent, SHARED.resolve())

    def test_each_module_taken_is_the_core_s_file_under_blog_studio_s_name(self):
        for name, (shared, given) in TAKEN.items():
            with self.subTest(module=name):
                self.assertIn(shared, shared_runner.WHOLE)
                module = importlib.import_module(name)
                self.assertEqual(
                    Path(module.__file__).resolve(), (SHARED / f'{shared}.py').resolve()
                )
                self.assertIs(sys.modules[name], module)
                package, _, short = name.rpartition('.')
                self.assertIs(getattr(sys.modules[package], short), module)
                self.assertEqual(module.PRODUCT, 'Blog Studio')
                self.assertEqual(
                    {key: value.__name__ for key, value in module.MODULES.items()}, given
                )
                self.assertIs(module.WorkspaceError, support.WorkspaceError)

    def test_the_host_modules_are_blog_studio_s_own(self):
        from studio_brand import companion, settings, source
        from studio_sync import gitstate, team

        for held in (team.home, team.hub, team.workspace, source.hub):
            self.assertIs(held, support)
        self.assertIs(team.gitstate, gitstate)
        self.assertIs(source.companion, companion)
        self.assertIs(source.settings, settings)
        self.assertNotIn('runner', sys.modules)
        registry = sys.modules.get('hub')
        self.assertTrue(registry is None or registry is not support)

    def test_blog_studio_s_values(self):
        from studio_sync import team

        self.assertEqual(
            (team.ITEM, team.NOTIFY, team.TAG_UNDER_TOOL, team.REVISION_MARK, team.APP),
            ('blog', 'BLOG_STUDIO_NOTIFY', True, '', 'Blog Studio'),
        )


class DeliberateChangeTests(unittest.TestCase):
    """What the shared modules do that Blog Studio's own copies did not (issue #543)."""

    def test_a_folder_is_not_copied_into_itself(self):
        from studio_sync import team

        with tempfile.TemporaryDirectory() as made:
            folder = Path(made) / 'blog'
            folder.mkdir()
            (folder / 'draft.md').write_text('Synthetic.\n')
            for target in (folder / 'inside', folder):
                with self.assertRaises(support.WorkspaceError) as refused:
                    team.copy_in(folder, target)
                self.assertEqual(str(refused.exception), team.INTO_ITSELF)
            self.assertEqual(
                sorted(path.name for path in Path(made).rglob('*')), ['blog', 'draft.md']
            )

    def test_an_unreadable_brand_repository_is_the_shared_refusal(self):
        from studio_brand import source

        self.assertTrue(issubclass(source.Unreadable, support.WorkspaceError))
        with tempfile.TemporaryDirectory() as place:
            with self.assertRaises(source.Unreadable):
                source.head(str(Path(place) / 'missing'), Path(place))

    def test_a_quick_question_runs_without_a_watcher(self):
        from studio_brand import companion

        code, out, _ = companion.ask([sys.executable, '-c', 'print("asked")'], None, 'A command')
        self.assertEqual((code, out), (0, 'asked\n'))


if __name__ == '__main__':
    unittest.main()
