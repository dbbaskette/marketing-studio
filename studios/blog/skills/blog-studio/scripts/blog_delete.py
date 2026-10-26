"""Delete a blog from the page, keep it for thirty days, and bring it back.

A deletion stops whatever is running for the blog, its job and its tool jobs, and waits for
them to end. Then it takes the blog out and removes what only this computer kept for it: its
run state, diagnostics, receipts, upload ledgers and tool jobs. What happens to the blog's
own folder depends on where the blog lives:

- In a local workspace the folder moves under `.blog-runs/deleted/<id>/blog`.
- In a team workspace it is taken out of the shared branch in one commit that says who
  deleted it and when; the commit is remembered so the files can be checked out again. A
  folder git had nothing to commit for moves to the local keep instead.
- With a Team Hub selected, a tombstone revision takes the blog off the shared list, as the
  CLI's `remove` does; the shared history stays, and this computer's binding is dropped.

The record under `.blog-runs/deleted/<id>.json` drives the "Recently deleted" list and is
written as soon as the folder is out, so a failure later in the deletion still leaves the
blog restorable. Restore puts the folder, the Hub binding (publishing an active revision
again) and a stopped run state back; nothing starts by itself. Records older than KEEP_DAYS,
and the files they kept, are let go of when the list is read.
"""

from datetime import datetime, timedelta, timezone
import shutil
import time
import unicodedata

import studio
import blog_runner

# Typographic marks a person types as their plain forms.
PLAIN_MARKS = str.maketrans(
    {
        '‘': "'",
        '’': "'",
        '‚': "'",
        '“': '"',
        '”': '"',
        '„': '"',
        '–': '-',
        '—': '-',
        '\ufeff': ' ',  # the page's \s counts a byte-order mark as a space
    }
)


def plain_title(value):
    """A title as a person would type it: NFKC, plain quotes and dashes, one space between
    words, no case. Both the typed text and the stored title go through this."""
    value = unicodedata.normalize('NFKC', value).translate(PLAIN_MARKS)
    return ' '.join(value.split()).casefold()


def same_title(typed, stored):
    return isinstance(typed, str) and plain_title(typed) == plain_title(stored)


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
KEPT_ALREADY = (
    'An earlier deleted copy of this blog is still kept. Restore that one first, or wait '
    'until it is let go of. Nothing was deleted.'
)
HUB_STAYS = 'It leaves the shared list; its history stays in your Team Hub.'
HUB_UNREACHED = (
    'The Team Hub could not be reached, so the blog cannot be put back on the shared list. '
    'Check access, then restore it again. It stays among the recently deleted.'
)
HUB_BOUND = (
    'Another blog here is already bound to the same shared blog. Reconcile them in chat '
    'before restoring this one.'
)
TEAM_WAITS = (
    'It is gone from this computer. Your team sees it gone the next time you choose Share now.'
)
ALREADY_BACK = 'This blog was already brought back.'


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
    if not same_title(data['title'], record['title']):
        raise ValueError(MISTITLED)
    return directory, record


def _jobs(root, ident):
    """Every tool job file that names the blog, whatever its state."""
    import tool_jobs

    found = []
    for path in studio.inside(root, '.blog-runs', 'tools').glob('*.json'):
        try:
            value = tool_jobs.read(root, path.stem)
        except (OSError, ValueError, KeyError):
            continue
        if (value.get('metadata') or {}).get('article') == ident:
            found.append(value)
    return found


def _stop(root, engine, ident):
    """Stop the blog's job and cancel its tool jobs, as Stop does; nothing is deleted yet.
    Returns what the deletion must wait for: the blog itself and each job that was working."""
    import tool_jobs

    state = engine.local(ident)
    state.update(enabled=False, status='stopped')
    engine.keep_local(ident, state)
    if engine.current == ident:
        engine.stop.set()
    awaited = {ident}
    for job in _jobs(root, ident):
        if job['status'] in ('queued', 'working'):
            awaited.add('tool:' + job['id'])
            tool_jobs.control(root, job['id'], 'cancel', engine)
    engine.wake.set()
    return awaited


