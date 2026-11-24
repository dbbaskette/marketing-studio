"""Rebrand a Google file: Harness Brand's `rebrand run`, one background job at a time.

What a caller needs to know
---------------------------
    brand_rebrand.choices(place)                          # [{'id', 'name'}]: the brands there are
    brand_rebrand.source(link)                            # (address, 'slides' | 'docs'), or WorkspaceError
    brand_rebrand.check(found, place, link, brand)        # asks `rebrand status`; refuses in its words
    brand_rebrand.start(found, place, link, brand, review, reviewer)   # the job, in the background
    brand_rebrand.view(place)                             # {'job', 'brands'}: what the page shows
    brand_rebrand.stop(); brand_rebrand.clear()

- Only a Google Slides or Google Docs address is taken, and it reaches `rebrand run` as one
  argument of a command list, rebuilt from the file's id: never through a shell.
- `rebrand status --brand ID` is asked first. A brand Harness Brand cannot rebrand with is
  refused in Harness Brand's own words, with what to do.
- `rebrand run` makes a separate native copy in the person's Google Drive with this computer's
  Google sign-in (gcloud), and never edits the original. With `review` (off unless the person
  ticks it) Harness Brand sends the pages and their text to the assistant's provider for a
  read-only review: `--review --reviewer <the assistant in Shared settings>`.
- One rebrand at a time in this Marketing Studio. Its record is MARKETING_STUDIO_DATA's
  `brand-rebrand/job.json`; its run folder, given as `--run-dir`, is `brand-rebrand/runs/<id>/`,
  where Harness Brand writes report.md and result.json. A page reloaded meanwhile reads the
  record again; a job left running by a Marketing Studio that closed reads as stopped.
- The result gives the copy's link, the report, and Harness Brand's verdict in its own words
  (its status and next action). Without the review the copy awaits the person's own look at
  every page: it is never called accepted.
- Tests replace Harness Brand with a stand-in script; nothing here reaches Google itself.
"""
from __future__ import annotations

import json
import re
import secrets
import shlex
import threading
import time
from pathlib import Path

from studio_core import brand_data

from . import brand_skill, brand_store, state
from .errors import WorkspaceError

SCHEMA = 1
SECONDS = 3600                 # one run, review included
STATUS_SECONDS = 60
LINES = 100
REPORT_LIMIT = 200_000
LINK = re.compile(r'https://docs\.google\.com/(presentation|document)/(?:u/\d{1,2}/)?d/([A-Za-z0-9_-]{20,200})(?:[/?#][^\s]*)?')
COPY = re.compile(r'https://docs\.google\.com/(presentation|document)/[^\s"<>]{1,400}')
KINDS = {'presentation': 'slides', 'document': 'docs'}
WHAT = {'slides': 'Google Slides deck', 'docs': 'Google Doc'}
STAGES = {'exporting_source': 'Exporting the original from Google Drive; it is not changed',
          'applying_brand': 'Applying the brand to a copy on this computer',
          'reviewing_original_and_branded': 'The assistant is reviewing the pages',
          'creating_native_copy': 'Making the new copy in your Google Drive',
          'verifying_native_copy': 'Checking that the new copy kept every word',
          'checking_native_render': 'Checking how the new copy looks'}
VERDICTS = {'branded': 'branded', 'branded_with_exceptions': 'branded with exceptions',
            'review_incomplete': 'review not complete', 'incomplete': 'incomplete', 'error': 'did not finish'}
FINISHED = ('branded', 'branded_with_exceptions')
NOT_A_LINK = ('Paste the link of a Google Slides or Google Docs file. It starts with '
              'https://docs.google.com/presentation/d/ or https://docs.google.com/document/d/.')
LOCK = threading.RLock()
RUNNING: dict[str, tuple[threading.Thread, threading.Event]] = {}


def folder() -> Path:
    return state.data_root() / 'brand-rebrand'


def record_path() -> Path:
    return folder() / 'job.json'


# --- what is asked for -----------------------------------------------------------------

def source(link) -> tuple[str, str]:
    """(the file's address, rebuilt from its id, and 'slides' or 'docs')."""
    if not isinstance(link, str) or len(link) > 2000:
        raise WorkspaceError(NOT_A_LINK)
    found = LINK.fullmatch(link.strip())
    if not found:
        raise WorkspaceError(NOT_A_LINK)
    kind, ident = found.groups()
    return f'https://docs.google.com/{kind}/d/{ident}/edit', KINDS[kind]


