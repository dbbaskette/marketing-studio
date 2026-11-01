"""Training Studio's guides and briefs marked ready, read for Add existing work to library:
never changed.

What is offered
---------------
Only a learner guide or a brief the person marked ready, while the version on disk is the
one marked: what Training Studio's Mark ready keeps in the library (`runner/library.py`).
A training is a folder in the remembered workspace marked by `.training-studio/session.json`.
Each guide or brief is added as Training material, Created here, as learners read it: its
coverage notes (`<!-- covers: … -->`, `<!-- findings: … -->`) are left out, as Training
Studio leaves them out, and it is titled as Training Studio titles it ("<training>: level
101 learner guide").

- "Marked ready" is read as Training Studio reads it (`workspace.person_statuses`): the
  version approved is the file on disk, nothing it was built from changed since (its
  blueprint, the research and, for a brief, the kind of brief), and on the desk the person
  marked it, not only the desk on its way through. A stage the training skips, or marked
  unavailable, offers nothing.
- Its key is the training's own, `training:<folder>-<part>.<material>`: the one
  `sources/library.json` records, else the one Training Studio makes from the training's
  folder and the moment its run started. A training with neither (worked on only in a
  conversation, with no run) is left out and said: Keep in library on its desk keeps it.
- Training Studio keeps no PDF of a guide or brief, so none is added.
- What Training Studio calls it travels with it, as `native`: the training's folder, the
  material's name and level, the hash of the version marked ready, and who marked it when.

Left out: drafts, materials changed or out of date since they were marked ready, a training
whose records Training Studio could not open, and decks, scenarios, blueprints and research.
No record is written, no lock is taken, no Git, network, Google, assistant or reader
program is used, and every read is bounded and refuses links.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from studio_core import training_migration as migration

from . import reading
from .store import LIMITS, TITLE, _plain

STATE = '.training-studio'
SESSION, RUN, STATUS = f'{STATE}/session.json', f'{STATE}/run.json', 'sources/library.json'
KEY = re.compile(r'training:[a-z0-9-]{1,120}-[a-f0-9]{12}')
LEVELS = ('101', '201', '301', '401')
KEPT = ('document', 'brief')                 # what Mark ready keeps in the library
SKIPPABLE = ('document', 'brief', 'deck', 'scenario', 'yoodli')
DESK_ACCEPTED = ('desk', 'review-policy')     # accepted on the desk's way, not by the person
LABELS = {'document': 'learner guide', 'brief': 'brief'}
RESEARCH_REPORT = '.harness-research/research-report.md'
RESEARCH_RECORD = '.harness-research/research.json'
RESEARCH_COPY = 'research-report.md'
RECORD = 1_000_000
ENTRIES = 2_000
# Coverage notes, as Training Studio's gdocs.strip_comments finds them.
COMMENT = re.compile(r'<!--\s*(?:covers|findings):.*?-->', re.DOTALL)
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
BLANK_LINE = re.compile(r'[ \t]*\r?\n')
NO_PDF = 'Training Studio keeps no PDF of it, so it is added as Markdown.'


def _named(name: str) -> bool:
    return not name.startswith('.') and name.isprintable() and len(name) <= 200


def _records(root: Path) -> tuple[dict, dict | None]:
    """(session, run) as Training Studio reads them (`migration_records`): the desk's
    effective records when the training was opened on the desk. Raises ValueError when
    Training Studio would refuse to open it."""
    if (root / migration.PENDING).exists() or (root / migration.PENDING).is_symlink():
        raise ValueError('opening it on the desk was interrupted')
    if not reading.unlinked(root, SESSION):
        raise ValueError('its records are linked')
    session_bytes = reading.bounded(root / SESSION, RECORD)
    if session_bytes is None:
        raise ValueError('its session record cannot be read')
    if not any((root / name).exists() or (root / name).is_symlink() for name in migration.WRITES):
        run_bytes = reading.bounded(root / RUN, RECORD)
        try:
            session = json.loads(session_bytes)
            run = json.loads(run_bytes) if run_bytes is not None else None
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ValueError('its records cannot be read') from None
        return session, run if isinstance(run, dict) else None
    run_bytes = reading.bounded(root / RUN, RECORD)
    origin, desk_session, desk_run = (reading.record(root / name, RECORD) for name in
                                      (migration.ORIGIN, migration.DESK_SESSION, migration.DESK_RUN))
    if run_bytes is None or None in (origin, desk_session, desk_run):
        raise ValueError('its desk records cannot be verified')
    session, run = migration.validated(origin, desk_session, desk_run, session_bytes, run_bytes,
                                       root.name)

    def read(name):
        return reading.bounded(root / name, migration.input_limit(name)) \
            if reading.unlinked(root, name) else None
    migration.shared_inputs(origin, read, session)
    return session, run


def _shaped(session) -> bool:
    """The parts of a session record this reads, in the shape Training Studio saves."""
    if not isinstance(session, dict) or session.get('schema') != 1:
        return False
    settings = session.get('settings')
    return (isinstance(session.get('title'), str) and isinstance(session.get('levels'), list)
            and all(level in LEVELS for level in session['levels'])
            and isinstance(session.get('artifacts'), dict)
            and all(isinstance(entry, dict) for entry in session['artifacts'].values())
            and isinstance(session.get('unavailable'), dict) and isinstance(settings, dict)
            and settings.get('brief_kind') in ('product', 'competitive')
            and isinstance(settings.get('stages'), list))


class _Training:
    """One training's statuses, as Training Studio's `workspace` computes them, for the
    materials Mark ready keeps and everything they are built from."""

    def __init__(self, root: Path, session: dict):
        self.root, self.session, self.known, self.hashes = root, session, {}, {}

    def spec(self, name: str) -> tuple[str, tuple, str, tuple]:
        """(file, upstream, stage, extras) of a material, as `workspace.artifact` says."""
        base, _, level = name.partition('@')
        folder = f'{level}/' if level else ''
        if base == 'intake':
            return 'intake.md', (), 'intake', ()
        if base == 'research-plan':
            return f'{STATE}/research-plan.json', ('intake',), 'research-plan', ()
        if base == 'research':
            return RESEARCH_REPORT, ('research-plan',), 'research', ()
        same = (lambda other: f'{other}@{level}') if level else (lambda other: other)
        if base == 'blueprint':
            return f'{folder}blueprint.md', ('intake', 'research'), 'blueprint', ()
        if base == 'document':
            return f'{folder}document.md', (same('blueprint'),), 'document', ()
        if base == 'brief':
            return (f"{folder}{self.session['settings']['brief_kind']}-brief.md",
                    (same('blueprint'), 'research'), 'brief', ('setting:brief_kind',))
        raise ValueError(name)

    def sha(self, relative: str) -> str | None:
        """A file's hash, read once per scan of this training."""
        if relative not in self.hashes:
            self.hashes[relative] = reading.digest(self.root / relative) \
                if reading.unlinked(self.root, relative) else None
        return self.hashes[relative]

    def record_file(self) -> str:
        return 'research/facts.json' if self.session.get('research_contract') else RESEARCH_RECORD

    def research_record(self):
        if self.session.get('research_contract'):
            from studio_core.research_contract import read_bundle
            try:
                value, _ = read_bundle(self.root / 'research')
                return value
            except (OSError, ValueError, KeyError, TypeError):
                return None
        value = reading.record(self.root / RESEARCH_RECORD, 64_000_000)
        recognised = (isinstance(value, dict) and value.get('schema') == 1
                      and value.get('owner') == 'harness-research'
                      and isinstance(value.get('items'), list)
                      and isinstance(value.get('results'), dict))
        return value if recognised else None

    def research_fingerprint(self) -> str | None:
        report = self.sha(RESEARCH_REPORT)
        if report is None:
            return None
        if self.session.get('research_contract') and self.research_record() is None:
            return hashlib.sha256((report + ':research-changed').encode()).hexdigest()
        parts = [report, self.sha(self.record_file()), self.sha(RESEARCH_COPY)]
        return hashlib.sha256('\n'.join(part or '-' for part in parts).encode()).hexdigest()

    def research_intact(self) -> bool:
        bundle = self.session.get('research')
        if self.session.get('research_contract') and self.research_record() is None:
            return False
        return bool(isinstance(bundle, dict)
                    and self.sha(self.record_file()) == bundle.get('record_sha256')
                    and self.sha(RESEARCH_COPY) == bundle.get('report_sha256'))

    def inputs(self, name: str) -> dict:
        _, upstream, _, extras = self.spec(name)
        found = {}
        for one in upstream:
            found[one] = self.research_fingerprint() if one == 'research' else self.sha(self.spec(one)[0])
        for extra in extras:
            found[extra] = self.session['settings'][extra.partition(':')[2]]
        return found

    def status(self, name: str) -> str:
        """`workspace._status`, with each upstream's status worked out first."""
        if name in self.known:
            return self.known[name]
        file, upstream, stage, _ = self.spec(name)
        for one in upstream:
            self.status(one)
        if stage in SKIPPABLE and stage not in self.session['settings']['stages']:
            found = 'skipped'
        elif stage in self.session['unavailable']:
            found = 'unavailable'
        elif (current := self.sha(file)) is None:
            found = 'not-started'
        elif (entry := self.session['artifacts'].get(name)) is None:
            found = 'draft'
        elif any(self.known[one] == 'stale' for one in upstream) \
                or entry.get('built_from') != self.inputs(name):
            found = 'stale'
        else:
            approved = entry.get('approved')
            found = 'approved' if (isinstance(approved, dict) and approved.get('sha256') == current
                                   and approved.get('inputs') == entry.get('built_from')
                                   and (name != 'research' or self.research_intact())) else 'draft'
        self.known[name] = found
        return found

    def marked_ready(self, name: str) -> dict | None:
        """The approval of a guide or brief the person marked ready, while its file is that
        version (`workspace.person_statuses`); else None."""
        if self.status(name) != 'approved':
            return None
        approved = self.session['artifacts'][name]['approved']
        if self.session.get('flow') == 'desk' and approved.get('by') in DESK_ACCEPTED \
                and (self.session.get('desk_ready') or {}).get(name) != approved.get('sha256'):
            return None
        return approved


