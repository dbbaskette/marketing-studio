"""Blog Studio takes the shared runner's whole modules from the core.

Each module Blog Studio takes is the core's file, one object under Blog Studio's own name
and in `sys.modules`, with Blog Studio's values, and with Blog Studio's own modules standing
in for the host modules the shared code names: Blog Studio has no `runner` package, and its
`hub` is the Team Hub registry, not the Git primitives the shared code calls `hub`.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import ast
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

from studio_core import shared_runner
from studio_sync import support

SHARED = Path(__file__).resolve().parents[3] / 'core' / 'studio_core' / 'shared_runner'
FOLDERS = [isolation.SCRIPTS / 'studio_sync', isolation.SCRIPTS / 'studio_brand']
OWN = {'__init__.py', 'support.py', 'settings.py'}  # Blog Studio's own, not shared code
# Blog Studio's module, the shared runner's module it is, and the modules it was given.
TAKEN = {
    'studio_sync.gitstate': (
        'gitstate',
        {
            'home': 'studio_sync.support',
            'hub': 'studio_sync.support',
            'sync_guidance': 'studio_sync.support',
            'workspace': 'studio_sync.support',
        },
    ),
    'studio_brand.brand': (
        'brand',
        {
            'workspace': 'studio_sync.support',
            'companion': 'studio_brand.companion',
            'brand_source': 'studio_brand.source',
        },
    ),
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
        from studio_brand import brand
        from studio_sync import gitstate, team

        self.assertEqual(
            (team.ITEM, team.NOTIFY, team.TAG_UNDER_TOOL, team.REVISION_MARK, team.APP),
            ('blog', 'BLOG_STUDIO_NOTIFY', True, '', 'Blog Studio'),
        )
        self.assertEqual(
            (gitstate.TOOL, gitstate.FOLDER, gitstate.ITEM, gitstate.ITEMS, gitstate.REMEMBERED),
            ('blog-studio', 'blogs', 'blog', 'blogs', ('name', 'repo', 'folder')),
        )
        self.assertEqual(
            (gitstate.PLACE, gitstate.KEEP_SHARE, gitstate.HELD, gitstate.SYNC_LOCKS),
            (support.place, support.keep_share, support.sync_lock, ()),
        )
        self.assertFalse(gitstate.SET_UP_KEEPS_SHARE)
        self.assertIs(gitstate.Workspace.blog, gitstate.Workspace.item)
        self.assertEqual(
            (brand.ROOTS, brand.UNABLE, brand.QUICK_ASKS, brand.MEDIUM, brand.TELLS_DELIVERY),
            ({}, 'a blog cannot use a brand', False, 'blog', False),
        )
        self.assertEqual((brand.PINS, brand.FLOOR, brand.DOCTOR_PROFILE), (None, None, None))

    def test_no_file_in_the_two_folders_holds_more_than_a_facade(self):
        # Every module there but Blog Studio's own is a facade: a docstring, imports,
        # constant values (strings and tuples of them), and one `sys.modules[__name__] =
        # whole_module(...)`. No function or class of shared code is kept here.
        found = sorted(path for folder in FOLDERS for path in folder.glob('*.py'))
        self.assertEqual(
            sorted(path.name for path in found if path.name not in OWN),
            ['brand.py', 'companion.py', 'gitstate.py', 'source.py', 'team.py'],
        )
        for path in found:
            if path.name in OWN:
                continue
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                made = 0
                for node in tree.body:
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        continue
                    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                        continue  # the docstring
                    self.assertIsInstance(node, ast.Assign, ast.dump(node)[:80])
                    target = node.targets[0]
                    if isinstance(target, ast.Subscript):
                        self.assertEqual(ast.unparse(target), 'sys.modules[__name__]')
                        self.assertEqual(node.value.func.id, 'whole_module')
                        made += 1
                    else:
                        ast.literal_eval(node.value)  # a plain value, nothing else
                self.assertEqual(made, 1)
        for path in FOLDERS:
            self.assertFalse((path / 'vendor.json').exists())


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

    def test_a_nameless_address_keeps_its_clone_folder_and_git_missing_says_workspace(self):
        from unittest import mock

        # A clone's folder name on disk: unchanged, so a rejoin finds the clone it made.
        self.assertEqual(support.name_from('https://example.invalid/---.git'), 'hub')
        with tempfile.TemporaryDirectory() as place:
            with (
                mock.patch.object(support.subprocess, 'run', side_effect=OSError('no git')),
                mock.patch.object(support.shutil, 'which', return_value=None),
                mock.patch.object(support, 'own_ssh', return_value=True),
            ):
                with self.assertRaises(support.WorkspaceError) as refused:
                    support.run(Path(place), 'fetch')
        self.assertEqual(
            str(refused.exception),
            'A workspace needs git, which is not installed. Install it and try again.',
        )

    def test_the_brand_skill_runs_no_readiness_check_or_audit_for_a_blog(self):
        from studio_brand import brand

        ran = []
        made = brand.Brand(
            Path(tempfile.gettempdir()) / 'synthetic-brand',
            run=lambda command, cwd=None: ran.append(command) or (0, '{}', ''),
        )
        ran.clear()
        for refused in (made.ready, lambda: made.audit(Path('deck.pptx'), 'fictional', None)):
            with self.assertRaises(support.WorkspaceError) as said:
                refused()
            self.assertEqual(
                str(said.exception),
                'Blog Studio runs no brand readiness check or audit, so the brand skill was '
                'not asked.',
            )
        self.assertEqual(ran, [])

    def test_a_quick_question_runs_without_a_watcher(self):
        from studio_brand import companion

        code, out, _ = companion.ask([sys.executable, '-c', 'print("asked")'], None, 'A command')
        self.assertEqual((code, out), (0, 'asked\n'))


if __name__ == '__main__':
    unittest.main()