def _ended(engine, awaited):
    deadline = time.monotonic() + STOP_WAIT
    while engine.current in awaited:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def _forget(root, ident):
    """Remove what only this computer kept for the blog."""
    import tool_jobs

    studio.inside(root, '.blog-runs', ident + '.json').unlink(missing_ok=True)
    for folder in ('creations', 'desk-creations'):
        for path in studio.inside(root, '.blog-runs', folder).glob('*.json'):
            if _names(path, ident, ('id',)):
                path.unlink()
    studio.inside(root, '.blog-runs', 'desk-jobs', ident + '.json').unlink(missing_ok=True)
    # A start's phase and problem, and research staged while it worked (desk_jobs.staging).
    studio.inside(root, '.blog-runs', 'desk-starts', ident + '.json').unlink(missing_ok=True)
    shutil.rmtree(studio.inside(root, '.blog-runs', 'desk-starts', ident), ignore_errors=True)
    import desk_finish

    desk_finish.forget(root, ident)  # Finishing suggestions waiting for this blog.
    # What Finishing sent to the blog's Google Doc, kept on this computer.
    studio.inside(root, '.blog-runs', 'desk-google', ident + '.json').unlink(missing_ok=True)
    studio.inside(root, '.blog-runs', 'diagnostics', ident + '.json').unlink(missing_ok=True)
    blog_runner.said_path(root, ident).unlink(missing_ok=True)
    active = studio.inside(root, '.active-article.json')
    if _names(active, ident, ('id',)):
        active.unlink()
    for path in studio.inside(root, '.desk-receipts').glob('*.json'):
        if _names(path, ident, ('local_id',)):
            path.unlink()
    for path in studio.inside(root, '.uploads').glob('*.json'):
        if _names(path, ident, ('result', 'article', 'id')):
            path.unlink()
    for job in _jobs(root, ident):
        tool_jobs.path(root, job['id']).unlink(missing_ok=True)


def _material_out(root, ident, record):
    """Keep the uploaded files only this blog pinned beside its deleted copy, and drop
    the upload ledgers that named them. Files another blog pins stay where they are."""
    pinned = [
        entry['source_id']
        for entry in record.get('sources', [])
        if 'material' in entry.get('purposes', [])
    ]
    wanted = list(dict.fromkeys([*record.get('material', []), *pinned]))
    if not wanted:
        return []
    others = set()
    for session in studio.inside(root, 'articles').glob('*/session.json'):
        if session.parent.name == ident:
            continue
        try:
            others.update(entry['source_id'] for entry in studio.read_json(session)['sources'])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    moved = []
    for source in wanted:
        here = studio.material(root, studio.identifier(source))
        if source in others or not here.is_dir():
            continue
        target = folder(root) / ident / 'material' / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(here), str(target))
        moved.append(source)
    for path in studio.inside(root, '.uploads').glob('*.json'):
        try:
            result = studio.read_json(path).get('result') or {}
            rows = [*(result.get('files') or []), *([result] if result.get('source') else [])]
            named = {row['source']['id'] for row in rows}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if named & set(moved):
            path.unlink()
    return moved


def _material_back(root, ident):
    """Put a restored blog's kept files back where its run reads them."""
    kept = folder(root) / ident / 'material'
    for directory in sorted(kept.iterdir()) if kept.is_dir() else []:
        target = studio.material(root, studio.identifier(directory.name))
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(directory), str(target))


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


def _keep(root, directory, ident):
    """Move the folder under the local keep. Refuses when an earlier copy is still there."""
    trash = folder(root) / ident
    if trash.exists():
        raise ValueError(KEPT_ALREADY)
    trash.mkdir(parents=True)
    shutil.move(str(directory), str(trash / 'blog'))


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
        awaited = _stop(root, engine, ident)
    if not _ended(engine, awaited):
        raise ValueError(NOT_ENDED)
    with studio.locked(root):
        adapter = authorize_write(root)
        directory, record = check(root, data)  # still here, and unchanged meanwhile
        guard(root, ident)
        title = record['title']
        found = space(root)
        if (folder(root) / ident).exists():
            raise ValueError(KEPT_ALREADY)
        local = studio.inside(root, '.blog-runs', ident + '.json')
        state = studio.read_json(local) if local.is_file() else None
        binding = None
        if adapter:
            adapter.reload()
            binding = adapter.state['items'].get('articles/' + ident)
        commit = None
        if found:
            from studio_sync import gitstate, support, team

            by = gitstate.identity(found.repo)
            try:
                removed = gitstate.remove(
                    found, ident, f'{title}: {by} deletes this blog, on {team.day(studio.now())}'
                )
            except support.GitError:
                removed = False  # the folder is ignored: git has nothing of it to take out
            if removed:
                commit = support.git(found.repo, 'rev-parse', 'HEAD').strip()
                shutil.rmtree(directory, ignore_errors=True)  # what git ignored in the folder
            elif directory.exists():
                _keep(root, directory, ident)  # git had nothing of it to take out
        else:
            _keep(root, directory, ident)
        # The record goes down before anything else, so a failure below leaves it restorable.
        entry = {
            'schema': 1,
            'id': ident,
            'title': title,
            'deleted_at': studio.now(),
            'commit': commit,
            'local': state,
            'hub': binding,
        }
        studio.write_json(record_path(root, ident), entry)
        entry['material'] = _material_out(root, ident, record)
        if entry['material']:
            studio.write_json(record_path(root, ident), entry)
        if adapter and binding:
            # As the CLI's remove does: a tombstone takes it off the shared list; history stays.
            tomb = adapter.hub.save(
                'article',
                title,
                '',
                item=binding['item'],
                parents=[binding['revision']],
                status='tombstone',
                sync=True,
            )
            entry['hub'] = {**binding, 'tombstone': tomb['revision']}
            studio.write_json(record_path(root, ident), entry)
            adapter.state['items'].pop('articles/' + ident, None)
            adapter.persist()
        _forget(root, ident)
    notice = HUB_STAYS if binding else TEAM_WAITS if found and found.share != 'decision' else None
    # No 'id' here: the team post-action would otherwise claim the blog again.
    return {'deleted': True, 'title': title, 'notice': notice}


