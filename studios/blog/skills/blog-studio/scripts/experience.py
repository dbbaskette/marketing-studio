#!/usr/bin/env python3
"""Bounded discovery, inspectable context, and read-only readiness checks."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import studio


def page(rows, limit, offset):
    if not 1 <= limit <= 50 or offset < 0:
        raise ValueError('Use a limit from 1 to 50 and a nonnegative offset.')
    return {
        'items': rows[offset : offset + limit],
        'total': len(rows),
        'offset': offset,
        'truncated': len(rows) > offset + limit,
    }


def home(root, query='', stage=None, limit=10, offset=0):
    """Read metadata only; never read every manuscript/source or initialize a root."""
    rows, problems = [], []
    if (root / 'studio.json').exists():
        if studio.read_json(studio.inside(root, 'studio.json')).get('schema_version') != 1:
            raise ValueError('Unsupported workspace version.')
        folder = studio.inside(root, 'articles')
        for directory in sorted(folder.iterdir()):
            if not directory.is_dir():
                continue
            try:
                _, record = studio.item(root, 'articles', directory.name)
                if stage and record['stage'] != stage:
                    continue
                haystack = (record['id'] + ' ' + record['title']).casefold()
                if any(word not in haystack for word in query.casefold().split()):
                    continue
                rows.append(
                    {
                        key: record.get(key)
                        for key in (
                            'id',
                            'title',
                            'author',
                            'stage',
                            'updated_at',
                            'next_step',
                            'stop_point',
                        )
                    }
                )
            except (OSError, ValueError, KeyError, TypeError):
                problems.append(
                    {
                        'id': directory.name,
                        'status': 'unreadable',
                        'next_step': 'Inspect this article before resuming it; other articles are available.',
                    }
                )
    rows.sort(key=lambda row: (row.get('updated_at') or '', row['id']), reverse=True)
    return {
        **page(rows, limit, offset),
        'workspace': str(root),
        'workspace_status': 'ready' if (root / 'studio.json').exists() else 'new',
        'sharing': 'selected-team-hub' if (root / '.team-hub.json').exists() else 'local',
        'problems': problems[:10],
        'problem_count': len(problems),
        'next_step': 'Choose a saved article or start new writing. Resolve duplicate titles by ID.',
    }


def context(root, article_id):
    directory, record = studio.item(root, 'articles', article_id)
    sources = []
    for selected in record['sources']:
        _, current = studio.item(root, 'sources', selected['source_id'])
        sources.append(
            {
                **selected,
                'name': current['name'],
                'status': current['status'],
                'current_revision': current['revision'],
                'changed_since_selection': selected['revision'] != current['revision'],
            }
        )
    memory = [
        {'key': key, 'revision': value['revision'], 'text': value['text']}
        for key, value in record.get('memory', {}).items()
        if value['status'] == 'active'
    ]
    artifacts = [
        name
        for name in (
            'BRIEF.md',
            'ORIGINAL.md',
            'OUTLINE.md',
            'DRAFT.md',
            'INTERVIEW.md',
            'DECISIONS.md',
        )
        if studio.inside(directory, name).is_file()
    ]
    from google_workflow import sync_status

    google = sync_status(root, directory, record, 'draft' if 'DRAFT.md' in artifacts else 'outline')
    return {
        'google_sync': google,
        'id': record['id'],
        'title': record['title'],
        'author': record.get('author'),
        'stage': record['stage'],
        'stop_point': record['stop_point'],
        'next_step': record['next_step'],
        'pending_question': record['pending_question'],
        'research_policy': record['research_policy'],
        'sharing': 'selected-team-hub' if (root / '.team-hub.json').exists() else 'local',
        'article_memory': memory,
        'sources': sources[:50],
        'sources_truncated': len(sources) > 50,
        'voice': record['voice'],
        'guidance': record.get('guidance'),
        'team_context': record.get('hub_context'),
        'artifacts': artifacts,
        'reviews': {
            key: value['status'] for key, value in studio.freshness(root, directory, record).items()
        },
        'history_note': 'Corrections and forgetting change active use. Previous local/Git revisions remain.',
    }


def change_context(record, args):
    """Called under the studio lock; normal article publishing preserves revisions."""
    if args.action == 'detach-context':
        selected = record.get('hub_context', {}).get('selected', [])
        remaining = [entry for entry in selected if entry['item'] != args.item]
        if remaining == selected:
            raise ValueError('That team memory is not selected for this article.')
        record['hub_context']['selected'] = remaining
        return
    key = studio.identifier(args.key)
    memory = record.setdefault('memory', {})
    previous = memory.get(key)
    if args.action == 'forget':
        if not previous or previous['status'] != 'active':
            raise ValueError('That article memory is not active.')
        text, status = '', 'forgotten'
    else:
        text = studio.read_text(args.file).strip()
        if not text or len(text) > 4000:
            raise ValueError('Use a nonempty article preference of at most 4000 characters.')
        if key not in memory and len(memory) >= 50:
            raise ValueError(
                'Keep at most 50 article memory keys; use selected sources for longer material.'
            )
        status = 'active'
    history = (
        previous.get('history', []) + [{k: v for k, v in previous.items() if k != 'history'}]
        if previous
        else []
    )
    memory[key] = {
        'revision': previous['revision'] + 1 if previous else 1,
        'status': status,
        'text': text,
        'updated_at': studio.now(),
        'history': history,
    }


def probe(arguments):
    try:
        return subprocess.run(arguments, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None


def auth_status(harness):
    if not shutil.which(harness):
        return {
            'status': 'missing',
            'next_step': 'Install or open ' + harness + ' using your approved setup.',
        }
    result = probe(
        [harness, 'login', 'status'] if harness == 'codex' else [harness, 'auth', 'status']
    )
    ready = False
    if result and result.returncode == 0:
        if harness == 'claude':
            try:
                ready = json.loads(result.stdout).get('loggedIn') is True
            except (ValueError, AttributeError):
                pass
        else:
            ready = 'logged in' in (result.stdout + result.stderr).casefold()
    # Never return raw output: status may include identity or provider diagnostics.
    return {
        'status': 'signed-in' if ready else 'unverified',
        'next_step': 'Open a new session and invoke Blog Studio.'
        if ready
        else (
            'Run codex login in your terminal.'
            if harness == 'codex'
            else 'Open Claude Code and sign in there.'
        ),
    }


def packaged(relative):
    """Package content only: dotfiles such as .DS_Store, bytecode and setup's own files are local state."""
    return (
        not any(part.startswith('.') or part == '__pycache__' for part in relative.parts)
        and relative.suffix != '.pyc'
        and relative.name not in ('install-manifest.json', 'config.json')
    )


