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


def reason_for(flag: str, attached, reason: str | None) -> str | None:
    """The reason that goes with a flag: given with --reason, or after the flag itself, as
    guidance written before --reason does."""
    if attached is None:
        if reason is not None:
            raise workspace.WorkspaceError(f'--reason goes with {flag}.')
        return None
    if isinstance(attached, str):
        if reason is not None and reason != attached:
            raise workspace.WorkspaceError('Give the reason once, with --reason.')
        return attached
    if not (reason or '').strip():
        raise workspace.WorkspaceError(workspace.give_a_reason('chat'))
    return reason


def reasoned(parser, flag: str, text: str) -> None:
    """A flag that is given with --reason, and still takes the reason itself."""
    parser.add_argument(flag, nargs='?', const=True, metavar='REASON', help=text)


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


# Nothing continues a training a conversation made (GitHub issue #547). The helper's
# commands that wrote one answer ENDED for it and change nothing. Three of them did work a
# desk training needs, which this computer drives (a hand edit saved, a Google Doc's edits
# recovered, the copies and levels it keeps): those work on a desk training as before
# (DESK_COMMANDS). The others never changed a desk training: there they say the desk's own
# way (DESK_WAY), and everywhere else they change nothing.
DESK_COMMANDS = ('save', 'checkpoint', 'export')
ENDED_COMMANDS = ('approve', 'skip', 'research-import', 'pin')
ENDED = ('Training Studio no longer continues a training made in a conversation with this '
         'helper: bring it in on the Training Studio page, or start a new training.')
