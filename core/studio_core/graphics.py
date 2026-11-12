"""Document graphics: who draws the pictures a document needs, with which model, and the
Gemini key that drawing with Gemini takes.

The choice (`graphics.provider`, `graphics.model`) is a shared setting in the studios
config. The key is not: it is kept in a file of its own beside that config, readable only
by this person, never returned to a page, never logged and never written into the config.
A key in the launch environment (GEMINI_API_KEY) is used before a saved one.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from studio_core import studios_config

PROVIDERS = ('gemini', 'codex')
MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}')
KEY = re.compile(r'[A-Za-z0-9_\-]{20,200}')
ENVIRONMENT = 'GEMINI_API_KEY'
HOST = 'generativelanguage.googleapis.com'
SECONDS = 20
LIMIT = 4 * 1024 * 1024
PAGES = 5


class Unavailable(ValueError):
    """Why the model list or the key is unavailable, in words for the person."""


def key_path() -> Path:
    return studios_config.path().with_name('studios-graphics-key')


def _saved() -> str:
    where = key_path()
    try:
        if where.is_symlink() or not where.is_file():
            return ''
        return where.read_text(encoding='utf-8').strip()[:200]
    except (OSError, UnicodeError):
        return ''


def key(environ=None) -> str:
    """The Gemini key to draw with: the launch environment's, else the saved one."""
    environ = os.environ if environ is None else environ
    return (environ.get(ENVIRONMENT) or '').strip() or _saved()


def key_state(environ=None) -> dict:
    """Whether a key is there and where from. Never the key."""
    environ = os.environ if environ is None else environ
    if (environ.get(ENVIRONMENT) or '').strip():
        return {'set': True, 'source': 'environment'}
    return {'set': True, 'source': 'saved'} if _saved() else {'set': False, 'source': None}


def save_key(value) -> dict:
    if not isinstance(value, str) or not KEY.fullmatch(value.strip()):
        raise Unavailable('That does not look like a Gemini API key. Paste the key from '
                          'Google AI Studio, with nothing around it.')
    where = key_path()
    where.parent.mkdir(parents=True, exist_ok=True)
    handle, pending = tempfile.mkstemp(prefix='.graphics-key-', dir=where.parent)
    try:
        os.fchmod(handle, 0o600)
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(value.strip() + '\n')
        os.replace(pending, where)
    except BaseException:
        Path(pending).unlink(missing_ok=True)
        raise
    return key_state()


def clear_key() -> dict:
    key_path().unlink(missing_ok=True)
    return key_state()


def chosen(shared: dict, assistant_default: str = 'claude') -> dict:
    """The provider and model in force. With none chosen, the provider follows the
    assistant as it always did: Codex draws for Codex, Gemini for Claude Code."""
    saved = shared.get('graphics') if isinstance(shared.get('graphics'), dict) else {}
    provider = saved.get('provider')
    if provider not in PROVIDERS:
        agent = (shared.get('assistant') or {}).get('agent') or assistant_default
        provider = 'codex' if agent == 'codex' else 'gemini'
    model = saved.get('model')
    return {'provider': provider, 'model': model if isinstance(model, str) and model else None,
            'explicit': saved.get('provider') in PROVIDERS}


def check(group) -> None:
    """A `graphics` group as the shared settings form may save it."""
    if not isinstance(group, dict) or set(group) - {'provider', 'model'}:
        raise ValueError('That document graphics setting is not recognized.')
    if group.get('provider') not in (None, *PROVIDERS):
        raise ValueError('Choose Gemini or Codex for document graphics.')
    model = group.get('model')
    if model is not None and (not isinstance(model, str) or not MODEL.fullmatch(model)):
        raise ValueError('Give the graphics model as its ID, without spaces.')


def https(path: str, secret: str, seconds: int = SECONDS):
    """One bounded GET to the Gemini API. The key goes in a header, never the address."""
    connection = http.client.HTTPSConnection(HOST, timeout=seconds)
    try:
        connection.request('GET', path, headers={'x-goog-api-key': secret,
                                                 'Accept': 'application/json'})
        response = connection.getresponse()
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise Unavailable('Gemini listed more models than this page reads.')
        if response.status != 200:
            return response.status, {}   # Never a provider's own words, or a reflected key.
        return response.status, json.loads(raw)
    finally:
        connection.close()


