"""Create isolated module contexts for legacy product facades, and bind shared parts.

Each facade retains its own public constants and patchable module globals while
all implementations come from one source file. Product modules never share mutable
runtime configuration.

`bind` takes the other road: a studio keeps its own module, and the functions and
methods both studios share are rebuilt inside it, with its globals, so they read the
studio module's names and every patch on it. `unresolved` lists the names a bound
function would fail to find, which otherwise shows only when it is called.
"""
import builtins
import dis
import importlib.util
import sys
from types import CodeType, FunctionType, ModuleType

_MISSING = object()
_LOADS = frozenset({'LOAD_GLOBAL', 'LOAD_NAME', 'LOAD_FROM_DICT_OR_GLOBALS'})
_STORES = frozenset({'STORE_NAME', 'DELETE_NAME'})


def fresh_module(source, name, values):
    """Run `source` as a new module called `name`, with `values` set before it runs.

    The module is `sys.modules[name]` while it runs, so its own top level (a dataclass,
    a fellow module importing it) finds it. If it raises, the earlier entry is put back.
    """
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    module.__dict__.update(values)
    previous = sys.modules.get(name, _MISSING)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    sys.modules[name] = module
    return module


def _rebuilt(function, namespace, label):
    """`function` again, reading `namespace` as its globals."""
    code = function.__code__
    if '__class__' in code.co_freevars:
        raise ValueError(f'{label} uses super() without arguments, which would name the '
                         'shared class; give super() its class and instance.')
    made = FunctionType(code, namespace, function.__name__, function.__defaults__,
                        function.__closure__)
    made.__kwdefaults__ = None if function.__kwdefaults__ is None else dict(function.__kwdefaults__)
    made.__doc__ = function.__doc__
    made.__qualname__ = function.__qualname__
    made.__annotations__ = dict(function.__annotations__)
    made.__dict__.update(function.__dict__)
    made.__module__ = namespace['__name__']
    return made


def _method(raw, namespace, label):
    """A class attribute holding a function, rebuilt with `namespace`."""
    if isinstance(raw, FunctionType):
        return _rebuilt(raw, namespace, label)
    if isinstance(raw, staticmethod):
        return staticmethod(_rebuilt(raw.__func__, namespace, label))
    if isinstance(raw, classmethod):
        return classmethod(_rebuilt(raw.__func__, namespace, label))
    if type(raw) is property:
        parts = [None if part is None else _rebuilt(part, namespace, label)
                 for part in (raw.fget, raw.fset, raw.fdel)]
        return property(*parts, raw.__doc__)
    raise ValueError(f'{label} is not a function, property, staticmethod or classmethod, '
                     'so it cannot be bound.')


def _functions(raw):
    """The functions inside one class attribute (or one module value)."""
    if isinstance(raw, FunctionType):
        return [raw]
    if isinstance(raw, (staticmethod, classmethod)):
        return [raw.__func__]
    if isinstance(raw, property):
        return [part for part in (raw.fget, raw.fset, raw.fdel) if isinstance(part, FunctionType)]
    return []


def bind(namespace, source, names=(), methods=None):
    """Bind `source`'s `names`, and the `methods` of its classes, into a studio module.

    `namespace` is the studio module's dict (`globals()`). Each function named is rebuilt
    with `namespace` as its globals, so it reads the studio module's names; any other value
    is copied. `methods` maps a class in `namespace` to the names of methods on the class of
    the same name in `source`, rebuilt the same way and set on the studio's class. Module
    objects `source` imported are copied when `namespace` has none by that name.

    Refuses, with ValueError and before changing anything, a function that uses `super()`
    without arguments and a name or method the studio defines itself. What was bound is
    appended to `namespace['__shared_parts__']`.
    """
    methods = dict(methods or {})
    shared = vars(source)
    values = {}
    for name in names:
        if name in namespace:
            raise ValueError(f'{namespace["__name__"]} already defines {name}, so the shared '
                             f'{name} from {source.__name__} is not bound over it.')
        if name not in shared:
            raise ValueError(f'{source.__name__} has no {name} to bind.')
        value = shared[name]
        values[name] = _rebuilt(value, namespace, name) if isinstance(value, FunctionType) else value
    attributes = {}
    for class_name, method_names in methods.items():
        target = namespace.get(class_name)
        origin = shared.get(class_name)
        if not isinstance(target, type) or not isinstance(origin, type):
            raise ValueError(f'Both {namespace["__name__"]} and {source.__name__} need a class '
                             f'{class_name} to bind its methods.')
        for method in method_names:
            label = f'{class_name}.{method}'
            if method in vars(target):
                raise ValueError(f'{namespace["__name__"]}.{label} is already defined, so the '
                                 f'shared {label} from {source.__name__} is not bound over it.')
            if method not in vars(origin):
                raise ValueError(f'{source.__name__}.{class_name} has no {method} to bind.')
            attributes[(class_name, method)] = _method(vars(origin)[method], namespace, label)
    imported = {name: value for name, value in shared.items()
                if isinstance(value, ModuleType) and not name.startswith('__')
                and name not in namespace and name not in values}
    namespace.update(imported)
    namespace.update(values)
    for (class_name, method), value in attributes.items():
        setattr(namespace[class_name], method, value)
    namespace.setdefault('__shared_parts__', []).append({
        'source': source.__name__, 'names': list(names),
        'methods': {name: list(listed) for name, listed in methods.items()}})


def _loaded(code):
    """Every global name `code` and the code inside it loads, in order, once each."""
    found = []
    stored = {instruction.argval for instruction in dis.get_instructions(code)
              if instruction.opname in _STORES}
    for instruction in dis.get_instructions(code):
        if instruction.opname in _LOADS:
            name = instruction.argval
            if instruction.opname != 'LOAD_GLOBAL' and name in stored:
                continue          # a class body reading its own name
            if name not in found:
                found.append(name)
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            found += [name for name in _loaded(constant) if name not in found]
    return found


def unresolved(namespace):
    """`'<function>: <name>'` for each global a bound function or method reads that neither
    `namespace` nor the builtins have, nested code and comprehensions included."""
    known = vars(builtins)
    missing = []
    for record in namespace.get('__shared_parts__', []):
        bound = [(name, namespace.get(name)) for name in record['names']]
        for class_name, method_names in record['methods'].items():
            owner = vars(namespace.get(class_name, type))
            bound += [(f'{class_name}.{method}', owner.get(method)) for method in method_names]
        for label, raw in bound:
            for function in _functions(raw):
                for name in _loaded(function.__code__):
                    line = f'{label}: {name}'
                    if name not in namespace and name not in known and line not in missing:
                        missing.append(line)
    return missing
