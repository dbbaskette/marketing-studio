"""The shared Document Library: uploads and finished studio work kept once, on this computer,
and offered to every studio as context a project chooses.

What a caller needs to know
---------------------------
    from studio_core import document_library as library
    library.location()                  # {'root', 'saved', 'shown'}: nothing is written
    found = library.opened()            # the Library when its folder exists, else None
    made = library.opened(create=True)  # an explicit use: the location is frozen and made
    made.add_upload(name, data, operation=...)          # an upload, original and Markdown
    made.retain(key=..., studio=..., kind=..., title=..., text=...)   # finished work
    found.catalog(query=..., kind=..., studio=..., offset=..., limit=...)
    found.preview(ident, revision)      # readable Markdown, bounded
    found.snapshot(ident, revision)     # what a project pins: checked against its hashes
    found.heads(ids)                    # each document's newest revision, for Update available
    found.filters(studio) / made.remember(studio, filters)   # browsing, never a selection
    found.keyed(keys) / made.adopt(key=..., ...)   # existing work, added only when confirmed

`adopt.py` previews and confirms Add existing work to library over the studios' remembered
workspaces; `blog_existing.py` reads Blog Studio's team library for it, changing nothing.
See `store.py` for the record contract. The library never selects context, never starts
research or an assistant, and never shares anything: a project's choice is the project's.
"""
from .store import (FORMATS, KINDS, LIMITS, ORIGINS, STUDIOS, Library, LibraryError,
                    location, opened)

__all__ = ['FORMATS', 'KINDS', 'LIMITS', 'ORIGINS', 'STUDIOS', 'Library', 'LibraryError',
           'location', 'opened']
