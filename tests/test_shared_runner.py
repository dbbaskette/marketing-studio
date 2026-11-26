"""The shared runner's package and the way a studio takes its parts.

`studio_core.modules.bind` rebuilds a shared module's functions with a studio module's
globals, so they read the studio's names and every patch on the studio module reaches them;
`unresolved` lists the names a bound function would fail to find when called; `fresh_module`
registers a module under its name while it runs. Nothing here starts a studio.
"""
import ast
import importlib.util
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))

from studio_core import modules  # noqa: E402

SHARED = ROOT / 'core' / 'studio_core' / 'shared_runner'
PRODUCT_WORDS = ('Presentation Studio', 'Training Studio', 'Blog Studio', 'PRESENTATION_STUDIO',
                 'TRAINING_STUDIO', 'BLOG_STUDIO', 'presentation-studio', 'training-studio',
                 'blog-studio')
HOSTS = ('home', 'hub', 'workspace', 'sync_guidance')   # a studio's host modules


def source_module(text, name='shared_parts_example'):
    """A module made from `text`, as a shared runner file would be."""
    module = types.ModuleType(name)
    exec(compile(textwrap.dedent(text), name + '.py', 'exec'), vars(module))
    return module


def studio(text='', name='studio_example'):
    """A studio module's namespace."""
    namespace = {'__name__': name}
    exec(compile(textwrap.dedent(text), name + '.py', 'exec'), namespace)
    return namespace


