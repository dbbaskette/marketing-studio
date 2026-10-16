"""Blog Studio's folder in a shared studios repository, with one confirmed driver per blog."""

from contextlib import contextmanager
from contextvars import ContextVar
import json
from pathlib import Path
import shutil

import studio
import studios_config
from studio_sync import gitstate, team
from studio_sync import support

_INTERNAL = ContextVar('team_internal', default=False)


@contextmanager
def internal():
    token = _INTERNAL.set(True)
    try:
        yield
    finally:
        _INTERNAL.reset(token)


def space(root):
    root = Path(root).resolve()
    marker = root / 'hub.json'
    if not marker.is_file():
        return None
    found = gitstate.marker(root.parent, root.name)
    if found is None:
        return None
    return gitstate.Workspace(
        found['name'],
        root.parent,
        root.name,
        found['branch'],
        found.get('repository'),
        preference(root),
    )


def preference(root):
    studios_config.migrate(root)
    shared, _ = studios_config.read()
    chosen = shared.get('share', 'decision')
    return chosen if chosen in gitstate.SHARE else 'decision'


def record(root, ident):
    return support.read_json(studio.inside(root, studio.identifier(ident), 'run.json'), {})


def driver(root, ident):
    return team.driver(space(root), record(root, ident))


def guard(root, ident):
    found = space(root)
    if found:
        why = team.elsewhere(found, record(root, ident))
        if why:
            raise ValueError(why)


def guard_path(path):
    """Backstop every artifact write, including late worker and direct helper writes."""
    if _INTERNAL.get():
        return
    path = Path(path).resolve()
    for parent in path.parents:
        if (parent / 'hub.json').is_file() and (parent / 'hub.json').parent.name == 'blogs':
            relative = path.relative_to(parent)
            if len(relative.parts) >= 2 and not relative.parts[0].startswith('.'):
                ident = relative.parts[0]
                if (parent / ident / 'run.json').is_file():
                    guard(parent, ident)
            return


def _learn(root, found, at):
    """A takeover keeps this computer's unshared commits under a private ref before replay."""
    if gitstate.changed(found):
        raise ValueError(
            'Local files changed while checking the repository. Keep them with git before sharing; no work was overwritten.'
        )
    for folder in root.iterdir():
        if not folder.is_dir() or folder.name.startswith('.'):
            continue
        ident = folder.name
        current = record(root, ident)
        incoming = gitstate.theirs(found, ident + '/run.json', at)
        if not incoming:
            continue
        try:
            remote = json.loads(incoming)
        except ValueError:
            raise ValueError('A shared blog has an unreadable driver record.') from None
        if team.ours(found, current) and not team.ours(found, remote):
            import blog_runner

            runner = blog_runner.ENGINES.get(str(root))
            if runner is not None:
                state = runner.local(ident)
                state.update(
                    enabled=False,
                    status='needs-attention',
                    error='This blog was taken over on another computer. Unshared writing is kept in Git recovery refs.',
                )
                runner.keep_local(ident, state)
                if runner.current == ident:
                    runner.stop.set()
            kept = gitstate.set_aside(found, ident, at)
            state = team.kept('taken')
            state[str(folder)] = {**remote.get('driver', {}), 'at': studio.now(), 'kept': kept}
            team.keep('taken', state)


def refresh(root, push=False):
    found = space(root)
    if not found:
        return {'shared': False, 'notice': 'This is a local writing workspace.'}
    held = support.Held(found.repo / '.git/blog-studio.lock')
    with held:
        changed = gitstate.changed(found)
        if changed:
            raise ValueError(
                'Local files changed outside a recorded decision: '
                + ', '.join(changed[:5])
                + '. Keep them with git before sharing; no local work was overwritten.'
            )
    # Upstream holds this lock only to inspect/replay the clone, never during fetch/push.
    report = gitstate.sync(found, push=push, before=lambda at: _learn(root, found, at), held=held)
    with held, internal():
        studio.write_json(root / '.team-sync.json', {'report': report})
    return report


