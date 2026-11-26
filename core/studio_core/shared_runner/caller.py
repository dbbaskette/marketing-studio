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
    caller.shown(described)               # a set-up or brand description as this caller is
                                          # shown it: no folder path for a remote caller
    caller.bring_refused(path)            # the sentence refusing a remote caller Bring in of
                                          # a folder on this computer; None otherwise

The bridge adds `X-Marketing-Studio-Via: network` to every request it carries to a studio,
building its upstream headers from a fixed allow-list, so a network caller can neither send
nor strip it. A request is remote if and only if it carries that header with the value
`network`. A loopback caller that sends it only refuses itself what a phone is refused.

A remote caller may still give a Google Drive folder link and upload files; only a folder
path on this computer is refused (`source_intake.REMOTE`), so a phone on the local network
cannot read this computer's folders. Nothing here reads a folder or uses the network.

Set-up and the brand skill's repository (GitHub issue #539, the owner's ruling: refuse
folders, allow addresses). For a remote caller, `settings_refused` refuses the two set-up
routes whatever they were sent (SETUP_ROUTES: `/api/setup`, `/api/setup/check`), so no
folder here is checked or set for a phone; and the brand skill's repository route (BRAND_ROUTE,
`/api/brand`) unless `repository` is a web repository address: `https://` with a host,
`ssh://` with a host, or the `user@host:path` form, which git reads as a remote, on a host
that is not this computer. Anything git may read as a path on this computer (a folder,
`file://`, `host:path` without a user, an empty address) is refused, and so is an address
whose host is this computer (`localhost` and any name under it, a loopback or unspecified
address in any spelling, this computer's own host name): over ssh that reads a folder here.
Hosts on the local network stay allowed: a team's own git server is a web address. Only
the address's text is read: no name is looked up. When such an address cannot be read,
`unread_said` gives a remote caller a sentence with none of git's own words, which can
name hosts and ports; a caller on this computer keeps git's reason. A caller on this
computer is never refused here: what it may do is as before. Every other route answers
None.

What a remote caller is shown (the owner's decision: a phone cannot set or ask about a
folder on this computer, and is not shown folder paths). `shown` is applied to every answer
that describes set-up or the brand: a value under a `path` key that names a folder on this
computer is left out (None), and any other value that names one (a brand skill's
repository, or a team repository, saved as a folder) is said only as FOLDER_HERE. A folder
is told by its shape alone: it starts with `/`, `~` or `file:`. A sentence that names one
anywhere in it (`brand_data.names_a_folder`, the test Marketing Studio's page and the setup
pages use), such as the upkeep report's sentence for a broken skill link, is said only as
FOLDER_SAID, wherever it sits in the description. A caller on this computer is shown
everything as before. `bring_refused` refuses a remote caller's Bring in of a
folder before anything about the folder is read, so its refusals cannot tell a phone what
is there. Deck pages still name each deck by its folder; that is not covered here.
"""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager

from studio_core import brand_data, repository_address, source_folders, source_intake

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
BRAND_UNREAD = ("The brand skill's repository could not be read from here. The reason is "
                'shown when it is given on this computer itself.')


def this_computer(host) -> bool:
    """Whether a host names this computer; the rule every studio shares
    (studio_core.repository_address). Nothing is looked up."""
    return repository_address.this_computer(host)


def web_repository(address) -> bool:
    """Whether a repository address is one git reads as a remote on another computer,
    never a path here. One rule for a phone in every studio and in Marketing Studio:
    studio_core.repository_address.web_repository. Read from its text alone."""
    return repository_address.web_repository(address)


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


FOLDER_HERE = 'a folder on this computer'
# Said to a remote caller in place of a sentence that names a folder on this computer, such as
# the upkeep report's sentence for a broken skill link (GitHub issue #539).
FOLDER_SAID = ('The reason names a folder on this computer, so it can be seen only on that '
               'computer itself.')
BRING_HERE = ('Bring work in from a folder on this computer itself: from a phone, folders '
              'here are not read.')


def _a_folder(value) -> bool:
    """Whether a value names a folder on this computer, by its shape alone."""
    return isinstance(value, str) and value.strip()[:1] in ('/', '~') \
        or isinstance(value, str) and value.strip().lower().startswith('file:')


def _hidden(value, key=None):
    if isinstance(value, dict):
        return {name: _hidden(one, name) for name, one in value.items()}
    if isinstance(value, list):
        return [_hidden(one, key) for one in value]
    if _a_folder(value) and not _a_sentence(value):
        return None if key == 'path' else FOLDER_HERE
    if isinstance(value, str) and brand_data.names_a_folder(value):
        return FOLDER_SAID          # a sentence naming one, as Marketing Studio's page says it
    return value


def _a_sentence(value) -> bool:
    """Whether a value that starts with a folder goes on as a sentence ("/x is not the link
    the installer placed, ... there."): words after it, and a full stop at its end."""
    text = value.strip()
    return text.endswith('.') and ' ' in text


def shown(described):
    """A set-up or brand description as this caller is shown it: as it is on this computer;
    through the network bridge, with no folder path (see the module's docstring)."""
    return _hidden(described) if remote() else described


def bring_refused(path) -> str | None:
    """For a remote caller, the sentence that refuses Bring in of a folder on this computer,
    before the folder is read; None for a caller on this computer."""
    if not remote():
        return None
    return BRING_HERE if on_this_computer(path) or not isinstance(path, str) else None
