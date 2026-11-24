"""Slow imports and Google calls as background jobs, so a page request never waits on them.

What a caller needs to know
---------------------------
    import_jobs.ROUTES                     # the page's POST routes that run as a job
    import_jobs.start(root, route, data)   # {'job': {...}, 'background': True}, at once
    import_jobs.view(root, ident)          # the job as the page polls it, or None
    import_jobs.stop(root, ident)          # Stop, where stopping is safe

- The page posts the same request as before. Blog Studio's page server answers at once with
  a job, saved with the other tool jobs (`.blog-runs/tools/<id>.json`, tool_jobs), and runs
  the very same route on a thread of its own: `management.dispatch`, with every lock, check,
  Team Hub step and Google read it always had. Its answer, or its refusal with the same HTTP
  status and words, is kept in the job, so what the page is given is what it was given when
  it waited for the request. The request itself (files, links) is never written to disk.
- The page polls `GET /api/tool-job?job=<id>` (read without the workspace lock, so it
  answers while the job holds it) and shows what the job is doing, with Stop where stopping
  is safe: a check or a read that saves nothing is dropped when it ends, and adding links to
  the library stops after the batch being fetched, keeping every link already added (adding
  again with the same operation continues). Sending to Google, starting a blog from a Doc
  and bringing a Doc's text to the desk change things as they go, so they have no Stop.
- Adding links to the library fetches one batch per call, as before; the job calls again
  until every link has been tried, in place of the page's own loop.
- Jobs run one at a time, in the order they were asked for, beside the writing worker.
  A job that was working when Blog Studio stopped is said to have been interrupted
  (tool_jobs.recover); run it again from the page.
"""

from __future__ import annotations

import secrets
import threading

import studio
import tool_jobs

KIND = 'import'
# route: (what the page says while it runs, whether Stop is safe)
ROUTES = {
    'library-add-preview': ('Checking the items', True),
    'library-add': ('Adding to the library', True),
    'google-preview': ('Reading the Google Doc', True),
    'google-start': ('Starting from the Google Doc', False),
    'desk-google-plan': ('Checking what would be sent to the Google Doc', True),
    'desk-google-compare': ('Reading the Google Doc’s accepted text', True),
    'desk-google-send': ('Sending to the Google Doc', False),
    'editor-google-send': ('Sending feedback to the Google Doc', False),
    'desk-google-take': ('Bringing the Google Doc’s text to the desk', False),
    # A folder or a spreadsheet for the source picker (management.files_intake): read, then
    # saved as files for the blog, in one go.
    'files-intake': ('Reading the folder', False),
}
TURNS = 40  # Calls one library add may make: 40 batches of links, as the page made before.
STOPPED = 'Stopped. Nothing was changed.'
_ONE = threading.Lock()  # One job runs at a time; the next waits its turn.
_HELD = threading.Lock()  # Guards reading and writing a job's file between threads.
_RUNNING = set()  # The ids of jobs with a thread in this process.


def running(ident):
    return ident in _RUNNING


def _save(root, job):
    with _HELD:
        tool_jobs.write(root, job)


def _read(root, ident):
    with _HELD:
        return tool_jobs.read(root, ident)


def _update(root, ident, **changes):
    """Change a job as saved, unless it already ended. Returns it as saved now."""
    with _HELD:
        job = tool_jobs.read(root, ident)
        if job.get('status') == 'working':
            job.update(changes)
            tool_jobs.write(root, job)
        return job


def public(job):
    """The job as the page reads it. Its request is never part of it."""
    return {
        'id': job['id'],
        'kind': KIND,
        'route': job['route'],
        'label': job['label'],
        'status': job['status'],
        'progress': job.get('progress') or '',
        'stoppable': bool(job.get('stoppable')) and job['status'] == 'working',
        'stopping': bool(job.get('stopping')),
        'created_at': job.get('created_at'),
        'started_at': job.get('started_at'),
        'finished_at': job.get('finished_at'),
        'result': job.get('result'),
        'error': job.get('error') or '',
        'error_status': job.get('error_status'),
        'error_reply': job.get('error_reply'),
    }


