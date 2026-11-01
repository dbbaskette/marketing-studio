"""Infographic Studio's authenticated native foundation APIs."""
from __future__ import annotations

from http import HTTPStatus
from copy import copy
from pathlib import Path

from studio_core import server as core
from studio_core.document_library import context as library_context

from .contracts import PRODUCT, Invalid
from . import activity, api, computer, exports, history, settings, sources
from .engine import Engine
from .validation import require

WEB = Path(__file__).parent / 'web'
shared = core.for_product(
    '_infographic_studio_server', PRODUCT, 'X-Infographic-Studio-Token', WEB,
    {'/': ('index.html', 'text/html; charset=utf-8'),
     '/style.css': ('style.css', 'text/css; charset=utf-8'),
     '/infographic.css': ('infographic.css', 'text/css; charset=utf-8'),
     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
     '/drafting.js': ('drafting.js', 'text/javascript; charset=utf-8'),
     '/research.js': ('research.js', 'text/javascript; charset=utf-8')},
    None, Invalid, reads=('/api/status', '/api/projects', '/api/project', '/api/asset',
                         '/api/desk', '/api/activity', '/api/source', '/api/preferences', '/api/computer', '/api/download', '/api/history', '/api/history-before', '/api/image-request', '/api/team', '/api/team-download', '/api/research-task', '/api/research-status'),
    writes=('/api/research-job', '/api/research-control', '/api/research-sources', '/api/projects', '/api/project', '/api/action', '/api/preferences', '/api/csv-preview', '/api/csv-selection', '/api/source-preview', '/api/remote-preview', '/api/handoff-inventory', '/api/handoff-preview', '/api/research-preview', '/api/team', '/api/brand-current', *library_context.ROUTES))


