"""Create isolated module contexts for legacy product facades.

Each facade retains its own public constants and patchable module globals while
all implementations come from one source file. Product modules never share mutable
runtime configuration.
"""
import importlib.util
import sys


def fresh_module(source, name, values):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    module.__dict__.update(values)
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module