DESK_WAY = {
    'approve': ('On the desk a material is approved by marking it ready: Mark ready on the '
                'page, or `studio desk ready` in a conversation once the person says so.'),
    'skip': ('On the desk a material is left out or brought back with Change settings on the '
             'page, or `studio desk scope` in a conversation at the person\'s request.'),
    'research-import': ('On the desk research is supplied with `studio desk submit` (kind '
                        'research) in a conversation, or made by the page\'s own research '
                        'step.'),
    'pin': ('On the desk the runner records the tasks it starts itself, so nothing is pinned '
            'by hand.'),
}


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

    save = commands.add_parser('save', help='record an artifact of a desk training')
    save.add_argument('artifact', help='the artifact, with @<level> if there are levels')
    how = save.add_mutually_exclusive_group()
    how.add_argument('--from', dest='source', metavar='FILE',
                     help='replace the artifact with this file; the old version is kept')
    how.add_argument('--built', action='store_true',
                     help='the file on disk is a fresh build against its inputs')
    save.add_argument('--coverage', metavar='FILE',
                      help='deck only: JSON mapping each objective to the slides covering it')

    export = commands.add_parser(
        'export', help='make a Word copy of an artifact with pandoc, and record it')
    export.add_argument('artifact', help='the document, the brief or a Yoodli scenario')
    made = export.add_mutually_exclusive_group()
    made.add_argument('--file', help='record a copy made another way, at this path, instead')
    reasoned(made, '--unavailable', 'record that no copy could be made, with why in --reason')
    export.add_argument('--reason', help='why no copy could be made')

    checkpoint = commands.add_parser('checkpoint', help='record where a desk training is')
    checkpoint.add_argument('--stage', choices=workspace.STAGES,
                            help='the stage the training is at')
    checkpoint.add_argument('--level', choices=workspace.LEVELS,
                            help='the level being worked on')
    checkpoint.add_argument('--next', dest='next_step', metavar='TEXT',
                            help='the next step, in a sentence')
    question = checkpoint.add_mutually_exclusive_group()
    question.add_argument('--question', metavar='TEXT',
                          help='the question waiting on the user')
    question.add_argument('--no-question', action='store_true',
                          help='clear the waiting question and the gate')
    checkpoint.add_argument('--brief-kind', choices=workspace.BRIEF_KINDS,
                            help='the kind of brief to write')
    checkpoint.add_argument('--deck-target', choices=workspace.DECK_TARGETS,
                            help='build the deck as a PowerPoint file or in Google Slides')
    checkpoint.add_argument('--brand', help='the brand the deck is built in; empty for none')
    checkpoint.add_argument('--delivery', choices=workspace.DELIVERIES,
                            help='how the deck is used: live, presented in a session, or '
                                 'reading, read on its own')
    checkpoint.add_argument('--copies', action=ListOf, options=workspace.COPIES, nargs='*',
                            help='copies to keep of each document and brief, separated by '
                                 'spaces; alone, none')
    levels = checkpoint.add_mutually_exclusive_group()
    levels.add_argument('--levels', action=ListOf, options=workspace.LEVELS, nargs='+',
                        help='the levels of a levelled training, separated by spaces; '
                             'never drops a level with work in it')
    levels.add_argument('--add-level', dest='add_levels', action=ListOf,
                        options=workspace.LEVELS, nargs='+',
                        help='add one or more levels to a levelled training')
    checkpoint.add_argument('--gate', metavar='ARTIFACT',
                            help='the artifact waiting at the gate; --no-question clears it')
    checkpoint.add_argument('--approval', choices=workspace.APPROVAL,
                            help='where gates are decided; only the page moves it back to chat')

    check = commands.add_parser('check', help='run the checks and report readiness')
    check.add_argument('--complete', action='store_true',
                       help='exit 1 unless the training is ready')
    check.add_argument('--all', action='store_true', help='list checks that passed too')

    commands.add_parser('list', help='the trainings on this computer, most recent first')
    for name in ENDED_COMMANDS:
        ended = commands.add_parser(name, help='not used on the desk, which has its own way')
        ended.add_argument('given', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    for plugin in plugins():
        plugin.register(commands)
    return top


def not_here(command: str, root: Path) -> str:
    """What a removed command, or a desk command given for a training that is not desk work,
    answers for the training in `root`: ENDED for one a conversation made, the desk's own way
    for a desk training, and otherwise what the training's own record says of it."""
    import write_guard
    if workspace.made_in_conversation(root):
        return ENDED
    session = workspace.load(root)   # no training here: its own refusal
    if workspace.on_desk(session):
        return DESK_WAY[command]
    return write_guard.SAVED_RUNNER


def dispatch(args: argparse.Namespace, root: Path) -> dict:
    """Helper writes serialize with desk ownership changes and refuse what they may not
    change (`write_guard`). A conversation's training is changed by none of them."""
    if args.command in ENDED_COMMANDS:
        raise workspace.WorkspaceError(not_here(args.command, root))
    if args.command in DESK_COMMANDS and workspace.made_in_conversation(root):
        raise workspace.WorkspaceError(ENDED)
    google_write = args.command == 'google' and args.google_command in {'push', 'record', 'pull', 'unlink'}
    if args.command not in DESK_COMMANDS and not google_write:
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
    if args.command == 'save':
        coverage = None
        if args.coverage:
            coverage = json.loads(Path(args.coverage).read_text(encoding='utf-8'))
        source = Path(args.source) if args.source else None
        entry = workspace.save(root, args.artifact, source, args.built, coverage)
        state = workspace.status(root)['artifacts'][args.artifact]
        return {'artifact': args.artifact, 'sha256': entry['sha256'], 'status': state}
    if args.command == 'export':
        unavailable = reason_for('--unavailable', args.unavailable, args.reason)
        return workspace.export(root, args.artifact, args.file, unavailable,
                                convert=workspace.pandoc)
    if args.command == 'checkpoint':
        return workspace.checkpoint(root, args.stage, args.next_step, args.question,
                                    args.no_question, args.deck_target, args.brand,
                                    args.brief_kind, args.level, args.levels, args.copies,
                                    args.approval, args.gate, add_levels=args.add_levels,
                                    delivery=args.delivery)
    return run_checks(root, args.all)


def ended(argv: list[str] | None) -> tuple[str, Path] | None:
    """The command asked for and the training's folder, when the command is one of
    ENDED_COMMANDS, whatever else was given with it: it is answered before the rest is read
    (GitHub issue #547). None for any other command."""
    rest = list(sys.argv[1:] if argv is None else argv)
    folder = '.'
    while rest and rest[0].startswith('--dir'):
        if rest[0] == '--dir':
            folder, rest = (rest[1] if len(rest) > 1 else folder), rest[2:]
        else:
            folder, rest = rest[0].partition('=')[2], rest[1:]
    if rest and rest[0] in ENDED_COMMANDS:
        return rest[0], Path(folder).resolve()
    return None


def main(argv: list[str] | None = None) -> int:
    found = ended(argv)
    if found:
        try:
            said = not_here(*found)
        except workspace.WorkspaceError as refusal:
            said = str(refusal)
        print(json.dumps({'error': said}))
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
