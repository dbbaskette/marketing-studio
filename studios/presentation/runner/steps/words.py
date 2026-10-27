"""A slide's words on the desk: the new words put into the outline and into the section as it
is drawn, checked by the slides tool, with no composer.

What a caller needs to know
---------------------------
    outline = words.retext(outline, slide_id, field, text)       # a new outline, not written
    section = words.patch_section(drawn, slide_id, field, old, new)  # a new drawn section
    lines = words.fits(root, run, section_id, section, slides, outline)  # the tool's lines
    words.land(root, run, section_id, section)                   # kept as a new drawn file
    words.retold(root, slide_id, outline, knows)                 # the start's outline told

- A field is one of FIELDS, or a point's label or text: ('points', index, 'label'|'text').
  Title, subtitle, detail, caveat, source and notes are the slide's own fields in a drawn
  section. A point's words are text in its canvas: the old words must be found in exactly
  one piece of the slide's text, where they are replaced; otherwise nothing is patched
  (NOT_FOUND), and the slide is redrawn instead.
- `fits` is the check a composer's section passes (`worker_tools.check_section`): what was
  fixed is as it was, every approved word is there, and the slides tool compiles it. It
  refuses rather than shrinks: words that no longer fit come back as the tool's own lines.
- `land` writes only this computer's work/build/drawn/; `retold` only the start's given/
  outline (work/), so the next start of the deck keeps every section whose words are the
  same. Neither starts a job; the engine puts the deck together afterwards.
"""
from __future__ import annotations

import copy
import json
import secrets
import tempfile
from pathlib import Path

import home
from workspace import WorkspaceError, write_atomic

import runner  # noqa: F401  puts the core on the import path
from runner.steps import build

FIELDS = ('title', 'subtitle', 'detail', 'caveat', 'source', 'notes')
KEYS = ('label', 'text')
NO_FIT = 'These words do not fit the slide as it is drawn.'
NOT_FOUND = 'The old words were not found once on the drawn slide.'
NO_FIELD = 'Choose the title, subtitle, detail, a point, the caveat, the source or the notes.'
TOO_LONG = 2000   # characters in one field's words


def field_of(field):
    """A field as the desk names it: one of FIELDS, or ('points', index, 'label'|'text')
    (a list from the page is taken as that tuple). Refused otherwise."""
    if isinstance(field, str) and field in FIELDS:
        return field
    if isinstance(field, (list, tuple)) and len(field) == 3 and field[0] == 'points' \
            and type(field[1]) is int and field[1] >= 0 and field[2] in KEYS:
        return ('points', field[1], field[2])
    raise WorkspaceError(NO_FIELD)


def text_of(slide: dict, field) -> str:
    """A slide's words in one field, '' where it has none."""
    field = field_of(field)
    if isinstance(field, tuple):
        points = slide.get('points') or []
        if field[1] >= len(points):
            raise WorkspaceError(NO_FIELD)
        return str(points[field[1]].get(field[2]) or '')
    value = slide.get(field)
    return str((value.get('text') if isinstance(value, dict) else value) or '')


def retext(outline: dict, slide_id: str, field, text: str) -> dict:
    """A new outline with one slide's words in one field changed. The given one is kept."""
    field = field_of(field)
    if not isinstance(text, str) or len(text) > TOO_LONG:
        raise WorkspaceError(f'Keep the words to {TOO_LONG:,} characters.')
    if (field == 'title' or isinstance(field, tuple)) and '\n' in text.strip():
        raise WorkspaceError('Keep a title and a point to one line.')
    made = copy.deepcopy(outline)
    slide = next((one for one in build.slides_of(made) if one.get('id') == slide_id), None)
    if slide is None:
        raise WorkspaceError('The deck has no such slide.')
    text = text.strip()
    if isinstance(field, tuple):
        points = slide.get('points') or []
        if field[1] >= len(points):
            raise WorkspaceError(NO_FIELD)
        points[field[1]][field[2]] = text
    elif text:
        slide[field] = text
    else:
        slide.pop(field, None)
    return made


def _texts(node, found: list) -> None:
    """Every dict in a drawing that shows a piece of text, in order."""
    if isinstance(node, list):
        for item in node:
            _texts(item, found)
    elif isinstance(node, dict):
        for key in ('text', 'value', 'label'):
            if isinstance(node.get(key), str) and node.get('type') != 'badge':
                found.append((node, key))
        for value in node.values():
            if isinstance(value, (dict, list)):
                _texts(value, found)


