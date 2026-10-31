"""Validate the shared settings without asking providers or guessing model catalogs."""
import re
from pathlib import Path
from urllib.parse import urlsplit

from studio_core import model_profiles, research_sites, runtime

WorkspaceError = ValueError

EFFORTS = {'claude': ('low', 'medium', 'high', 'xhigh', 'max'),
           'codex': ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')}
FIELDS = {'person': {'name'}, 'assistant': {'agent', 'model', 'effort'},
          'team': {'repository', 'branch'}, 'local': {'root'}, 'render': {'previews'},
          'brand': {'repository', 'release', 'brand', 'variant', 'skill'}}


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
    if not isinstance(changes, dict) or set(changes) - {*FIELDS, 'output', 'share', 'models', 'research'}:
        raise WorkspaceError('Choose only the shared settings shown on this page.')
    if any(key in current and not isinstance(current[key], dict) for key in (*FIELDS, 'research')):
        raise WorkspaceError('A shared settings section is not an object. Restore a valid settings file.')
    merged = dict(current)
    for group, value in changes.items():
        if group == 'research':
            merged[group] = {**(current.get(group) or {}), **research_sites.check_shared(value)}
            continue
        if group == 'models':
            model_profiles.check_changes(value)
            merged[group] = model_profiles.merge(current.get(group, {}), value)
            continue
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
    for group, fields in FIELDS.items():
        for key in fields:
            value = (merged.get(group) or {}).get(key)
            if value is not None and (not isinstance(value, str) or len(value) > 2000
                                      or any(ord(c) < 32 for c in value)):
                raise WorkspaceError('Use short text without control characters for settings.')
    for group in ('team', 'brand'):
        address = (merged.get(group) or {}).get('repository')
        if address:
            repository(address)
    assistant = merged.get('assistant') or {}
    agent = assistant.get('agent') or runtime.assistant_default()
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
    if (merged.get('render') or {}).get('previews') not in (None, 'local', 'drive'):
        raise WorkspaceError('Choose local or Google Drive slide previews.')
    skill = (merged.get('brand') or {}).get('skill')
    if skill and not Path(skill).expanduser().is_absolute():
        raise WorkspaceError('Use Git repository for a brand skill URL. Installed skill folder '
                             'needs an absolute path or one beginning with ~/.')
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
    model_profiles.check(merged)
    return merged


SETUP_VERSION = 1


def ready(values):
    """A partial form or an unreadable configuration is never completed setup."""
    setup = values.get('setup')
    if not isinstance(setup, dict) or type(setup.get('version')) is not int \
            or setup['version'] != SETUP_VERSION:
        return False
    try:
        require_workspace(values)
    except (ValueError, TypeError):
        return False
    return True


def require_workspace(values):
    check({}, values)
    if not ((values.get('team') or {}).get('repository')
            or (values.get('local') or {}).get('root')):
        raise ValueError('Choose a local work folder or a repository before finishing setup.')


def visible(values):
    """The leaves a shared setup form owns; unknown settings remain untouched."""
    return {**{group: {name: (values.get(group) or {}).get(name) for name in names}
               for group, names in FIELDS.items()},
            **{name: values.get(name) for name in ('output', 'share')},
            'models': model_profiles.visible(values),
            'research': {'sites': list((values.get('research') or {}).get('sites') or [])}}


def save(config, changes, seen):
    if not isinstance(seen, dict):
        raise ValueError('Reload shared settings before saving changes.')
    if isinstance(changes, dict) and 'research' in changes:
        # Saved as the studios read them: canonical, deduplicated, at most fifty.
        changes = {**changes, 'research': research_sites.check_shared(changes['research'])}
    check(changes, config.read()[0])

    def guard(current):
        check(changes, current)
        # Every leaf the form changes that someone else changed differently since it was
        # shown. Nothing is written while there is one.
        stale = []
        if 'research' in changes and 'sites' in changes['research']:
            held = (current.get('research') or {}).get('sites') or []
            before = (seen.get('research') or {}).get('sites') or []
            if held != before and held != changes['research']['sites']:
                stale.append(('research', 'sites'))
        for path, wanted in model_profiles.leaves(
                {key: value for key, value in changes.items() if key != 'research'}):
            held, before = model_profiles.get(current, path), model_profiles.get(seen, path)
            if held != before and held != wanted:
                stale.append(path)
        # Profile edits also depend on the assistant and inherited defaults the form saw.
        if 'models' in changes:
            for key in ('agent', 'model', 'effort'):
                held = (current.get('assistant') or {}).get(key)
                before = (seen.get('assistant') or {}).get(key)
                wanted = (changes.get('assistant') or {}).get(key, before)
                if held != before and held != wanted and ('assistant', key) not in stale:
                    stale.append(('assistant', key))
        if stale:
            raise Conflict(stale)
    return config.update(changes, guard=guard)


# What the shared settings form calls each value, for a refusal that names it.
LABELS = {('person', 'name'): 'Your name', ('assistant', 'agent'): 'Assistant',
          ('assistant', 'model'): 'Model', ('assistant', 'effort'): 'Reasoning',
          ('local', 'root'): 'Workspace folder', ('team', 'repository'): 'Repository address',
          ('team', 'branch'): 'Branch', ('share',): 'Share changes',
          ('brand', 'repository'): 'Brand Git repository', ('brand', 'skill'): 'Installed skill folder',
          ('brand', 'brand'): 'Default brand', ('brand', 'variant'): 'Default variant',
          ('brand', 'release'): 'Brand skill release', ('output',): 'Deliver as',
          ('render', 'previews'): 'Slide previews', ('research', 'sites'): 'Research sites',
          ('models', 'mode'): 'Model routing', ('models', 'agent'): 'Model profiles'}


def label(path):
    path = tuple(path)
    if path in LABELS:
        return LABELS[path]
    if len(path) == 4 and path[:2] == ('models', 'profiles'):
        part = {'selection': 'model choice', 'model': 'model', 'effort': 'reasoning'}.get(path[3], 'model')
        return f'{path[2].capitalize()} {part}'
    return 'Model profiles' if path[:1] == ('models',) else '.'.join(path)


class Conflict(ValueError):
    """A save refused because someone else changed the same values first. `fields` are
    their dotted paths, such as person.name; the message names them as the form does."""

    def __init__(self, paths):
        self.fields = ['.'.join(path) for path in paths]
        names = list(dict.fromkeys(f'“{label(path)}”' for path in paths))
        named = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
        super().__init__(f'{named} {"was" if len(names) == 1 else "were"} changed in another tab or studio '
                         'while this page was open, so nothing was saved. Choose Load newer settings '
                         'to compare; your other edits stay on the form.')


def finish(config, prepare):
    values, problem = config.read()
    if problem:
        raise ValueError(problem)
    require_workspace(values)
    defaults = {}
    if not (values.get('assistant') or {}).get('agent'):
        defaults['assistant'] = {'agent': runtime.assistant_default()}
    if values.get('output') is None:
        defaults['output'] = 'pptx'
    prepared = dict(values)
    for key, value in defaults.items():
        prepared[key] = {**(values.get(key) or {}), **value} if isinstance(value, dict) else value
    prepare(prepared)

    def guard(current):
        require_workspace(current)
        if visible(current) != visible(values):
            raise ValueError('Another studio changed settings during setup. Reload the page and try again.')
    config.update({**defaults, 'setup': {'version': SETUP_VERSION}}, guard=guard)
