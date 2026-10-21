"""Delete a blog from the page, keep it for thirty days, and bring it back.

A deletion stops whatever is running for the blog, takes it out of every list and removes
what only this computer kept for it: its run state, diagnostics, receipts, upload ledgers
and tool jobs. What happens to the blog's own folder depends on where the blog lives:

- In a local workspace the folder moves under `.blog-runs/deleted/<id>/blog`.
- In a team workspace it is taken out of the shared branch in one commit that says who
  deleted it and when; the commit is remembered so the files can be checked out again.
- With a Team Hub selected the shared revisions stay in the Hub, so teammates can still
  open it there; only this computer's binding to it is dropped.

A record under `.blog-runs/deleted/<id>.json` drives the "Recently deleted" list. Restore
puts the folder, the binding and a stopped run state back; nothing starts by itself. Records
older than KEEP_DAYS, and the files they kept, are let go of when the list is read.
"""

from datetime import datetime, timedelta, timezone
import shutil
import time

import studio
import blog_runner

KEEP_DAYS = 30
STOP_WAIT = 30  # seconds a working job may take to end before nothing is deleted
MISTITLED = (
    'That is not the title of this blog. Nothing was deleted: open the blog again before '
    'you delete it.'
)
NOT_ENDED = (
    'It was stopped, but its worker has not ended yet, so it was not deleted. Try deleting '
    'it again in a moment.'
)
HUB_STAYS = 'It stays shared in your Team Hub; teammates can still open it from there.'
TEAM_WAITS = (
    'It is gone from this computer. Your team sees it gone the next time you choose Share now.'
)


def folder(root):
    return studio.inside(root, '.blog-runs', 'deleted')


def record_path(root, ident):
    return folder(root) / (studio.identifier(ident) + '.json')


def versions(root, ident):
    """The blog, and every version token a page may have shown for it."""
    directory, record = studio.item(root, 'articles', ident)
    known = {studio.digest((directory / 'session.json').read_bytes())}
    if studio.inside(directory, blog_runner.STATE).is_file():
        try:
            known.add(blog_runner.survey(root, ident)['expected'])
        except ValueError:
            pass  # A run this runtime cannot read can still be deleted by its detail version.
    return directory, record, known


def check(root, data):
    if set(data) != {'id', 'expected', 'title'}:
        raise ValueError('Unknown delete field.')
    if not isinstance(data['id'], str):
        raise ValueError('Choose a saved blog.')
    directory, record, known = versions(root, data['id'])
    if not isinstance(data['expected'], str) or data['expected'] not in known:
        raise ValueError('This blog changed. Reload before deleting it.')
    if data['title'] != record['title']:
        raise ValueError(MISTITLED)
    return directory, record


def _ended(engine, ident):
    deadline = time.monotonic() + STOP_WAIT
    while engine.current == ident:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def _stop(root, engine, ident):
    """Stop the blog's job and cancel its tool jobs, as Stop does; nothing is deleted yet."""
    import tool_jobs

    state = engine.local(ident)
    state.update(enabled=False, status='stopped')
    engine.keep_local(ident, state)
    if engine.current == ident:
        engine.stop.set()
    for job in tool_jobs.listing(root, ident):
        if job['status'] in ('queued', 'working'):
            tool_jobs.control(root, job['id'], 'cancel', engine)
    engine.wake.set()


def _forget(root, ident):
    """Remove what only this computer kept for the blog. Returns the run state it had."""
    import tool_jobs

    state = None
    local = studio.inside(root, '.blog-runs', ident + '.json')
    if local.is_file():
        state = studio.read_json(local)
        local.unlink()
    for path in studio.inside(root, '.blog-runs', 'creations').glob('*.json'):
        if _names(path, ident, ('id',)):
            path.unlink()
    studio.inside(root, '.blog-runs', 'diagnostics', ident + '.json').unlink(missing_ok=True)
    active = studio.inside(root, '.active-article.json')
    if _names(active, ident, ('id',)):
        active.unlink()
    for path in studio.inside(root, '.desk-receipts').glob('*.json'):
        if _names(path, ident, ('local_id',)):
            path.unlink()
    for path in studio.inside(root, '.uploads').glob('*.json'):
        if _names(path, ident, ('result', 'article', 'id')):
            path.unlink()
    for job in tool_jobs.listing(root, ident):
        tool_jobs.path(root, job['id']).unlink(missing_ok=True)
    return state


def _names(path, ident, keys):
    if not path.is_file():
        return False
    try:
        value = studio.read_json(path)
    except (OSError, ValueError):
        return False
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return value == ident


