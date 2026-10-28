#!/usr/bin/env python3
"""Infographic Studio checked editing desk. Provider work requires an explicit action."""
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
    top = argparse.ArgumentParser(description=PRODUCT + ': supplied information to a checked single-page export.')
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
    for name in ('action', 'inspect', 'history', 'computer', 'preferences'):
        command = commands.add_parser(name, help={
            'action': 'Run a checked desk action from JSON; see the native skill for action fields.',
            'inspect': 'Read current content, findings, deliveries and recovery without provider work.',
            'history': 'List immutable saved revisions.',
            'computer': 'Show non-secret local prerequisites; never generate a test image.',
            'preferences': 'Read page/image defaults; shared assistant and brand settings stay authoritative.'}[name])
        if name in ('action', 'inspect', 'history'):
            command.add_argument('id')
        if name == 'history': command.add_argument('--before', type=int, help='Read an earlier page of immutable revisions.')
        if name == 'action':
            command.add_argument('--file', required=True, type=Path, help='JSON action with expected_revision and stage data.')
    preview = commands.add_parser('csv-preview', help='Inspect UTF-8 CSV without capturing it or calling a provider.')
    preview.add_argument('--file', required=True, type=Path)
    for name in ('source', 'facts', 'stories', 'brand', 'image-brief', 'select', 'layout', 'suggest',
                 'build', 'preview', 'check', 'inspect-images', 'approve', 'export', 'restore',
                 'edit-text', 'review', 'image-start', 'image-cancel', 'revise-art', 'revise-story', 'repair'):
        operation = commands.add_parser(name, help='Checked ' + name + ' action; existing work is preserved on failure.')
        operation.add_argument('id')
        operation.add_argument('--expected-revision', required=True, type=int)
        if name in ('source', 'facts', 'stories', 'brand', 'image-brief'):
            operation.add_argument('--file', required=True, type=Path)
        if name == 'source':
            operation.add_argument('--selection', type=Path, help='Confirmed CSV scope JSON, after csv-preview.')
            operation.add_argument('--replace-id')
        fields = {'select': ('story-id',), 'build': ('request-id',), 'repair': ('request-id',),
                  'restore': ('revision',), 'edit-text': ('element-id', 'text'),
                  'image-start': ('brief-id', 'provider', 'request-id'), 'image-cancel': ('request-id',),
                  'revise-art': ('change', 'preserve', 'request-id'), 'revise-story': ('story-id', 'instruction')}
        for field in fields.get(name, ()):
            operation.add_argument('--' + field, required=True, type=int if field == 'revision' else str)
        if name == 'layout': operation.add_argument('--arrangement', choices=('stack', 'columns'), default='stack')
        if name == 'suggest': operation.add_argument('--automatic', action='store_true')
        if name == 'export': operation.add_argument('--draft', action='store_true')
        if name == 'restore': operation.add_argument('--sha256')
        if name == 'revise-story': operation.add_argument('--block-id')
        if name == 'review':
            operation.add_argument('--export-id', required=True)
            operation.add_argument('--observation', required=True, action='append', dest='observations')
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'csv-preview':
            from runner import sources
            kind, raw = sources.read_file(args.file)
            if kind != 'csv':
                raise Invalid('Choose a CSV file to preview.')
            value = sources.csv_preview(raw)
        elif args.command == 'preferences':
            from runner import settings
            value = settings.snapshot()
        elif args.command == 'computer':
            from runner import computer
            value = computer.inspect()
        elif args.command == 'status':
            store = Store.current()
            value = {'product': PRODUCT, 'foundation': False, 'configured': store is not None,
                     'providers': 'not-checked', 'generation_available': False,
                     'projects': store.listing() if store else []}
        elif args.command == 'setup':
            store = Store.setup(args.workspace)
            value = {'product': PRODUCT, 'configured': True, 'workspace': str(store.root)}
        elif args.command == 'serve':
            if not 0 <= args.port <= 65535:
                raise Invalid('Choose a port from 0 to 65535.')
            from studio_core import onboarding
            configured, problem = onboarding.config(PRODUCT).read()
            store = Store.setup(args.workspace) if args.workspace is not None else Store.current()
            if store is None and not problem and onboarding.preferences.ready(configured):
                local = Path((configured.get('local') or {}).get('root') or '~/Studios').expanduser()
                store = Store.setup(local / 'infographic-workspace')
            from runner import server
            with file_lock(data_root() / '.studio-running.lock'):
                page = server.desk(store, args.port, standalone=True)
                try:
                    page.start()
                    value = {'product': PRODUCT, 'address': page.address, 'foundation': False}
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
            elif args.command == 'history':
                from runner import history
                value = history.entries(store, args.id, before=args.before)
            elif args.command == 'inspect':
                from runner.engine import Engine
                value = Engine(store).inspect(args.id)
            elif args.command == 'action':
                from runner import api
                sent = api.load_json(args.file)
                if not isinstance(sent, dict) or sent.get('id', args.id) != args.id:
                    raise Invalid('The action belongs to another infographic.')
                costly = sent.get('action') in ('suggest', 'build', 'art-direct', 'image-start', 'preview', 'export', 'inspect-images', 'revise-art', 'revise-story', 'repair')
                from runner.engine import Engine
                value = api.action(api.engine(store) if costly else Engine(store), {**sent, 'id': args.id})
            elif args.command != 'edit-brief':
                from runner import api, sources
                from runner.engine import Engine
                sent = {key: item for key, item in vars(args).items() if key not in ('command', 'file', 'selection') and item is not None}
                sent['action'] = args.command
                if hasattr(args, 'file'):
                    if args.command == 'source':
                        import base64
                        kind, raw = sources.read_file(args.file)
                        sent.update(data=base64.b64encode(raw).decode(), kind=kind, name=args.file.name)
                        if args.selection: sent['selection'] = api.load_json(args.selection)
                    else: sent['data'] = api.load_json(args.file)
                costly = args.command in ('suggest', 'build', 'image-start', 'preview', 'export', 'inspect-images', 'revise-art', 'revise-story', 'repair')
                value = api.action(api.engine(store) if costly else Engine(store), sent)
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
