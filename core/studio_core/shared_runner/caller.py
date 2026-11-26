"""Who sent the request a deck studio's page is answering: the person at this computer, or a
phone or tablet through Marketing Studio's network bridge.

What a caller needs to know
---------------------------
    with caller.answering(headers):       # around one request's answer, in the page
        ...
    caller.remote()                       # True while answering a request the bridge carried
    caller.folder_refused(sent)           # the sentence refusing a folder on this computer
                                          # to a remote caller in a source editor's folder add
    caller.settings_refused(route, sent)  # the sentence refusing a remote caller set-up, or a
                                          # brand repository that is not a web address; None
                                          # for anything else (GitHub issue #539)
    caller.web_repository(address)        # an https://, ssh:// or user@host:path address
                                          # on another computer
    caller.unread_said(said)              # why a brand repository could not be read, as a
                                          # remote caller is told it

The bridge adds `X-Marketing-Studio-Via: network` to every request it carries to a studio,
building its upstream headers from a fixed allow-list, so a network caller can neither send
nor strip it. A request is remote if and only if it carries that header with the value
`network`. A loopback caller that sends it only refuses itself what a phone is refused.

A remote caller may still give a Google Drive folder link and upload files; only a folder
path on this computer is refused (`source_intake.REMOTE`), so a phone on the local network
cannot read this computer's folders. Nothing here reads a folder or uses the network.

Set-up and the brand skill's repository (GitHub issue #539, the owner's ruling: refuse
folders, allow addresses). For a remote caller, `settings_refused` refuses the two set-up
routes whatever they were sent (SETUP_ROUTES: `/api/setup`, `/api/setup/check`), so a phone
learns nothing about any folder here; and the brand skill's repository route (BRAND_ROUTE,
`/api/brand`) unless `repository` is a web repository address: `https://` with a host,
`ssh://` with a host, or the `user@host:path` form, which git reads as a remote, on a host
that is not this computer. Anything git may read as a path on this computer (a folder,
`file://`, `host:path` without a user, an empty address) is refused, and so is an address
whose host is this computer (`localhost` and any name under it, a loopback or unspecified
address in any spelling, this computer's own host name): over ssh that reads a folder here.
Hosts on the local network stay allowed: a team's own git server is a web address. Only
the address's text is read: no name is looked up. When such an address cannot be read,
`unread_said` gives a remote caller a sentence with none of git's own words, which can
name hosts and ports; a caller on this computer keeps git's reason. A caller on this computer is never refused here: what it
may do is as before. Every other route answers None.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import threading
from contextlib import contextmanager
from urllib.parse import urlsplit

from studio_core import source_folders, source_intake

VIA_HEADER = 'X-Marketing-Studio-Via'
NETWORK = 'network'
_local = threading.local()


def carried(headers) -> bool:
    """Whether these request headers say the network bridge carried the request."""
    try:
        values = headers.get_all(VIA_HEADER) or []
    except AttributeError:
        values = [headers.get(VIA_HEADER)] if headers and headers.get(VIA_HEADER) else []
    return any(str(value).strip().lower() == NETWORK for value in values)


@contextmanager
def answering(headers):
    """Mark the request being answered on this thread as remote or not, for its answer."""
    before = getattr(_local, 'remote', False)
    _local.remote = carried(headers)
    try:
        yield _local.remote
    finally:
        _local.remote = before


def remote() -> bool:
    """True while this thread answers a request the network bridge carried."""
    return bool(getattr(_local, 'remote', False))


def on_this_computer(location) -> bool:
    """Whether a folder a person gave is a path on this computer, not a Google Drive folder
    link or identity. Read from its shape alone: nothing is looked up."""
    if not isinstance(location, str):
        return False
    value = location.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in '\'"':
        value = value[1:-1].strip()
    if re.match(r'https?://', value, re.I) or source_folders.DRIVE_ID.fullmatch(value):
        return False
    return bool(value)


def folder_refused(sent) -> str | None:
    """For a remote caller, the sentence that refuses a source editor's folder add of a folder
    on this computer; None for anything else (a Drive folder, an upload, a local caller)."""
    if not remote() or not isinstance(sent, dict) or sent.get('action') != 'folder':
        return None
    return source_intake.REMOTE if on_this_computer(sent.get('location')) else None


SETUP_ROUTES = ('/api/setup', '/api/setup/check')
BRAND_ROUTE = '/api/brand'
SETUP_HERE = ('Set the workspace up on this computer itself: from a phone, set-up is not '
              'offered, and nothing is said about the folders here.')
BRAND_ADDRESS = ("From a phone, give the brand skill's repository as a web address "
                 '(https://… or git@host:owner/repository.git). A folder on this computer, '
                 'or clearing it, is done on this computer itself.')
# The scp-like form git reads as a remote: a user, a host and a path, with no slash before
# the colon and nothing that could be read as an option.
_HOST = re.compile(r'[a-z0-9_][a-z0-9_.:-]*(%[a-z0-9_.-]+)?')
_SCP = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.+-]*@[A-Za-z0-9][A-Za-z0-9.-]*:[^\s]+')


BRAND_UNREAD = ("The brand skill's repository could not be read from here. The reason is "
                'shown when it is given on this computer itself.')


def _numbers(host: str):
    """The address a host written as numbers stands for, in any spelling git and ssh take
    (`127.1` and `2130706433` are 127.0.0.1), or None for a name."""
    plain = host.strip('[]').split('%', 1)[0]
    try:
        found = ipaddress.ip_address(plain)
    except ValueError:
        try:
            found = ipaddress.IPv4Address(socket.inet_aton(plain))
        except (OSError, ValueError):
            return None
    mapped = getattr(found, 'ipv4_mapped', None)
    return mapped or found


def _own_names() -> set[str]:
    """This computer's own host name, its short form and its local-network form."""
    try:
        name = socket.gethostname().strip().rstrip('.').casefold()
    except OSError:
        return set()
    short = name.split('.', 1)[0]
    return {one for one in (name, short, short + '.local') if one}


