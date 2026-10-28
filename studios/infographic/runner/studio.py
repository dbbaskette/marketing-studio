#!/usr/bin/env python3
"""Infographic Studio native foundation commands. No command starts a provider."""
import sys

if sys.version_info < (3, 11):
    raise SystemExit('Infographic Studio requires Python 3.11 or newer.')

if not __package__:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from pathlib import Path
import signal
import threading

from runner.contracts import PRODUCT, Invalid
from runner.workspace import Store, data_root, file_lock


def parser():
    top = argparse.ArgumentParser(description=PRODUCT + ' foundations; image generation is not implemented yet.')
    commands = top.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='Read local state without setup, accounts, or provider checks.')
    for name in ('setup', 'serve'):
        command = commands.add_parser(name)
        command.add_argument('--workspace', type=Path, help='Explicit local workspace, kept outside the application repository.')
        if name == 'serve':
            command.add_argument('--port', type=int, default=0)
            command.add_argument('--open', action='store_true', help='Open the foundation page in your default browser.')
    create = commands.add_parser('create', help='Save a new brief in an already configured workspace.')
    create.add_argument('title')
    create.add_argument('--preset', choices=('a4', 'letter', 'digital'), default='a4')
    create.add_argument('--direction', choices=('direct', 'suggest', 'hybrid'), default='suggest')
    show = commands.add_parser('show')
    show.add_argument('id')
    edit = commands.add_parser('edit-brief')
    edit.add_argument('id')
    edit.add_argument('--expected-revision', required=True, type=int)
    edit.add_argument('--file', required=True, type=Path, help='UTF-8 JSON brief, at most 64 KB.')
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'status':
            store = Store.current()
            value = {'product': PRODUCT, 'foundation': True, 'configured': store is not None,
                     'providers': 'not-checked', 'generation_available': False,
                     'projects': store.listing() if store else []}
        elif args.command == 'setup':
            store = Store.setup(args.workspace)
            value = {'product': PRODUCT, 'configured': True, 'workspace': str(store.root)}
        elif args.command == 'serve':
            if not 0 <= args.port <= 65535:
                raise Invalid('Choose a port from 0 to 65535.')
            store = Store.setup(args.workspace)
            from runner import server
            with file_lock(data_root() / '.studio-running.lock'):
                page = server.desk(store, args.port)
                try:
                    page.start()
                    value = {'product': PRODUCT, 'address': page.address, 'foundation': True}
                    if sys.stdout.isatty():
                        value['url'] = page.url
                    print(json.dumps(value), flush=True)
                    if args.open:
                        server.shared.show(page.url)
                    for name in (signal.SIGTERM, signal.SIGINT):
                        signal.signal(name, server.shared.interrupt)
                    threading.Event().wait()
                except KeyboardInterrupt:
                    pass
                finally:
                    page.stop()
            return 0
        else:
            store = Store.current()
            if store is None:
                raise Invalid('Set up or launch Infographic Studio before creating work.')
            if args.command == 'create':
                value = store.create(args.title, preset=args.preset, direction=args.direction)
            elif args.command == 'show':
                value = store.read(args.id)
            else:
                with args.file.open('rb') as stream:
                    raw = stream.read(64_001)
                if len(raw) > 64_000:
                    raise Invalid('A brief is at most 64 KB.')
                value = store.edit_brief(args.id, json.loads(raw), expected_revision=args.expected_revision)
        print(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, RecursionError) as failure:
        message = str(failure) if isinstance(failure, Invalid) else 'Infographic Studio could not read or save that request.'
        print(json.dumps({'error': message}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
