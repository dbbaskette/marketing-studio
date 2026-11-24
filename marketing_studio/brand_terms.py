"""What brand packs, icon libraries and their working copies are made of, as every part
of brand storage names it. marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import re


SCHEMA = 1
LIBRARIES = 'icon-libraries'
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}$')
VARIANT = re.compile(r'^[a-z][a-z0-9-]{0,30}$')
FILE_NAME = re.compile(r'^[^/\\\x00-\x1f]{1,120}$')
KINDS = ('brand', 'library')
LIBRARY_KINDS = ('glyph', 'picture')
SOURCE_LIMIT = 40_000_000       # bytes in one source file
LINES = 200                     # task lines kept
SEALS = ('files', 'sources', 'brandSha256')
JUDGEMENT = ('relationship', 'contentRange', 'components', 'searchTerms', 'delivery',
             'searchable', 'notes')
PARTS = {'roles': ('brand.json', 'Colour roles and slide settings'),
         'layouts': ('layouts.json', 'What each layout is for'),
         'guide': ('guide.md', 'Brand rules, voice and slides'),
         'directions': ('directions.json', 'Deck directions'),
         'audit': ('audit.json', 'Audit limits')}
SEEN = ('.png', '.svg', '.jpg', '.jpeg')
MEDIA = {'.png': 'image/png', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
PREVIEW_HELP = ('Previews need LibreOffice and Poppler on this computer (brew install --cask '
                'libreoffice; brew install poppler). The layouts are measured all the same.')
