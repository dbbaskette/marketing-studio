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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))

from studio_core import modules  # noqa: E402

SHARED = ROOT / 'core' / 'studio_core' / 'shared_runner'
PRODUCT_WORDS = ('Presentation Studio', 'Training Studio', 'PRESENTATION_STUDIO',
                 'TRAINING_STUDIO', 'presentation-studio', 'training-studio')


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
