"""Presentation Studio takes the shared runner's modules from the core.

Each whole module is the core's file, one object as `runner.<name>` and in `sys.modules`;
each module with shared parts finds every name its bound functions and methods read, they
read this studio's module, and no later definition of the studio's own replaced them.
"""
import importlib
import sys
import unittest
from pathlib import Path
from types import FunctionType

import helpers
import runner_support  # noqa: F401  puts the runner on the import path

import runner
from studio_core import modules, shared_runner

SHARED = helpers.REPO.parent.parent / 'core' / 'studio_core' / 'shared_runner'


def _parts(raw):
    if isinstance(raw, property):
        return [raw.fget, raw.fset, raw.fdel]
    return [getattr(raw, '__func__', raw)]


def bound(namespace):
    """(label, what the studio holds, what the shared module holds) for each name and
    method `bind` set in `namespace`."""
    for record in namespace['__shared_parts__']:
        source = vars(sys.modules[record['source']])
        for name in record['names']:
            yield name, namespace[name], source[name]
        for class_name, methods in record['methods'].items():
            owner, origin = vars(namespace[class_name]), vars(source[class_name])
            for method in methods:
                yield f'{class_name}.{method}', owner[method], origin[method]


class SharedRunnerUseTests(unittest.TestCase):
    def test_the_shared_runner_is_the_core_s(self):
        self.assertEqual(Path(shared_runner.__file__).resolve().parent, SHARED.resolve())

    def test_whole_modules_come_from_core(self):
        for name in shared_runner.WHOLE:
            with self.subTest(module=name):
                module = importlib.import_module('runner.' + name)
                self.assertEqual(Path(module.__file__).resolve(), (SHARED / f'{name}.py').resolve())
                self.assertIs(sys.modules['runner.' + name], module)
                self.assertIs(getattr(runner, name), module)
                self.assertEqual(module.PRODUCT, 'Presentation Studio')

    def test_bound_parts_find_every_name(self):
        for name in shared_runner.PARTS:
            with self.subTest(module=name):
                module = importlib.import_module('runner.' + name)
                namespace = vars(module)
                self.assertIn('__shared_parts__', namespace)
                self.assertEqual(modules.unresolved(namespace), [])
                for label, held, shared in bound(namespace):
                    if not any(isinstance(part, FunctionType) for part in _parts(shared)):
                        self.assertIs(held, shared, label)      # a copied value
                        continue
                    for mine, theirs in zip(_parts(held), _parts(shared)):
                        if theirs is None:
                            self.assertIsNone(mine, label)
                            continue
                        # the shared code, not a later definition of the studio's own
                        self.assertIs(mine.__code__, theirs.__code__, label)
                        self.assertIs(mine.__globals__, namespace, label)


if __name__ == '__main__':
    unittest.main()
