"""Where research may look: your documents, your sites and/or the public web.

A run keeps its choice as {'documents': bool, 'sites': [canonical site, ...], 'web': bool}.
`sites` empty means your sites are off. A site is a canonical https base URL: a public host
and an optional path, written https://host[/path] and shown as host/path. Every place a
research job saves or fetches a page asks `refused(url, choice)`, on every hop.
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import unquote, urlsplit, urlunsplit

MOST = 50                  # sites in one list
LONGEST = 2000             # characters in one site
SHOWN = 5                  # sites a summary names before "and N more"
LABEL = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)$')
# A last label of digits or 0x-hex makes a browser or resolver read the name as an IPv4
# address (127.1, 0x7f.1), so such a name is never a site.
NUMERIC = re.compile(r'^(?:0x[0-9a-f]*|[0-9]+)$')
PRIVATE_SUFFIXES = ('.local', '.localhost', '.internal', '.lan', '.home.arpa', '.test',
                    '.intranet', '.corp', '.private')
EMPTY = 'Choose where research may look: your documents, your sites or the public web.'
NO_DOCUMENTS = ('No documents were given, so choose your sites or the public web for '
                'research, or add documents.')
NO_SITES = 'Choose at least one of your sites, or turn your sites off.'

LEGACY_DOCUMENTS = ('supplied-only', 'documents', 'selected')
LEGACY_BOTH = ('web-allowed', 'public', 'public-web', 'both', 'mixed')


# --- one site ----------------------------------------------------------------------------

def _public_host(host: str) -> bool:
    """A host name or address research may name: public, never this computer or a private
    network. Names are checked by their form; their addresses are checked at fetch time."""
    try:
        address = ipaddress.ip_address(host.strip('[]'))
    except ValueError:
        pass
    else:
        return (getattr(address, 'ipv4_mapped', None) or address).is_global
    if host == 'localhost' or host.endswith(PRIVATE_SUFFIXES) or '.' not in host:
        return False
    if NUMERIC.match(host.rsplit('.', 1)[-1]):
        return False
    return all(LABEL.match(label) for label in host.split('.'))


def _ascii_host(host: str) -> str | None:
    """The host as it is looked up: lowercased, without a trailing dot, a Unicode name in
    its punycode form. None when it cannot be encoded."""
    host = host.lower().rstrip('.')
    if host.isascii():
        return host
    try:
        return host.encode('idna').decode('ascii').lower()
    except UnicodeError:
        return None


def fetchable(url: str) -> str:
    """The address as it is fetched: without its fragment, which is never sent. Fetchers
    check and request this form, so a '#' cannot hide a path from the check."""
    return urlunsplit(urlsplit(url)._replace(fragment=''))


def _clean_path(path: str) -> str | None:
    """The path with no trailing slash, or None when it may not be used: a '.' or '..'
    segment, an encoded slash or backslash, or a control character."""
    lowered = path.lower()
    if '%2f' in lowered or '%5c' in lowered or '\\' in path:
        return None
    decoded = unquote(path)
    # A segment such as '..;x' is a dot segment to servers that drop ;-parameters.
    if any(ord(c) < 32 for c in decoded) or any(
            segment.split(';', 1)[0] in ('.', '..') for segment in decoded.split('/')):
        return None
    return path.rstrip('/')


def site(value) -> str:
    """The canonical https://host[/path] for what a person typed, or a ValueError with a
    sentence that names it."""
    if not isinstance(value, str):
        raise ValueError('Give each research site as an https address.')
    given = value.strip()
    named = given if len(given) <= 80 else given[:77] + '…'
    if not given or len(given) > LONGEST or any(c.isspace() or ord(c) < 32 for c in given):
        raise ValueError(f'"{named}" is not a web address. Give an https address such as '
                         'https://docs.example.com/guide.')
    if '://' not in given:
        given = 'https://' + given
    try:
        parts = urlsplit(given)
        port = parts.port
    except ValueError:
        raise ValueError(f'"{named}" is not a web address.') from None
    if parts.scheme.lower() != 'https':
        raise ValueError(f'"{named}": research sites use https only.')
    if parts.username or parts.password or '@' in parts.netloc:
        raise ValueError(f'"{named}" carries a name or password. Give the address without them.')
    if parts.query or parts.fragment or given.endswith(('?', '#')):
        raise ValueError(f'"{named}": leave out the part after ? or #. A site is a host and '
                         'an optional path.')
    if port not in (None, 443):
        raise ValueError(f'"{named}": research sites use the standard https port.')
    host = _ascii_host(parts.hostname or '')
    if host is None:
        raise ValueError(f'"{named}" has a host name that cannot be used.')
    if not host:
        raise ValueError(f'"{named}" has no host name.')
    if not _public_host(host):
        raise ValueError(f'"{named}" is not a public site. Research never reads this '
                         'computer or a private network.')
    path = _clean_path(parts.path)
    if path is None:
        raise ValueError(f'"{named}": the path may not hold "." or ".." parts or encoded slashes.')
    if ':' in host:
        host = '[' + host + ']'
    return 'https://' + host + path


def sites(values) -> list[str]:
    """A whole list, canonical, deduplicated in its order, of at most MOST sites."""
    if not isinstance(values, list):
        raise ValueError('Give research sites as a list of https addresses.')
    kept = list(dict.fromkeys(site(value) for value in values))
    if len(kept) > MOST:
        raise ValueError(f'Keep at most {MOST} research sites.')
    return kept


def shown(value: str) -> str:
    """A site as the pages show it: host/path."""
    return value.removeprefix('https://')


def defaults(values) -> list[str]:
    """The shared list from what the studios config holds, keeping only usable sites."""
    research = values.get('research') if isinstance(values, dict) else None
    listed = research.get('sites') if isinstance(research, dict) else None
    kept = []
    for value in listed if isinstance(listed, list) else ():
        try:
            kept.append(site(value))
        except ValueError:
            continue
    return list(dict.fromkeys(kept))[:MOST]


def check_shared(value) -> dict:
    """The shared settings' research section, canonical, or a ValueError."""
    if not isinstance(value, dict) or set(value) - {'sites'}:
        raise ValueError('Give research settings as a list of sites.')
    return {'sites': sites(value.get('sites') or [])} if 'sites' in value else {}


