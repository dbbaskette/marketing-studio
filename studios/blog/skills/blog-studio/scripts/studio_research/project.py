"""An item's research folder, laid out the same in every studio.

What a caller needs to know
---------------------------
    sources = project.snapshot(folder, documents)       # [{title, origin, text, status}, ...]
    plan = project.build_plan(topic, purpose, scope, questions, sources, input_files)
    answered = project.save_plan(folder, plan, allow_web)     # {'run', 'carried', ...}
    project.record(folder, run, item, finding)                 # retries a busy save
    found = project.status(folder)                             # the normalized status
    project.publish_report(folder)                             # research/report.md, for the gate

- The layout, inside the item's own folder (a training, a deck, a blog):
      .harness-research/research.json        harness-research's record          shared
      .harness-research/research-report.md   its report, rewritten on each save  shared
      research/plan.json, research/plan.md   the plan handed over, and readable  shared
      research/report.md                     the report the research gate shows  shared
      research/web/<sha256>.md               public pages a worker saved          shared
      research/sources/<key>.md              snapshots of supplied documents      this computer only
- A supplied document is {title, origin, text, status}. Its `key` is the first 16 hex digits
  of the SHA-256 of origin, a newline and text, so a document has the same name wherever the
  item is opened. Only a `ready` one is written; any other is listed with no file and a
  limits sentence, which harness-research reports as a gap. Snapshots of documents no longer
  supplied are removed.
- `status` never raises for research that has not started: it says `not-started`.
- Part of the shared research component (docs/research-component-spec.md).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from . import runtime

RECORD = Path('.harness-research') / 'research.json'
HARNESS_REPORT = Path('.harness-research') / 'research-report.md'
PLAN = Path('research') / 'plan.json'
PLAN_MD = Path('research') / 'plan.md'
REPORT = Path('research') / 'report.md'
WEB = Path('research') / 'web'
SOURCES = Path('research') / 'sources'
VERDICTS = ('supported', 'contradicted', 'insufficient', 'unavailable')
UNRESOLVED = ('insufficient', 'unavailable')
SCOPES = {
    'supplied-only': 'Uploaded sources only',
    'public-web': 'Uploaded sources plus external research',
}
BUSY_TRIES = 20  # times a finding is offered while another save holds the lock
BUSY_WAIT = 0.25


def tool() -> runtime.Research:
    """The installed harness-research, found when it is first needed."""
    return runtime.Research()


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
    try:
        with os.fdopen(handle, 'wb') as out:
            out.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def key(origin: str, text: str) -> str:
    """A supplied document's name in every copy of the item: from its origin and its text."""
    return hashlib.sha256((origin + '\n' + text).encode('utf-8')).hexdigest()[:16]


def snapshot(folder: Path, documents) -> list[dict]:
    """Write each ready document to research/sources/ and return harness-research's source
    manifest. Snapshots of documents no longer supplied are removed."""
    folder = Path(folder)
    place = folder / SOURCES
    place.mkdir(parents=True, exist_ok=True)
    manifest, kept = [], set()
    for document in documents:
        name = key(document['origin'], document['text'])
        if name in kept:
            continue
        kept.add(name)
        entry = {'id': name, 'title': document['title'], 'origin': document['origin']}
        if document.get('status', 'ready') == 'ready':
            path = place / (name + '.md')
            data = document['text'].encode('utf-8')
            if not path.is_file() or path.read_bytes() != data:
                write_atomic(path, data)
            manifest.append({**entry, 'file': (SOURCES / path.name).as_posix(), 'limits': 'none'})
        else:
            manifest.append(
                {
                    **entry,
                    'file': None,
                    'limits': f'This document is not ready to read ({document.get("status")}).',
                }
            )
    for stale in place.glob('*.md'):
        if stale.stem not in kept:
            stale.unlink()
    return sorted(manifest, key=lambda entry: entry['id'])