def deleted(root):
    """The blogs deleted in the last KEEP_DAYS days, newest first. Older ones are let go of;
    a record that cannot be read is left alone and left out."""
    rows = []
    now = datetime.now(timezone.utc)
    for path in sorted(folder(root).glob('*.json')) if folder(root).is_dir() else []:
        try:
            record = studio.read_json(path)
            at = datetime.fromisoformat(record['deleted_at'])
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            until = at + timedelta(days=KEEP_DAYS)
            gone = until <= now
            title = record.get('title') or path.stem
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if gone:
            path.unlink(missing_ok=True)
            shutil.rmtree(folder(root) / path.stem, ignore_errors=True)
            continue
        rows.append(
            {
                'id': path.stem,
                'title': title,
                'deleted_at': record['deleted_at'],
                'until': until.isoformat(),
            }
        )
    rows.sort(key=lambda row: row['deleted_at'], reverse=True)
    return rows


def _shown(root, engine, ident):
    """The restored blog as the page opens it next: a blog on the writing desk opens there."""
    import desk

    directory, record = studio.item(root, 'articles', ident)
    on_desk = desk.on_desk(directory)
    try:
        return {**engine.describe(ident), 'on_desk': on_desk}
    except ValueError:
        return {'title': record['title'], 'on_desk': on_desk}


def _record_commit(found, record, ident):
    from studio_sync import gitstate, team

    by = gitstate.identity(found.repo)
    gitstate.commit(
        found,
        f'{record["title"]}: {by} restores this blog, on {team.day(studio.now())}',
        [ident],
    )


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
    engine = blog_runner.engine(root)
    directory = studio.inside(root, 'articles', ident)
    if directory.exists():
        # A teammate, or an earlier try, already brought it back: the record is stale.
        session = directory / 'session.json'
        if session.is_file() and studio.read_json(session).get('title') == record.get('title'):
            _material_back(root, ident)
            path.unlink(missing_ok=True)
            shutil.rmtree(folder(root) / ident, ignore_errors=True)
            shown = _shown(root, engine, ident)
            return {**shown, 'id': ident, 'restored': True, 'notice': ALREADY_BACK}
        raise ValueError('A different blog with this ID is already here. Nothing was restored.')
    binding = record.get('hub') if isinstance(record.get('hub'), dict) else None
    if adapter and binding:
        adapter.reload()
        for key, saved in adapter.state['items'].items():
            if (
                key.startswith('articles/')
                and saved.get('item') == binding.get('item')
                and studio.inside(root, 'articles', key.split('/', 1)[1]).is_dir()
            ):
                raise ValueError(HUB_BOUND)
        if binding.get('tombstone') and not adapter.hub.refresh().get('fresh'):
            raise ValueError(HUB_UNREACHED)
    found = space(root)
    kept = folder(root) / ident / 'blog'
    if found and record.get('commit'):
        from studio_sync import support

        support.git(
            found.repo, 'checkout', record['commit'] + '~1', '--', f'{found.folder}/{ident}'
        )
        _record_commit(found, record, ident)
    elif kept.is_dir():
        shutil.move(str(kept), str(directory))
        if found:
            from studio_sync import support

            try:
                _record_commit(found, record, ident)
            except support.GitError:
                pass  # kept here because git had nothing of it; it still has nothing
    else:
        raise ValueError('The files of this blog are no longer kept here.')
    _material_back(root, ident)  # Its uploaded files are back before the Hub reads the blog.
    if adapter and binding:
        if binding.get('tombstone'):
            # The binding points at the tombstone with no fingerprint, so publishing makes a
            # new active revision of the restored files on top of it.
            adapter.state['items']['articles/' + ident] = {
                **{key: value for key, value in binding.items() if key != 'tombstone'},
                'revision': binding['tombstone'],
                'fingerprint': '',
            }
            adapter.persist()
            report = adapter.publish_mutation('article', {'id': ident})
            if report.get('sync_status', report.get('status')) not in ('shared', 'synchronized'):
                raise ValueError(
                    'The blog is back here, but the Team Hub did not take it back on the '
                    'shared list yet: ' + str(report.get('next_step') or report.get('status'))
                )
        else:
            adapter.state['items']['articles/' + ident] = binding
            adapter.persist()
    if studio.inside(directory, blog_runner.STATE).is_file():
        state = record.get('local') if isinstance(record.get('local'), dict) else {}
        state.update(enabled=False, status='stopped', error='')
        engine.keep_local(ident, state)
    path.unlink(missing_ok=True)
    shutil.rmtree(folder(root) / ident, ignore_errors=True)
    return {**_shown(root, engine, ident), 'id': ident, 'restored': True}