def delete(root, data):
    """Delete the blog named by {id, expected, title}; the title must be typed as shown."""
    from management import authorize_write
    from team_workspace import guard, space

    engine = blog_runner.engine(root)
    with studio.locked(root):
        authorize_write(root)
        check(root, data)
        ident = data['id']
        guard(root, ident)
        _stop(root, engine, ident)
    if not _ended(engine, ident):
        raise ValueError(NOT_ENDED)
    with studio.locked(root):
        adapter = authorize_write(root)
        directory, record = check(root, data)  # still here, and unchanged meanwhile
        guard(root, ident)
        title = record['title']
        found = space(root)
        commit = binding = None
        if found:
            from studio_sync import gitstate, support, team

            by = gitstate.identity(found.repo)
            gitstate.remove(
                found, ident, f'{title}: {by} deletes this blog, on {team.day(studio.now())}'
            )
            commit = support.git(found.repo, 'rev-parse', 'HEAD').strip()
            shutil.rmtree(directory, ignore_errors=True)  # what git ignored in the folder
        else:
            trash = folder(root) / ident
            if trash.exists():
                shutil.rmtree(trash)
            trash.mkdir(parents=True)
            shutil.move(str(directory), str(trash / 'blog'))
        if adapter:
            adapter.reload()
            binding = adapter.state['items'].pop('articles/' + ident, None)
            adapter.persist()
        state = _forget(root, ident)
        studio.write_json(
            record_path(root, ident),
            {
                'schema': 1,
                'id': ident,
                'title': title,
                'deleted_at': studio.now(),
                'commit': commit,
                'local': state,
                'hub': binding,
            },
        )
    notice = HUB_STAYS if binding else TEAM_WAITS if found and found.share != 'decision' else None
    # No 'id' here: the team post-action would otherwise claim the blog again.
    return {'deleted': True, 'title': title, 'notice': notice}


def deleted(root):
    """The blogs deleted in the last KEEP_DAYS days, newest first. Older ones are let go."""
    rows = []
    for path in sorted(folder(root).glob('*.json')) if folder(root).is_dir() else []:
        try:
            record = studio.read_json(path)
            at = datetime.fromisoformat(record['deleted_at'])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        until = at + timedelta(days=KEEP_DAYS)
        if until <= datetime.now(timezone.utc):
            path.unlink(missing_ok=True)
            shutil.rmtree(folder(root) / path.stem, ignore_errors=True)
            continue
        rows.append(
            {
                'id': record.get('id', path.stem),
                'title': record.get('title') or path.stem,
                'deleted_at': record['deleted_at'],
                'until': until.isoformat(),
            }
        )
    rows.sort(key=lambda row: row['deleted_at'], reverse=True)
    return rows


def restore(root, data):
    """Bring a recently deleted blog back, stopped; nothing starts by itself."""
    from management import authorize_write
    from team_workspace import space

    if set(data) != {'id'} or not isinstance(data['id'], str):
        raise ValueError('Choose a recently deleted blog.')
    ident = studio.identifier(data['id'])
    path = record_path(root, ident)
    if not path.is_file():
        raise ValueError('This blog is not among the recently deleted ones.')
    adapter = authorize_write(root)
    record = studio.read_json(path)
    directory = studio.inside(root, 'articles', ident)
    if directory.exists():
        raise ValueError('A blog with this ID is already here. Nothing was restored.')
    found = space(root)
    kept = folder(root) / ident / 'blog'
    if found and record.get('commit'):
        from studio_sync import gitstate, support, team

        by = gitstate.identity(found.repo)
        support.git(
            found.repo, 'checkout', record['commit'] + '~1', '--', f'{found.folder}/{ident}'
        )
        gitstate.commit(
            found,
            f'{record["title"]}: {by} restores this blog, on {team.day(studio.now())}',
            [ident],
        )
    elif kept.is_dir():
        shutil.move(str(kept), str(directory))
    else:
        raise ValueError('The files of this blog are no longer kept here.')
    if adapter and record.get('hub'):
        adapter.reload()
        adapter.state['items']['articles/' + ident] = record['hub']
        adapter.persist()
    engine = blog_runner.engine(root)
    if studio.inside(directory, blog_runner.STATE).is_file():
        state = record.get('local') if isinstance(record.get('local'), dict) else {}
        state.update(enabled=False, status='stopped', error='')
        engine.keep_local(ident, state)
    path.unlink(missing_ok=True)
    shutil.rmtree(folder(root) / ident, ignore_errors=True)
    try:
        shown = engine.describe(ident)
    except ValueError:
        shown = {'title': studio.item(root, 'articles', ident)[1]['title']}
    return {**shown, 'id': ident, 'restored': True}