def build_plan(topic, purpose, scope, questions, sources, input_files=()) -> dict:
    """The plan harness-research takes. `questions` are {id, question, public_query, claim},
    a claim being {file, quote, start} in one of the item's own files."""
    return {
        'topic': topic,
        'purpose': purpose,
        'scope': scope,
        'input_files': sorted(input_files),
        'sources': sources,
        'items': [
            {
                'id': item['id'],
                'question': item['question'],
                'public_query': item.get('public_query'),
                'claim': item.get('claim'),
            }
            for item in questions
        ],
    }


def render_plan(plan: dict) -> str:
    """The plan, readable, for the plan gate."""
    lines = [
        '# Research plan',
        '',
        f'Topic: {plan["topic"]}',
        f'Purpose: {plan["purpose"]}; scope: {SCOPES.get(plan["scope"], plan["scope"])}.',
        '',
    ]
    if plan.get('sources'):
        lines += ['## Documents', '']
        for source in plan['sources']:
            gap = '' if source.get('file') else f' ({source["limits"]})'
            lines.append(f'- {source["title"]}: {source["origin"]}{gap}')
        lines.append('')
    lines += ['## Questions', '']
    for item in plan['items']:
        lines.append(f'- **{item["id"]}**: {item["question"]}')
        if item.get('public_query'):
            lines.append(f'  Search words: {item["public_query"]}')
        if item.get('claim'):
            lines.append(f'  Claim in {item["claim"]["file"]}: “{item["claim"]["quote"]}”')
    return '\n'.join(lines) + '\n'


def save_plan(folder: Path, plan: dict, allow_web: bool = False, research=None) -> dict:
    """Write research/plan.json and plan.md, then hand the plan to harness-research."""
    folder = Path(folder)
    text = json.dumps(plan, indent=2, ensure_ascii=False) + '\n'
    write_atomic(folder / PLAN, text.encode('utf-8'))
    write_atomic(folder / PLAN_MD, render_plan(plan).encode('utf-8'))
    return (research or tool()).plan(folder, folder / PLAN, allow_web=allow_web)


def read_record(folder: Path) -> dict | None:
    path = Path(folder) / RECORD
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def planned(folder: Path) -> set:
    """The keys of the supplied documents the current plan was made with."""
    saved = read_record(folder) or {}
    return {source['id'] for source in saved.get('sources') or [] if source.get('file')}


def record(folder: Path, run: str, item: str, finding: dict, research=None) -> dict:
    """Record one finding, offering it again while another save holds the lock."""
    research = research or tool()
    for left in range(BUSY_TRIES, 0, -1):
        try:
            return research.record(Path(folder), run, item, finding)
        except runtime.Refused as refusal:
            if not refusal.busy or left == 1:
                raise
            time.sleep(BUSY_WAIT)
    raise AssertionError('unreachable')


def status(folder: Path, research=None) -> dict:
    """Where the research stands, in the shape every studio shows."""
    folder = Path(folder)
    if read_record(folder) is None:
        return {
            'run': None,
            'status': 'not-started',
            'pending': [],
            'unresolved': [],
            'stale_items': [],
            'carried': [],
            'source_gaps': [],
            'completed': 0,
            'total': 0,
            'report': HARNESS_REPORT.as_posix(),
            'file': RECORD.as_posix(),
        }
    found = (research or tool()).status(folder)
    return {
        'run': found.get('run'),
        'status': found.get('status'),
        'pending': found.get('pending', []),
        'unresolved': found.get('unresolved', []),
        'stale_items': found.get('staleItems', []),
        'carried': found.get('carried', []),
        'source_gaps': found.get('sourceGaps', []),
        'completed': found.get('completed', 0),
        'total': found.get('total', 0),
        'report': HARNESS_REPORT.as_posix(),
        'file': RECORD.as_posix(),
    }


def publish_report(folder: Path) -> Path:
    """Copy harness-research's report to research/report.md, the copy the research gate
    shows and approves, so it does not change while it is being decided on."""
    folder = Path(folder)
    write_atomic(folder / REPORT, (folder / HARNESS_REPORT).read_bytes())
    return folder / REPORT