class BindTests(unittest.TestCase):
    def test_a_bound_function_reads_the_studio_module_s_names(self):
        shared = source_module("""
            GREETING = 'shared'

            def say():
                return GREETING + PRODUCT
        """)
        namespace = studio("PRODUCT = '!'\nGREETING = 'studio'\n")
        modules.bind(namespace, shared, ('say',))
        self.assertEqual(namespace['say'](), 'studio!')
        namespace['GREETING'] = 'patched'
        self.assertEqual(namespace['say'](), 'patched!')
        self.assertIs(namespace['say'].__globals__, namespace)
        self.assertEqual(namespace['say'].__module__, 'studio_example')
        self.assertEqual(namespace['__shared_parts__'],
                         [{'source': 'shared_parts_example', 'names': ['say'], 'methods': {}}])

    def test_defaults_keyword_defaults_docstrings_and_values_are_kept(self):
        shared = source_module("""
            LIMIT = 3

            def count(a, b=2, *, c=LIMIT):
                '''Count.'''
                return a + b + c + EXTRA
        """)
        namespace = studio('EXTRA = 10\n')
        modules.bind(namespace, shared, ('count', 'LIMIT'))
        self.assertEqual(namespace['count'](1), 16)
        self.assertEqual(namespace['count'].__doc__, 'Count.')
        self.assertEqual(namespace['count'].__kwdefaults__, {'c': 3})
        self.assertEqual(namespace['LIMIT'], 3)

    def test_modules_the_source_imported_are_copied_when_the_studio_lacks_them(self):
        shared = source_module("""
            import json
            import os

            def dump(value):
                return json.dumps(value)
        """)
        own_os = types.ModuleType('os')
        namespace = studio()
        namespace['os'] = own_os
        modules.bind(namespace, shared, ('dump',))
        self.assertIs(namespace['json'], sys.modules['json'])
        self.assertIs(namespace['os'], own_os)
        self.assertEqual(namespace['dump']([1]), '[1]')

    def test_methods_and_properties_are_set_on_the_studio_class(self):
        shared = source_module("""
            class Thing:
                def hello(self):
                    return 'hello ' + PRODUCT

                @property
                def size(self):
                    return self._size * SCALE

                @size.setter
                def size(self, value):
                    self._size = value + OFFSET

                @size.deleter
                def size(self):
                    self._size = DELETED

                @staticmethod
                def plain():
                    return PRODUCT

                @classmethod
                def made(cls):
                    return cls.__name__ + PRODUCT
        """)
        namespace = studio("""
            PRODUCT, SCALE, OFFSET, DELETED = 'Studio', 10, 1, 0

            class Thing:
                _size = 1

                def own(self):
                    return 'own'
        """)
        names = ['hello', 'size', 'plain', 'made']
        modules.bind(namespace, shared, methods={'Thing': names})
        Thing = namespace['Thing']
        thing = Thing()
        self.assertEqual(thing.hello(), 'hello Studio')
        self.assertEqual(thing.own(), 'own')
        self.assertEqual(thing.size, 10)
        thing.size = 4
        self.assertEqual(thing.size, 50)
        del thing.size
        self.assertEqual(thing.size, 0)
        self.assertEqual(Thing.plain(), 'Studio')
        self.assertEqual(Thing.made(), 'ThingStudio')
        namespace['PRODUCT'] = 'Patched'
        self.assertEqual(thing.hello(), 'hello Patched')
        self.assertIsInstance(vars(Thing)['size'], property)
        self.assertIsInstance(vars(Thing)['plain'], staticmethod)
        self.assertIsInstance(vars(Thing)['made'], classmethod)
        self.assertIs(vars(Thing)['size'].fset.__globals__, namespace)
        self.assertEqual(Thing.hello.__module__, 'studio_example')
        self.assertEqual(namespace['__shared_parts__'],
                         [{'source': 'shared_parts_example', 'names': [],
                           'methods': {'Thing': names}}])

    def test_each_call_is_recorded(self):
        shared = source_module("""
            A = 1

            class Thing:
                def f(self):
                    return A
        """)
        namespace = studio('class Thing:\n    pass\n')
        modules.bind(namespace, shared, ('A',))
        modules.bind(namespace, shared, methods={'Thing': ['f']})
        self.assertEqual(namespace['__shared_parts__'], [
            {'source': 'shared_parts_example', 'names': ['A'], 'methods': {}},
            {'source': 'shared_parts_example', 'names': [], 'methods': {'Thing': ['f']}}])

    def test_zero_argument_super_is_refused(self):
        shared = source_module("""
            class Base:
                def hello(self):
                    return 'base'

            class Thing(Base):
                def hello(self):
                    return super().hello() + '!'

                def nested(self):
                    return [super().hello() for _ in range(1)]
        """)
        for method in ('hello', 'nested'):
            with self.subTest(method=method):
                namespace = studio('class Thing:\n    pass\n')
                with self.assertRaisesRegex(ValueError, 'super'):
                    modules.bind(namespace, shared, methods={'Thing': [method]})
                self.assertNotIn(method, vars(namespace['Thing']))
                self.assertNotIn('__shared_parts__', namespace)

    def test_super_given_its_class_is_bound_and_finds_the_studio_s_class(self):
        # Naming `super` at all gives a method a __class__ cell; only a call without
        # arguments reads it, so one given its class and instance binds.
        shared = source_module("""
            class Thing:
                def hello(self):
                    return super(Thing, self).hello() + PRODUCT

                def later(self):
                    return (lambda: super(Thing, self).hello())()
        """)
        namespace = studio("""
            PRODUCT = '!'

            class Base:
                def hello(self):
                    return 'studio base'

            class Thing(Base):
                pass
        """)
        modules.bind(namespace, shared, methods={'Thing': ['hello', 'later']})
        self.assertEqual(namespace['Thing']().hello(), 'studio base!')
        self.assertEqual(namespace['Thing']().later(), 'studio base')
        self.assertEqual(modules.unresolved(namespace), [])

    def test_a_name_the_studio_defines_is_refused(self):
        shared = source_module("""
            A = 1

            def f():
                return A

            class Thing:
                def g(self):
                    return A
        """)
        namespace = studio("""
            def f():
                return 'own'

            class Thing:
                def g(self):
                    return 'own'
        """)
        with self.assertRaisesRegex(ValueError, 'already'):
            modules.bind(namespace, shared, ('A', 'f'))
        self.assertNotIn('A', namespace)
        self.assertEqual(namespace['f'](), 'own')
        with self.assertRaisesRegex(ValueError, 'already'):
            modules.bind(namespace, shared, methods={'Thing': ['g']})
        self.assertEqual(namespace['Thing']().g(), 'own')
        self.assertNotIn('__shared_parts__', namespace)

    def test_a_method_for_a_class_the_studio_lacks_is_refused(self):
        shared = source_module("""
            class Thing:
                def g(self):
                    return 1
        """)
        with self.assertRaises(ValueError):
            modules.bind(studio(), shared, methods={'Thing': ['g']})