def choices(place) -> list[dict]:
    """The brands in the brands folder, by id, with the name each pack gives itself."""
    shown = []
    for ident in brand_data.brands(place.folder):
        name = ident
        for kind in brand_data.PROFILES:
            told = brand_store.read_json(place.folder / ident / kind / 'brand.json', {})
            if isinstance(told, dict) and isinstance(told.get('name'), str) and told['name'].strip():
                name = told['name'].strip()[:80]
                break
        shown.append({'id': ident, 'name': name})
    return shown


def _reason(err: str, code: int) -> str:
    """What Harness Brand said was wrong, in its own sentences, without its generic last line."""
    lines = [line.strip() for line in err.splitlines() if line.strip()
             and not line.strip().startswith(('Usage:', '(node:', '(Use `node'))]
    own = [line for line in lines if not line.startswith('Rebranding command failed')]
    lines = own or lines
    return ' '.join(line.removeprefix('Brand assets: ') for line in lines) or f'It ended with exit code {code}.'


def check(found, place, link, brand) -> dict:
    """Ask Harness Brand whether it can rebrand with `brand`, before anything runs."""
    address, kind = source(link)
    named = {each['id']: each['name'] for each in choices(place)}
    if not isinstance(brand, str) or brand not in named:
        raise WorkspaceError('Choose a brand from this page.')
    code, out, err = brand_skill.run(found.command + ['rebrand', 'status', '--brand', brand],
                                     env=brand_skill.environment(place.folder), seconds=STATUS_SECONDS)
    if code != 0:
        reason = _reason(err, code)
        todo = '' if 'rebrand setup' in reason else (
            ' Set up rebranding for it with: ' + shlex.join(found.command + ['rebrand', 'setup', '--brand', brand])
            + ', then try again.')
        raise WorkspaceError(f'{named[brand]} cannot rebrand a file yet. {brand_skill.SKILL} says: {reason}{todo}')
    try:
        told = json.loads(out)
    except ValueError:
        told = None
    if not isinstance(told, dict):
        raise WorkspaceError(f'{brand_skill.SKILL} did not say whether {named[brand]} can rebrand a file. '
                             'Update Harness Brand, then try again.')
    return {'source': address, 'kind': kind, 'what': WHAT[kind], 'brand': brand, 'name': named[brand]}


# --- the record ------------------------------------------------------------------------

def _read() -> dict | None:
    job = brand_store.read_json(record_path())
    return job if isinstance(job, dict) and job.get('schema') == SCHEMA else None


def _keep(job: dict) -> None:
    brand_store.write_json(record_path(), job)


def _alive() -> bool:
    running = RUNNING.get('job')
    return bool(running and running[0].is_alive())


def _copy_link(value) -> str | None:
    """A link to the copy, only when it is a Google Slides or Docs address."""
    return value if isinstance(value, str) and COPY.fullmatch(value) else None


def _checkpoint(job: dict) -> str | None:
    """The copy's link Harness Brand saved in the run folder once it was made, if it was."""
    told = brand_store.read_json(Path(job['runDir']) / 'checkpoint.json', {})
    return _copy_link(told.get('url')) if isinstance(told, dict) else None


def view(place=None) -> dict:
    """What the page shows: the last job, and the brands a file can be rebranded with."""
    with LOCK:
        job = _read()
        if job and job.get('state') == 'running' and not _alive():
            copy = job.get('copy') or _checkpoint(job)
            job.update(state='stopped', ended=time.time(), copy=copy,
                       detail='Marketing Studio was closed while this ran, so it was stopped.'
                       + (' A copy had already been made in your Google Drive; check it before you use it.' if copy
                          else ' No copy had been made.'))
            _keep(job)
    shown = {'job': job}
    if place is not None:
        shown['brands'] = choices(place)
    return shown


# --- the job ---------------------------------------------------------------------------

def _outcome(job: dict, out: str, err: str) -> dict | None:
    """Harness Brand's result: result.json in the run folder, else what it printed."""
    told = brand_store.read_json(Path(job['runDir']) / 'result.json')
    if not isinstance(told, dict):
        for text in [out, *reversed(err.splitlines())]:
            try:
                told = json.loads(text)
            except ValueError:
                continue
            if isinstance(told, dict) and 'status' in told:
                break
            told = None
    if not isinstance(told, dict):
        return None
    status = str(told.get('status') or 'error')
    review = told.get('visual_review')
    report = Path(job['runDir']) / 'report.md'
    try:
        brand_store.no_links(report)
        with report.open(encoding='utf-8', errors='replace') as stream:
            text = stream.read(REPORT_LIMIT + 1)
    except (OSError, WorkspaceError):
        text = None
    return {'status': status, 'verdict': VERDICTS.get(status, status.replace('_', ' ')),
            'next': str(told['next_action'])[:1000] if told.get('next_action') else None,
            'url': _copy_link(told.get('url')), 'name': str(told.get('name') or '')[:300] or None,
            'error': str(told['error'])[:2000] if told.get('error') else None,
            'review': (str(review.get('status')) if isinstance(review, dict) else str(review)) if job['review'] and review else None,
            'report': None if text is None else text[:REPORT_LIMIT],
            'reportWhole': text is not None and len(text) <= REPORT_LIMIT,
            'reportPath': str(report) if text is not None else None}


