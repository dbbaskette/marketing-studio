#!/usr/bin/env python3
"""Training Studio helper. Run from the training directory; every command prints JSON."""
import sys

if sys.version_info < (3, 11):
    sys.exit('Training Studio needs Python 3.11 or newer; this is '
             + sys.version.split()[0] + '.')

import argparse
import importlib.util
import json
from pathlib import Path

import home
import workspace
from assess import describe, run_checks


class JsonParser(argparse.ArgumentParser):
    """An argument parser whose usage errors are JSON, like every other refusal."""

    def error(self, message):
        print(json.dumps({'error': message}))
        sys.exit(2)


class ListOf(argparse.Action):
    """A flag that takes a list: values separated by spaces, or by commas as before, each
    one of `options`."""

    def __init__(self, option_strings, dest, options=(), **kwargs):
        self.options = tuple(options)
        kwargs.setdefault('metavar', '{' + ','.join(self.options) + '}')
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        found = [part.strip() for value in values for part in value.split(',') if part.strip()]
        for value in found:
            if value not in self.options:
                parser.error(f'argument {option_string}: invalid choice: {value!r} '
                             f"(choose from {', '.join(self.options)})")
        setattr(namespace, self.dest, found)


def plugins() -> list:
    """Optional command modules: every cmd_*.py beside this file.

    Each defines register(commands), which adds its sub-commands and gives each a `handler`
    default: a function taking (args, root) and returning the JSON to print.
    """
    found = []
    for path in sorted(Path(__file__).resolve().parent.glob('cmd_*.py')):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        found.append(module)
    return found


# The commands that continued a training a conversation made, which nothing does any more
# (GitHub issue #547). Typed, each answers with ENDED and changes nothing.
ENDED_COMMANDS = ('save', 'approve', 'skip', 'checkpoint', 'research-import', 'pin', 'export')
ENDED = ('Training Studio no longer continues a training made in a conversation with this '
         'helper. Bring it in on the Training Studio page and open it on the desk, or start a '
         'new training.')


def summarise(root: Path) -> dict:
    """Status for the user; also remembers where this training is."""
    report = describe(root)
    home.remember(root, report['title'], report['levels'])
    return report


def parser() -> argparse.ArgumentParser:
    top = JsonParser(prog='training.py', description=__doc__)
    top.add_argument('--dir', default='.',
                     help='training directory (default: the current directory)')
    commands = top.add_subparsers(dest='command', required=True, parser_class=JsonParser)

    init = commands.add_parser('init', help='retired; use checked desk commands for new work')
    init.add_argument('--title', required=True, help='the title of the training')
    init.add_argument('--levels', action=ListOf, options=workspace.LEVELS, nargs='+',
                      default=[], help='the levels, separated by spaces, for example 101 301; '
                                       'omit for a plain training')
    init.add_argument('--brief-kind', choices=workspace.BRIEF_KINDS, default='product',
                      help='the kind of brief to write (default: product)')
    init.add_argument('--deck-target', choices=workspace.DECK_TARGETS,
                      help='build the deck as a PowerPoint file or in Google Slides')
    init.add_argument('--brand', help='the brand the deck is built in; empty for none')
    init.add_argument('--delivery', choices=workspace.DELIVERIES, default='live',
                      help='how the deck is used: live, presented in a session, or reading, '
                           'read on its own (default: live)')
    init.add_argument('--copies', action=ListOf, options=workspace.COPIES, nargs='*',
                      default=[], help='copies to keep of each document and brief, separated '
                                       'by spaces; alone, none')
    init.add_argument('--yoodli', action='store_true',
                      help='also build a Yoodli scenario from each scenario file (optional)')
    init.add_argument('--approval', choices=workspace.APPROVAL, default='chat',
                      help='where gates are decided: in the conversation, or on the page')

    commands.add_parser('status', help='stage, next step and the status of every artifact')

    check = commands.add_parser('check', help='run the checks and report readiness')
    check.add_argument('--complete', action='store_true',
                       help='exit 1 unless the training is ready')
    check.add_argument('--all', action='store_true', help='list checks that passed too')

    commands.add_parser('list', help='the trainings on this computer, most recent first')
    for name in ENDED_COMMANDS:
        ended = commands.add_parser(name, help='ended: a training a conversation made is '
                                               'brought in and opened on the desk')
        ended.add_argument('given', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    for plugin in plugins():
        plugin.register(commands)
    return top


def dispatch(args: argparse.Namespace, root: Path) -> dict:
    """Helper writes serialize with desk ownership changes and refuse what they may not
    change (`write_guard`)."""
    if args.command in ENDED_COMMANDS:
        raise workspace.WorkspaceError(ENDED)
    google_write = args.command == 'google' and args.google_command in {'push', 'record', 'pull', 'unlink'}
    if not google_write:
        return _dispatch(args, root)
    import write_guard
    with write_guard.admitted(root):
        return _dispatch(args, root)


def _dispatch(args: argparse.Namespace, root: Path) -> dict:
    handler = getattr(args, 'handler', None)
    if handler is not None:
        return handler(args, root)
    if args.command == 'list':
        return {'trainings': home.trainings()}
    if args.command == 'init':
        raise workspace.WorkspaceError('New training cannot use init. Use the checked desk commands for new work.')
    if args.command == 'status':
        return summarise(root)
    return run_checks(root, args.all)


def ended(argv: list[str] | None) -> bool:
    """Whether the command asked for is one that continued a conversation's training, whatever
    else was given with it: it is answered before anything is read (GitHub issue #547)."""
    rest = list(sys.argv[1:] if argv is None else argv)
    while rest and rest[0].startswith('--dir'):
        rest = rest[2:] if rest[0] == '--dir' else rest[1:]
    return bool(rest) and rest[0] in ENDED_COMMANDS


def main(argv: list[str] | None = None) -> int:
    if ended(argv):
        print(json.dumps({'error': ENDED}))
        return 2
    args = parser().parse_args(argv)
    try:
        output = dispatch(args, Path(args.dir).resolve())
    except workspace.WorkspaceError as refusal:
        print(json.dumps({'error': str(refusal)}))
        return 2
    except (OSError, ValueError) as failure:
        print(json.dumps({'error': f'{type(failure).__name__}: {failure}'}))
        return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.command != 'check':
        return 0
    return 0 if (output['ready'] if args.complete else output['checks_passed']) else 1


if __name__ == '__main__':
    sys.exit(main())
