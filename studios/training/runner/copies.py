"""The copies a training asked for: a Google Doc or a Word file of a guide, a brief or a
Yoodli scenario.

What a caller needs to know
---------------------------
    copies.wanted(root, problems=None)       # every copy the training asks for, as shown
    made, problems = copies.make(root, google=None, word=None)
    found = copies.check(root, google=None)  # each Doc, as Google has it now, when asked
    entry = copies.remake(root, name, google=None)   # a Doc Google cannot find, made anew

- An entry is {'artifact', 'label', 'kind', 'state', 'link', 'problem'}. `kind` is 'google'
  or 'word'. `state` is 'made', 'out-of-date' or 'not-made'. `link` is the Doc's address,
  or the Word file's path from the training's folder, once there is one. `label` is the
  artifact's name as a person reads it.
- What is wanted is what the core says: `gdocs.copy_states` for Google Docs and
  `workspace.export_states` for Word. This module adds no rule of its own about which
  artifacts get a copy.
- `make` makes every wanted copy of an approved artifact that is not current, and leaves
  the rest alone. It never raises for a copy that cannot be made. A Word copy that cannot
  be made is recorded through the core as unavailable, with the reason. A Google Doc that
  cannot be made has nowhere in the core to say why, so `make` returns `problems`:
  {artifact: sentence}. The caller keeps them and passes them back to `wanted`.
- `google` is a `gdocs.Transport`; left out, it is `gdocs.GcloudTransport()`, which uses
  the Google access this computer already has. No credential is asked for, stored or
  printed here. `word` is a callable (source: Path, target: Path) -> None; left out, it
  runs pandoc through the core's `workspace.pandoc`, with its reasons worded for a person,
  and a computer without pandoc gets a sentence saying so.
- Nothing is approved, skipped or decided here.

`made` holds the entries of the copies this call made, as `wanted` would now give them.
A copy of something that is not approved yet is listed by `wanted` as not made, with no
problem: it is made when its file is approved.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import gdocs
import workspace
from workspace import WorkspaceError

STATES = {'current': 'made', 'outdated': 'out-of-date', 'missing': 'not-made',
          'unavailable': 'not-made'}
AGAIN = 'try the copies again'
NOT_SET_UP = ('Google access is not set up on this computer: the gcloud command was not '
              'found. Install the Google Cloud CLI, run `gcloud auth login '
              f'--enable-gdrive-access` in a terminal, then {AGAIN}.')
NO_PANDOC = ('Word copies are made with pandoc, which is not on this computer. Install it, '
             f'then {AGAIN}.')
PANDOC_SAYS = {   # the core's reasons for no Word copy, said for a person
    'missing': NO_PANDOC,
    'slow': ('pandoc did not finish in {seconds} seconds, so the Word copy was not made. '
             f'{workspace.sentence(AGAIN)}.'),
    'start': ('pandoc could not be started ({why}), so the Word copy was not made. '
              f'{workspace.sentence(AGAIN)}.'),
    'said': f'pandoc could not make the Word copy ({{said}}). Put that right, then {AGAIN}.'}
# What the core says to an assistant, which has commands to run, said here for a person.
MISSING_DOC = ('Google could not find the Doc. It may have been deleted, or the signed-in '
               'account cannot open it. Make a new Google Doc from here.')
CHANGED_THERE = ('Someone has changed the Google Doc since it was last sent, so it was left '
                 f'as it is. Bring the Doc’s changes in from here, then {AGAIN}.')
REWORDED = (
    ('changed since the last sync', CHANGED_THERE),
    ('could not find the Doc', MISSING_DOC),
)


# --- what is wanted ------------------------------------------------------------------------

def wanted(root: Path, problems: dict | None = None) -> list[dict]:
    """Every copy the training asks for, in the order of what each is a copy of."""
    root = Path(root)
    session = workspace.load(root)
    docs, files = gdocs.copy_states(root, session), workspace.export_states(root, session)
    links = gdocs.read_links(root)['docs'] if docs else {}
    listed = []
    for name in workspace.artifact_names(root, session):
        if name in docs:
            entry = _entry(name, 'google', STATES[docs[name]],
                           links.get(name, {}).get('url'), (problems or {}).get(name))
            if links.get(name, {}).get('conflict'):
                entry['conflict'] = True
            listed.append(entry)
        if name in files:
            made = session['exports'].get(name) or {}
            state = STATES[files[name]]
            listed.append(_entry(name, 'word', state,
                                 None if state == 'not-made' else made.get('file'),
                                 made.get('unavailable')))
    return listed


def _entry(name: str, kind: str, state: str, link, problem) -> dict:
    return {'artifact': name, 'label': workspace.label(name), 'kind': kind, 'state': state,
            'link': link if isinstance(link, str) else None,
            'problem': problem if state != 'made' and isinstance(problem, str) else None}


# --- making them ---------------------------------------------------------------------------

def make(root: Path, google=None, word=None) -> tuple[list[dict], dict]:
    """Make every wanted copy of something approved that is not current. Returns the
    copies made and, for each Google Doc that could not be, why."""
    root = Path(root).resolve()
    approved = {name for name, status
                in workspace.statuses(root, workspace.load(root)).items()
                if status == 'approved'}
    tried, problems = [], {}
    for entry in wanted(root):
        name = entry['artifact']
        if entry['state'] == 'made' or name not in approved:
            continue
        tried.append((name, entry['kind']))
        if entry['kind'] == 'word':
            _word(root, name, word or pandoc)
        elif google is None and shutil.which('gcloud') is None:
            problems[name] = NOT_SET_UP
        else:
            google = google or gdocs.GcloudTransport()
            problem = _google(root, name, google)
            if problem:
                problems[name] = problem
    now = {(entry['artifact'], entry['kind']): entry for entry in wanted(root, problems)}
    return [now[key] for key in tried if key in now and now[key]['state'] == 'made'], problems


def _google(root: Path, name: str, transport) -> str | None:
    """Make one Google Doc, or bring it up to date. Returns why it could not be, else
    None. A Doc someone has edited is never written over."""
    try:
        gdocs.push(root, name, transport)
    except WorkspaceError as refusal:
        said = str(refusal)
        return next((ours for theirs, ours in REWORDED if theirs in said), said)
    except Exception as failure:  # a copy that cannot be made never stops a run
        # Only what kind of failure it was: its own words could hold anything.
        return ('Google Drive did not answer as it should have '
                f'({type(failure).__name__}), so the Google Doc was not made. Wait a '
                f'little, then {AGAIN}.')
    return None


def _word(root: Path, name: str, convert) -> None:
    """Make one Word copy beside its file and record it through the core, or record
    through the core why there is none."""
    spec = workspace.artifact(root, workspace.load(root), name)
    relative = Path(spec['file']).with_suffix('.docx').as_posix()
    reason = None
    try:
        source, target = workspace.managed(root, spec['file']), workspace.managed(root, relative)
        # Made outside the training first: a conversion that fails leaves nothing half
        # made where a copy belongs.
        with tempfile.TemporaryDirectory() as scratch:
            draft = Path(scratch) / target.name
            convert(source, draft)
            if not draft.is_file() or not draft.stat().st_size:
                raise WorkspaceError('The converter left no Word file. '
                                     f'{workspace.sentence(AGAIN)}.')
            workspace.write_atomic(target, draft.read_bytes())
    except WorkspaceError as refusal:
        reason = str(refusal)
    except Exception as failure:  # a copy that cannot be made never stops a run
        reason = (f'The Word copy could not be made ({type(failure).__name__}). '
                  f'{workspace.sentence(AGAIN)}.')
    try:
        workspace.export(root, name, **({'unavailable': reason} if reason
                                        else {'file': relative}))
    except WorkspaceError:
        pass  # the record could not be written now; the copy is tried again next time


def pandoc(source: Path, target: Path) -> None:
    """Convert a Markdown file to Word through the core's pandoc, kept to the one
    file it is given. Refuses with a sentence for a person when pandoc is not on this
    computer, does not finish or makes no copy."""
    workspace.pandoc(source, target, PANDOC_SAYS)


def remake(root: Path, name: str, google=None) -> dict:
    """Make a new Google Doc of an approved file whose Doc Google cannot find: the old link
    is removed, and the Doc is made again from the file as it stands. The old Doc, if there
    is one, is left as it is. Returns the copy as `wanted` now gives it."""
    root = Path(root).resolve()
    if name not in gdocs.read_links(root)['docs']:
        raise WorkspaceError('That copy has no Google Doc to make again.')
    gdocs.unlink(root, name)
    google = google or gdocs.GcloudTransport()
    problem = _google(root, name, google)
    if problem:
        raise WorkspaceError(problem)
    return next(entry for entry in wanted(root) if entry['artifact'] == name
                and entry['kind'] == 'google')


# --- what Google has --------------------------------------------------------------------

def check(root: Path, google=None) -> dict[str, str]:
    """For each linked Google Doc, whether it was changed in Google since it was last sent:
    'remote changed', 'both changed' (here too), else 'made'; 'unchecked' for one Google
    could not be asked about. Google is asked only here, when the person asks."""
    root = Path(root)
    google = google or gdocs.GcloudTransport()
    session, found = workspace.load(root), {}
    for name, entry in sorted(gdocs.read_links(root)['docs'].items()):
        try:
            file = workspace.artifact(root, session, name)['file']
            known = entry.get('remote_sha256')
            moved = bool(known) and gdocs.digest(
                gdocs.canonical(google.export(entry['file_id']))) != known
        except WorkspaceError:
            found[name] = 'unchecked'
            continue
        changed = workspace.sha256_file(root / file) != entry.get('local_sha256')
        found[name] = gdocs.STATES[changed, moved] if moved else 'made'
    return found


PULLED = ("The Doc's changes are in. Review {label} again; what is built from it is made "
          "again after you approve.")
BOTH = ("{label} was changed here and in its Google Doc. The Doc's text is kept beside it; "
        "nothing was replaced. Choose which to keep.")
KEPT_OURS = "This version is sent to the Google Doc, replacing what was changed there."
UNPLACED = ("These headings were brought in but not placed in the guide's sections, because "
            "their hidden note was removed in the Doc: {headings}. Put them back under a "
            "heading, or ask for changes.")


def worded(said: str, label: str) -> str:
    """A sentence about a copy, with its label in it, that never starts lower-case."""
    text = said.format(label=label)
    return text[:1].upper() + text[1:]


def pull(root: Path, name: str, google=None, choose=None) -> dict:
    """Bring in an edit, preserving both sides of a conflict until an explicit choice."""
    if choose not in (None, 'theirs', 'ours'):
        raise WorkspaceError('Choose the Doc’s version or this version.')
    google = google or gdocs.GcloudTransport()
    _, spec, path = gdocs.target(root, name)
    entry = gdocs.linked(gdocs.read_links(root), name)
    beside = Path(spec['file']).with_suffix('.remote.md').as_posix()
    remote_file = workspace.managed(root, beside)
    if choose:
        conflict = entry.get('conflict') or {}
        remote = gdocs.canonical(google.export(entry['file_id']))
        if (not conflict or workspace.sha256_file(path) != conflict.get('local')
                or workspace.sha256_file(remote_file) != conflict.get('beside')
                or gdocs.digest(remote) != conflict.get('remote')):
            raise WorkspaceError('One version changed again. Bring the Doc’s changes in again before choosing.')
        if choose == 'ours':
            gdocs.push(root, name, google, force=True)
            result = 'kept'
        else:
            text = remote_file.read_text(encoding='utf-8')
            workspace.save(root, name, source=remote_file, edit=True)
            gdocs.settle(root, name, entry, text, remote)
            result = 'pulled'
        with workspace.locked(root):
            links = gdocs.read_links(root)
            links['docs'][name].pop('conflict', None)
            gdocs.write_links(root, links)
        return {'result': result, 'beside': None, 'unplaced': []}
    try:
        outcome = gdocs.pull(root, name, google)
    except WorkspaceError as refusal:
        if 'both changed since the last sync' not in str(refusal):
            raise
        remote = gdocs.canonical(google.export(entry['file_id']))
        text, _ = gdocs.restore_comments(remote, entry['anchors'])
        # The second read must still be the version saved beside the local file.
        if remote_file.read_text(encoding='utf-8') != text:
            raise WorkspaceError('The Doc changed again. Bring its changes in again before choosing.')
        with workspace.locked(root):
            links = gdocs.read_links(root)
            links['docs'][name]['conflict'] = {
                'local': workspace.sha256_file(path), 'remote': gdocs.digest(remote),
                'beside': workspace.sha256_file(remote_file)}
            gdocs.write_links(root, links)
        return {'result': 'both-changed', 'beside': beside, 'unplaced': []}
    # Headings whose hidden note was taken out in the Doc come in, but out of their sections.
    return {'result': 'pulled' if outcome['result'] == 'pulled' else 'nothing', 'beside': None,
            'unplaced': [item['heading'] for item in outcome.get('unplaced') or ()]}
