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
    for name in ('action', 'inspect', 'history', 'computer', 'preferences', 'source-show'):
        command = commands.add_parser(name, help={
            'action': 'Run a checked desk action from JSON; see the native skill for action fields.',
            'inspect': 'Read current content, findings, deliveries and recovery without provider work.',
            'history': 'List immutable saved revisions.',
            'computer': 'Show non-secret local prerequisites; never generate a test image.',
            'preferences': 'Read page/image defaults; shared assistant and brand settings stay authoritative.',
            'source-show': 'Read an exact captured source and its extraction coverage without fetching.'}[name])
        if name in ('action', 'inspect', 'history', 'source-show'):
            command.add_argument('id')
        if name == 'source-show': command.add_argument('--source-id', required=True)
        if name == 'history': command.add_argument('--before', type=int, help='Read an earlier page of immutable revisions.')
        if name == 'action':
            command.add_argument('--file', required=True, type=Path, help='JSON action with expected_revision and stage data.')
    extra=commands.add_parser('handoff-inventory');extra.add_argument('--root',type=Path,required=True);extra.add_argument('--studio',required=True)
    extra=commands.add_parser('handoff-preview');extra.add_argument('--root',type=Path,required=True);extra.add_argument('--studio',required=True);extra.add_argument('--file',required=True);extra.add_argument('--expected-sha256',required=True)
    extra=commands.add_parser('research-task');extra.add_argument('id');extra.add_argument('--source-mode',choices=('selected','mixed','public'),default='selected')
    extra=commands.add_parser('research-preview');extra.add_argument('id');extra.add_argument('--case',type=Path,required=True);extra.add_argument('--source-mode',choices=('selected','mixed','public'),default='selected')
    extra=commands.add_parser('team');extra.add_argument('--operation',choices=('status','connect','sync','claim','take','retry'),default='status');extra.add_argument('--file',type=Path,help='Exact JSON claim/head arguments for explicit operations.')
    browse = commands.add_parser('library-browse', help='List the shared Document Library; chooses nothing and writes nothing.')
    browse.add_argument('--query', default='')
    browse.add_argument('--kind', choices=('upload', 'blog', 'presentation', 'training', 'infographic'))
    browse.add_argument('--offset', type=int, default=0)
    remote = commands.add_parser('remote-preview', help='Explicitly read one Google Doc or public page into a local preview.')
    remote.add_argument('--kind', choices=('google-doc', 'url'), required=True)
    remote.add_argument('--url', required=True)
    remote.add_argument('--account')
    remote.add_argument('--tab', action='append', dest='tabs')
    preview = commands.add_parser('csv-preview', help='Inspect UTF-8 CSV without capturing it or calling a provider.')
    preview.add_argument('--file', required=True, type=Path)
    preview = commands.add_parser('source-preview', help='Capture a local document preview and show readable coverage; no providers.')
    preview.add_argument('--file', required=True, type=Path)
    preview.add_argument('--selection', type=Path)
    for name in ('source', 'source-import', 'facts', 'stories', 'brand', 'image-brief', 'select', 'layout', 'suggest',
                 'build', 'preview', 'check', 'inspect-images', 'approve', 'export', 'restore',
                 'google-deliver', 'edit-text', 'review', 'image-start', 'image-cancel', 'image-recover', 'visual-layout', 'revise-art', 'revise-story', 'repair',
                 'library', 'library-update', 'library-keep'):
        operation = commands.add_parser(name, help='Checked ' + name + ' action; existing work is preserved on failure.')
        operation.add_argument('id')
        operation.add_argument('--expected-revision', required=True, type=int)
        if name in ('source', 'facts', 'stories', 'brand', 'image-brief'):
            operation.add_argument('--file', required=True, type=Path)
        if name == 'library':
            operation.add_argument('--file', required=True, type=Path,
                                   help='JSON list of {"id", "revision"} chosen from library-browse.')
        if name == 'source':
            operation.add_argument('--selection', type=Path, help='Confirmed CSV scope JSON, after csv-preview.')
            operation.add_argument('--replace-id')
        if name == 'source-import':
            operation.add_argument('--capture-id', required=True)
            operation.add_argument('--replace-id')
        if name in ('source', 'source-import'):
            operation.add_argument('--acknowledge-warnings', action='store_true')
        fields = {'select': ('story-id',), 'build': ('request-id',), 'repair': ('request-id',),
                  'restore': ('revision',), 'edit-text': ('element-id', 'text'),
                  'image-start': ('brief-id', 'provider', 'request-id'), 'image-cancel': ('request-id',), 'image-recover': ('request-id',),
                  'revise-art': ('change', 'preserve', 'request-id'), 'revise-story': ('story-id', 'instruction'),
                  'library-update': ('document',), 'library-keep': ('export-id',)}
        for field in fields.get(name, ()):
            operation.add_argument('--' + field, required=True, type=int if field == 'revision' else str)
        if name == 'google-deliver':
            for key in ('export-id', 'request-id'): operation.add_argument('--' + key, required=True)
            operation.add_argument('--account')
            operation.add_argument('--folder')
            operation.add_argument('--reconcile', action='store_true')
        if name == 'layout': operation.add_argument('--arrangement', choices=('infographic', 'stack', 'columns'), default='infographic')
        if name == 'suggest':
            operation.add_argument('--automatic', action='store_true')
            operation.add_argument('--fresh', action='store_true', help='Explicitly request a new assistant response instead of checking a saved one.')
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
        if args.command.startswith('handoff-'):
            from runner import handoffs
            value=handoffs.inventory(args.root,args.studio) if args.command=='handoff-inventory' else handoffs.prepare(args.root,args.studio,args.file,args.expected_sha256)
        elif args.command in ('research-task','research-preview'):
            from runner import research
            store=Store.current()
            if store is None:raise Invalid('Configure Infographic Studio before preparing research.')
            task=research.task(store.read(args.id),args.source_mode)
            value=task if args.command=='research-task' else research.prepare(args.case,expected_task=task)
        elif args.command=='team':
            from runner import team,api
            values=api.load_json(args.file) if args.file else {}
            if args.operation=='status':value={**team.status(),'workspace_owner':Store.current().owner if Store.current() else None}
            elif args.operation in ('connect','sync'):value=team.connect()
            elif args.operation=='retry':value=team.retry_pending(**values)
            else:
                store=Store.current();ident=values.pop('id');value=(team.claim if args.operation=='claim' else team.take)(store,ident,**values)
        elif args.command == 'library-browse':
            from studio_core.document_library import context as library_context
            value = library_context.answer('/api/library', {'filters': {'query': args.query, 'kind': args.kind},
                                           'offset': args.offset, 'limit': 25}, 'infographic')
        elif args.command == 'remote-preview':
            from runner import remote_sources
            value = remote_sources.google(args.url, account=args.account, tabs=args.tabs) if args.kind == 'google-doc' else remote_sources.public(args.url)
        elif args.command == 'source-preview':
            from runner import api, intake, sources
            kind, raw = sources.read_file(args.file)
            value = intake.prepare(raw, kind=kind, name=args.file.name,
                                   selection=api.load_json(args.selection) if args.selection else None)
        elif args.command == 'csv-preview':
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
            elif args.command == 'source-show':
                from runner import sources
                project = store.read(args.id)
                source = next((s for s in project['sources'] if s['id'] == args.source_id), None)
                if source is None: raise Invalid('Choose a captured source from this infographic.')
                value = {'source': source, 'text': sources.read(store, project, source)}
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
                costly = sent.get('action') in ('visual-layout', 'image-recover', 'suggest', 'build', 'art-direct', 'image-start', 'preview', 'export', 'inspect-images', 'revise-art', 'revise-story', 'repair')
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
                    elif args.command == 'library': sent['picks'] = api.load_json(args.file)
                    else: sent['data'] = api.load_json(args.file)
                costly = args.command in ('visual-layout', 'image-recover', 'suggest', 'build', 'image-start', 'preview', 'export', 'inspect-images', 'revise-art', 'revise-story', 'repair')
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
