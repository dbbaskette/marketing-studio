"""Bounded contextual jobs on Blog Studio's existing single-worker scheduler."""

import json
import re

import studio

KINDS = {
    'voice-learn',
    'voice-audition',
    'voice-guide',  # A voice guide made from a few samples (article_tools).
    'style-learn',
    'repurpose',
    'interview-question',
    'interview-outline',
    # The writing desk (desk_jobs.py): a section note, the whole draft, a selection, a first
    # pass; and a start's angles (before a blog exists), research, outline and draft.
    'desk-section',
    'desk-revise-all',
    'desk-selection',
    'desk-first-pass',
    'desk-angles',
    'desk-research',
    'desk-outline',
    'desk-draft',
    # Finishing on the desk: proposals to preview, then apply, edit or skip.
    'finish-humanize',
    'finish-facts',
    'finish-headline',
    'finish-feedback',
    'finish-voice',
}
DESK = (
    'desk-section',
    'desk-revise-all',
    'desk-selection',
    'desk-first-pass',
    'desk-angles',
    'desk-research',
    'desk-outline',
    'desk-draft',
    'finish-humanize',
    'finish-facts',
    'finish-headline',
    'finish-feedback',
    'finish-voice',
)


def path(root, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('Choose a saved tool operation.')
    return studio.inside(root, '.blog-runs', 'tools', ident + '.json')


def read(root, ident):
    target = path(root, ident)
    if not target.is_file() or target.is_symlink():
        raise ValueError('This tool operation is unavailable.')
    return studio.read_json(target)


def write(root, value):
    target = path(root, value['id'])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    studio.write_json(target, value)
    target.chmod(0o600)


def create(root, ident, kind, payload, guidance, basis, metadata):
    if kind not in KINDS:
        raise ValueError('Choose a supported tool task.')
    target = path(root, ident)
    request = {'kind': kind, 'payload': payload, 'basis': basis, 'metadata': metadata}
    fingerprint = studio.digest(json.dumps(request, sort_keys=True).encode())
    if target.exists():
        saved = read(root, ident)
        if saved['fingerprint'] != fingerprint:
            raise ValueError('This operation belongs to another request. Start a new task.')
        return public(saved)
    if len(json.dumps(payload)) > 1_000_000:
        raise ValueError('Use smaller selected excerpts for this task.')
    from blog_runner import settings
    from studio_core import model_profiles

    defaults = settings(root)['defaults']
    import studios_config

    shared, problem = studios_config.read()
    if problem:
        raise ValueError(problem)
    assistant = shared.get('assistant') or {}
    same_agent = assistant.get('agent') == defaults['engine']
    saved = {
        'id': ident,
        **request,
        'fingerprint': fingerprint,
        'guidance': guidance,
        'status': 'queued',
        'created_at': studio.now(),
        'attempts': 0,
        'engine': defaults['engine'],
        'seconds': defaults['seconds'],
        'model_profiles': model_profiles.snapshot(
            shared,
            defaults['engine'],
            assistant.get('model') if same_agent else None,
            assistant.get('effort') if same_agent else None,
        ),
        'result': None,
        'error': '',
    }
    write(root, saved)
    return public(saved)


def public(value):
    result = value.get('result')
    return {
        key: value.get(key)
        for key in (
            'id',
            'kind',
            'status',
            'created_at',
            'started_at',
            'finished_at',
            'attempts',
            'error',
            'metadata',
            'model_selection',
            'applied',
            'saved_content',
        )
    } | {
        'result': result,
        'words': len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", (result or {}).get('content', ''))),
        'characters': len((result or {}).get('content', '')),
    }


def control(root, ident, action, engine):
    saved = read(root, ident)
    if saved['metadata'].get('article'):
        from team_workspace import guard

        guard(root, saved['metadata']['article'])
    if action == 'cancel':
        if saved['status'] in ('queued', 'working'):
            saved['status'] = 'cancelled'
            write(root, saved)
            if engine.current == 'tool:' + ident:
                engine.stop.set()
    elif action == 'retry':
        if saved['kind'] in DESK:
            raise ValueError('Run it again from the desk, where the draft it changes is shown.')
        if saved['status'] not in ('failed', 'cancelled') or saved['attempts'] >= 3:
            raise ValueError(
                'This task cannot be retried. Start a new task after reviewing its inputs.'
            )
        saved.update(status='queued', error='')
        write(root, saved)
        engine.wake.set()
    else:
        raise ValueError('Choose cancel or retry.')
    return public(saved)


def recover(root):
    folder = studio.inside(root, '.blog-runs', 'tools')
    for target in folder.glob('*.json'):
        try:
            value = read(root, target.stem)
            if value['status'] == 'working':
                value.update(
                    status='failed',
                    error='This task was interrupted. Your inputs are kept; retry when ready.',
                )
                write(root, value)
        except (ValueError, OSError, KeyError):
            continue


def once(engine):
    root = engine.root
    folder = studio.inside(root, '.blog-runs', 'tools')
    with studio.locked(root):
        values = []
        for target in folder.glob('*.json'):
            try:
                saved = read(root, target.stem)
                if saved['status'] == 'queued':
                    values.append(saved)
            except (ValueError, OSError, KeyError):
                continue
        if not values or engine.closed.is_set():
            return
        saved = min(values, key=lambda value: value['created_at'])
        ident = saved['id']
        if saved['kind'] in DESK and saved['metadata'].get('article'):
            import team_workspace

            try:
                team_workspace.guard(root, saved['metadata'].get('article'))
            except ValueError as error:
                # Another computer took the blog since this was queued: it never runs here.
                saved.update(
                    status='cancelled',
                    error=(
                        'Another computer drives this blog now, so this did not run. ' + str(error)
                    )[:1000],
                    finished_at=studio.now(),
                )
                write(root, saved)
                return
        from studio_core import model_profiles

        try:
            choice = model_profiles.route(saved, 'Blog Studio', 'draft', purpose=saved['kind'])
        except (ValueError, KeyError, TypeError) as error:
            saved.update(status='failed', error=str(error)[:1000], attempts=saved['attempts'] + 1)
            write(root, saved)
            return
        saved.update(
            status='working',
            started_at=studio.now(),
            attempts=saved['attempts'] + 1,
            model_selection=choice,
        )
        write(root, saved)
        engine.current = 'tool:' + ident
        engine.stop.clear()
    try:
        if saved['kind'] == 'desk-research':
            import desk_jobs

            # Research before a desk start's writing: a plan, then research, as runs do.
            result = desk_jobs.research_run(engine, saved)
        else:
            result = engine.worker(
                saved['engine'],
                saved['payload'],
                saved['guidance'],
                seconds=saved['seconds'],
                web=False,
                stop=engine.stop,
                model_selection=choice,
            )
        if (
            saved['kind'] in DESK
            and isinstance(result, dict)
            and isinstance(result.get('content'), str)
            and len(result['content']) > 200_000
        ):
            raise ValueError(
                'The rewrite came back longer than 200,000 characters, more than one part of '
                'a draft holds. Nothing was changed; run it again with a narrower note.'
            )
        if (
            not isinstance(result, dict)
            or not isinstance(result.get('content'), str)
            or not result['content'].strip()
            or len(result['content']) > 200_000
            or not isinstance(result.get('notes', ''), str)
            or len(result.get('notes', '')) > 10_000
        ):
            raise ValueError('The tool returned an unreadable result. Retry or adjust the inputs.')
        with studio.locked(root):
            current = _working(root, ident)
            if current is None or engine.stop.is_set():
                return
            current.update(status='ready', result=result, finished_at=studio.now())
            write(root, current)
            shared = _ended(root, current)
        _share(root, shared)
    except Exception as error:
        shared = None
        with studio.locked(root):
            current = _working(root, ident)
            if current is not None:
                current.update(status='failed', error=str(error)[:1000], finished_at=studio.now())
                write(root, current)
                shared = _ended(root, current)
        _share(root, shared)
    finally:
        engine.current = None


def _ended(root, job):
    """A desk job settles into its draft as soon as it ends, under the lock already held."""
    if job['kind'] not in DESK:
        return None
    import desk_jobs

    return desk_jobs.ended(root, job)


def _share(root, ident):
    if ident:
        import desk_jobs

        desk_jobs.share(root, ident)


def _working(root, ident):
    """The job as saved, while it is still working; None once it was cancelled, finished or
    removed meanwhile, as when its blog was deleted."""
    try:
        current = read(root, ident)
    except (ValueError, OSError):
        return None
    return current if current.get('status') == 'working' else None


def listing(root, article=None):
    folder = studio.inside(root, '.blog-runs', 'tools')
    values = []
    for target in folder.glob('*.json'):
        try:
            value = read(root, target.stem)
            if value['kind'] == 'desk-angles':
                continue  # Angles for a blog not yet made belong to its start page.
            if value['metadata'].get('article') == article:
                values.append(
                    {key: value.get(key) for key in ('id', 'kind', 'status', 'created_at')}
                )
        except (OSError, ValueError, KeyError):
            continue
    return sorted(values, key=lambda value: value['created_at'], reverse=True)[:20]
