"""The same shared setup page inside any independently launched studio.

The host retains its token, loopback and origin protections. No content, provider
jobs, installers or update actions are exposed by this page.
"""
import threading
from pathlib import Path
from urllib.parse import urlsplit

from studio_core import graphics, preferences, brand_catalog, brand_data, repository_address, research_sites, runtime
from studio_core.model_catalog import Catalog
from studio_core.server import for_product
from studio_core.studios_config import for_product as config_for

WEB = Path(__file__).resolve().parent / 'setup_web'
ASSETS = {'/onboarding/': ('index.html', 'text/html; charset=utf-8'),
          '/onboarding/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/onboarding/home.css': ('home.css', 'text/css; charset=utf-8'),
          '/onboarding/style.css': ('style.css', 'text/css; charset=utf-8')}

# A phone on Marketing Studio's private link (GitHub issue #539). The network bridge adds this
# header, with the value `network`, to every request it carries, and a network caller can
# neither send nor strip it. Read here, not through the deck studios' shared runner, because
# every studio serves this page, Blog Studio and Infographic Studio included.
VIA_HEADER = 'X-Marketing-Studio-Via'
# The shared settings that hold a folder on this computer: the folders, always; the
# repositories when not given as a web address of another computer (repository_address).
FOLDERS = (('local', 'root'), ('brand', 'skill'))
REPOSITORIES = (('brand', 'brands'), ('brand', 'repository'), ('team', 'repository'))
# Said to a phone in place of a failure whose text may name a folder on this computer.
REMOTE_FAILED = 'That could not be done here. See why on the computer the studios run on.'


# What a phone may do with each route of this page, decided route by route; a route added
# without a decision here fails tests/test_onboarding_phone.py.
PHONE = {
    '/onboarding/api/home': 'Allowed: the saved settings, as the page shows them; nothing is looked up.',
    '/onboarding/api/models': 'Allowed: an assistant’s models, read or looked up again; no folder.',
    '/onboarding/api/shared': 'Allowed, except a change to a setting holding a folder (folders_refused).',
    '/onboarding/api/setup': 'Allowed: finishes setup with the saved settings; it takes no folder.',
    '/onboarding/api/graphics': 'Allowed: models listed; a key is refused (graphics.act).',
    '/onboarding/api/brands': 'Names and states only; a skill folder is refused unread.',
    '/onboarding/api/brands-repository': 'Allowed: the saved setting is got, answered without folders.',
    '/onboarding/api/research-site': 'Allowed: a web address is checked; no folder.',
}


def carried(headers) -> bool:
    """Whether these request headers say the network bridge carried the request."""
    try:
        values = headers.get_all(VIA_HEADER) or []
    except AttributeError:
        values = [headers.get(VIA_HEADER)] if headers and headers.get(VIA_HEADER) else []
    return any(str(value).strip().lower() == 'network' for value in values)


def _leaf(values, group, key):
    """A setting exactly as it is written: an absent one reads as null, as a save writes it."""
    part = values.get(group) if isinstance(values, dict) else None
    return part.get(key) if isinstance(part, dict) else None


def _set(value) -> bool:
    return value not in (None, '')


def folders_refused(changes, held):
    """For a caller that came over the network: the sentence refusing a shared settings save
    that would change a setting holding a folder on this computer, or None. `held` is what the
    settings file holds, read under its lock (for_phone). A setting passes when the save would
    write exactly the value held, character for character, so the other settings of the same
    form can be saved; the save's own check of an outdated form still decides the rest. A
    folder setting cannot be changed at all, emptied included. A repository can be changed to
    a web address of another computer (repository_address.web_repository), or emptied when it
    held one; any other value, a folder or an address of this computer, is refused."""
    if not isinstance(changes, dict):
        return None
    folders, addresses = [], []
    for group, key in (*FOLDERS, *REPOSITORIES):
        part = changes.get(group)
        if not isinstance(part, dict) or key not in part:
            continue
        wanted, before = _leaf(changes, group, key), _leaf(held, group, key)
        if wanted == before:
            continue
        named = f'“{preferences.label((group, key))}”'
        if (group, key) in FOLDERS:
            if _set(wanted) or _set(before):
                folders.append(named)
        elif _set(wanted) and not repository_address.web_repository(wanted):
            addresses.append(named)        # a folder, or an address of this computer
        elif not _set(wanted) and _set(before) and not repository_address.web_repository(before):
            addresses.append(named)        # emptying one that holds such a value
    if not folders and not addresses:
        return None
    said = []
    if folders:
        said.append(f'{_listed(folders)} {"names a folder" if len(folders) == 1 else "name folders"} on '
                    'the computer the studios run on, so '
                    f'{"it is" if len(folders) == 1 else "they are"} changed only on that computer.')
    if addresses:
        said.append(f'From the private network link, {_listed(addresses)} '
                    f'{"takes" if len(addresses) == 1 else "take"} only an https or ssh address of '
                    'another computer; a folder, or an address of the computer the studios run on, '
                    'is set only on that computer.')
    one = len(folders) + len(addresses) == 1
    said.append(f'Put {"it" if one else "them"} back as {"it was" if one else "they were"} to save '
                'your other changes here.')
    return ' '.join(said)


def _listed(names):
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


