"""Validate the shared settings without asking providers or guessing model catalogs."""
import re
from pathlib import Path
from urllib.parse import urlsplit

from .errors import WorkspaceError

EFFORTS = {'claude': ('low', 'medium', 'high', 'xhigh', 'max'),
           'codex': ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')}
FIELDS = {'person': {'name'}, 'assistant': {'agent', 'model', 'effort'},
          'team': {'repository', 'branch'}, 'local': {'root'},
          'brand': {'repository', 'release', 'brand', 'variant'}}


def repository(value):
    if not isinstance(value, str) or len(value) > 2000 or value.startswith('-') \
            or any(c.isspace() or ord(c) < 32 for c in value):
        raise WorkspaceError('Give a repository address without spaces or credentials.')
    try:
        parts = urlsplit(value)
        if parts.password or (parts.scheme in ('http', 'https') and parts.username) \
                or parts.query or parts.fragment or '::' in value:
            raise ValueError()
        if parts.scheme:
            if parts.scheme not in ('https', 'http', 'ssh') or not parts.hostname:
                raise ValueError()
        elif not (re.fullmatch(r'[\w.-]+@[\w.-]+:[\w./~-]+', value)
                  or Path(value).expanduser().is_absolute()):
            raise ValueError()
    except ValueError:
        raise WorkspaceError('Use an https or ssh repository address, or an absolute local path, without credentials.')
    return value


def branch(value):
    if not value or value.startswith(('-', '/', '.')) or value.endswith(('/', '.', '.lock')) \
            or any(c in value for c in ' ~^:?*[\\') or '..' in value or '@{' in value \
            or '//' in value or any(part.startswith('.') or part.endswith('.lock') for part in value.split('/')):
        raise WorkspaceError('Give a Git branch name, such as main.')


def check(changes, current):
    if not isinstance(changes, dict) or set(changes) - {*FIELDS, 'output', 'share'}:
        raise WorkspaceError('Choose only the shared settings shown on this page.')
    merged = dict(current)
    for group, value in changes.items():
        if group in FIELDS:
            if not isinstance(value, dict) or set(value) - FIELDS[group]:
                raise WorkspaceError('That shared setting is not recognized.')
            merged[group] = {**(current.get(group) or {}), **value}
            values = value.values()
        else:
            merged[group] = value
            values = [value]
        if any(v is not None and (not isinstance(v, str) or len(v) > 2000
               or any(ord(c) < 32 for c in v)) for v in values):
            raise WorkspaceError('Use short text without control characters for settings.')
    for group in ('team', 'brand'):
        address = (merged.get(group) or {}).get('repository')
        if address:
            repository(address)
    assistant = merged.get('assistant') or {}
    agent = assistant.get('agent') or 'claude'
    if agent not in EFFORTS:
        raise WorkspaceError('Choose Claude Code or Codex.')
    model, effort = assistant.get('model'), assistant.get('effort')
    if model and (len(model) > 100 or model.startswith('-') or any(c.isspace() for c in model)):
        raise WorkspaceError('Give the model ID your assistant knows, without spaces.')
    if effort and effort not in EFFORTS[agent]:
        raise WorkspaceError('Choose a reasoning level supported by that assistant.')
    if len((merged.get('person') or {}).get('name') or '') > 100:
        raise WorkspaceError('Your name is at most 100 characters.')
    if merged.get('output') not in (None, 'google', 'pptx'):
        raise WorkspaceError('Choose Google or PowerPoint and Word files.')
    if merged.get('share') not in (None, 'decision', 'asked'):
        raise WorkspaceError('Choose when you want to share changes.')
    name = (merged.get('team') or {}).get('branch')
    if name:
        branch(name)
    brand = merged.get('brand') or {}
    for field in ('brand', 'variant'):
        if brand.get(field) and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', brand[field]):
            raise WorkspaceError('Use a short brand or variant ID with letters, numbers, dots or dashes.')
    release = brand.get('release')
    if release and (not brand.get('repository') or not re.fullmatch(r'[\w][\w.+-]{0,99}', release)
                    or '..' in release):
        raise WorkspaceError('Give a brand repository and a release tag such as v1.4.0.')
    root = (merged.get('local') or {}).get('root')
    if root and not Path(root).expanduser().is_absolute():
        raise WorkspaceError('Choose an absolute work folder, or one beginning with ~/.')
    return merged
