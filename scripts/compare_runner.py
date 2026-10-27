#!/usr/bin/env python3
"""Compare one runner module of Presentation Studio and Training Studio, definition by definition.

    python3 scripts/compare_runner.py <module> [<module> ...]
    python3 scripts/compare_runner.py --counts <module> [<module> ...]

Each top-level function, constant (an assignment) and class is a definition; so is each
method and class-level assignment inside a class, named `Class.name`, and a class's own
line with its decorators and docstring, named `Class`. Imports and other top-level
statements are not compared. A definition is

    same            the same text in both copies;
    words only      the same once product words (Presentation Studio, Training Studio and
                    their variable and folder spellings) and item words (deck, decks,
                    training, trainings, in any case) are set aside;
    different       in both copies, differing in more than those words;
    one side only   in one copy only, named with the studio that has it.

Standard library only; it reads `studios/presentation/runner/<module>.py` and
`studios/training/runner/<module>.py` and changes nothing.
"""
import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDES = (('Presentation Studio', ROOT / 'studios' / 'presentation' / 'runner'),
         ('Training Studio', ROOT / 'studios' / 'training' / 'runner'))
KINDS = ('same', 'words only', 'different', 'one side only')

# Product words first, so "Training Studio" is not read as the item word "training".
WORDS = [(re.compile(pattern), replacement) for pattern, replacement in (
    (r'Presentation Studio|Training Studio', '<PRODUCT>'),
    (r'PRESENTATION_STUDIO|TRAINING_STUDIO', '<PRODUCT_VARIABLE>'),
    (r'presentation-studio|training-studio', '<product-folder>'),
    (r'presentation_studio|training_studio', '<product_name>'),
    (r'(?<![A-Za-z])(?:DECKS|TRAININGS)(?![A-Za-z])', '<ITEMS>'),
    (r'(?<![A-Za-z])(?:DECK|TRAINING)(?![A-Za-z])', '<ITEM>'),
    (r'(?<![A-Za-z])(?:Decks|Trainings)(?![a-z])', '<Items>'),
    (r'(?<![A-Za-z])(?:Deck|Training)(?![a-z])', '<Item>'),
    (r'(?<![A-Za-z])(?:decks|trainings)(?![a-z])', '<items>'),
    (r'(?<![A-Za-z])(?:deck|training)(?![a-z])', '<item>'),
)]


def normalised(text):
    for pattern, replacement in WORDS:
        text = pattern.sub(replacement, text)
    return text


def _lines(lines, first, last):
    return ''.join(lines[first - 1:last])


def _start(node):
    return min([node.lineno] + [decorator.lineno for decorator in getattr(node, 'decorator_list', [])])


def _targets(node):
    """The names an assignment sets, as one label."""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names = []
    for target in targets:
        for part in ast.walk(target):
            if isinstance(part, ast.Name):
                names.append(part.id)
            elif isinstance(part, ast.Attribute):
                names.append(ast.unparse(part))
    return ', '.join(names) or ast.unparse(targets[0])


def definitions(text):
    """`{name: text}` for each definition in a module's `text`, in the file's order."""
    lines = text.splitlines(keepends=True)
    found = {}

    def add(name, value):
        label, count = name, 1
        while label in found:            # defined twice: keep both, numbered
            count += 1
            label = f'{name} #{count}'
        found[label] = value

    def walk(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(prefix + node.name, _lines(lines, _start(node), node.end_lineno))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                add(prefix + _targets(node), _lines(lines, node.lineno, node.end_lineno))
            elif isinstance(node, ast.ClassDef):
                first = node.body[0]
                header_end = (first.end_lineno if ast.get_docstring(node) is not None
                              else first.lineno - 1)
                add(prefix + node.name, _lines(lines, _start(node), max(header_end, node.lineno)))
                walk(node.body, prefix + node.name + '.')

    walk(ast.parse(text).body, '')
    return found


def compare(left_text, right_text, left='Presentation Studio', right='Training Studio'):
    """`{kind: [name, ...]}` for the definitions of two copies of one module."""
    ours, theirs = definitions(left_text), definitions(right_text)
    found = {kind: [] for kind in KINDS}
    for name, text in ours.items():
        if name not in theirs:
            found['one side only'].append(f'{name} ({left})')
        elif text == theirs[name]:
            found['same'].append(name)
        elif normalised(text) == normalised(theirs[name]):
            found['words only'].append(name)
        else:
            found['different'].append(name)
    found['one side only'] += [f'{name} ({right})' for name in theirs if name not in ours]
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('modules', nargs='+', metavar='module',
                        help='a runner module both studios have, such as team or slides')
    parser.add_argument('--counts', action='store_true', help='print only the counts')
    options = parser.parse_args(argv)
    for module in options.modules:
        paths = [folder / f'{module}.py' for _, folder in SIDES]
        missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
        if missing:
            print(f'{module}: not found: {", ".join(missing)}', file=sys.stderr)
            return 1
        texts = [path.read_text(encoding='utf-8') for path in paths]
        found = compare(*texts, left=SIDES[0][0], right=SIDES[1][0])
        lines = ' / '.join(str(len(text.splitlines())) for text in texts)
        print(f'{module}.py (lines {lines}): ' + ', '.join(
            f'{len(found[kind])} {kind}' for kind in KINDS))
        if not options.counts:
            for kind in KINDS:
                print(f'  {kind} ({len(found[kind])}):')
                for name in found[kind]:
                    print(f'    {name}')
            print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
