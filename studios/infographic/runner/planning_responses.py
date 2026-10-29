"""Private, revision-bound planning responses; validation retries never imply new AI work."""
from .contracts import MAX_RECORD_BYTES, basis, canonical, digest
from .validation import require, sha
from .workspace import _atomic, _json

LIMIT = MAX_RECORD_BYTES + 16_384


def pointer(store, ident):
    root = store._project(ident) / 'jobs'
    for folder in (root, root / 'planning'):
        require(not folder.is_symlink() and (not folder.exists() or folder.is_dir()),
                'The saved planning folder is unsafe. Your sources are kept.')
    path = root / 'planning-current.json'
    require(not path.is_symlink(), 'The saved planning reference cannot be a link.')
    return path


def load(store, project):
    path = pointer(store, project['id'])
    if not path.exists():
        return None
    ref = _json(store.root, path.relative_to(store.root).as_posix(), 8192)
    require(isinstance(ref, dict) and set(ref) == {'schema', 'response', 'accepted', 'problem'}
            and type(ref['schema']) is int and ref['schema'] == 1
            and sha(ref['response']) and type(ref['accepted']) is bool
            and (ref['problem'] is None or isinstance(ref['problem'], str) and len(ref['problem']) <= 1000),
            'The saved planning reference cannot be read safely.')
    record = _json(store.root, f"projects/{project['id']}/jobs/planning/{ref['response']}.json", LIMIT)
    require(isinstance(record, dict) and set(record) == {'schema', 'owner', 'project', 'revision', 'basis', 'answer'}
            and type(record['schema']) is int and record['schema'] == 1
            and record['owner'] == store.owner and record['project'] == project['id']
            and type(record['revision']) is int and record['revision'] >= 0
            and isinstance(record['basis'], dict) and set(record['basis']) == set(basis(project))
            and all(sha(value) for value in record['basis'].values())
            and digest(record) == ref['response']
            and isinstance(record['answer'], dict) and set(record['answer']) == {'facts', 'stories'},
            'The saved planning response is not owned or intact. Your sources are kept.')
    if ref['accepted'] or record['revision'] != project['revision'] or record['basis'] != basis(project):
        return None
    return record['answer']


def save(store, project, answer):
    require(len(canonical(answer)) <= MAX_RECORD_BYTES, 'The planning response exceeds its private storage limit.')
    record = {'schema': 1, 'owner': store.owner, 'project': project['id'],
              'revision': project['revision'], 'basis': basis(project), 'answer': answer}
    ident = digest(record)
    path = pointer(store, project['id'])
    with store.locked():
        store.expect(store.read(project['id']), project['revision'])
        store.write_blob(project['id'], f'jobs/planning/{ident}.json', canonical(record))
        _atomic(path, canonical({'schema': 1, 'response': ident, 'accepted': False, 'problem': None}))


def accepted(store, ident):
    path = pointer(store, ident)
    ref = _json(store.root, path.relative_to(store.root).as_posix(), 8192)
    _atomic(path, canonical({**ref, 'accepted': True}))


def rejected(store, ident, problem):
    path = pointer(store, ident)
    ref = _json(store.root, path.relative_to(store.root).as_posix(), 8192)
    _atomic(path, canonical({**ref, 'problem': str(problem)[:1000]}))


def status(store, project):
    try:
        answer = load(store, project)
        result = {'available': answer is not None}
        if answer is not None:
            ref = _json(store.root, pointer(store, project['id']).relative_to(store.root).as_posix(), 8192)
            result['detail'] = ref['problem']
        return result
    except (ValueError, OSError):
        return {'available': False, 'problem': 'The saved planning response cannot be read safely. Your source material is kept.'}