def _key(root: Path, run: dict | None) -> str | None:
    """The training's library key (`library._key`): the one recorded for it, else the one
    made from its folder and the moment its run started; None when it has neither."""
    held = (reading.record(root / STATUS, 100_000) or {}).get('key')
    if isinstance(held, str) and KEY.fullmatch(held):
        return held
    plain = re.sub(r'[^a-z0-9-]+', '-', root.name.lower()).strip('-')[:120] or 'training'
    started = (run or {}).get('started_at')
    if isinstance(started, str) and started:
        return f"training:{plain}-{hashlib.sha256(f'{root.name}{chr(0)}{started}'.encode()).hexdigest()[:12]}"
    return None


def readable(text: str) -> str:
    """The text as learners read it: Training Studio's `gdocs.strip_comments`, without its
    anchors. A coverage note inside a fenced code block stays."""
    fences, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line)
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0]:
                fences.append((fence[1], offset + len(line)))
                fence = None
        elif marker:
            fence = (marker.group(1)[0], offset)
        offset += len(line)
    if fence is not None:
        fences.append((fence[1], len(text)))
    kept, position = '', 0
    for match in COMMENT.finditer(text):
        if any(start <= match.start() < end for start, end in fences):
            continue
        line_start = text.rfind('\n', 0, match.start()) + 1
        newline = text.find('\n', match.end())
        line_end = len(text) if newline < 0 else newline + 1
        own_line = not (text[line_start:match.start()] + text[match.end():line_end]).strip()
        if own_line:
            kept += text[position:line_start]
            position = line_end
            follows = BLANK_LINE.match(text, position)
            if follows and (not kept.strip() or kept.endswith(('\n\n', '\n\r\n'))):
                position = follows.end()
        else:
            kept += text[position:match.start()].rstrip(' \t')
            position = match.end()
    return kept + text[position:]


