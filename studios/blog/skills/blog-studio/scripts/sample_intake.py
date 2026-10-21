"""Writing samples that arrive as a LinkedIn export.

The export becomes the checked rows management.upload saves for files: its About text as
author background and each article as a voice sample, all by its person. Links to posts
are not read here; they go through voice_links and the library import.
"""

import base64
import binascii
import csv
import zipfile

import linkedin_import

MAX_ARCHIVE = 10 * 1024 * 1024
NOT_AN_EXPORT = 'That file is not a LinkedIn export zip. Download "Get a copy of your data" again.'


def checked_linkedin(root, entry):
    """The About text and each article of a LinkedIn export, as checked uploads. The
    About text is author background; the articles are authored voice samples."""
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
    except (zipfile.BadZipFile, csv.Error, RuntimeError):
        raise ValueError(NOT_AN_EXPORT) from None
    rows = []
    author = found.get('name') or None  # the request's own author name wins over this
    about = '\n\n'.join(part for part in (found['headline'], found['summary']) if part)
    if about:
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
    for index, article in enumerate(found['articles'], 1):
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
    if found['limitations']:
        rows[0]['note'] = ' '.join(found['limitations'])
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