def start(root, route, data, runner=None):
    """Save the job and start it on its own thread. `runner(root, route, data)` is the route
    itself (management.dispatch); a test may pass its own."""
    if route not in ROUTES:
        raise ValueError('Unknown management action.')
    if not isinstance(data, dict):
        raise ValueError('Supply a JSON object.')
    label, stoppable = ROUTES[route]
    article = data.get('id') if isinstance(data.get('id'), str) else None
    job = {
        'id': secrets.token_hex(16),
        'kind': KIND,
        'route': route,
        'label': label,
        'status': 'working',
        'stoppable': stoppable,
        'progress': label + '…',
        'created_at': studio.now(),
        'started_at': None,
        'finished_at': None,
        'result': None,
        'error': '',
        # tool_jobs reads these of every job it lists or recovers.
        'attempts': 1,
        'metadata': {'article': article, 'import': route},
    }
    _save(root, job)
    if runner is None:
        import management

        runner = management.dispatch
    thread = threading.Thread(
        target=_run, args=(root, job['id'], route, data, runner), daemon=True,
        name='blog-studio-import-' + job['id'][:8],
    )
    _RUNNING.add(job['id'])
    thread.start()
    return {'job': public(job), 'background': True}


def _run(root, ident, route, data, runner):
    if not _ONE.acquire(blocking=False):
        try:
            _update(root, ident, progress='Waiting for the import before it to finish…')
        except (ValueError, OSError):
            pass  # Said again once it starts.
        _ONE.acquire()
    try:
        job = _update(root, ident, started_at=studio.now(), progress=ROUTES[route][0] + '…')
        if job['status'] != 'working':
            return  # Stopped while it waited: it never ran.
        if route == 'library-add':
            result = _library_add(root, ident, data, runner)
        else:
            result = runner(root, route, data)
        with _HELD:
            job = tool_jobs.read(root, ident)
            if job['status'] != 'working':
                return  # Stopped: a check or a read that saves nothing is dropped.
            job.update(status='ready', result=result, finished_at=studio.now(), progress='')
            tool_jobs.write(root, job)
    except Exception as exc:  # Kept in the job, said as the request would have said it.
        import management

        status, reply = management.failure(exc, True)
        if status == 500:
            management.note_unexpected(exc)
        with _HELD:
            try:
                job = tool_jobs.read(root, ident)
            except (ValueError, OSError):
                return
            if job['status'] == 'working':
                job.update(
                    status='failed',
                    error=reply.get('error') or 'The import could not be completed.',
                    error_status=status,
                    error_reply=reply,
                    finished_at=studio.now(),
                    progress='',
                )
                tool_jobs.write(root, job)
    finally:
        _ONE.release()
        _RUNNING.discard(ident)


def _added(result):
    items = len(result.get('items') or [])
    return items - (result.get('remaining') or 0), items


def _library_add(root, ident, data, runner):
    """Add every item, one batch of links per call, until each link has been tried or the
    person stops it. The first call carries `retry`, as the page's first call did."""
    result = runner(root, 'library-add', data)
    again = {key: value for key, value in data.items() if key != 'retry'}
    for _ in range(TURNS):
        if not result.get('remaining'):
            break
        done, items = _added(result)
        job = _update(root, ident, progress=f'Added {done} of {items}…')
        if job.get('stopping'):
            return {**result, 'stopped': True}
        before = result.get('remaining')
        result = runner(root, 'library-add', again)
        if result.get('remaining') == before:
            break  # Nothing moved: say what is left, as the page did after its turns.
    return result


def stop(root, ident):
    """Stop a job where it is safe: at once for a check or a read that saves nothing (its
    answer is dropped when it comes), after the batch under way for adding links. Refused for
    a job that changes things as it goes."""
    with _HELD:
        job = tool_jobs.read(root, ident)
        if job.get('kind') != KIND:
            raise ValueError('Choose an import that is running.')
        if job['status'] != 'working':
            return public(job)
        if not job.get('stoppable'):
            raise ValueError(
                job['label'] + ' changes things as it goes, so it cannot be stopped part way. '
                'It ends by itself.'
            )
        if job['route'] == 'library-add':
            job.update(stopping=True, progress='Stopping after the links being fetched now…')
        else:
            job.update(
                status='cancelled', error=STOPPED, finished_at=studio.now(), progress=''
            )
        tool_jobs.write(root, job)
        return public(job)


def view(root, ident):
    """The job as the page polls it, or None when it is not an import (another tool job)."""
    try:
        job = _read(root, ident)
    except (ValueError, OSError):
        return None
    if job.get('kind') != KIND:
        return None
    return public(job)
