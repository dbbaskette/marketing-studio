#!/usr/bin/env python3
"""The runner's command line.

    studio serve [--port N] [--open]
                               start the runner and print the link to its page
    studio status              what is set up and where every run is, as JSON for a script
    studio saved-work [--folder PATH]
                               which saved trainings still need each older path, as JSON;
                               read-only

`serve` is started by a person. To a terminal it prints the link whole, with its key. To
anything else, such as an assistant or a pipe, it prints the address without the key and
opens the page in the browser itself, so only the person ever holds the key. With --open,
which the installed launcher uses, a person's terminal is given the link and the page is
opened for them as well. It runs until
it is interrupted, and picks every training up where its files say it is when started again.
It fetches a shared workspace when it starts and every few minutes while it serves, and can
tell the person through the computer's own notifications when no page is open. Once it
answers, it looks in the background at whether the skills are in place and current, puts
back a link the installer placed that has gone missing, and at most once a day asks which
releases exist (see `upkeep`). `status` says what was last found, and asks nothing online.
One runner serves on a computer at a time: a second would undo what the first is doing.
"""
import sys

if sys.version_info < (3, 11):
    sys.exit('The runner needs Python 3.11 or newer; this is ' + sys.version.split()[0] + '.')

import argparse
import json
import os
import re
import signal
from contextlib import contextmanager
from pathlib import Path

if not __package__:  # started by its path
    # Through `current`, the first place Python looks is that link: it is made this
    # version's own folder, so a later version installed while this one runs is never read.
    if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
        sys.path[0] = str(Path(__file__).resolve().parent)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runner  # noqa: F401,E402  puts the core on the import path
import cmd_desk  # noqa: E402
import home  # noqa: E402
from workspace import WorkspaceError  # noqa: E402

from runner import engine as engines  # noqa: E402
from runner import gitstate, page, setup, upkeep as upkeeping  # noqa: E402

RESTART = 'TRAINING_STUDIO_RESTART'   # the key, from a runner opening a newer version
KEY = re.compile(r'[A-Za-z0-9_-]{32,128}')


@contextmanager
def only_runner():
    """Be the one runner serving on this computer, or refuse. A runner that ended without
    saying so is not counted."""
    path = home.data_root() / 'runner.pid'
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            kept = path.read_text(encoding='utf-8').strip() if path.is_file() else ''
            if kept.isdigit() and int(kept) != os.getpid() and home.alive(int(kept)):
                raise WorkspaceError(
                    f'A runner is already serving on this computer (process {kept}). Use '
                    'its page, or stop it before starting another. If none is running, '
                    f'remove {path} and try again.')
            path.unlink(missing_ok=True)
            continue
        os.write(handle, f'{os.getpid()}\n'.encode())
        os.close(handle)
        break
    else:
        raise WorkspaceError(f'Could not write {path}, which says a runner is serving.')
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def handed_over() -> str | None:
    """The key a runner that stopped to open a newer version handed to this one, taken out
    of the environment at once so nothing this runner starts is given it."""
    kept = os.environ.pop(RESTART, None)
    try:
        token = json.loads(kept)['token'] if kept else None
    except (ValueError, KeyError, TypeError):
        return None
    return token if isinstance(token, str) and KEY.fullmatch(token) else None


def serve(args, make=engines.Engine, out=None, opener=cmd_desk.show, keeper=None,
          execv=os.execv) -> int:
    """Print one line of JSON, then serve until interrupted. `keeper` makes what looks
    after the skills here, given what to call once it has changed them. When it stops to
    open a newer version, it runs `execv` with the command that opens Training Studio, on
    the same port and with the same key, so the page that is open carries on."""
    out = out or sys.stdout
    token = handed_over()
    space = gitstate.current()
    if space is not None:
        gitstate.identity(space.repo)  # nothing can be recorded without one; says the fix
    with only_runner():
        setup.migrate()     # the values every studio shares, into the file they all read
        from studio_core import workspace_setup, onboarding
        shared_store = onboarding.config('Training Studio')
        workspace_setup.launch(gitstate, shared_store, 'training')
        engine = make()
        engine.upkeep = (keeper or upkeeping.Upkeep)(after=engine.look_again)
        try:
            server = page.Studio(engine, args.port, token=token)
        except OSError:
            if not token:
                raise
            token, server = None, page.Studio(engine, 0)   # the port was taken meanwhile
        def prepare(values):
            workspace_setup.configure(gitstate, values, 'training')

        def configured():
            engine.saved()
            engine.resume(wait=False)

        onboarding.attach(server, 'Training Studio', page.desk.TOKEN_HEADER,
                          prepare, shared_store, after=configured)
        engine.upkeep.leave = server.leave
        signal.signal(signal.SIGTERM, cmd_desk.interrupt)
        try:
            # Opened again in its own place, the page that is open already has the key.
            shown = cmd_desk.announce(server, out.isatty(),
                                      (lambda url: False) if token else opener)
            print(json.dumps(shown), file=out, flush=True)
            if out.isatty() and getattr(args, 'open', False):
                opener(server.url)   # the person's own terminal, and their own browser
            if not hasattr(server, 'answer') or onboarding.preferences.ready(shared_store.read()[0]):
                engine.resume(wait=False)   # the page answers while the workspace is fetched
            engine.upkeep.start()       # and while the skills are looked at
            server.serve()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
    command = getattr(engine.upkeep, 'restarting', None)
    if not command:
        return 0
    os.environ[RESTART] = json.dumps({'token': server.token})
    try:
        execv(command[0], [*command, '--port', str(server.port)])
    except OSError as failure:
        os.environ.pop(RESTART, None)
        print(json.dumps({'error': f'Training Studio could not open again by itself '
                                   f'({failure}). Open it again.'}), file=out, flush=True)
        return 2
    return 0


