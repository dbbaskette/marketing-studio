"""Who sent the request a deck studio's page is answering: the person at this computer, or a
phone or tablet through Marketing Studio's network bridge.

What a caller needs to know
---------------------------
    from studio_core.shared_runner import caller
    with caller.answering(headers):       # around one request's answer, in the page
        ...
    caller.remote()                       # True while answering a request the bridge carried
    caller.folder_refused(sent)           # the sentence refusing a folder on this computer
                                          # to a remote caller in a source editor's folder add

The bridge adds `X-Marketing-Studio-Via: network` to every request it carries to a studio,
building its upstream headers from a fixed allow-list, so a network caller can neither send
nor strip it. A request is remote if and only if it carries that header with the value
`network`. A loopback caller that sends it only refuses itself what a phone is refused.

A remote caller may still give a Google Drive folder link and upload files; only a folder
path on this computer is refused (`source_intake.REMOTE`), so a phone on the local network
cannot read this computer's folders. Nothing here reads a folder or uses the network.
"""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager

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
