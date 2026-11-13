"""Copy a deck's setup into the start form, to change and start as a new deck.

What a caller needs to know
---------------------------
    copy_setup.of(engine, path)   # the form, its starting material, and a source draft

- The answer is {'title', 'form', 'upload', 'text', 'sources', 'left'}. `form` is the form
  the deck was started with, as its record keeps it. `upload` is the file it started from
  ({'name', 'size', 'encoded'}, in base64), for a deck made from an uploaded document or
  deck; `text` is the text pasted for one made from pasted text; a Google link is in the
  form itself. `sources` is a new source draft, as the start form's editor takes one: what
  the deck's research read and where it may search, then every other readable document the
  deck was given since, from the copy it kept. `left` says, in sentences, what could not be
  brought.
- The deck copied is only read. It may be working, finished or driven by someone else.
  Nothing is started and nothing of it changes: the new deck is made by Start, as any other.
- A document pinned from the Document Library is brought as the revision the deck kept, as
  a file. It is no longer tied to the library.
- Documents and the deck's starting material are kept only on the computer they were added
  on. Where they are not here, `left` says so and the form asks for them again.
"""
from __future__ import annotations

import base64
from pathlib import Path

from workspace import WorkspaceError

import runner  # noqa: F401  puts the core on the import path
from runner import decks, documents
from runner.steps import existing
from studio_core import research_sites, research_sources

INCOMING = 'sources/incoming'
TITLE = '{title} copy'
FORM = ('route', 'title', 'audience', 'goal', 'notes', 'minutes', 'brand', 'variant', 'output',
        'delivery', 'research', 'research_questions', 'level', 'selected', 'look', 'reading')
NO_FILE = ('The file it started from, “{name}”, is not on this computer. Choose it again in '
           'step 1.')
NO_TEXT = 'The text it started from is not on this computer. Paste it again in step 1.'
SOURCES_LEFT = ('What its research read could not be copied ({why}). Add the sources again '
                'in step 3.')
DOCUMENT_LEFT = '“{name}” could not be copied ({why}). Add it again in step 3.'
FULL = ('A deck takes at most {most} files and pasted texts, so {count} of its documents '
        'were not copied.')


def _file(path: Path, name: str) -> dict | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw:
        return None
    return {'name': name, 'size': len(raw), 'encoded': base64.b64encode(raw).decode('ascii')}


def _material(root: Path, form: dict, entries: list[dict], left: list[str]):
    """The file or text the deck started from, and the entry it is kept as (never a
    research source of the copy)."""
    route, source = form.get('route'), form.get('source') or {}
    kind = source.get('kind')
    first = entries[0] if route == 'document' and entries else None
    if kind == 'upload':
        name = source.get('name') or 'upload'
        kept = root / existing.SOURCE if route == 'existing' \
            else root / first['original'] if first else None
        found = _file(root / INCOMING / 'upload', name) or (_file(kept, name) if kept else None)
        if found is None:
            left.append(NO_FILE.format(name=name))
        return found, None, first
    if kind == 'paste':
        text = None
        try:
            waiting = root / INCOMING / 'pasted.txt'
            text = waiting.read_text(encoding='utf-8') if waiting.is_file() \
                else documents.text_of(root, first) if first and first['readable'] else None
        except (OSError, WorkspaceError):
            text = None
        if not text:
            left.append(NO_TEXT)
        return None, text or None, first
    return None, None, first if kind == 'google' else None


def _documents(root: Path, entries: list[dict], store, made: dict, left: list[str]) -> dict:
    """Add each readable document to the draft, as a file. One that cannot be read here is
    said in `left` and leaves the draft as it was."""
    held = sum(source.get('kind') not in research_sources.LINKS for source in made['sources'])
    kept = [entry for entry in entries if entry['readable']]
    room = max(0, research_sources.MOST - held)
    if len(kept) > room:
        left.append(FULL.format(most=research_sources.MOST, count=len(kept) - room))
    for entry in kept[:room]:
        name = entry['name']
        try:
            if Path(name).suffix.lower() not in research_sources.TYPES:
                raise ValueError('its type is not one the start form takes')
            raw = (root / entry['original']).read_bytes()
            before = {source['id'] for source in made['sources']}
            made = store.mutate(made['id'], made['revision'], 'capture', kind='file', name=name,
                                content=base64.b64encode(raw).decode('ascii'))
            new = next(source for source in made['sources'] if source['id'] not in before)
            if new['status'] != 'ready':
                made = store.mutate(made['id'], made['revision'], 'remove', source=new['id'])
                raise ValueError((new.get('problem') or 'it could not be read').rstrip('.'))
        except (OSError, ValueError) as failure:
            why = failure.strerror if isinstance(failure, OSError) and failure.strerror \
                else str(failure)
            left.append(DOCUMENT_LEFT.format(name=name, why=why))
    return made


def of(engine, path) -> dict:
    """What the start form is filled in with to make a deck like this one."""
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('There is no deck there.')
    with engine.files:
        record = engine._load(root)
    kept = record.get('form') if isinstance(record.get('form'), dict) else {}
    form = {key: kept[key] for key in FORM if key in kept}
    form.setdefault('route', record.get('route'))
    title = form.get('title') or record.get('title') or 'Untitled'
    source = kept.get('source') or {}
    if source.get('kind') in ('upload', 'google', 'paste'):
        form['source'] = {key: source[key] for key in ('kind', 'name', 'link') if key in source}
    left: list[str] = []
    try:
        entries = documents.listed(root)
    except (OSError, ValueError, WorkspaceError):
        entries = []
    upload, text, first = _material(root, kept, entries, left)
    made = None
    if form.get('route') != 'existing':
        from studio_core import studios_config
        shared, _ = studios_config.read()
        store = research_sources.Sources(engine.space().root / '.research-sources')
        looks = research_sites.effective(decks.research_from(kept) or
                                         {'documents': False, 'sites': [], 'web': False})
        sites = research_sites.defaults(shared)
        try:
            made = store.from_inputs(root, record.get('research_inputs'), looks, sites=sites)
        except (OSError, ValueError, KeyError) as failure:
            left.append(SOURCES_LEFT.format(why=str(failure).rstrip('.')
                                            or type(failure).__name__))
            made = store.from_inputs(root, None, looks, sites=sites)
        made = _documents(root, [entry for entry in entries if entry is not first], store,
                          made, left)
    return {'title': TITLE.format(title=title), 'form': form, 'upload': upload, 'text': text,
            'sources': made, 'left': left}