def before(root, ident=None):
    if space(root):
        report = refresh(root)
        if report.get('conflict'):
            raise ValueError(report['notice'])
        if ident:
            guard(root, ident)


def _readme(root, ident):
    folder, info = studio.item(root, 'articles', ident)
    if (folder / 'README.md').exists():
        return
    lines = ['# ' + info['title'], '', 'Made with Blog Studio. Edit through the page or skill.', '']
    for name in (
        'BRIEF.md',
        'ORIGINAL.md',
        'OUTLINE.md',
        'DRAFT.md',
        'derived/blog-review.md',
        'derived/blog-package.md',
    ):
        if (folder / name).is_file():
            lines.append(f'- [{Path(name).stem}]({name})')
    if len(lines) == 4:
        lines.extend(
            [
                'Open the files in this folder to read the blog and its saved stages.',
                'New documents appear here as the writing progresses.',
            ]
        )
    with internal():
        studio.atomic(folder / 'README.md', ('\n'.join(lines) + '\n').encode())


def saved(root, ident=None, message='Keep Blog Studio decision'):
    found = space(root)
    if not found:
        return None
    with support.locked(found.repo / '.git/blog-studio.lock'):
        if ident:
            studio.identifier(ident)
            if not (root / ident / 'run.json').is_file():
                with internal():
                    studio.write_json(root / ident / 'run.json', {'schema': 1, 'driver': None})
                gitstate.commit(found, 'Keep selected shared references', ['.shared'])
                _take(root, ident, found)
            guard(root, ident)
            _readme(root, ident)
        gitstate.commit(found, message, [ident, '.shared'] if ident else ['.shared'])
    return (
        refresh(root, push=True)
        if found.share == 'decision'
        else {'shared': False, 'notice': 'Saved here. Choose Share now to send your decisions.'}
    )


def _take(root, ident, found):
    prior = record(root, ident)
    claim = team.claim(found)
    with internal():
        studio.write_json(root / ident / 'run.json', {**prior, 'schema': 1, 'driver': claim})
    gitstate.commit(found, 'Take blog ' + ident, [ident])
    report = gitstate.sync(found, before=lambda at: _learn(root, found, at))
    # A claim must reach the shared branch before any worker or edit may proceed.
    if found.address and (not report['shared'] or not team.ours(found, record(root, ident))):
        gitstate.set_aside(found, ident)
        gitstate.sync(found, push=False)
        raise ValueError(
            'The blog could not be claimed. Nothing will run here. '
            + (report['notice'] or 'Another computer took it.')
        )


def action(root, ident, action, expected=None):
    found = space(root)
    if not found:
        raise ValueError('Join a team repository before taking or handing over a blog.')
    studio.item(root, 'articles', ident)
    with support.locked(found.repo / '.git/blog-studio.lock'):
        if gitstate.changed(found):
            raise ValueError(
                'Keep local edits with git before changing a blog driver; no work was overwritten.'
            )
        report = gitstate.sync(found, push=False, before=lambda at: _learn(root, found, at))
        if not report['reached'] or report['conflict']:
            raise ValueError(
                'Check the team repository before changing its driver. ' + (report['notice'] or '')
            )
        if gitstate.changed(found):
            gitstate.commit(found, 'Keep local work before changing a driver')
        if expected is not None:
            import blog_runner

            if blog_runner.survey(root, ident)['expected'] != expected:
                raise ValueError(
                    'This blog changed. Reload before changing its driver or publishing it.'
                )
        if action in ('take', 'takeover'):
            if (
                action == 'take'
                and team.driver(found, record(root, ident))
                and not team.ours(found, record(root, ident))
            ):
                raise ValueError('Another computer drives this blog. Choose Take over explicitly.')
            _take(root, ident, found)
        elif action == 'handover':
            guard(root, ident)
            with internal():
                studio.write_json(
                    root / ident / 'run.json', {**record(root, ident), 'driver': None}
                )
            gitstate.commit(found, 'Hand over blog ' + ident, [ident])
            report = gitstate.sync(found)
            if not report['shared']:
                raise ValueError(
                    'The handover is saved here but is not shared yet. Share now before another computer takes it.'
                )
        elif action == 'publish':
            guard(root, ident)
            if not blog_runner_complete(root, ident):
                raise ValueError('Approve every planned stage before publishing a revision.')
            gitstate.commit(found, 'Publish blog ' + ident, [ident])
            report = gitstate.sync(found)
            if found.address and not report['shared']:
                raise ValueError('Share the blog before publishing a numbered revision.')
            return team.publish(
                found,
                ident,
                studio.item(root, 'articles', ident)[1]['title'],
                True,
                gitstate.identity(found.repo),
            )
        else:
            raise ValueError('Choose take, takeover, handover or publish.')
    return status(root)


