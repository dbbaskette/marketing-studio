"""A studio's private loopback link, and the Document Library item it is opened with.
marketing_studio.launcher re-exports every name here."""

import re
from urllib.parse import urlsplit

from .errors import WorkspaceError


def local_link(link):
    try:
        url = urlsplit(link)
        return (url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
                and url.path == '/' and not url.query and not url.username and not url.password
                and re.fullmatch(r'(?:token=)?[A-Za-z0-9_-]{32,128}', url.fragment))
    except (ValueError, TypeError):
        return False


# A Document Library item a studio is opened with (Continue in another studio): the library's
# own document ID and a revision number, nothing else.
LIBRARY_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
LIBRARY_REVISIONS = 1_000      # the most revisions one document keeps (document_library.LIMITS)


def library_item(value):
    """(id, revision) of `{'id', 'revision'}` sent to /api/open, refused unless the id is in
    the Document Library's own format, the revision is a whole number it can hold, and that
    revision is in the library, readable and not removed from it. Nothing is written."""
    if not isinstance(value, dict) or set(value) - {'id', 'revision'}:
        raise WorkspaceError('Choose a document shown in the Library.')
    ident, revision = value.get('id'), value.get('revision')
    if not isinstance(ident, str) or not LIBRARY_ID.fullmatch(ident) \
            or type(revision) is not int or not 1 <= revision <= LIBRARY_REVISIONS:
        raise WorkspaceError('Choose a document shown in the Library.')
    from studio_core import document_library
    found = document_library.opened()
    if found is None:
        raise WorkspaceError('The Document Library has not been made on this computer yet.')
    try:
        row = found.describe(ident, revision)
    except document_library.LibraryError as failure:
        raise WorkspaceError(str(failure)) from None
    if row.get('hidden'):
        raise WorkspaceError(f'“{row["title"]}” was removed from the library. Restore it first.')
    if not row.get('readable'):
        raise WorkspaceError(f'“{row["title"]}” has no text a studio can use: {row.get("problem") or ""}'.strip())
    return ident, revision


def with_library(link, ident, revision):
    """`link` with `library=<id>@<revision>` added to its fragment, built here from a checked
    id and revision: no text from a request reaches the link. Any earlier `library=` is
    replaced; everything else in the fragment (the token above all) is kept as it was."""
    if not isinstance(ident, str) or not LIBRARY_ID.fullmatch(ident) \
            or type(revision) is not int or not 1 <= revision <= LIBRARY_REVISIONS:
        raise WorkspaceError('Choose a document shown in the Library.')
    parsed = urlsplit(link)
    fragment = [part for part in parsed.fragment.split('&') if part and part.partition('=')[0] != 'library']
    fragment.append(f'library={ident}@{revision}')
    return parsed._replace(fragment='&'.join(fragment)).geturl()