def this_computer(host) -> bool:
    """Whether a host names this computer: localhost or a name under it, a loopback or
    unspecified address, or this computer's own host name. Nothing is looked up."""
    if not isinstance(host, str) or not host.strip():
        return True
    name = host.strip().rstrip('.').casefold()
    if name == 'localhost' or name.endswith('.localhost'):
        return True
    found = _numbers(name)
    if found is not None:
        return found.is_loopback or found.is_unspecified
    return name in _own_names()


def web_repository(address) -> bool:
    """Whether a repository address is one git reads as a remote on another computer,
    never a path here: an https:// or ssh:// address, or user@host:path, whose host is not
    this computer. Read from its text alone."""
    if not isinstance(address, str):
        return False
    value = address.strip()
    if not value or any(character.isspace() or ord(character) < 32 for character in value):
        return False
    if _SCP.fullmatch(value):
        return not this_computer(value.split('@', 1)[1].split(':', 1)[0])
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return False
    # A user or host that starts with a dash would reach ssh as an option
    # (ssh://-oProxyCommand=...), and a host is letters, digits, dots, dashes and colons.
    user = parts.netloc.rpartition('@')[0]
    if not host or user.startswith('-') or not _HOST.fullmatch(host):
        return False
    return parts.scheme.lower() in ('https', 'ssh') and not this_computer(host)


def unread_said(said: str) -> str:
    """Why a brand repository could not be read, as this caller is told it: git's own
    reason on this computer, a plain sentence (BRAND_UNREAD) through the network bridge."""
    return BRAND_UNREAD if remote() else said


def settings_refused(route, sent) -> str | None:
    """For a remote caller, the sentence that refuses set-up (`SETUP_ROUTES`), or a brand
    repository that is not a web address (`BRAND_ROUTE`); None for a caller on this
    computer, and for every other route."""
    if not remote():
        return None
    if route in SETUP_ROUTES:
        return SETUP_HERE
    if route == BRAND_ROUTE:
        given = sent.get('repository') if isinstance(sent, dict) else None
        return None if web_repository(given) else BRAND_ADDRESS
    return None