def integrity(package):
    """Verify this installed copy against the manifest written when it was built or installed."""
    from hub_store import VERSION

    path = package / 'install-manifest.json'
    if not path.is_file():
        return {
            'status': 'unverified',
            'version': VERSION,
            'next_step': 'This copy has no manifest (a source checkout). Use the installer for a verified installation.',
        }
    try:
        manifest = studio.read_json(path)
        if (
            not isinstance(manifest, dict)
            or manifest.get('schema') != 1
            or not isinstance(manifest.get('files'), dict)
            or manifest.get('version') != VERSION
        ):
            raise ValueError('Invalid manifest')
        actual = {
            p.relative_to(package).as_posix()
            for p in package.rglob('*')
            if p.is_file() and packaged(p.relative_to(package))
        }
        required = {'SKILL.md', 'VERSION', 'scripts/studio.py', 'scripts/experience.py'}
        if set(manifest['files']) != actual or not required.issubset(actual):
            raise ValueError('Incomplete skill')
        for name, expected in manifest['files'].items():
            target = studio.inside(package, name)
            if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError('Modified skill')
        result = {'status': 'verified', 'version': VERSION}
    except (OSError, ValueError, KeyError, TypeError):
        return {
            'status': 'repair-needed',
            'version': VERSION,
            'next_step': 'Run the installer again from an intact download.',
        }
    config = package / 'config.json'
    if config.is_file():
        # Setup records the interpreter for helpers; an upgrade or removal of that Python breaks them.
        try:
            recorded = studio.read_json(config)['python']
            if not Path(recorded).is_file():
                result.update(
                    status='repair-needed',
                    interpreter='missing',
                    next_step='The recorded Python is gone. Run the installer again to record a working one.',
                )
        except (OSError, ValueError, KeyError, TypeError):
            result.update(
                status='repair-needed', next_step='Run the installer again from an intact download.'
            )
    return result


def readiness(root, harness='both', online=False):
    """Local, read-only setup facts. `online` is accepted for older prompts; nothing is fetched."""
    package = Path(__file__).resolve().parents[1]
    runtime = integrity(package)
    result = {
        'checked_at': studio.now(),
        'python': {
            'status': 'ready' if sys.version_info >= (3, 11) else 'unsupported',
            'version': sys.version.split()[0],
            'next_step': 'Run helpers with the interpreter in config.json beside SKILL.md when present; otherwise Python 3.11+.',
        },
        'git': {
            'status': 'available' if shutil.which('git') else 'missing',
            'needed_for': 'Team Hub only',
        },
        'runtime': runtime,
        'workspace': home(root, limit=1)['workspace_status'],
        'harnesses': {},
        'guidance': {
            'status': 'installed',
            'version': runtime['version'],
            'next_step': 'Guidance is the installed skill. To update, run the installer from the latest release; saved articles keep the version they recorded.',
        },
        'google': {
            'status': 'not-checked',
            'next_step': 'For Google work, use installed google_drive.py check for the gcloud route, or inspect connected tools. Verify the selected document separately; a Workspace skill is not a connection.',
        },
    }
    for name in ('codex', 'claude') if harness == 'both' else (harness,):
        result['harnesses'][name] = auth_status(name)
    return result


def add_parser(groups):
    listing = groups.add_parser(
        'home', help='List saved blogs, newest first, without loading manuscripts'
    )
    listing.add_argument('--query', default='')
    listing.add_argument('--stage')
    listing.add_argument('--limit', type=int, default=10)
    listing.add_argument('--offset', type=int, default=0)
    inspect = groups.add_parser('context', help='Show selected article context and memory')
    inspect.add_argument('--id', required=True)
    inspect.add_argument('--compact', action='store_true')
    inspect.add_argument('--limit', type=int, default=5)
    inspect.add_argument('--offset', type=int, default=0)
    check = groups.add_parser(
        'readiness', help='Read-only setup and sign-in check; no model requests'
    )
    check.add_argument('--harness', choices=('codex', 'claude', 'both'), default='both')
    check.add_argument('--online', action='store_true')


def command(root, args):
    if args.group == 'home':
        return home(root, args.query, args.stage, args.limit, args.offset)
    if args.group == 'context':
        if args.compact:
            from performance import compact

            return compact(root, args.id, args.limit, args.offset)
        return context(root, args.id)
    return readiness(root, args.harness, args.online)