class for_phone:
    """The shared settings `config` as a caller over the network may save them: each save is
    checked by folders_refused against what the file holds under its lock, before the save's
    own check, so nothing that changes a folder setting is written in between."""

    def __init__(self, config):
        self.config = config

    def read(self):
        return self.config.read()

    def update(self, changes, guard=None):
        def checked(held):
            refused = folders_refused(changes, held)
            if refused:
                raise preferences.WorkspaceError(refused)
            if guard is not None:
                guard(held)
        return self.config.update(changes, guard=checked)


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
            writes = ('/onboarding/api/shared', '/onboarding/api/setup', '/onboarding/api/models', '/onboarding/api/graphics', '/onboarding/api/brands', '/onboarding/api/brands-repository', '/onboarding/api/research-site')

            def read(self, path, one):
                if path.endswith('/models'):
                    return protocol.as_json(200, owner.models.get(one('agent')))
                return protocol.as_json(200, owner.snapshot())

            def write(self, path, sent):
                remote = owner.remote()
                if path.endswith('/research-site'):
                    # One site checked as a save would check it; nothing is saved.
                    return protocol.as_json(200, {'site': research_sites.site(sent.get('site'))})
                if path.endswith('/brands-repository'):
                    # Only the saved setting is fetched, so a form never fetches an address it did not save.
                    values, problem = owner.store.read()
                    if problem:
                        raise ValueError(problem)
                    return protocol.as_json(200, brand_data.got((values.get('brand') or {}).get('brands'),
                                                                remote=remote))
                if path.endswith('/brands'):
                    skill = sent.get('skill')
                    # A phone's skill folder is refused unread by the lookup below, whatever it says.
                    if not remote and skill is not None and (not isinstance(skill, str) or len(skill) > 2000
                                                             or not Path(skill).expanduser().is_absolute()):
                        raise ValueError('Choose an absolute installed brand skill folder, or leave it blank.')
                    # A failure of either lookup leaves the other standing.
                    values, problem = owner.store.read()
                    store = brand_data.lookup(None if problem else (values.get('brand') or {}).get('brands'),
                                              remote=remote)
                    return protocol.as_json(200, {**brand_catalog.listed(skill, remote=remote), 'store': store})
                if path.endswith('/graphics'):
                    # A key is taken only on the computer itself, as Marketing Studio's page does.
                    return protocol.as_json(200, graphics.act(sent, remote=remote))
                if path.endswith('/models'):
                    return protocol.as_json(200, owner.models.get(sent.get('agent'), refresh=True))
                with owner.lock:
                    if path.endswith('/shared'):
                        before = owner.store.read()[0]
                        # A phone's save is checked for folder settings under the file's lock.
                        preferences.save(for_phone(owner.store) if remote else owner.store,
                                         sent.get('changes'), sent.get('seen'))
                        after, problem = owner.store.read()
                        # A brands folder on this computer is read by Harness Brand from this save on.
                        done = None if problem else brand_data.saved(before, after)
                        if done is not None:
                            return protocol.as_json(200, {**owner.snapshot(), 'brands_saved': done})
                    else:
                        if sent.get('done') is not True:
                            raise ValueError('Finish shared setup before opening the studio.')
                        preferences.finish(owner.store, owner.prepare)
                        owner.after()
                    return protocol.as_json(200, owner.snapshot())

        self.page = Page(port)
        self.page.token = token
        self.protocol = protocol
        # Each request is answered on its own thread: whether this one came over the bridge.
        self.caller = threading.local()

    def remote(self) -> bool:
        """True while this thread answers a request the network bridge carried."""
        return bool(getattr(self.caller, 'remote', False))

    def snapshot(self):
        values, problem = self.store.read()
        return {'shared': preferences.without_retired(values), 'shared_problem': problem,
                'setup': {'done': not problem and preferences.ready(values)},
                # Each kind of work as the form fills it in, with the kinds not yet saved.
                'models_shown': None if problem else preferences.model_profiles.shown(values),
                'studios': [], 'efforts': preferences.EFFORTS,
                'graphics': graphics.snapshot({} if problem else values, runtime.assistant_default()),
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
        self.caller.remote = carried(headers)
        try:
            # A script or a style sheet comes back with its caching headers as a fourth part.
            reply = self.page.answer(target, headers, method, body)
            status, kind, data = reply[:3]
            if kind == 'text/html; charset=utf-8':
                html = data.decode().replace('Marketing Studio', self.product)
                html = html.replace('X-Marketing-Studio-Token', self.protocol.TOKEN_HEADER)
                html = html.replace('data-standalone="false"', 'data-standalone="true"')
                for name in ('app.js', 'home.css', 'style.css'):
                    html = html.replace('"/' + name + '"', '"/onboarding/' + name + '"')
                data = html.encode()
            return (status, kind, data, *reply[3:])
        except self.protocol.Refusal as failure:
            return self.protocol.as_json(failure.status, {'error': str(failure)})
        except preferences.Conflict as failure:
            return self.protocol.as_json(409, {'error': str(failure), 'conflict': {'fields': failure.fields}})
        except ValueError as failure:
            said = str(failure)
            if self.remote() and brand_data.names_a_folder(said):
                said = REMOTE_FAILED   # a phone is never told a folder on this computer
            return self.protocol.as_json(409, {'error': said})
        except Exception:
            # Any other failure, such as a folder that cannot be read or written, names what
            # it failed on: a phone is told only that it failed and where to see why.
            if not self.remote():
                raise
            return self.protocol.as_json(409, {'error': REMOTE_FAILED})
        finally:
            self.caller.remote = False


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