def _material(training: _Training, key: str, name: str, content: bool
              ) -> tuple[dict | None, str | None]:
    root, session = training.root, training.session
    base, _, level = name.partition('@')
    file = training.spec(name)[0]
    approved = training.marked_ready(name)
    # Titled exactly as Mark ready titles it, so the library sees the same title.
    title = session.get('title') or root.name
    words = f'level {level} {LABELS[base]}' if level else LABELS[base]
    shown = _plain(f'{title}: {words}', TITLE) or 'Untitled'
    if approved is None:
        return None, None
    data = reading.bounded(root / file, LIMITS['text']) if reading.unlinked(root, file) else None
    if data is None or reading.sha(data) != approved.get('sha256'):
        return None, f'“{shown[:120]}” was left out: its file changed while it was read.'
    try:
        # Read as Training Studio reads it: universal newlines, then without coverage notes.
        text = readable(data.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'))
    except UnicodeDecodeError:
        return None, f'“{shown[:120]}” was left out: its text could not be read.'
    if not text.strip():
        return None, f'“{shown[:120]}” was left out: it has no text to add.'
    digest = approved['sha256']
    native = {'studio': 'training', 'record': 'marked-ready', 'training': root.name,
              'material': name, 'kind': base, 'level': level or None, 'sha256': digest,
              'brief_kind': session['settings']['brief_kind'] if base == 'brief' else None,
              'marked_by': approved.get('by') if isinstance(approved.get('by'), str) else None,
              'marked_at': approved.get('at') if isinstance(approved.get('at'), str) else None}
    return {'key': f"{key}.{base}" + (f'-{level}' if level else ''), 'studio': 'training',
            'kind': 'training', 'origin': 'created', 'title': shown, 'author': None,
            'text': text if content else None, 'original': None,
            'markdown_sha': reading.sha(text.encode('utf-8')), 'original_sha': None,
            'pdf': None, 'pdf_sha': None, 'pdf_note': None, 'filename': None,
            'project': {'id': root.name, 'title': title, 'revision': digest[:12]},
            'native': native, 'gaps': [NO_PDF], 'note': 'Marked ready',
            'folder': root, 'material': name}, None


def _training(root: Path, content: bool) -> tuple[list[dict], list[str], int]:
    """(Its guides and briefs marked ready, what was left out and why, how many guides and
    briefs are not marked ready)."""
    try:
        session, run = _records(root)
    except (ValueError, KeyError, TypeError, AttributeError) as refusal:
        return [], [f'“{root.name}” was left out: {str(refusal).rstrip(".")}. Open it in '
                    'Training Studio first.'], 0
    if not _shaped(session):
        return [], [f'“{root.name}” was left out: its record is not in a shape Training '
                    'Studio saves.'], 0
    training = _Training(root, session)
    names = [base if level is None else f'{base}@{level}'
             for level in (session['levels'] or [None]) for base in KEPT]
    found, gaps, waiting = [], [], 0
    ready = [name for name in names if training.marked_ready(name) is not None]
    waiting = sum(1 for name in names if name not in ready
                  and training.status(name) not in ('skipped', 'unavailable', 'not-started'))
    if not ready:
        return [], [], waiting
    key = _key(root, run)
    title = _plain(session.get('title'), TITLE) or root.name
    if key is None:   # a random key here would be a second document when Mark ready keeps it
        return [], [f'“{title[:120]}” was left out: Training Studio has no library key for it. '
                    'Choose Keep in library on each Ready guide or brief on its desk.'], waiting
    for name in ready:
        one, why = _material(training, key, name, content)
        if one:
            found.append(one)
        elif why:
            gaps.append(why)
    return found, gaps, waiting


def _checked(root: Path, content: bool) -> tuple[list[dict], list[str], int]:
    try:
        return _training(root, content)
    except (TypeError, ValueError, AttributeError, KeyError, OSError, RecursionError):
        return [], [f'“{root.name}” was left out: its record is not in a shape Training '
                    'Studio saves.'], 0


def load(root, candidate: dict) -> dict:
    """The candidate read again with its text, refused when it is no longer what the
    preview read."""
    found, _, _ = _checked(candidate['folder'], True)
    one = next((one for one in found if one['key'] == candidate['key']), None)
    if not one or any(one[name] != candidate[name] for name in ('title', 'markdown_sha')):
        raise ValueError(f'“{candidate["title"][:120]}” changed in Training Studio after the '
                         'preview.')
    return one


def scan(root, content: bool = False) -> dict:
    """{'candidates', 'gaps', 'more', 'readable'}: the workspace's guides and briefs marked
    ready, with the hashes of their Markdown as read now, and what was left out and why."""
    root = Path(root)
    folders, more = reading.folders(root, _named, ENTRIES)
    candidates, gaps, waiting = [], [], 0
    for folder in folders:
        if not (folder / SESSION).is_file():
            continue
        found, why, left = _checked(folder, content)
        candidates.extend(found)
        gaps.extend(why)
        waiting += left
    if waiting:
        gaps.append(f'{waiting} learner guide{"" if waiting == 1 else "s"} or brief'
                    f'{"" if waiting == 1 else "s"} not marked ready '
                    f'{"is" if waiting == 1 else "are"} not offered.')
    if more:
        gaps.append(f'Only the first {ENTRIES} training folders were looked at.')
    return {'candidates': candidates, 'gaps': gaps, 'more': more, 'readable': True}