def patch_section(section: dict, slide_id: str, field, old: str, new: str) -> dict:
    """A new drawn section with one slide's words changed: a field of the slide set as it
    is, or a point's old words replaced where they are drawn, once. NOT_FOUND when they
    are drawn more than once, or not at all."""
    field = field_of(field)
    made = copy.deepcopy(section)
    slide = next((one for one in made.get('slides') or () if isinstance(one, dict)
                  and one.get('id') == slide_id), None)
    if slide is None:
        raise WorkspaceError(NOT_FOUND)
    new = (new or '').strip()
    if not isinstance(field, tuple):
        if field == 'caveat' and isinstance(slide.get('caveat'), dict):
            slide['caveat'] = {**slide['caveat'], 'text': new}
        elif new:
            slide[field] = new
        else:
            slide.pop(field, None)
        return made
    old = (old or '').strip()
    if not old or not new:
        raise WorkspaceError(NOT_FOUND)
    found = []
    _texts([slide.get('canvas'), slide.get('connect')], found)
    held = [(node, key) for node, key in found if old in node[key]]
    if len(held) != 1 or held[0][0][held[0][1]].count(old) != 1:
        raise WorkspaceError(NOT_FOUND)
    node, key = held[0]
    node[key] = node[key].replace(old, new)
    return made


def fits(root, run: dict, section: str, patched: dict, slides, outline: dict) -> list[str]:
    """The slides tool's lines where the patched section no longer fits, and the runner's
    where an approved word is gone: empty when it fits. Checked against `outline`, the start's
    approved outline with the new words, as a composer's section is."""
    from runner import worker_tools
    spec = build.section_spec(root, run, section, outline=outline)
    with tempfile.TemporaryDirectory(prefix='presentation-words-') as scratch:
        problems, _, _, _ = worker_tools.check_section(
            json.dumps(patched, ensure_ascii=False), spec, slides, Path(scratch))
    return list(problems)


def given(root) -> dict:
    """The start's approved outline, as the build began from it."""
    state = build.read_state(root)
    began = state.get('start') or {}
    if not began:
        raise WorkspaceError('There is no drawing of this deck on this computer.')
    found = home.read_json(Path(root) / began['folder'] / 'given' / 'outline.json', None)
    if not isinstance(found, dict):
        raise WorkspaceError('There is no drawing of this deck on this computer.')
    return found


def with_words(whole: dict, outline: dict, slide_id: str) -> dict:
    """The start's approved outline with one slide's words as `outline` has them now."""
    made = copy.deepcopy(whole)
    now = next((one for one in build.slides_of(outline) if one.get('id') == slide_id), None)
    for at, slide in enumerate(made.get('slides') or ()):
        if isinstance(slide, dict) and slide.get('id') == slide_id and now is not None:
            kept = {key: value for key, value in slide.items()
                    if key not in (*FIELDS, 'points')}
            made['slides'][at] = {**kept, **{key: now[key] for key in (*FIELDS, 'points')
                                             if key in now}}
    return made


def land(root, run: dict, section: str, patched: dict) -> Path:
    """Keep the patched section as a new drawn file of this computer's, so the deck is put
    together again from it (`Engine._needs_whole`). Returns the file."""
    root = Path(root)
    state = build.read_state(root)
    entry = (state.get('sections') or {}).get(section)
    if entry is None:
        raise WorkspaceError(f'The deck has no drawing of {section} here.')
    file = build.DRAWN / f'{section}-w{secrets.token_hex(3)}.json'
    write_atomic(root / file, json.dumps(patched, ensure_ascii=False, indent=2) + '\n')
    state['sections'][section] = {**entry, 'file': file.as_posix(),
                                  'round': len(state.get('rounds') or ()), 'words': True,
                                  'at': home.now()}
    build.write_state(root, state)
    return root / file


def retold(root, whole: dict, knows=frozenset()) -> None:
    """Write the start's approved outline again with the new words: given/outline.json, and
    the slides tool's copy of it, so a later start keeps the sections they did not change."""
    root = Path(root)
    began = build.read_state(root).get('start') or {}
    folder = root / began['folder']
    home.write_json(folder / 'given' / 'outline.json', whole)
    if (folder / build.TOOL_OUTLINE).is_file():
        home.write_json(folder / build.TOOL_OUTLINE, build.for_tool(whole, knows))