class UnresolvedTests(unittest.TestCase):
    def test_unresolved_names_are_found_in_nested_code(self):
        shared = source_module("""
            def f():
                return [MISSING for _ in range(2)]
        """)
        namespace = studio()
        modules.bind(namespace, shared, ('f',))
        self.assertEqual(modules.unresolved(namespace), ['f: MISSING'])
        namespace['MISSING'] = 1
        self.assertEqual(modules.unresolved(namespace), [])

    def test_every_kind_of_nested_code_and_method_is_walked(self):
        shared = source_module("""
            def outer():
                def inner():
                    return {key: IN_DICT for key in range(1)}
                gen = (IN_GENERATOR for _ in range(1))
                return inner, gen, lambda: IN_LAMBDA, len

            class Thing:
                def method(self):
                    return IN_METHOD

                @property
                def size(self):
                    return IN_GETTER

                @size.setter
                def size(self, value):
                    IN_SETTER

                @staticmethod
                def plain():
                    return {IN_SET for _ in range(1)}

                @classmethod
                def made(cls):
                    return IN_CLASSMETHOD
        """)
        namespace = studio('class Thing:\n    pass\n')
        modules.bind(namespace, shared, ('outer',),
                     methods={'Thing': ['method', 'size', 'plain', 'made']})
        self.assertEqual(sorted(modules.unresolved(namespace)), sorted([
            'outer: IN_DICT', 'outer: IN_GENERATOR', 'outer: IN_LAMBDA',
            'Thing.method: IN_METHOD', 'Thing.size: IN_GETTER', 'Thing.size: IN_SETTER',
            'Thing.plain: IN_SET', 'Thing.made: IN_CLASSMETHOD']))

    def test_a_class_body_inside_a_function_reads_its_own_names(self):
        shared = source_module("""
            def f():
                class Inner:
                    x = 1
                    y = x + OUTSIDE
                return Inner
        """)
        namespace = studio()
        modules.bind(namespace, shared, ('f',))
        self.assertEqual(modules.unresolved(namespace), ['f: OUTSIDE'])

    def test_nothing_bound_has_nothing_unresolved(self):
        self.assertEqual(modules.unresolved(studio('A = 1\n')), [])


class FreshModuleTests(unittest.TestCase):
    def setUp(self):
        made = tempfile.TemporaryDirectory()
        self.addCleanup(made.cleanup)
        self.folder = Path(made.name)
        self.name = 'fresh_module_example'
        self.addCleanup(sys.modules.pop, self.name, None)

    def write(self, text):
        path = self.folder / 'source.py'
        path.write_text(textwrap.dedent(text), encoding='utf-8')
        return path

    def test_a_fresh_module_is_registered_while_it_runs(self):
        source = self.write("""
            import dataclasses
            import sys

            SELF = sys.modules[__name__]

            @dataclasses.dataclass
            class Point:
                x: 'int'
        """)
        module = modules.fresh_module(source, self.name, {'PRODUCT': 'Example'})
        self.assertIs(module.SELF, module)
        self.assertIs(sys.modules[self.name], module)
        self.assertEqual(module.PRODUCT, 'Example')
        self.assertEqual(module.Point(1).x, 1)

    def test_a_source_that_raises_leaves_the_earlier_entry(self):
        earlier = types.ModuleType(self.name)
        sys.modules[self.name] = earlier
        source = self.write("raise RuntimeError('no')\n")
        with self.assertRaises(RuntimeError):
            modules.fresh_module(source, self.name, {})
        self.assertIs(sys.modules[self.name], earlier)
        del sys.modules[self.name]
        with self.assertRaises(RuntimeError):
            modules.fresh_module(source, self.name, {})
        self.assertNotIn(self.name, sys.modules)


def _without_for_product_docstrings(text):
    """The file's text with each `for_product` docstring left out."""
    lines = text.splitlines(keepends=True)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == 'for_product' and ast.get_docstring(node) is not None:
            first = node.body[0]
            for at in range(first.lineno - 1, first.end_lineno):
                lines[at] = '\n'
    return ''.join(lines)