def status(root):
    migration_notice, migration_problem = studios_config.migrate(root)
    found = space(root)
    shared, problem = studios_config.read()
    preferences = {
        'repository': shared.get('team', {}).get('repository') or '',
        'branch': shared.get('team', {}).get('branch') or 'main',
        'share': shared.get('share') or 'decision',
        'shared_problem': problem or migration_problem,
        'migration_notice': migration_notice,
        'shared_before': team_before(shared),
    }
    if found:
        return {
            **preferences,
            'joined': True,
            'workspace': str(root),
            'active_repository': found.address,
            'active_branch': found.branch,
            'configuration_notice': 'Shared team settings changed. Join the configured repository to use it here; this workspace and its writing are kept.'
            if (preferences['repository'], preferences['branch']) != (found.address, found.branch)
            else None,
            'report': support.read_json(root / '.team-sync.json', {}).get('report', {}),
            'published': team.published(found),
        }
    return {
        'joined': False,
        **preferences,
    }


def team_before(shared):
    return {
        'team': {key: shared.get('team', {}).get(key) for key in ('repository', 'branch')},
        'share': shared.get('share'),
    }


def join(address, branch='main', share='decision', shared_before=None):
    studios_config.repository(address)
    if share not in ('decision', 'asked'):
        raise ValueError('Choose a listed sharing mode.')
    if shared_before is None:
        shared_before = team_before(studios_config.read()[0])
    if (
        not isinstance(shared_before, dict)
        or set(shared_before) != {'team', 'share'}
        or not isinstance(shared_before['team'], dict)
        or set(shared_before['team']) != {'repository', 'branch'}
    ):
        raise ValueError('Reload the displayed team settings before joining.')
    # The core owns a distinct clone, never the checkout used by Training or Presentation Studio.
    with support.locked(support.data_root() / '.joining-blog.lock'):
        studios_config.update({}, expected=shared_before)
        found = gitstate.join(
            address, folder='blogs', branch=branch, share=share, remember_workspace=False
        )
        with internal():
            studio.initialize(found.root)
            studio.write_json(found.root / '.team-sync.json', {})
        gitstate.commit(found, 'Set up Blog Studio writing folders')
        report = gitstate.sync(found)
        if not report['shared']:
            raise ValueError(
                'The team folder was kept here but could not be shared. Check repository write access and retry joining.'
            )
        studios_config.update(
            {'team': {'repository': address, 'branch': found.branch}, 'share': share},
            expected=shared_before,
        )
        gitstate.remember(found)
    return found.root


def migrate(root, legacy_root, selected, sources=(), profiles=(), memories=()):
    before(root)
    with studio.locked(root):
        return _migrate(root, legacy_root, selected, sources, profiles, memories)