def image_model(entry) -> dict | None:
    """One listed model as a choice, when it draws pictures. Gemini's list has no field
    for what a model puts out, so a picture model is known by its name."""
    if not isinstance(entry, dict):
        return None
    name = str(entry.get('name') or '').removeprefix('models/')
    if not MODEL.fullmatch(name) or not any(word in name.lower() for word in ('image', 'banana')):
        return None
    shown = entry.get('displayName')
    shown = ' '.join(str(shown).split())[:80] if isinstance(shown, str) and shown.strip() else name
    about = entry.get('description')
    return {'name': name, 'label': name if shown == name else f'{shown} ({name})',
            'about': ' '.join(str(about).split())[:160] if isinstance(about, str) and about.strip() else None}


def gemini_models(secret: str | None = None, transport=https) -> dict:
    """The picture models this key can use, asked of Gemini itself. Nothing is drawn."""
    secret = key() if secret is None else secret
    if not secret:
        raise Unavailable('Save a Gemini API key first, then list the models it can use.')
    found, token = [], None
    for _ in range(PAGES):
        query = {'pageSize': 1000, **({'pageToken': token} if token else {})}
        try:
            status, body = transport('/v1beta/models?' + urlencode(query), secret)
        except Unavailable:
            raise
        except (OSError, ValueError) as failure:
            raise Unavailable('Gemini could not be reached to list its models. Enter a model '
                              'ID, or try again.') from failure
        if status in (400, 401, 403):
            raise Unavailable('Gemini did not accept this key. Check it in Google AI Studio '
                              'and save it again.')
        if status != 200 or not isinstance(body, dict):
            raise Unavailable('Gemini could not list its models just now. Enter a model ID, '
                              'or try again.')
        for entry in body.get('models') or ():
            model = image_model(entry)
            if model and all(model['name'] != other['name'] for other in found):
                found.append(model)
        token = body.get('nextPageToken')
        if not isinstance(token, str) or not token:
            break
    if not found:
        raise Unavailable('This key lists no picture models. Enter a model ID instead.')
    return {'models': sorted(found, key=lambda one: one['name']),
            'source': 'Your Gemini API key’s model list'}


def listed(provider: str, transport=https) -> dict:
    """What the form shows for a provider's models: the list, or why there is none."""
    if provider != 'gemini':
        return {'provider': provider, 'models': [], 'source': None,
                'problem': None, 'note': 'Codex draws with its own built-in image tool, '
                'under your Codex sign-in. There is no model to choose and no key to enter.'}
    try:
        return {'provider': provider, **gemini_models(transport=transport), 'problem': None}
    except Unavailable as failure:
        return {'provider': provider, 'models': [], 'source': None, 'problem': str(failure)}


def snapshot(shared: dict, assistant_default: str = 'claude') -> dict:
    """What a settings page shows beside the saved choice: the provider in force and
    whether a key is here. Never the key."""
    return {'chosen': chosen(shared, assistant_default), 'key': key_state()}


def act(sent, remote: bool = False, transport=https) -> dict:
    """One request from the Document graphics form: list a provider's models, save the
    key, or remove it. A key is only ever taken on this computer itself, never over the
    phone link, which is not encrypted."""
    if not isinstance(sent, dict) or set(sent) - {'models', 'key', 'clear'}:
        raise ValueError('That document graphics request is not recognized.')
    if 'key' in sent or sent.get('clear'):
        if remote:
            raise ValueError('Enter the Gemini key on the computer that runs Marketing '
                             'Studio. It is not taken over the phone link.')
        state = clear_key() if sent.get('clear') else save_key(sent.get('key'))
        return {'key': state}
    provider = sent.get('models')
    if provider not in PROVIDERS:
        raise ValueError('Choose Gemini or Codex for document graphics.')
    return {**listed(provider, transport), 'key': key_state()}