class SharedRunnerFileTests(unittest.TestCase):
    def files(self):
        found = sorted(SHARED.rglob('*.py'))
        self.assertIn(SHARED / '__init__.py', found)
        return found

    def test_the_package_lists_its_modules(self):
        spec = importlib.util.find_spec('studio_core.shared_runner')
        self.assertIsNotNone(spec)
        from studio_core import shared_runner
        self.assertIsInstance(shared_runner.WHOLE, tuple)
        self.assertIsInstance(shared_runner.PARTS, tuple)
        for name in shared_runner.WHOLE + shared_runner.PARTS:
            self.assertTrue((SHARED / (name + '.py')).is_file(), name)
        self.assertFalse(set(shared_runner.WHOLE) & set(shared_runner.PARTS))

    def test_no_shared_runner_file_names_a_product(self):
        for path in self.files():
            text = path.read_text(encoding='utf-8')
            for word in PRODUCT_WORDS:
                self.assertNotIn(word, text, path.name)

    def test_shared_modules_import_each_other_through_runner(self):
        for path in self.files():
            text = _without_for_product_docstrings(path.read_text(encoding='utf-8'))
            self.assertNotIn('shared_runner import', text, path.name)
            self.assertNotIn('from studio_core.shared_runner.', text, path.name)

    def test_shared_modules_reach_their_fellows_through_runner_or_the_value_passed(self):
        from studio_core import shared_runner
        fellows = set(shared_runner.WHOLE + shared_runner.PARTS)
        for path in self.files():
            whole = path.stem in shared_runner.WHOLE
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split('.')[0]
                        # a whole module takes its host modules through host_module, so a
                        # module its studio passed is the one it uses
                        self.assertFalse(whole and top in HOSTS, f'{path.name}: import {top}')
                        self.assertNotIn(top, fellows, f'{path.name}: import {top}')
                elif isinstance(node, ast.ImportFrom):
                    top = (node.module or '').split('.')[0]
                    self.assertFalse(whole and top in HOSTS, f'{path.name}: from {top}')
                    self.assertNotIn(top, fellows, f'{path.name}: from {top}')
                elif isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'host_module':
                    first, named = node.args[0], node.args[1].value
                    fellow = any(keyword.arg == 'fellow' and keyword.value.value is True
                                 for keyword in node.keywords)
                    self.assertIn(named, fellows if fellow else HOSTS, f'{path.name}: {named}')
                    self.assertEqual(getattr(first, 'func', None) and first.func.id, 'globals',
                                     path.name)


def _fake(name, **values):
    module = types.ModuleType(name)
    module.__dict__.update(values)
    return module


class HostModuleTests(unittest.TestCase):
    """A shared module's host and fellow modules: the ones its studio passed, else imported
    by name as before."""

    def setUp(self):
        made = tempfile.TemporaryDirectory()
        self.addCleanup(made.cleanup)
        folder = Path(made.name)
        (folder / 'runner').mkdir()
        (folder / 'runner' / '__init__.py').write_text('')
        (folder / 'runner' / 'fellow_example.py').write_text("WHO = 'fellow'\n")
        (folder / 'host_example.py').write_text("WHO = 'host'\n")
        isolated = mock.patch.dict(sys.modules)
        isolated.start()
        self.addCleanup(isolated.stop)
        for name in [name for name in sys.modules if name.split('.')[0] == 'runner']:
            del sys.modules[name]
        sys.path.insert(0, str(folder))
        self.addCleanup(sys.path.remove, str(folder))

    def test_a_module_not_passed_is_imported_by_name(self):
        self.assertEqual(modules.host_module({}, 'host_example').WHO, 'host')
        found = modules.host_module({'MODULES': {}}, 'fellow_example', fellow=True)
        self.assertEqual(found.WHO, 'fellow')
        self.assertIs(found, sys.modules['runner.fellow_example'])
        self.assertIs(found, sys.modules['runner'].fellow_example)

    def test_a_fellow_is_found_as_from_runner_import_finds_it(self):
        import runner
        replaced = _fake('runner.fellow_example')
        runner.fellow_example = replaced
        self.assertIs(modules.host_module({}, 'fellow_example', fellow=True), replaced)

    def test_a_module_passed_is_the_one_used(self):
        own_hub, own_fellow = _fake('own_hub'), _fake('own_fellow')
        namespace = {'MODULES': {'host_example': own_hub, 'fellow_example': own_fellow}}
        self.assertIs(modules.host_module(namespace, 'host_example'), own_hub)
        self.assertIs(modules.host_module(namespace, 'fellow_example', fellow=True), own_fellow)
        self.assertNotIn('host_example', sys.modules)
        self.assertNotIn('runner', sys.modules)


