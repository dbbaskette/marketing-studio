"""The same shared setup page inside any independently launched studio.

The host retains its token, loopback and origin protections. No content, provider
jobs, installers or update actions are exposed by this page.
"""
import threading
from pathlib import Path
from urllib.parse import urlsplit

from studio_core import preferences, brand_catalog, research_sites, runtime
from studio_core.model_catalog import Catalog
from studio_core.server import for_product
from studio_core.studios_config import for_product as config_for

WEB = Path(__file__).resolve().parent / 'setup_web'
ASSETS = {'/onboarding/': ('index.html', 'text/html; charset=utf-8'),
          '/onboarding/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/onboarding/home.css': ('home.css', 'text/css; charset=utf-8'),
          '/onboarding/style.css': ('style.css', 'text/css; charset=utf-8')}


def config(product):
    return config_for(__name__ + '.' + product.replace(' ', '_'), product, ValueError,
                      preferences.repository, strict_groups=True)


class Controller:
    def __init__(self, port, token, product, header, prepare, store=None, after=None):
        self.store = store or config(product)
        self.prepare = prepare
        self.after = after or (lambda: None)
        self.product = product
        self.models = Catalog()
        self.lock = threading.RLock()
        protocol = for_product(__name__ + '.http.' + product.replace(' ', '_'), product,
                               header, WEB, ASSETS, None, ValueError)
        owner = self

        class Page(protocol.Page):
            reads = ('/onboarding/api/home', '/onboarding/api/models')
            writes = ('/onboarding/api/shared', '/onboarding/api/setup', '/onboarding/api/models', '/onboarding/api/brands', '/onboarding/api/research-site')

            def read(self, path, one):
                if path.endswith('/models'):
                    return protocol.as_json(200, owner.models.get(one('agent')))
                return protocol.as_json(200, owner.snapshot())

            def write(self, path, sent):
                if path.endswith('/research-site'):
                    # One site checked as a save would check it; nothing is saved.
                    return protocol.as_json(200, {'site': research_sites.site(sent.get('site'))})
                if path.endswith('/brands'):
                    skill = sent.get('skill')
                    if skill is not None and (not isinstance(skill, str) or len(skill) > 2000
                                             or not Path(skill).expanduser().is_absolute()):
                        raise ValueError('Choose an absolute installed brand skill folder, or leave it blank.')
                    return protocol.as_json(200, brand_catalog.choices(skill))
                if path.endswith('/models'):
                    return protocol.as_json(200, owner.models.get(sent.get('agent'), refresh=True))
                with owner.lock:
                    if path.endswith('/shared'):
                        preferences.save(owner.store, sent.get('changes'), sent.get('seen'))
                    else:
                        if sent.get('done') is not True:
                            raise ValueError('Finish shared setup before opening the studio.')
                        preferences.finish(owner.store, owner.prepare)
                        owner.after()
                    return protocol.as_json(200, owner.snapshot())

        self.page = Page(port)
        self.page.token = token
        self.protocol = protocol

    def snapshot(self):
        values, problem = self.store.read()
        return {'shared': values, 'shared_problem': problem,
                'setup': {'done': not problem and preferences.ready(values)},
                'studios': [], 'efforts': preferences.EFFORTS,
                'assistant_default': runtime.assistant_default()}

    def accepts(self, target):
        path = urlsplit(target).path
        if path.startswith('/onboarding/'):
            return True
        values, problem = self.store.read()
        return path in ('/', '/index.html') and (problem or not preferences.ready(values))

    def answer(self, target, headers, method='GET', body=None):
        if urlsplit(target).path in ('/', '/index.html'):
            target = '/onboarding/'
        try:
            status, kind, data = self.page.answer(target, headers, method, body)
            if kind == 'text/html; charset=utf-8':
                html = data.decode().replace('Marketing Studio', self.product)
                html = html.replace('X-Marketing-Studio-Token', self.protocol.TOKEN_HEADER)
                html = html.replace('data-standalone="false"', 'data-standalone="true"')
                for name in ('app.js', 'home.css', 'style.css'):
                    html = html.replace('"/' + name + '"', '"/onboarding/' + name + '"')
                data = html.encode()
            return status, kind, data
        except self.protocol.Refusal as failure:
            return self.protocol.as_json(failure.status, {'error': str(failure)})
        except preferences.Conflict as failure:
            return self.protocol.as_json(409, {'error': str(failure), 'conflict': {'fields': failure.fields}})
        except ValueError as failure:
            return self.protocol.as_json(409, {'error': str(failure)})


def attach(desk, product, header, prepare, store, after=None):
    """Attach to a real native desk; CLI test doubles need no HTTP adapter."""
    if not hasattr(desk, 'answer'):
        return None
    controller = Controller(desk.port, desk.token, product, header, prepare, store, after=after)
    native = desk.answer

    def answer(target, headers, method='GET', body=None):
        if controller.accepts(target):
            return controller.answer(target, headers, method, body)
        return native(target, headers, method, body)
    desk.answer = answer
    return controller
