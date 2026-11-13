"""Copy a training's setup into the start form, to change and start as a new training.

What a caller needs to know
---------------------------
    copy_setup.of(engine, path)   # the form's values, and a source draft holding its documents

- The answer is {'title', 'values', 'flags_review', 'slide_text_review', 'sources', 'left'}.
  `values` are what Change settings shows (`settings_change.values`). `sources` is a new
  source draft, as the start form's editor takes one: what the training's research read
  (links, files, pasted text and where it may search), then every readable document added
  to it since, from the copy the training kept. `left` says, in sentences, what could not
  be brought.
- The training copied is only read. It may be working, finished or run by someone else.
  Nothing is started and nothing of it changes: the new training is made by Start, as any
  other, and researches again from the first.
- A document pinned from the Document Library is brought as the revision the training kept,
  as a file. It is no longer tied to the library.
- Documents are kept only on the computer they were added on. Where they are not here,
  `sources` holds none of them and `left` says so.
"""
from __future__ import annotations

import base64
from pathlib import Path

import workspace
from workspace import WorkspaceError

import runner  # noqa: F401  puts the core on the import path
from runner import drafts, pipeline, settings_change
from studio_core import research_sites, research_sources

TITLE = '{title} copy'
SOURCES_LEFT = ('What its research read could not be copied ({why}). Add the documents '
                'again in step 2.')
DOCUMENT_LEFT = '“{name}” could not be copied ({why}). Add it again in step 2.'
FULL = ('A training takes at most {most} files and pasted texts, so {count} of its documents '
        'were not copied.')


def _store(engine) -> research_sources.Sources:
    return research_sources.Sources(engine.space().root / '.research-sources')


def _documents(engine, root: Path, store, made: dict, left: list[str]) -> dict:
    """Add each readable document the training kept to the draft, as a file. One that cannot
    be read here is said in `left` and leaves the draft as it was."""
    kinds = research_sources.TYPES
    held = sum(source.get('kind') not in research_sources.LINKS for source in made['sources'])
    kept = [entry for entry in engine.documents.listed(root) if entry['readable']]
    room = max(0, research_sources.MOST - held)
    if len(kept) > room:
        left.append(FULL.format(most=research_sources.MOST, count=len(kept) - room))
    for entry in kept[:room]:
        name = entry['name']
        try:
            if Path(name).suffix.lower() not in kinds:
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
    """What the start form is filled in with to make a training like this one."""
    root = engine.driven(path)
    if root is None:
        raise WorkspaceError('No run is driving this training.')
    with engine.files:
        record = engine._load(root)
        session = workspace.load(root)
        values = settings_change.values(root, session, record)
    from studio_core import studios_config
    shared, _ = studios_config.read()
    store, left = _store(engine), []
    looks = pipeline.research_of(record)
    sites = research_sites.defaults(shared)
    try:
        made = store.from_inputs(root, record.get('research_inputs'), looks, sites=sites)
    except (OSError, ValueError, KeyError) as failure:
        # Its captures may be on another computer. Where research may search is still copied.
        left.append(SOURCES_LEFT.format(why=str(failure).rstrip('.') or type(failure).__name__))
        made = store.from_inputs(root, None, looks, sites=sites)
    made = _documents(engine, root, store, made, left)
    return {'title': TITLE.format(title=session['title']), 'values': values,
            # A training made before these were asked takes the start form's own choices.
            'flags_review': drafts.on_desk(record) and record.get('research_flags') != 'assistant',
            'slide_text_review': not drafts.on_desk(record) or bool(record.get('deck_content')),
            'sources': made, 'left': left}