def _migrate(root, legacy_root, selected, sources=(), profiles=(), memories=()):
    """Copy explicitly selected legacy work; never write to or refresh the old Hub."""
    from hub_workspace import active
    from hub_store import immutable_files

    legacy_root = Path(legacy_root).resolve()
    if not space(root) or legacy_root == root:
        raise ValueError('Choose a separate joined team workspace as the destination.')
    adapter = active(legacy_root)
    if not adapter or not any((selected, sources, profiles, memories)):
        raise ValueError('Select a legacy Team Hub workspace and article IDs to migrate.')
    graph = adapter.hub.graph()
    queue, chosen, memory_revisions = [], set(), set()
    pending = [('articles', studio.identifier(ident)) for ident in selected]
    pending += [('sources', studio.identifier(ident)) for ident in sources]
    pending += [('profiles', studio.identifier(ident)) for ident in profiles]
    for ident in memories:
        heads = graph['heads'].get(ident, [])
        if len(heads) != 1 or graph['revisions'][heads[0]]['kind'] in (
            'article',
            'source',
            'voice',
        ):
            raise ValueError('Choose an unambiguous legacy memory item.')
        memory_revisions.add(heads[0])
    plans, seen = [], set()
    while pending:
        group, ident = pending.pop()
        if (group, ident) in seen:
            continue
        seen.add((group, ident))
        folder, info = studio.item(legacy_root, group, ident)
        destination = studio.inside(root, group, ident)
        if destination.exists():
            raise ValueError('Migration would overwrite local work: ' + ident)
        problem = team.unacceptable(folder)
        if problem:
            raise ValueError(problem)
        plans.append((folder, destination))
        if group == 'articles':
            pending.extend(('sources', entry['source_id']) for entry in info['sources'])
            if info['voice'].get('mode') == 'profile':
                pending.append(('profiles', info['voice']['profile_id']))
            memory_revisions.update(
                ref['revision'] for ref in info.get('hub_context', {}).get('selected', [])
            )
        if group == 'profiles':
            pending.extend(('sources', ident) for ident in info['sample_ids'])
        bound = adapter.state['items'].get(group + '/' + ident)
        if bound:
            queue.append(bound['revision'])
    queue.extend(memory_revisions)
    while queue:
        revision = queue.pop()
        if revision in chosen:
            continue
        metadata = graph['revisions'][revision]
        chosen.add(revision)
        queue.extend(metadata['parents'])
        queue.extend(entry['revision'] for entry in metadata['dependencies'])
    selected_graph = {'revisions': {revision: graph['revisions'][revision] for revision in chosen}}
    immutable = immutable_files(adapter.hub.files(), selected_graph)
    archive = root / '.shared/legacy' / adapter.hub.id
    if archive.exists():
        raise ValueError(
            'This legacy Hub already has a migration archive; choose a fresh destination to avoid replacing history.'
        )
    for revision in chosen:
        metadata = graph['revisions'][revision]
        if (
            metadata['kind'] not in ('article', 'source', 'voice')
            and (root / '.shared/memory' / (revision + '.json')).exists()
        ):
            raise ValueError('Migration would overwrite an existing memory revision.')
    # Validate the entire plan before writing. Copy failure removes only this new migration.
    created = []
    try:
        with internal():
            for folder, destination in plans:
                destination.parent.mkdir(parents=True, exist_ok=True)
                team.copy_in(folder, destination)
                created.append(destination)
            for (revision, relative), content in immutable.items():
                studio.atomic(studio.inside(archive, revision, relative), content)
            for revision in chosen:
                metadata = graph['revisions'][revision]
                if metadata['kind'] in ('article', 'source', 'voice'):
                    continue
                body = immutable[(revision, 'BODY.md')].decode('utf-8')
                studio.write_json(
                    root / '.shared/memory' / (revision + '.json'), {**metadata, 'body': body}
                )
        if not selected:
            saved(root, message='Migrate selected legacy references and memory')
        for ident in selected:
            saved(root, ident, 'Migrate selected legacy blog')
    except Exception:
        # A committed copy is retained on a sharing failure; removing it would lose the queued work.
        if not gitstate.known(space(root), '.shared/legacy/' + adapter.hub.id):
            for destination in created:
                shutil.rmtree(destination, ignore_errors=True)
            shutil.rmtree(archive, ignore_errors=True)
        raise
    return {
        'migrated': selected,
        'legacy_unchanged': True,
        'workspace': str(root),
        'archive': '.shared/legacy/' + adapter.hub.id,
    }


