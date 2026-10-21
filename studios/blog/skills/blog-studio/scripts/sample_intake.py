"""Writing samples that arrive as a LinkedIn export.

The export becomes the checked rows management.upload saves for files: its About text as
author background and each article as a voice sample, all by its person. Links to posts
are not read here; they go through voice_links and the library import.
"""

import base64
import binascii
import csv
import zipfile
import zlib

import blog_library
import linkedin_import
import studio

MAX_ARCHIVE = 10 * 1024 * 1024
NOT_AN_EXPORT = 'That file is not a LinkedIn export zip. Download "Get a copy of your data" again.'


def checked_linkedin(root, entry, limit=19):
    """The About text and each article of a LinkedIn export, as checked uploads. The
    About text is author background; the articles are authored voice samples.

    Everything is checked here, before anything is saved: an article too long to share
    is left out, and at most `limit` articles are read, each with a note on the first row.
    """
    if set(entry) != {'linkedin'} or not isinstance(entry['linkedin'], str):
        raise ValueError('Give the LinkedIn export on its own.')
    try:
        data = base64.b64decode(entry['linkedin'], validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(NOT_AN_EXPORT) from None
    if not data or len(data) > MAX_ARCHIVE:
        raise ValueError(
            'Upload a LinkedIn export of at most 10 MiB; request only Profile and Articles.'
        )
    try:
        found = linkedin_import.parse(data)
    except (
        zipfile.BadZipFile,
        csv.Error,
        RuntimeError,
        UnicodeDecodeError,
        EOFError,
        zlib.error,
        NotImplementedError,
    ):
        raise ValueError(NOT_AN_EXPORT) from None
    rows, notes = [], list(found['limitations'])
    # The request's own author name wins over this; a profile name that is not a usable
    # author name is left out rather than refusing the export.
    try:
        author = studio.checked_author(found.get('name'))
    except ValueError:
        author = None
    about = '\n\n'.join(part for part in (found['headline'], found['summary']) if part)
    if about and len(about.encode()) > blog_library.MAX_TEXT:
        notes.append('The About text was left out: too long to share.')
    elif about:
        rows.append(
            _row(
                'linkedin-about.md',
                'LinkedIn · About',
                about,
                'LinkedIn export: Profile.csv',
                'author-background',
                author,
            )
        )
    articles = [a for a in found['articles'] if len(a['text'].encode()) <= blog_library.MAX_TEXT]
    if len(articles) < len(found['articles']):
        notes.append(
            '%d articles were left out: too long to share.'
            % (len(found['articles']) - len(articles))
        )
    if len(articles) > limit:
        articles = articles[:limit]
        notes.append(
            'Only the first %d articles were read; upload the rest in another export.' % limit
        )
    for index, article in enumerate(articles, 1):
        rows.append(
            _row(
                'linkedin-article-%d.md' % index,
                'LinkedIn · ' + article['title'][:480],
                article['text'],
                'LinkedIn export: ' + article['origin'],
                'voice-sample',
                author,
            )
        )
    if not rows:
        raise ValueError(' '.join(notes) or 'This LinkedIn export has nothing to read.')
    if notes:
        rows[0]['note'] = ' '.join(notes)
    return rows


def _row(filename, title, text, origin, purpose, author):
    return {
        'filename': filename,
        'shown': title,
        'suffix': '.md',
        'content': text.encode(),
        'text': text,
        'status': 'ready',
        'note': '',
        'title': title,
        'origin': origin,
        'purpose': purpose,
        'author': author,
    }