class Page(shared.Page):
    def __init__(self, port, store, engine=None):
        super().__init__(port)
        self.store = store
        self.injected = engine is not None
        self.engine = engine or Engine(store)
        self.activity = activity.Activity()
        from .research_jobs import Jobs
        self.research = Jobs(store) if store is not None else None

    def body_limit(self, target, headers):
        if target == '/api/research-sources':
            try: self.check_token(headers)
            except shared.Refusal: return super().body_limit(target, headers)
        return 24_000_000 if target in ('/api/action', '/api/csv-preview', '/api/csv-selection', '/api/source-preview', '/api/research-sources') else super().body_limit(target, headers)

    def check_token(self, headers):
        if len(headers.get_all('X-Infographic-Studio-Token') or []) != 1:
            raise shared.Refusal(HTTPStatus.FORBIDDEN, 'Send exactly one page key.')
        super().check_token(headers)

    def read(self, path, one):
        if path not in ('/api/preferences', '/api/computer', '/api/status'):
            require(self.store is not None, 'Finish shared setup before opening Infographic Studio projects.')
        if path == '/api/team-download':
            from . import team
            mime,raw=team.download(one('id'),one('format'))
            return 200,mime,raw
        if path == '/api/team':
            from . import team
            return shared.as_json(200,{**team.status(),'workspace_owner':self.store.owner})
        if path == '/api/research-status':
            return shared.as_json(200, self.research.read(one('id')))
        if path == '/api/research-task':
            from . import research
            return shared.as_json(200,research.task(self.store.read(one('id')),one('source_mode')))
        if path == '/api/desk':
            ident = one('id')
            return shared.as_json(HTTPStatus.OK, {**self.engine.inspect(ident),
                                                  'activity': self.activity.snapshot(ident)})
        if path == '/api/activity':
            ident = one('id')
            project = self.store.read(ident)
            from .image_jobs import Jobs
            return shared.as_json(200, {'activity': self.activity.snapshot(ident),
                                       'revision': project['revision'],
                                       'recovery': Jobs(self.store, {}).recovery(ident)})
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
            # Home shows the work each infographic is doing now; observing starts nothing.
            return shared.as_json(HTTPStatus.OK, {'projects': [
                {**item, 'activity': self.activity.snapshot(item['id'])} for item in self.store.listing()]})
        if path == '/api/project':
            return shared.as_json(HTTPStatus.OK, {'project': self.store.read(one('id'))})
        if path == '/api/source':
            project = self.store.read(one('id'))
            source = next((s for s in project['sources'] if s['id'] == one('source')), None)
            require(source is not None, 'Choose one captured source from this infographic.')
            start = int(one('start'))
            value = sources.read(self.store, project, source)
            require(0 <= start <= len(value), 'Choose a position within the captured source.')
            return shared.as_json(200, {'source': source, 'text': value[start:start + 20_000],
                                      'start': start, 'end': min(start + 20_000, len(value)), 'total': len(value)})
        if path == '/api/asset':
            mime, raw = self.store.read_asset(one('id'), one('asset'))
            return HTTPStatus.OK, mime, raw
        raise shared.Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')

    def write(self, path, sent):
        if path in library_context.ROUTES:
            # Browsing the shared Document Library chooses nothing and changes no infographic.
            try:
                return shared.as_json(HTTPStatus.OK, library_context.answer(path, sent, 'infographic'))
            except ValueError as error:
                raise Invalid(str(error)) from None
        if path not in ('/api/preferences', '/api/csv-preview', '/api/csv-selection'):
            require(self.store is not None, 'Finish shared setup before creating infographic work.')
        if path == '/api/research-job':
            require(isinstance(sent, dict) and set(sent) == {'id', 'expected_revision', 'research_inputs'}, 'Start one optional research request with the current source revision.')
            try:
                result = self.research.start(sent['id'], sent['expected_revision'], sent['research_inputs'])
            except (ValueError, OSError) as error:
                raise Invalid(str(error)) from None
            return shared.as_json(200, result)
        if path == '/api/research-control':
            require(isinstance(sent, dict) and set(sent) == {'id', 'action'}, 'Choose one research control.')
            try:
                result = self.research.control(sent['id'], sent['action'])
            except (ValueError, OSError) as error:
                raise Invalid(str(error)) from None
            return shared.as_json(200, result)
        if path == '/api/research-sources':
            from studio_core.research_sources import Sources
            try:
                return shared.as_json(200, Sources(self.store.root / '.research-sources',
                    account=lambda: settings.snapshot()['google']['account']).dispatch(sent))
            except ValueError as error:
                raise Invalid(str(error)) from None
        if path == '/api/action':
            try:
                configured = not self.injected and isinstance(sent, dict) and sent.get('action') in ('visual-layout', 'image-recover', 'suggest', 'art-direct', 'build', 'image-start', 'preview', 'export', 'inspect-images', 'revise-art', 'repair', 'revise-story', 'approve', 'review')
                verb = sent.get('action') if isinstance(sent, dict) else None
                if isinstance(verb, str) and verb in activity.LABELS:
                    self.store.read(sent.get('id'))
                    with self.activity.track(sent['id'], verb) as report:
                        found = api.engine(self.store) if configured else copy(self.engine)
                        found.progress = report
                        result = api.action(found, sent)
                        self.activity.outcome(sent['id'], result)
                elif verb in ('library', 'library-update'):
                    # Context never changes under work this page is running.
                    found = copy(self.engine)
                    found.research = self.research
                    found.activity = self.activity.snapshot(sent.get('id')) if isinstance(sent.get('id'), str) else None
                    result = api.action(found, sent)
                else:
                    result = api.action(self.engine, sent)
                return shared.as_json(HTTPStatus.OK, {'result': result})
            except Invalid:
                raise
            except Exception as failure:
                raise Invalid('Infographic Studio could not complete this action. Saved sources, history and earlier deliveries are kept.') from failure
        if path == '/api/preferences':
            require(isinstance(sent, dict) and set(sent) == {'changes', 'expected'}, 'Save only the shown native defaults and their revision.')
            return shared.as_json(HTTPStatus.OK, settings.save(sent['changes'], expected=sent['expected']))
        if path == '/api/team':
            from . import team
            require(isinstance(sent,dict) and sent.get('operation') in ('connect','sync','claim','take','retry'), 'Choose an explicit team action.')
            operation=sent['operation'];values={k:v for k,v in sent.items() if k!='operation'}
            allowed={'connect':set(),'sync':set(),'claim':{'id','expected_head','expected_claim','new_owner'},'take':{'id','expected_head','expected_claim'},'retry':{'expected_commit'}}
            require(set(values)<=allowed[operation],'Use only the selected team action fields.')
            if operation in ('connect','sync'):result=team.connect()
            elif operation=='retry':result=team.retry_pending(**values)
            else:
                ident=values.pop('id')
                result=(team.claim if operation=='claim' else team.take)(self.store,ident,**values)
            return shared.as_json(200,result)
        if path in ('/api/handoff-inventory','/api/handoff-preview'):
            from . import handoffs
            require(isinstance(sent,dict) and set(sent)<=({'root','studio'} if path.endswith('inventory') else {'root','studio','file','expected_sha256'}),'Select one studio material from its inventory.')
            return shared.as_json(200,(handoffs.inventory if path.endswith('inventory') else handoffs.prepare)(**sent))
        if path == '/api/research-preview':
            from . import research
            require(isinstance(sent,dict) and set(sent)=={'id','expected_revision','case','source_mode'},'Choose a research case for this exact infographic task.')
            project=self.store.read(sent['id']);self.store.expect(project,sent['expected_revision'])
            return shared.as_json(200,research.prepare(sent['case'],expected_task=research.task(project,sent['source_mode'])))
        if path == '/api/remote-preview':
            from . import remote_sources
            require(isinstance(sent, dict) and set(sent) <= {'kind', 'url', 'account', 'tabs'}, 'Preview one explicitly selected remote source.')
            require(sent.get('kind') in ('google-doc', 'url'), 'Choose Google Doc or public URL.')
            result = remote_sources.google(sent.get('url'), account=sent.get('account') or settings.snapshot()['google']['account'], tabs=sent.get('tabs')) if sent['kind'] == 'google-doc' else remote_sources.public(sent.get('url'))
            return shared.as_json(200, result)
        if path == '/api/source-preview':
            from . import intake
            require(isinstance(sent, dict) and set(sent) <= {'data', 'kind', 'name', 'selection'},
                    'Preview one supplied document and its explicit selection.')
            return shared.as_json(200, intake.prepare(api.source_bytes(sent.get('data')),
                kind=sent.get('kind'), name=sent.get('name'), selection=sent.get('selection')))
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
            from .research_jobs import Jobs
            self.page.research = Jobs(current)

        def stop(self):
            if self.page.research is not None:
                self.page.research.stop()
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