class WholeModuleTests(unittest.TestCase):
    """A studio that passes its host modules makes a whole module without a plain import."""

    def setUp(self):
        made = tempfile.TemporaryDirectory()
        self.addCleanup(made.cleanup)
        self.folder = Path(made.name).resolve()
        self.name = 'whole_module_example'
        self.addCleanup(sys.modules.pop, self.name, None)

        class Refused(ValueError):
            pass

        self.workspace = _fake('own_workspace', WorkspaceError=Refused, STATE_DIR='.example')
        self.home = _fake('own_home', data_root=lambda: self.folder / 'data')

    def loaded(self):
        return {name for name in (*HOSTS, 'runner') if name in sys.modules}

    def test_only_a_whole_module_is_made(self):
        from studio_core import shared_runner
        with self.assertRaises(ValueError):
            shared_runner.whole_module('page', self.name, 'Example')
        self.assertNotIn(self.name, sys.modules)

    def test_the_modules_passed_are_used_and_nothing_is_imported_by_name(self):
        from studio_core import shared_runner
        before = self.loaded()
        made = shared_runner.whole_module('companion', self.name, 'Example',
                                          MODULES={'workspace': self.workspace})
        self.assertIs(sys.modules[self.name], made)
        self.assertEqual(made.PRODUCT, 'Example')
        self.assertIs(made.WorkspaceError, self.workspace.WorkspaceError)
        self.assertEqual(Path(made.__file__).resolve(), (SHARED / 'companion.py').resolve())
        self.assertEqual(self.loaded(), before)

    def gitstate(self, **values):
        from studio_core import shared_runner
        hosts = {'home': self.home, 'hub': _fake('own_hub'), 'workspace': self.workspace,
                 'sync_guidance': _fake('own_guidance')}
        return shared_runner.whole_module('gitstate', self.name, 'Example', ITEM='piece',
                                          MODULES=hosts, **values)

    def test_a_sync_holds_the_lock_files_the_studio_names_in_order(self):
        from studio_core.process_lock import ProcessRLock
        made = self.gitstate(SYNC_LOCKS=('first.lock', 'second.lock'))
        repo = self.folder / 'repository'
        (repo / '.git').mkdir(parents=True)
        others = made._also_held(repo)
        self.assertEqual([lock._path() for lock in others],
                         [repo / '.git' / 'first.lock', repo / '.git' / 'second.lock'])
        self.assertTrue(all(isinstance(lock, ProcessRLock) for lock in others))
        order, taken = [], ProcessRLock.acquire

        def acquire(lock, *args, **kwargs):
            order.append(Path(lock._path()).name)
            return taken(lock, *args, **kwargs)

        space = types.SimpleNamespace(repo=repo)
        held = ProcessRLock(lambda: made.workspace_lock_path(repo, self.folder / 'data'))
        with mock.patch.object(ProcessRLock, 'acquire', acquire):
            with made._sync_locks(space, held, others):
                self.assertTrue(all(lock._is_owned() for lock in others))
        self.assertEqual(order, ['studios-write.lock', 'first.lock', 'second.lock'])
        elsewhere = self.folder / 'linked'
        elsewhere.mkdir()
        (elsewhere / '.git').write_text('gitdir: elsewhere\n')
        self.assertEqual(made._also_held(elsewhere), [])

    def test_a_studio_naming_no_lock_file_holds_none_and_its_item_word_names_a_folder(self):
        made = self.gitstate()
        repo = self.folder / 'repository'
        (repo / '.git').mkdir(parents=True)
        self.assertEqual(made._also_held(repo), [])
        space = made.Workspace('Example', repo, 'pieces', 'main')
        self.assertEqual(space.piece('one'), repo / 'pieces' / 'one')
        self.assertEqual(space.item('one'), repo / 'pieces' / 'one')
        self.assertIs(made.WorkspaceError, self.workspace.WorkspaceError)