# --- where a page is ---------------------------------------------------------------------

def under(url, listed) -> str | None:
    """The listed site a URL is under, or None. The URL must be https on the site's own
    host (no subdomain, no lookalike) and its path the site's path or one continuing it at
    a segment boundary."""
    # Two '#' are read differently by URL parsers (the first) and urllib (the last).
    # Whitespace too: urllib strips it from the ends, so '..%20#' would become '..'.
    if not isinstance(url, str) or not url or len(url) > 8000 or url.count('#') > 1 \
            or any(c.isspace() or ord(c) < 32 for c in url):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() != 'https' or parts.username or parts.password \
            or port not in (None, 443) or not parts.hostname:
        return None
    host = _ascii_host(parts.hostname)
    if host is None:
        return None
    path = _clean_path(parts.path)
    if path is None:
        return None
    path = unquote(path)
    for base in listed or ():
        target = urlsplit(base)
        if _ascii_host(target.hostname or '') != host:
            continue
        prefix = unquote(target.path.rstrip('/'))
        if not prefix or path == prefix or path.startswith(prefix + '/'):
            return base
    return None


# --- the choice ----------------------------------------------------------------------------

def choice(value, documents_given=True) -> dict:
    """The run's choice, canonical; refused with a sentence when nothing that applies is
    chosen. Documents count only when documents were given."""
    if not isinstance(value, dict) or set(value) - {'documents', 'sites', 'web'}:
        raise ValueError(EMPTY)
    if any(not isinstance(value.get(key, False), bool) for key in ('documents', 'web')):
        raise ValueError(EMPTY)
    chosen = {'documents': value.get('documents', False), 'sites': sites(value.get('sites') or []),
              'web': value.get('web', False)}
    found = effective(chosen, documents_given)
    if not (found['documents'] or found['sites'] or found['web']):
        raise ValueError(NO_DOCUMENTS if chosen['documents'] else EMPTY)
    return found


def effective(value, documents_given=True) -> dict:
    """What applies: your documents only when documents were given."""
    value = value or {}
    return {'documents': bool(value.get('documents')) and bool(documents_given),
            'sites': list(value.get('sites') or []), 'web': bool(value.get('web'))}