def add_parser(groups):
    commands = groups.add_parser(
        'team', help='Shared studios repository and blog drivers'
    ).add_subparsers(dest='action', required=True)
    cmd = commands.add_parser('join')
    cmd.add_argument('--repository', required=True)
    cmd.add_argument('--branch', default='main')
    cmd.add_argument('--share', choices=gitstate.SHARE, default='decision')
    commands.add_parser('status')
    commands.add_parser('sync')
    for name in ('take', 'takeover', 'handover', 'publish'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--id', required=True)
    cmd = commands.add_parser('migrate')
    cmd.add_argument('--from-workspace', required=True)
    cmd.add_argument('--article', action='append', default=[])
    cmd.add_argument('--source', action='append', default=[])
    cmd.add_argument('--profile', action='append', default=[])
    cmd.add_argument('--memory', action='append', default=[])


def command(root, args):
    if args.action == 'join':
        return status(join(args.repository, args.branch, args.share))
    if args.action == 'status':
        return status(root)
    if args.action == 'sync':
        return refresh(root, push=True)
    if args.action == 'migrate':
        return migrate(
            root, args.from_workspace, args.article, args.source, args.profile, args.memory
        )
    return action(root, args.id, args.action)


def memory_list(root):
    rows = []
    for path in sorted((root / '.shared/memory').glob('*.json')):
        value = studio.read_json(path)
        if (
            value.get('kind') not in ('rule', 'context', 'note', 'decision')
            or value.get('status') == 'tombstone'
        ):
            continue
        rows.append(
            {
                **value,
                'summary': value.get('body', '')[:200],
                'conflict': False,
                'lesson': None,
                'focused_workflow': False,
            }
        )
    latest = {}
    for row in rows:
        old = latest.get(row['item'])
        if old is None or str(row.get('created_at', '')) > str(old.get('created_at', '')):
            latest[row['item']] = row
    return list(latest.values())


def memory_detail(root, ident, revision=None):
    rows = memory_list(root)
    found = next(
        (
            row
            for row in rows
            if row['item'] == ident and (revision is None or row['revision'] == revision)
        ),
        None,
    )
    if found is None:
        raise ValueError('That memory changed or is unavailable. Reload team memory.')
    return {
        'record': {key: found[key] for key in ('item', 'revision', 'kind', 'title', 'scope')},
        'body': found['body'][:16000],
        'truncated': len(found['body']) > 16000,
        'editable': found['kind'] != 'decision',
        'read_only_reason': 'Decisions are read-only.' if found['kind'] == 'decision' else '',
        'continuation': 'Use Blog Studio. Inspect team memory ' + ident + '.',
    }


def save_memory(root, data):
    import uuid

    if data.get('kind') not in ('note', 'context', 'rule') or data.get('scope', 'team') not in (
        'team',
        'project',
        'author',
        'article',
    ):
        raise ValueError('Choose a listed memory kind and scope.')
    title, body = data.get('title'), data.get('body')
    if (
        not isinstance(title, str)
        or not 1 <= len(title) <= 200
        or not isinstance(body, str)
        or not 1 <= len(body) <= 16000
    ):
        raise ValueError('Provide a title up to 200 characters and memory up to 16000 characters.')
    ident = data.get('item') or uuid.uuid4().hex
    if not isinstance(ident, str) or not support.re.fullmatch('[a-f0-9]{32}', ident):
        raise ValueError('Choose a valid memory identity.')
    if data.get('item'):
        memory_detail(root, ident, data.get('revision'))
    revision = uuid.uuid4().hex
    value = {
        'item': ident,
        'revision': revision,
        'kind': data['kind'],
        'title': title,
        'body': body,
        'scope': {'level': data.get('scope', 'team'), 'key': data.get('scope_key', '')},
        'created_at': studio.now(),
        'status': 'active',
        'data': {},
    }
    studio.write_json(root / '.shared/memory' / (revision + '.json'), value)
    return value


def blog_runner_complete(root, ident):
    import blog_runner

    return blog_runner.survey(root, ident)['complete']