class WorkspaceValuesTests(WholeModuleTests):
    """What a studio that keeps its workspace its own way passes, and what the others get."""

    def setUp(self):
        super().setUp()
        self.written = {}
        self.home.write_json = lambda path, value: self.written.__setitem__(Path(path), value)
        self.home.read_json = lambda path, default=None: self.written.get(Path(path), default)

    def test_a_studio_passing_nothing_keeps_the_shared_ways(self):
        made = self.gitstate()
        self.assertEqual(made.IGNORED, ('work/', 'sources/', '**/.harness-research/guidance/',
                                        '**/.harness-slides/guidance/', '*.lock',
                                        '**/.studio/lock'))
        self.assertEqual(made.REMEMBERED, ('name', 'repo', 'folder', 'branch', 'address'))
        self.assertEqual((made.PLACE, made.KEEP_SHARE, made.HELD), (None, None, None))
        self.assertTrue(made.SET_UP_KEEPS_SHARE)
        space = made.Workspace('Example', self.folder / 'repo', 'pieces', 'main', 'address')
        made.remember(space)
        self.assertEqual(self.written[made.settings_path()],
                         {'schema': 1, 'name': 'Example', 'repo': str(self.folder / 'repo'),
                          'folder': 'pieces', 'branch': 'main', 'address': 'address'})

    def test_a_studio_s_own_record_and_reader(self):
        asked = []

        def place(kept, marker):
            asked.append((dict(kept), marker))
            return 'trunk', 'from-marker', 'asked'

        made = self.gitstate(REMEMBERED=('name', 'repo', 'folder'), PLACE=place,
                             IGNORED=('one/', 'two/'))
        self.assertEqual(made.IGNORED, ('one/', 'two/'))
        root = self.folder / 'repo' / 'pieces'
        root.mkdir(parents=True)
        (root / 'hub.json').write_text('{}')
        made.remember(made.Workspace('Example', self.folder / 'repo', 'pieces', 'main', 'x'))
        record = {'schema': 1, 'name': 'Example', 'repo': str(self.folder / 'repo'),
                  'folder': 'pieces'}
        self.assertEqual(self.written[made.settings_path()], record)
        self.assertEqual(made.current(), made.Workspace('Example', self.folder / 'repo',
                                                        'pieces', 'trunk', 'from-marker',
                                                        'asked'))
        self.assertEqual(asked, [(record, made.marker)])
        asked.clear()
        made.PLACE = lambda kept, marker: None
        self.assertIsNone(made.current())

    def test_a_studio_s_own_lock_for_a_sync(self):
        held = []

        class Lock:
            def __enter__(self):
                held.append('in')

            def __exit__(self, *exc):
                held.append('out')

        made = self.gitstate(HELD=lambda space: Lock())
        space = made.Workspace('Example', self.folder / 'repo', 'pieces', 'main', None)
        self.assertIsNone(made.sync(space)['reached'])   # no remote: nothing is held
        made.hub.run = lambda *args, **kwargs: types.SimpleNamespace(returncode=1, stderr='')
        made.worker_in_progress = lambda repo, refusal: True
        space = made.Workspace('Example', self.folder / 'repo', 'pieces', 'main', 'address')
        self.assertEqual(made.sync(space)['notice'], made.SYNC_WAIT)
        self.assertEqual(held, ['in', 'out'])


class DeckSyncLockTests(unittest.TestCase):
    def test_each_deck_studio_s_sync_also_holds_blog_studio_s_lock(self):
        # A deck studio's sync in a shared repository never runs while Blog Studio writes
        # there: its facade names Blog Studio's lock file, which the shared code does not.
        for studio in ('presentation', 'training'):
            facade = ROOT / 'studios' / studio / 'runner' / 'gitstate.py'
            calls = [node for node in ast.walk(ast.parse(facade.read_text(encoding='utf-8')))
                     if isinstance(node, ast.Call)
                     and getattr(node.func, 'id', None) == 'for_product']
            self.assertEqual(len(calls), 1, studio)
            passed = {keyword.arg: keyword.value for keyword in calls[0].keywords}
            self.assertEqual(ast.literal_eval(passed['SYNC_LOCKS']), ('blog-studio.lock',),
                             studio)


class CompareRunnerTests(unittest.TestCase):
    def test_definitions_are_sorted_into_same_words_only_different_and_one_side(self):
        spec = importlib.util.spec_from_file_location('compare_runner', ROOT / 'scripts' / 'compare_runner.py')
        compare_runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compare_runner)
        left = textwrap.dedent('''
            import os
            LIMIT = 3

            def same():
                return 1

            def worded():
                return 'Presentation Studio keeps the deck'

            def changed():
                return 1

            class Thing:
                def own(self):
                    return 'decks'

            def only_left():
                pass
        ''')
        right = textwrap.dedent('''
            import os
            LIMIT = 3

            def same():
                return 1

            def worded():
                return 'Training Studio keeps the training'

            def changed():
                return 2

            class Thing:
                def own(self):
                    return 'trainings'

            def only_right():
                pass
        ''')
        found = compare_runner.compare(left, right)
        self.assertEqual(found['same'], ['LIMIT', 'same', 'Thing'])
        self.assertEqual(found['words only'], ['worded', 'Thing.own'])
        self.assertEqual(found['different'], ['changed'])
        self.assertEqual(found['one side only'], ['only_left (Presentation Studio)',
                                                  'only_right (Training Studio)'])


if __name__ == '__main__':
    unittest.main()