def status(args, make=engines.Engine, out=None, keeper=None) -> int:
    """What is set up on this computer and where every run is. Starts nothing, changes
    nothing, and asks nothing online: the skills are looked at as they are."""
    engine = make()
    engine.upkeep = (keeper or upkeeping.Upkeep)()
    engine.upkeep.check(repair=False)
    report = {'version': gitstate.installed(), **setup.describe(engine), **engine.status()}
    print(json.dumps(report, indent=2, sort_keys=True), file=out or sys.stdout)
    return 0


def saved_work(args, make=engines.Engine, out=None) -> int:
    """Which saved trainings still need each older path. Starts nothing, changes nothing,
    and asks nothing online."""
    # This command inventories declared local roots without runner upkeep.
    report = make().saved_work(tuple(args.folder or ()))
    print(json.dumps(report, indent=2, sort_keys=True), file=out or sys.stdout)
    return 0


def desk_command(args, make=engines.Engine, out=None):
    """JSON conversation commands; no server, setup, upkeep or assistant launch."""
    from runner import desk_chat
    engine = make()
    try:
        data = None
        if getattr(args, 'input', None):
            stream = sys.stdin if args.input == '-' else open(args.input, encoding='utf-8')
            try:
                raw = stream.read(2_000_001)
            finally:
                if stream is not sys.stdin:
                    stream.close()
            if len(raw) > 2_000_000:
                raise WorkspaceError('The JSON input is too large.')
            try:
                data = json.loads(raw)
            except ValueError:
                raise WorkspaceError('Supply a valid JSON object.') from None
            if not isinstance(data, dict):
                raise WorkspaceError('Supply a JSON object.')
        action = args.desk_action
        if action == 'create':
            data = dict(data)
            named = data.pop('uploads', {})
            if not isinstance(named, dict) or len(named) > 1:
                raise WorkspaceError('Uploads maps one source filename to an explicit local path.')
            uploads = {}
            for name, value in named.items():
                if not isinstance(value, str) or not Path(value).is_absolute():
                    raise WorkspaceError('An upload needs an explicit absolute local path.')
                source = Path(value)
                if source.is_symlink() or not source.is_file() or source.stat().st_size > 64_000_000:
                    raise WorkspaceError('The upload must be a local file of at most 64 MB.')
                uploads[name] = source.read_bytes()
            result = desk_chat.create(engine, data, uploads)
        elif action == 'migration-preview':
            result = desk_chat.migration_preview(engine, args.folder)
        elif action == 'migrate':
            result = desk_chat.migrate(engine, args.folder, args.expected)
        elif action == 'show':
            result = desk_chat.show(engine, args.folder)
        elif action == 'context':
            result = desk_chat.context(engine, args.folder, args.target)
        elif action in ('save', 'submit', 'answer', 'ready', 'return-delivered', 'migration-preview', 'migrate'):
            result = getattr(desk_chat, action.replace('-', '_'))(engine, args.folder, data)
        else:
            required = {'expected_basis', 'scope'}
            optional = {'materials', 'deck_target', 'brand', 'yoodli'} if action == 'scope' else set()
            if not required <= set(data) or not set(data) <= required | optional:
                raise WorkspaceError('Supply expected_basis and scope, with only supported explicit material selections for scope changes.')
            operation = {'scope': desk_chat.set_scope, 'handoff': desk_chat.handoff, 'take': desk_chat.take}[action]
            result = operation(engine, args.folder, data['expected_basis'], data['scope'],
                               **{key: data[key] for key in optional if key in data})
        print(json.dumps(result, indent=2, sort_keys=True), file=out or sys.stdout)
        return 0
    except (ValueError, KeyError, TypeError) as error:
        raise WorkspaceError(str(error)) from None


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog='studio', description=__doc__.splitlines()[0])
    commands = top.add_subparsers(dest='command', required=True)
    serving = commands.add_parser('serve', help='start the runner and print the link')
    serving.add_argument('--port', type=cmd_desk.port, default=0,
                         help='the local port to serve on (default: one the system chooses)')
    serving.add_argument('--open', action='store_true',
                         help='also open the page in the browser, when started in a terminal')
    serving.set_defaults(handler=serve)
    commands.add_parser('status', help='what is set up and where every run is, as JSON'
                        ).set_defaults(handler=status)
    saving = commands.add_parser('saved-work', help='which saved trainings still need each '
                                 'older path, as JSON')
    saving.add_argument('--folder', action='append', type=Path,
                        help='a training folder to look at besides the workspace')
    saving.set_defaults(handler=saved_work)
    conversation = commands.add_parser('desk', help='checked conversation work as JSON')
    actions = conversation.add_subparsers(dest='desk_action', required=True)
    for name in ('create', 'show', 'save', 'context', 'submit', 'scope', 'handoff', 'take', 'answer', 'ready', 'return-delivered', 'migration-preview', 'migrate'):
        action = actions.add_parser(name)
        if name != 'create':
            action.add_argument('--folder', required=True, type=Path)
        if name not in ('show', 'context', 'migration-preview', 'migrate'):
            action.add_argument('--input', required=True, help='JSON file, or - for stdin')
        if name == 'migrate':
            action.add_argument('--expected', required=True)
        if name == 'context':
            action.add_argument('--target', required=True)
        action.set_defaults(handler=desk_command)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except WorkspaceError as refusal:
        print(json.dumps({'error': str(refusal)}))
        return 2
    except OSError as failure:
        print(json.dumps({'error': f'{type(failure).__name__}: {failure}'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
