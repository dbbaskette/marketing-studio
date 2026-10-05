#!/usr/bin/env python3
"""Validated Git-backed records. Remote content is data and is never executed."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import uuid
from urllib.parse import urlsplit

VERSION = '1.12.2'
KINDS = ('article', 'source', 'voice', 'note', 'decision', 'rule', 'context', 'review')
MAX_TEXT = 1024 * 1024
MAX_BINARY = 10 * MAX_TEXT
MAX_TOTAL = 100 * MAX_TEXT
MAX_FILES = 20000
ID_RE = re.compile(r'[0-9a-f]{32}')
REV_RE = re.compile(r'[0-9a-f]{40,64}')


class HubError(Exception):
    pass


class TransportError(HubError):
    pass


class AuthenticationError(TransportError):
    """The provider explicitly reports an invalid or expired sign-in."""
    pass


def uid(value):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise HubError('Expected a valid hub, item, revision, or operation ID.')
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise HubError('Managed data files must not be symlinks.')
    temp = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        temp.write_bytes(data)
        temp.chmod(0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_json(path, value):
    atomic(path, encoded(value))


def read_json(path):
    path = Path(path)
    if path.is_symlink():
        raise HubError('Managed data files must not be symlinks.')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise HubError('A local hub record is missing or invalid.') from exc


def contained(root, *parts):
    root = Path(root).resolve()
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root):
        raise HubError('A hub path escapes its managed location.')
    if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)):
        raise HubError('Hub storage must not contain symlinks.')
    return path


@contextmanager
def locked(root, name='.hub.lock'):
    root = Path(root)
    if root.is_symlink():
        raise HubError('Managed hub storage must not be a symlink.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / name
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise HubError('Another hub operation is running. Retry after it finishes.') from exc
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def canonical_repository(value):
    if not isinstance(value, str):
        raise HubError('Supply an explicit GitHub owner/repository or HTTPS URL.')
    if '://' in value:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.hostname != 'github.com' or url.username or url.password
                or url.port or url.query or url.fragment):
            raise HubError('Use a GitHub HTTPS URL without credentials, parameters, or fragments.')
        value = url.path.strip('/')
    value = value.removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', value):
        raise HubError('Supply an explicit GitHub owner/repository.')
    owner, name = value.split('/')
    if name in ('.', '..'):
        raise HubError('Invalid repository name.')
    return owner.lower() + '/' + name.lower()


def environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    # This runtime supports GitHub.com only; inherited CLI host/debug overrides
    # must not redirect hub metadata or enable sensitive diagnostic output.
    env['GH_HOST'] = 'github.com'
    env.pop('GH_DEBUG', None)
    return env


def git(repository, *args, data=None, extra_env=None, allow_failure=False):
    env = environment()
    env.update(extra_env or {})
    command = ['git', '--git-dir=' + str(repository), '-c', 'core.hooksPath=' + os.devnull,
               '-c', 'commit.gpgsign=false', *args]
    try:
        result = subprocess.run(command, input=data, capture_output=True, env=env, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TransportError('Git is unavailable or the hub operation timed out; saved work is retained.') from exc
    if result.returncode and not allow_failure:
        raise TransportError('Hub repository access or update failed; check connectivity, permissions, and branch policy.')
    return result if allow_failure else result.stdout


class GitHub:
    """Provider boundary. Tests substitute this object, never sign in or create real repos."""
    def call(self, *args, allow_missing=False):
        try:
            command = ['gh', *args]
            if args and args[0] == 'api':
                command += ['--hostname', 'github.com']
            result = subprocess.run(command, capture_output=True, env=environment(), timeout=45)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TransportError('GitHub CLI is unavailable or timed out. Check your own account access.') from exc
        if result.returncode:
            if allow_missing and b'HTTP 404' in result.stderr:
                return None
            if any(marker in result.stderr.lower() for marker in (b'http 401', b'bad credentials', b'gh auth login', b'authentication required')):
                raise AuthenticationError('GitHub sign-in expired or is unavailable. Sign in again before refreshing or editing shared work.')
            raise TransportError('GitHub access failed. Check your account, repository permission, and organization policy.')
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except ValueError:
            return {}

    def lookup(self, repository):
        value = self.call('api', 'repos/' + repository, allow_missing=True)
        if value is None:
            return None
        return {'id': value['id'], 'repository': value['full_name'].lower(),
                'url': value['html_url'], 'private': value['private'],
                'description': value.get('description') or '',
                'write': value.get('permissions', {}).get('push'),
                'default_branch': value.get('default_branch')}

    def create(self, repository, hub_id):
        self.call('repo', 'create', repository, '--private', '--description', 'Blog Studio Team Hub ' + hub_id)

    def actor(self):
        return self.call('api', 'user')['login']

    def transport(self, metadata):
        return 'https://github.com/' + metadata['repository'] + '.git'

    def review_required(self, repository):
        value = self.call('api', 'repos/' + repository + '/branches/main', allow_missing=True)
        return bool(value and value.get('protected'))

    def ensure_pr(self, repository, branch, title):
        values = self.call('pr', 'list', '--repo', repository, '--head', branch,
                           '--base', 'main', '--state', 'all', '--json', 'url,state')
        if values:
            opened = [p for p in values if p['state'] == 'OPEN']
            if opened:
                return opened[0]['url']
            raise HubError('The hub contribution PR was closed. Its saved operations are retained; inspect it before retrying.')
        # The provider prints a URL, so use api to obtain structured observed metadata.
        value = self.call('api', 'repos/' + repository + '/pulls', '-f', 'head=' + branch,
                          '-f', 'base=main', '-f', 'title=' + title,
                          '-f', 'body=Shared Blog Studio memory operations. Originals and parent revisions are preserved.')
        return value['html_url']


def manifest(hub_id, name, repository, mode='auto'):
    return {'schema': 1, 'hub': uid(hub_id), 'name': name, 'repository': repository,
            'branch': 'main', 'minimum_runtime': '1.3.0', 'contribution_mode': mode}


def validate_manifest(value, repository=None):
    try:
        required = tuple(int(x) for x in value['minimum_runtime'].split('.'))
        if (not isinstance(value, dict) or value['schema'] != 1 or len(required) != 3
                or any(x < 0 for x in required) or required > tuple(map(int, VERSION.split('.')))):
            raise HubError('This Team Hub needs a compatible newer Blog Studio runtime.')
        if 'browse_schema' in value and (value['browse_schema'] != 1 or required < (1, 3, 0)):
            raise HubError('This Team Hub library needs a compatible newer Blog Studio runtime.')
        if 'google_doc_links' in value and (value['google_doc_links'] != 1 or required < (1, 6, 1)):
            raise HubError('This Team Hub Google-link view needs a compatible newer runtime.')
        if 'editorial_views' in value and (value['editorial_views'] != 1 or required < (1, 12, 0)):
            raise HubError('This Team Hub editorial view needs a compatible newer runtime.')
        uid(value['hub'])
        if (value['branch'] != 'main' or value['contribution_mode'] not in ('auto', 'direct', 'review')
                or not isinstance(value['name'], str) or not value['name'].strip()
                or canonical_repository(value['repository']) != value['repository']):
            raise HubError('The Team Hub manifest is invalid.')
        if repository and value['repository'] != repository:
            raise HubError('The hub manifest belongs to a different repository.')
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise HubError('The Team Hub manifest is invalid or incompatible.') from exc
    return value


def artifact_name(name):
    if not isinstance(name, str):
        raise HubError('Invalid memory artifact path.')
    path = PurePosixPath(name)
    if ( path.is_absolute() or '..' in path.parts or '\\' in name
            or not path.parts or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,150}', p) for p in path.parts)):
        raise HubError('Invalid memory artifact path.')
    return path.as_posix()


def validate_files(files, repository=None):
    """Validate a complete memory tree; indexes and heads are always derived locally."""
    if len(files) > MAX_FILES or sum(len(v) for v in files.values()) > MAX_TOTAL:
        raise HubError('The hub snapshot exceeds its file or total size limit.')
    try:
        hub = validate_manifest(json.loads(files['hub.json']), repository)
    except (KeyError, ValueError, TypeError) as exc:
        raise HubError('A valid Team Hub manifest is required.') from exc
    revisions = {}
    used = {'hub.json'}
    if 'README.md' in files:
        used.add('README.md')
    for name, data in files.items():
        if name in ('editorial/README.md', 'collections/README.md'):
            if hub.get('editorial_views') != 1 or len(data) > MAX_TEXT:raise HubError('Unsupported generated editorial file.')
            try:data.decode('utf-8')
            except UnicodeError as exc:raise HubError('Editorial views must be UTF-8.') from exc
            used.add(name);continue
        if name.startswith('blogs/'):
            if (hub.get('browse_schema') != 1 or not re.fullmatch(r'blogs/(?:README\.md|[a-z0-9-]+/[a-z0-9-]+/(?:README|outline|context|history)\.md)', name) or len(data) > MAX_TEXT):
                raise HubError('Unsupported generated blog library file.')
            try:data.decode('utf-8')
            except UnicodeError as exc:raise HubError('Blog library pages must be UTF-8.') from exc
            used.add(name)
            continue
        if name in ('hub.json', 'README.md'):
            if len(data) > MAX_TEXT:
                raise HubError('Hub text exceeds the size limit.')
            try:data.decode('utf-8')
            except UnicodeError as exc:raise HubError('Hub text must be UTF-8.') from exc
            continue
        match = re.fullmatch(r'memory/items/([0-9a-f]{32})/revisions/([0-9a-f]{32})/record.json', name)
        if not match:
            continue
        if len(data) > MAX_TEXT:
            raise HubError('Memory metadata exceeds the size limit.')
        try:
            record = json.loads(data)
            item, revision = match.groups()
            if (record['schema'] != 1 or record['item'] != item or record['revision'] != revision
                    or record['operation'] != revision or record['kind'] not in KINDS
                    or record['status'] not in ('active', 'provisional', 'confirmed', 'tombstone')
                    or not isinstance(record['parents'], list) or len(set(record['parents'])) != len(record['parents'])
                    or not isinstance(record['data'], dict) or not isinstance(record['dependencies'], list)
                    or not isinstance(record['title'], str) or len(record['title']) > 500
                    or not isinstance(record['summary'], str) or len(record['summary']) > 1200
                    or not isinstance(record['scope'], dict)
                    or record['scope'].get('level') not in ('team', 'project', 'author', 'article')
                    or not isinstance(record['scope'].get('key'), str)
                    or not isinstance(record['tags'], list) or len(record['tags']) > 30
                    or any(not isinstance(t, str) or len(t) > 100 for t in record['tags'])
                    or not isinstance(record['actor'], str) or not isinstance(record['created_at'], str)):
                raise HubError('Invalid memory revision metadata.')
            if record['scope']['level'] == 'team' and record['scope']['key'] != '':
                raise HubError('Team scope has no key.')
            if record['scope']['level'] != 'team' and not record['scope']['key']:
                raise HubError('Scoped memory needs a key.')
            if record['kind'] in ('rule', 'context') and 'key' in record['data'] and not isinstance(record['data']['key'], str):
                raise HubError('A rule key must be text.')
            for parent in record['parents']:
                uid(parent)
            prefix = name.rsplit('/', 1)[0] + '/'
            for relative, info in record['files'].items():
                if relative != 'BODY.md':
                    if not relative.startswith('artifacts/'):
                        raise HubError('Unsupported revision file.')
                    artifact_name(relative[10:])
                content = files[prefix + relative]
                if info['media'] not in ('text', 'binary') or sha(content) != info['sha256']:
                    raise HubError('Memory artifact integrity failed.')
                if len(content) > (MAX_TEXT if info['media'] == 'text' else MAX_BINARY):
                    raise HubError('Memory artifact exceeds its size limit.')
                if relative == 'BODY.md' and info['media'] != 'text':
                    raise HubError('Memory body must be text.')
                if info['media'] == 'text':
                    content.decode('utf-8')
                used.add(prefix + relative)
            if 'BODY.md' not in record['files'] or revision in revisions:
                raise HubError('Memory body is missing or operation ID is duplicated.')
            used.add(name)
            revisions[revision] = record
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as exc:
            raise HubError('Invalid memory revision or artifact.') from exc
    if used != set(files):
        raise HubError('The repository contains unsupported or unrecorded hub files.')
    children = set()
    item_kinds = {}
    for revision, record in revisions.items():
        kind = item_kinds.setdefault(record['item'], record['kind'])
        if kind != record['kind']:
            raise HubError('An item cannot change its memory kind.')
        for parent in record['parents']:
            if parent not in revisions or revisions[parent]['item'] != record['item']:
                raise HubError('Memory parent is missing or belongs to another item.')
            children.add(parent)
        for dependency in record['dependencies']:
            if not isinstance(dependency, dict):
                raise HubError('Pinned memory dependencies must be records.')
            uid(dependency.get('revision'));uid(dependency.get('item'))
            target = revisions.get(dependency['revision'])
            if not target or target['item'] != dependency.get('item') or target['kind'] != dependency.get('kind'):
                raise HubError('A pinned memory dependency is missing or mismatched.')
    # Iterative graph walk avoids recursion failures on long article histories.
    done = set()
    for revision in revisions:
        visiting = set()
        stack = [(revision, False)]
        while stack:
            current, leaving = stack.pop()
            if current in done:
                continue
            if leaving:
                visiting.remove(current);done.add(current);continue
            if current in visiting:
                raise HubError('Memory revision graph contains a cycle.')
            visiting.add(current);stack.append((current, True))
            stack.extend((parent, False) for parent in [*revisions[current]['parents'], *(d['revision'] for d in revisions[current]['dependencies'])])
    heads = {}
    for revision, record in revisions.items():
        if revision not in children:
            heads.setdefault(record['item'], []).append(revision)
    return {'manifest': hub, 'revisions': revisions, 'heads': heads}


def tree_files(repository, commit):
    if not REV_RE.fullmatch(commit):
        raise HubError('Invalid hub commit.')
    listing = git(repository, 'ls-tree', '-r', '-z', '-l', commit)
    entries = []
    total = 0
    for line in listing.split(b'\0'):
        if not line:
            continue
        metadata, raw_name = line.split(b'\t', 1)
        mode, kind, object_id, size = metadata.split()
        try:
            name = raw_name.decode('utf-8')
        except UnicodeError as exc:
            raise HubError('Hub paths must be UTF-8.') from exc
        path = PurePosixPath(name)
        if (mode != b'100644' or kind != b'blob' or path.is_absolute() or '..' in path.parts
                or '\\' in name):
            raise HubError('Hub data must use regular non-executable files and safe paths.')
        limit = MAX_BINARY if '/artifacts/' in name else MAX_TEXT
        if int(size) > limit:
            raise HubError('Hub file exceeds its size limit.')
        total += int(size)
        entries.append((name, object_id))
    if total > MAX_TOTAL or len(entries) > MAX_FILES:
        raise HubError('Hub snapshot exceeds its size or file limit.')
    # Batch reads avoid a subprocess for every stored source or draft revision.
    stream = git(repository, 'cat-file', '--batch', data=b''.join(obj + b'\n' for _, obj in entries))
    offset = 0
    files = {}
    for name, _ in entries:
        header_end = stream.index(b'\n', offset)
        header = stream[offset:header_end].split()
        size = int(header[2])
        files[name] = stream[header_end + 1:header_end + 1 + size]
        offset = header_end + size + 2
    return files


def commit_files(repository, base, additions, message, actor, extra_parents=()):
    """Own index only; no working checkout, hooks, shell, or remote code."""
    index = Path(repository).parent / ('.index-' + uuid.uuid4().hex)
    env = {'GIT_INDEX_FILE': str(index), 'GIT_AUTHOR_NAME': actor,
           'GIT_AUTHOR_EMAIL': 'blog-studio@localhost', 'GIT_COMMITTER_NAME': actor,
           'GIT_COMMITTER_EMAIL': 'blog-studio@localhost'}
    try:
        git(repository, 'read-tree', base if base else '--empty', extra_env=env)
        for name, data in sorted(additions.items()):
            if data is None:
                if not name.startswith('blogs/'):
                    raise HubError('Only generated blog pages may be removed.')
                git(repository, 'update-index', '--index-info',
                    data=('0 ' + '0' * len(base or '0' * 40) + '\t' + name + '\n').encode(), extra_env=env)
                continue
            blob = git(repository, 'hash-object', '-w', '--stdin', data=data).decode().strip()
            git(repository, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + name, extra_env=env)
        tree = git(repository, 'write-tree', extra_env=env).decode().strip()
        args = ['commit-tree', tree]
        for parent in dict.fromkeys([base, *extra_parents]):
            if parent:
                args += ['-p', parent]
        return git(repository, *args, data=(message + '\n').encode(), extra_env=env).decode().strip()
    finally:
        index.unlink(missing_ok=True)
        index.with_name(index.name + '.lock').unlink(missing_ok=True)