def start(found, place, link, brand, review, reviewer) -> dict:
    """Check, then run `rebrand run` in the background as the one rebrand job."""
    if _alive():
        raise WorkspaceError('A rebrand is running. Wait for it to finish, or stop it, before starting another.')
    if reviewer not in ('claude', 'codex'):
        raise WorkspaceError('Choose Claude Code or Codex in Shared settings before asking for a review.')
    checked = check(found, place, link, brand)
    with LOCK:
        if _alive():
            raise WorkspaceError('A rebrand is running. Wait for it to finish, or stop it, before starting another.')
        ident = time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3)
        run_dir = folder() / 'runs' / ident   # made by Harness Brand, which wants a new folder
        job = {'schema': SCHEMA, 'id': ident, 'source': checked['source'], 'kind': checked['kind'],
               'brand': brand, 'brandName': checked['name'], 'review': review is True,
               'state': 'running', 'lines': ['Starting Harness Brand'], 'detail': '', 'copy': None,
               'result': None, 'started': time.time(), 'ended': None, 'runDir': str(run_dir)}
        (folder() / 'runs').mkdir(parents=True, exist_ok=True)
        _keep(job)
        command = found.command + ['rebrand', 'run', checked['source'], '--brand', brand, '--run-dir', str(run_dir)]
        if job['review']:
            command += ['--review', '--reviewer', reviewer]
        stop_event = threading.Event()
        thread = threading.Thread(target=_work, args=(job, command, brand_skill.environment(place.folder), stop_event),
                                  daemon=True, name='brand-rebrand')
        RUNNING['job'] = (thread, stop_event)
        thread.start()
    return view(place)


def _work(job: dict, command: list[str], env: dict, stop_event: threading.Event) -> None:
    def line(text):
        with LOCK:
            if not job['lines'] or job['lines'][-1] != text:
                job['lines'].append(text)
                del job['lines'][:-LINES]
                _keep(job)

    def heard(text):
        try:
            event = json.loads(text)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        if event.get('status') == 'progress' and isinstance(event.get('stage'), str):
            stage = event['stage']
            line(STAGES.get(stage, 'Working: ' + stage.replace('_', ' ')[:80]))
        elif event.get('status') == 'copy_created':
            with LOCK:
                job['copy'] = _copy_link(event.get('url')) or job['copy']
            line('The new copy is in your Google Drive')

    ending, detail, result = 'failed', 'It ended unexpectedly.', None
    try:
        try:
            code, out, err = brand_skill.run(command, env=env, seconds=SECONDS, stop=stop_event,
                                             each_error=heard, said=brand_skill.SKILL)
            result = _outcome(job, out, err)
            if result is None:
                ending, detail = 'failed', f'{brand_skill.SKILL} did not finish: {_reason(err, code)}'
            elif result['status'] in FINISHED and code == 0:
                ending, detail = 'done', ''
            else:
                ending, detail = 'failed', result['error'] or f'{brand_skill.SKILL} ended {result["verdict"]}.'
        except brand_skill.Stopped:
            ending, detail = 'stopped', 'It was stopped before it finished.'
        except WorkspaceError as failure:
            ending, detail = 'failed', str(failure)
        except Exception as failure:   # reported to the person, never lost
            ending, detail = 'failed', f'{type(failure).__name__}: {failure}'
    finally:
        with LOCK:
            job['copy'] = (result or {}).get('url') or job['copy'] or _checkpoint(job)
            if ending != 'done':
                detail += (' A copy had already been made in your Google Drive; check it before you use it.'
                           if job['copy'] else ' No copy was made in your Google Drive.')
            job.update(state=ending, detail=detail, result=result, ended=time.time())
            _keep(job)
            if RUNNING.get('job', (None,))[0] is threading.current_thread():
                del RUNNING['job']


def stop() -> None:
    running = RUNNING.get('job')
    if running and running[0].is_alive():
        running[1].set()


def wait(seconds: float = 30) -> None:
    """For tests: until the running job has ended."""
    running = RUNNING.get('job')
    if running:
        running[0].join(seconds)


def clear() -> None:
    """Put the last finished job away; its run folder and report stay on this computer."""
    with LOCK:
        if _alive():
            raise WorkspaceError('Stop the rebrand first.')
        record_path().unlink(missing_ok=True)