def legacy(value):
    """An older run's wording in the new shape. None for Blog Studio's no research."""
    if isinstance(value, dict):
        return effective(value)
    if value in LEGACY_DOCUMENTS:
        return {'documents': True, 'sites': [], 'web': False}
    if value in LEGACY_BOTH:
        return {'documents': True, 'sites': [], 'web': True}
    return None


def fetches(value) -> bool:
    """Whether research saves pages: your sites or the public web."""
    return bool(value.get('sites')) or bool(value.get('web'))


def source_mode(value) -> str:
    """Harness Research's source mode: pages from your sites are public captures."""
    if value.get('documents'):
        return 'mixed' if fetches(value) else 'selected'
    return 'public'


def plan_scope(value) -> str:
    """The research plan's scope, as Harness Research words it."""
    return 'public-web' if fetches(value) else 'supplied-only'


def _named(listed) -> str:
    names = [shown(value) for value in listed]
    if len(names) > SHOWN:
        return ', '.join(names[:SHOWN]) + f' and {len(names) - SHOWN} more'
    return ', '.join(names)


def parts(value) -> list[str]:
    found = []
    if value.get('documents'):
        found.append('your documents')
    if value.get('sites'):
        count = len(value['sites'])
        found.append(f'{count} of your sites ({_named(value["sites"])})')
    if value.get('web'):
        found.append('the public web')
    return found


def outside(count, listed) -> str | None:
    """What a research stop says of the pages refused for being outside your sites, or
    None when none was."""
    if not count or not listed:
        return None
    if count == 1:
        return f'1 page was outside your sites ({_named(listed)}) and was not saved.'
    return f'{count} pages were outside your sites ({_named(listed)}) and were not saved.'


def summary(value) -> str:
    """'from your documents and 3 of your sites (a, b, c)'."""
    found = parts(value)
    if not found:
        return 'from nothing'
    if len(found) == 1:
        return 'from ' + found[0]
    return 'from ' + ', '.join(found[:-1]) + ' and ' + found[-1]


def scope_text(value) -> str:
    """What the research task's scope says about where it may look."""
    said = []
    if value.get('documents'):
        said.append('Use the supplied documents.')
    if value.get('sites'):
        said.append('Allowed sites: ' + ', '.join(shown(s) for s in value['sites']) + '.')
        said.append('The wider public web may fill gaps the allowed sites leave.' if value.get('web')
                    else 'Pages from anywhere else on the public web are not allowed.')
    elif value.get('web'):
        said.append('Any public page may be used.')
    else:
        said.append('Nothing is searched for on the public web.')
    return ' '.join(said)


def guidance(value) -> str:
    """What the worker is told about searching. Empty when it saves no pages."""
    if not value.get('sites'):
        return ''
    queries = ', '.join('site:' + shown(s) for s in value['sites'][:SHOWN])
    said = ('Search the listed sites first: use site: queries (' + queries + ') or a site\'s '
            'own search page when your tools offer one. Save pages only from under these '
            'sites: ' + ', '.join(shown(s) for s in value['sites']) + '.')
    if value.get('web'):
        said += ' Use the wider public web only for gaps the listed sites leave.'
    else:
        said += ' Pages anywhere else are refused when you try to save them.'
    return said


def refused(url, value, redirected_from=None) -> str | None:
    """None when research may save this page; else a sentence naming the allowed sites,
    so the worker can correct itself. Private-address checks are the caller's and stay."""
    if value.get('web'):
        return None
    listed = value.get('sites') or []
    if not listed:
        return ('This research uses your documents only, so no page was saved. Work from '
                'the documents you were given.')
    if under(url, listed):
        return None
    allowed = ', '.join(shown(s) for s in listed)
    if redirected_from:
        try:
            where = urlsplit(url)
            landed = (where.hostname or '') + where.path
        except ValueError:
            landed = 'another address'
        return (f'That page redirected to {landed or "another address"}, outside the sites '
                f'this research may use, so it was not saved. Save pages from under: {allowed}.')
    return ('That page is outside the sites this research may use, so it was not saved. '
            f'Save pages from under: {allowed}.')


class Scope:
    """A run's choice, for a fetcher that checks every hop."""

    def __init__(self, value):
        self.choice = effective(value)

    def refuse(self, url, redirected_from=None):
        return refused(url, self.choice, redirected_from)

    def dump(self) -> dict:
        return dict(self.choice)

    @classmethod
    def load(cls, value):
        return cls(value)
