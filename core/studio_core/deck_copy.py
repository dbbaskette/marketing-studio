"""What a slide may show of a team's bookkeeping: nothing. One check, used by every studio.

What a caller needs to know
---------------------------
    deck_copy.internal(text, ids, slugs)      # the bookkeeping a text shows, or None
    deck_copy.problems(slides, ids, slugs)    # a sentence for each, saying where it goes

- `ids` are the identifiers the run itself defines: its objectives, modules and key points,
  its research findings, facts and sources. `slugs` are its own practice scenarios' slugs.
  Nothing else is taken for bookkeeping, so "O2 sensors", "g5.xlarge", "Model O3",
  "Research 2024", "Objectives 2 and 3", "real-time:" or "x86-64:" are ordinary words.
- An ID is bookkeeping after a bookkeeping word ("Finding g4", "Blueprint M1",
  "objectives O1–O3", "research findings g2"), in a list of two or more of them
  ("g1, g7"), or as the whole of what a field shows ("O4"). The word is matched whatever
  its case; an ID only as it is written. A slug is bookkeeping anywhere when it is
  hyphenated, as only a slug is, and otherwise only as a prefix ("main: …").
- A web address is a citation, and is left out of the check.
- Standard library only.
"""
from __future__ import annotations

import json
import re

WORD = r'(?i:research\s+findings?|findings?|objectives?|blueprint)'
SEP = r'\s*[,/–-]\s*'
SHOWN = ('title', 'subtitle', 'focal', 'caveat', 'source')   # what a slide shows, by field
TOLD = ("Audiences cannot follow finding, objective or blueprint IDs, or a scenario's slug. "
        'Cite a document the audience can look up by name in `source`, such as "Tanzu for '
        'Postgres 4.5 documentation", or leave it out; write a scenario by its title in '
        "words; and put the IDs in the slide's `provenance`, which goes only into the "
        'speaker notes.')


def _alternation(ids) -> str | None:
    known = sorted({str(ident) for ident in ids or () if str(ident).strip()},
                   key=lambda ident: (-len(ident), ident))
    return '(?:' + '|'.join(re.escape(ident) for ident in known) + ')' if known else None


def internal(text, ids=(), slugs=()) -> str | None:
    """The bookkeeping a piece of a slide's visible copy shows, or None when it shows none."""
    if not isinstance(text, str):
        return None
    bare = re.sub(r'https?://\S+', '', text)
    ident = _alternation(ids)
    patterns = []
    if ident:
        one = rf'(?<![\w-]){ident}(?![\w.-])'
        patterns += [rf'\b{WORD}\b[\s:#]*{one}(?:{SEP}{one})*',
                     rf'{one}(?:{SEP}{one})+',
                     rf'^\s*{one}(?:[\s,;/–-]+{one})*\s*$']
    for slug in slugs or ():
        if not isinstance(slug, str) or not slug.strip():
            continue
        escaped = re.escape(slug.strip())
        patterns.append(rf'(?<![\w-]){escaped}(?![\w-])' if re.search('[-_]', slug)
                        else rf'(?:^|(?<=[;.]\s)){escaped}:')
    for pattern in patterns:
        found = re.search(pattern, bare)
        if found:
            return found.group(0).strip(' ;.')
    return None


def _points(slide: dict) -> list[dict]:
    return [point for point in slide.get('points') or () if isinstance(point, dict)]


def problems(slides, ids=(), slugs=()) -> list[str]:
    """What is refused because a slide shows a team's bookkeeping, in any field a slide shows,
    with where it goes instead; and a `provenance` that is not text."""
    found = []
    for slide in slides or ():
        if not isinstance(slide, dict):
            continue
        where_id = slide.get('id') or 'a slide'
        if 'provenance' in slide and (not isinstance(slide['provenance'], str)
                                      or not slide['provenance'].strip()):
            found.append(f'{where_id}: `provenance` is text: the IDs and notes behind the '
                         'slide, which no slide shows. Leave it out when there are none.')
        seen = [(key, slide.get(key)) for key in SHOWN]
        seen += [(f"a point's {key}", point.get(key)) for point in _points(slide)
                 for key in ('label', 'text')]
        seen += [("a point's part", part) for point in _points(slide)
                 for part in point.get('parts') or () if isinstance(part, str)]
        for where, text in seen:
            shown = internal(text, ids, slugs)
            if shown:
                found.append(f'{where_id}: {where} shows {json.dumps(shown)}. {TOLD}')
    return found
