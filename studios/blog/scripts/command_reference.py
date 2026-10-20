#!/usr/bin/env python3
"""Generate/check the command inventory from the shipped argparse tree."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/blog-studio/scripts'))
import studio


def commands(parser, prefix='studio.py'):
    rows = []
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, child in action.choices.items():
            command = prefix + ' ' + name
            flags = ', '.join(
                '`' + item.option_strings[0] + '`'
                for item in child._actions
                if item.option_strings and item.dest != 'help'
            )
            rows.append('| `' + command + '` | ' + (flags or '—') + ' |')
            rows.extend(commands(child, command))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = (
        '# Blog Studio command inventory\n\nGenerated from `studio.py`; use `--help` on a listed command for required inputs and choices. Prefix each with `--root /absolute/workspace`. Optional global `--compact` returns the bounded outcome contract described in [capabilities](capabilities.md).\n\n| Command | Options |\n| --- | --- |\n'
        + '\n'.join(commands(studio.parser()))
        + '\n'
    )
    destination = ROOT / 'docs/commands.md'
    if args.check:
        if not destination.is_file() or destination.read_text() != content:
            parser.exit(1, 'Command inventory changed. Run python3 scripts/command_reference.py.\n')
    else:
        destination.write_text(content)


if __name__ == '__main__':
    main()
