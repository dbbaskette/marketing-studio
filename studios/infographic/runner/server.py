"""Infographic Studio's authenticated native foundation APIs."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from studio_core import server as core

from .contracts import PRODUCT, Invalid
from . import api, computer, exports, history, settings, sources
from .engine import Engine
from .validation import require

WEB = Path(__file__).parent / 'web'
shared = core.for_product(
    '_infographic_studio_server', PRODUCT, 'X-Infographic-Studio-Token', WEB,
    {'/': ('index.html', 'text/html; charset=utf-8'),
     '/style.css': ('style.css', 'text/css; charset=utf-8'),
     '/infographic.css': ('infographic.css', 'text/css; charset=utf-8'),
     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
     '/drafting.js': ('drafting.js', 'text/javascript; charset=utf-8')},
    None, Invalid, reads=('/api/status', '/api/projects', '/api/project', '/api/asset',
                         '/api/desk', '/api/preferences', '/api/computer', '/api/download', '/api/history', '/api/history-before', '/api/image-request'),
    writes=('/api/projects', '/api/project', '/api/action', '/api/preferences', '/api/csv-preview', '/api/csv-selection', '/api/brand-current'))


class Page(shared.Page):
    def __init__(self, port, store, engine=None):
        super().__init__(port)
        self.store = store
        self.injected = engine is not None
        self.engine = engine or Engine(store)

    def body_limit(self, target, headers):
        return 2_000_000 if target in ('/api/action', '/api/csv-preview', '/api/csv-selection') else super().body_limit(target, headers)

    def check_token(self, headers):
        if len(headers.get_all('X-Infographic-Studio-Token') or []) != 1:
            raise shared.Refusal(HTTPStatus.FORBIDDEN, 'Send exactly one page key.')
        super().check_token(headers)

    def read(self, path, one):
        if path not in ('/api/preferences', '/api/computer', '/api/status'):
            require(self.store is not None, 'Finish shared setup before opening Infographic Studio projects.')
        if path == '/api/desk':
            return shared.as_json(HTTPStatus.OK, self.engine.inspect(one('id')))
        if path == '/api/history':
            return shared.as_json(HTTPStatus.OK, {'history': history.entries(self.store, one('id'))})
        if path == '/api/history-before':
            return shared.as_json(HTTPStatus.OK, {'history': history.entries(self.store, one('id'), before=int(one('before')))})
        if path == '/api/image-request':
            from .image_jobs import Jobs
            return shared.as_json(HTTPStatus.OK, Jobs(self.store, {}).details(one('id'), one('request')))
        if path == '/api/preferences':
            return shared.as_json(HTTPStatus.OK, settings.snapshot())
        if path == '/api/computer':
            return shared.as_json(HTTPStatus.OK, computer.inspect())
        if path == '/api/download':
            mime, raw = exports.read(self.store, one('id'), one('export'), one('format'))
            return HTTPStatus.OK, mime, raw
        if path == '/api/status':
            return shared.as_json(HTTPStatus.OK, {'product': PRODUCT, 'foundation': False,
                                  'configured': self.store is not None, 'providers': 'not-checked',
                                  'generation_available': False})
        if path == '/api/projects':
            return shared.as_json(HTTPStatus.OK, {'projects': self.store.listing()})
        if path == '/api/project':
            return shared.as_json(HTTPStatus.OK, {'project': self.store.read(one('id'))})
        if path == '/api/asset':
            mime, raw = self.store.read_asset(one('id'), one('asset'))
            return HTTPStatus.OK, mime, raw
        raise shared.Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')

    def write(self, path, sent):
        if path not in ('/api/preferences', '/api/csv-preview', '/api/csv-selection'):
            require(self.store is not None, 'Finish shared setup before creating infographic work.')
        if path == '/api/action':
            try:
                configured = not self.injected and isinstance(sent, dict) and sent.get('action') in ('suggest', 'art-direct', 'build', 'image-start', 'preview', 'export', 'inspect-images', 'revise-art', 'repair', 'revise-story')
                return shared.as_json(HTTPStatus.OK, {'result': api.action(api.engine(self.store) if configured else self.engine, sent)})
            except Invalid:
                raise
            except Exception as failure:
                raise Invalid('Infographic Studio could not complete this action. Saved sources, history and earlier deliveries are kept.') from failure
        if path == '/api/preferences':
            require(isinstance(sent, dict) and set(sent) == {'changes', 'expected'}, 'Save only the shown native defaults and their revision.')
            return shared.as_json(HTTPStatus.OK, settings.save(sent['changes'], expected=sent['expected']))
        if path == '/api/csv-preview':
            import base64
            require(isinstance(sent, dict) and set(sent) == {'data'} and isinstance(sent['data'], str), 'Supply CSV bytes for preview.')
            return shared.as_json(HTTPStatus.OK, sources.csv_preview(api.source_bytes(sent['data'])))
        if path == '/api/csv-selection':
            import base64
            require(isinstance(sent, dict) and set(sent) == {'data', 'selection'} and isinstance(sent['data'], str), 'Validate one explicit CSV selection.')
            _, selection = sources.select_csv(api.source_bytes(sent['data']), sent['selection'])
            return shared.as_json(HTTPStatus.OK, {'valid': True, 'selection': selection})
        if path == '/api/brand-current':
            from . import brand
            require(isinstance(sent, dict) and set(sent) == {'id', 'expected_revision'}, 'Pin a brand to the exact current infographic revision.')
            chosen = settings.snapshot()['brand']
            require(chosen.get('skill') and chosen.get('brand'), 'Select an installed brand and variant in shared Marketing Studio settings first.')
            pinned = brand.export_selected(skill=Path(chosen['skill']), brand_id=chosen['brand'], variant=chosen.get('variant'))
            project = self.store.update(sent['id'], {'brand': pinned}, expected_revision=sent['expected_revision'])
            return shared.as_json(HTTPStatus.OK, {'project': project})
        if path == '/api/projects':
            if set(sent) - {'title', 'preset', 'direction', 'request_id'}:
                raise Invalid('Supply only a title, page preset, and direction.')
            project = self.store.create(sent.get('title'), preset=sent.get('preset', 'a4'),
                                        direction=sent.get('direction', 'suggest'), request_id=sent.get('request_id'))
            return shared.as_json(HTTPStatus.CREATED, {'project': project})
        if path == '/api/project':
            if set(sent) != {'id', 'expected_revision', 'brief'}:
                raise Invalid('Save the brief with its infographic ID and expected revision.')
            project = self.store.edit_brief(sent['id'], sent['brief'],
                                            expected_revision=sent['expected_revision'])
            return shared.as_json(HTTPStatus.OK, {'project': project})
        raise shared.Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')


def desk(store, port=0, engine=None, *, standalone=False):
    class Desk(shared.Desk):
        def set_store(self, current):
            self.page.store = current
            self.page.engine = Engine(current)

        def stop(self):
            from .images.codex import stop_owned
            from .workspace import data_root
            from .image_jobs import Jobs
            store = self.page.store
            for item in store.listing() if store is not None else ():
                if item.get('problem'):
                    continue
                try:
                    project = store.read(item['id'])
                    for attempt in project['attempts']:
                        if attempt['state'] in ('queued', 'running', 'unknown'):
                            project = Jobs(store, {}).cancel(project['id'], attempt['id'], expected_revision=project['revision'])
                except (ValueError, OSError):
                    # Never overwrite changed/unreadable work during shutdown.
                    pass
            if store is not None:
                stop_owned(store.root / 'projects')
            stop_owned(data_root() / 'jobs')
            super().stop()
    page = Desk(port=port, page=lambda actual_port: Page(actual_port, store, engine))
    if standalone:
        from studio_core import onboarding
        from .workspace import Store
        def prepare(values):
            current = Store.current()
            if current is None:
                local = Path((values.get('local') or {}).get('root') or '~/Studios').expanduser()
                current = Store.setup(local / 'infographic-workspace')
            page.set_store(current)
        onboarding.attach(page, PRODUCT, shared.TOKEN_HEADER, prepare, onboarding.config(PRODUCT))
    return page
