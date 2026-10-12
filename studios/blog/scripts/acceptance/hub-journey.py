#!/usr/bin/env python3
"""Hub CLI walkthrough using synthetic content only.

--live creates a private GitHub repository (needs explicit authorization).
--local-fixture needs no account or network: a folder of bare repositories and
a small stand-in for the GitHub CLI take the provider's place, and the helpers
run from this source tree. Both walk the same commands through the real
hub.py and studio.py entry points.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

# Answers the handful of GitHub CLI calls the Hub runtime makes, from local files.
LOCAL_GH = r'''#!/usr/bin/env python3
"""Offline stand-in for the GitHub CLI used by the Hub acceptance walkthrough."""
import json
from pathlib import Path
import subprocess
import sys

FIXTURE = Path(__file__).resolve().parent.parent
REMOTES = FIXTURE / 'remotes'
STATE = FIXTURE / 'github.json'


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {'repos': {}, 'pulls': {}}


def missing():
    sys.stderr.write('gh: Not Found (HTTP 404)\\n')
    return 1


def main(argv):
    state = load()
    if argv[:1] == ['api'] and len(argv) > 1:
        path = argv[1]
        if path == 'user':
            print(json.dumps({'login': 'synthetic-member'}))
            return 0
        parts = path.split('/')
        name = '/'.join(parts[1:3]).lower()
        repo = state['repos'].get(name)
        if parts[0] != 'repos' or repo is None:
            return missing()
        if len(parts) == 3:
            print(json.dumps({'id': repo['id'], 'full_name': name, 'html_url': 'https://github.com/' + name,
                              'private': True, 'description': repo['description'],
                              'permissions': {'push': True}, 'default_branch': 'main'}))
            return 0
        if parts[3:] == ['branches', 'main']:
            print(json.dumps({'name': 'main', 'protected': False}))
            return 0
        if parts[3:] == ['pulls']:
            fields = dict(value.split('=', 1) for flag, value in zip(argv[2:], argv[3:]) if flag == '-f')
            url = 'https://github.com/' + name + '/pull/' + str(len(state['pulls']) + 1)
            state['pulls'][name + ':' + fields['head']] = {'url': url, 'state': 'OPEN'}
            STATE.write_text(json.dumps(state, indent=2))
            print(json.dumps({'html_url': url}))
            return 0
        return missing()
    if argv[:2] == ['repo', 'create']:
        name = argv[2].lower()
        if name in state['repos']:
            sys.stderr.write('gh: repository already exists\\n')
            return 1
        path = REMOTES / (name + '.git')
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '--bare', '--quiet', '--initial-branch=main', str(path)], check=True)
        state['repos'][name] = {'id': len(state['repos']) + 1, 'description': argv[argv.index('--description') + 1]}
        STATE.write_text(json.dumps(state, indent=2))
        return 0
    if argv[:2] == ['pr', 'list']:
        name = argv[argv.index('--repo') + 1].lower()
        head = argv[argv.index('--head') + 1]
        found = state['pulls'].get(name + ':' + head)
        print(json.dumps([found] if found else []))
        return 0
    sys.stderr.write('gh stand-in: unsupported command\\n')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
'''


def local_fixture(base):
    """Folders that stand in for GitHub: a gh look-alike, a HOME, bare remotes."""
    fixture = base / 'local-github'
    for name in ('bin', 'home', 'remotes'):
        (fixture / name).mkdir(parents=True, exist_ok=True)
    shim = fixture / 'bin' / 'gh'
    shim.write_text(LOCAL_GH)
    shim.chmod(0o755)
    # The runtime always addresses https://github.com/<owner>/<repo>.git; Git is
    # told to read that from the local folder instead. No other setting is changed.
    (fixture / 'home' / '.gitconfig').write_text(
        '[url "' + str(fixture / 'remotes') + '/"]\n\tinsteadOf = https://github.com/\n'
    )
    return fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--repo',
        help='New private GitHub owner/repository to create '
        '(any synthetic name with --local-fixture)',
    )
    parser.add_argument(
        '--run-directory',
        required=True,
        type=Path,
        help='New absolute directory for isolated homes and receipts',
    )
    parser.add_argument(
        '--join-existing',
        action='store_true',
        help='Use the same authorized private test Hub for another isolated run',
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume failed setup before any synthetic documents were saved',
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Authorize creating the named private repository and posting synthetic fixtures',
    )
    parser.add_argument(
        '--local-fixture',
        action='store_true',
        help='No account or network: local bare repositories and a stand-in GitHub CLI; '
        'runs this source tree',
    )
    args = parser.parse_args()
    if args.live == args.local_fixture:
        parser.error(
            'Choose exactly one: --live (creates a private remote repository) or --local-fixture (offline)'
        )
    if args.local_fixture:
        args.repo = args.repo or 'synthetic/acceptance-hub'
        if args.join_existing or args.resume:
            parser.error('--local-fixture always starts from a new run directory')
    elif not args.repo:
        parser.error('--live needs --repo')
    base = args.run_directory.expanduser()
    if not base.is_absolute():
        parser.error('Use an absolute run directory')
    base = base.resolve()  # the runtime reports resolved clone paths (e.g. /private/tmp on macOS)
    if base.exists():
        if not args.resume:
            parser.error('Use a new run directory, or --resume for failed setup')
        previous = json.loads((base / 'report.json').read_text())
        if (
            previous['repository'] != args.repo
            or previous['status'] == 'PASS'
            or any(step['step'].startswith('studio ') for step in previous['steps'])
        ):
            parser.error(
                'Only failed setup for this same repository may be resumed; later runs need manual inspection'
            )
    source = Path(__file__).resolve().parents[2]
    original_home = Path.home()
    base.mkdir(parents=True, mode=0o700, exist_ok=args.resume)
    receipts = []
    report = {
        'repository': args.repo,
        'content': 'synthetic only',
        'status': 'running',
        'steps': receipts,
        'provider': 'local fixture (no account, no network)' if args.local_fixture else 'GitHub',
    }
    fixture = local_fixture(base) if args.local_fixture else None

    def record():
        (base / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def runtime(home):
        """Folder holding hub.py and studio.py for one member."""
        if args.local_fixture:
            return source / 'skills/blog-studio/scripts'
        return home / '.local/share/blog-studio/current/scripts'

    def registry(home):
        return home / 'hubs' if args.local_fixture else home / '.local/share/blog-studio/hubs'

    def run(label, argv, home, expected=0, raw=False):
        if args.local_fixture:
            env = dict(
                os.environ,
                HOME=str(fixture / 'home'),
                PYTHONDONTWRITEBYTECODE='1',
                PATH=str(fixture / 'bin') + os.pathsep + os.environ.get('PATH', ''),
            )
            env.pop('GH_CONFIG_DIR', None)
        else:
            env = dict(
                os.environ,
                HOME=str(original_home),
                GH_HOST='github.com',
                GH_CONFIG_DIR=os.environ.get('GH_CONFIG_DIR', str(original_home / '.config/gh')),
            )
        env.pop('GH_DEBUG', None)
        result = subprocess.run(
            [str(v) for v in argv], env=env, capture_output=True, text=True, timeout=120
        )
        receipt = {'step': label, 'command': [str(v) for v in argv], 'exit_code': result.returncode}
        outcome = result.stdout.strip() or result.stderr.strip()
        try:
            parsed = json.loads(outcome)
            if isinstance(parsed, dict):
                sync = parsed.get('hub_sync') if isinstance(parsed.get('hub_sync'), dict) else {}
                receipt['outcome'] = {
                    key: value
                    for key, value in {
                        'status': parsed.get('status'),
                        'hub_sync': sync.get('status'),
                        'error': parsed.get('error'),
                        'queued': parsed.get('queued', sync.get('queued')),
                        'held': parsed.get('held', sync.get('held')),
                        'conflicts': parsed.get('conflicts', sync.get('conflicts')),
                    }.items()
                    if value is not None
                }
        except ValueError:
            receipt['outcome'] = outcome[:300]
        receipts.append(receipt)
        record()
        if (result.returncode == 0) != (expected == 0):
            raise RuntimeError(label + ': unexpected result\n' + result.stderr + result.stdout)
        if expected:
            return result.stdout + result.stderr
        return result.stdout if raw else json.loads(result.stdout)

    def fixture_file(name, text):
        path = base / name
        path.write_text(text)
        return path

    try:
        homes = [base / name for name in ('author-a', 'author-b')]
        for home in homes:
            if args.local_fixture:
                home.mkdir()
                continue
            run(
                'install isolated ' + home.name,
                [
                    sys.executable,
                    source / 'installer/install.py',
                    'install',
                    '--home',
                    home,
                    '--source',
                    source / 'skills/blog-studio',
                    '--target',
                    'both',
                    '--yes',
                    '--json',
                ],
                home,
            )

        def hub_command(index, *words):
            home = homes[index]
            return [sys.executable, runtime(home) / 'hub.py', '--registry', registry(home), *words]

        def hub(index, *words, expected=0):
            label = 'hub ' + ' '.join(str(w) for w in words if not str(w).startswith('/'))[:70]
            return run(label, hub_command(index, *words), homes[index], expected=expected)

        def studio(index, *words, expected=0):
            home = homes[index]
            return run(
                'studio ' + ' '.join(str(w) for w in words[:2]),
                [sys.executable, runtime(home) / 'studio.py', '--root', workspaces[index], *words],
                home,
                expected=expected,
            )

        created = hub(
            0,
            *(
                ['join', '--repo', args.repo]
                if args.join_existing
                else [
                    'create',
                    '--repo',
                    args.repo,
                    '--name',
                    'Synthetic Blog Studio acceptance Hub',
                ]
            ),
            '--destination',
            homes[0] / 'blogs' / args.repo.split('/')[1],
        )
        joined = hub(
            1,
            'join',
            '--repo',
            args.repo,
            '--destination',
            homes[1] / 'blogs' / args.repo.split('/')[1],
        )
        assert created['hub'] == joined['hub']
        workspaces = [Path(value['workspace']) for value in (created, joined)]
        clones = [Path(value['clone']) for value in (created, joined)]
        for home, clone in zip(homes, clones, strict=False):
            assert clone == home / 'blogs' / args.repo.split('/')[1]
            assert (clone / '.git').is_dir()
        title = 'Synthetic ExampleDB tutorial ' + base.name
        renamed = 'Synthetic ExampleDB walkthrough ' + base.name
        draft = fixture_file(
            'synthetic-blog.md',
            '# Synthetic ExampleDB tutorial\n\nThis fictional product is only an acceptance fixture.\n\n## Prerequisites\n\nUse a disposable example.\n\n## Steps\n\nRead teh sample configuration and verify it.\n',
        )
        evidence = fixture_file(
            'synthetic-source.md',
            '# Synthetic source\n\nExampleDB is fictional. No real performance or product claims are made.\n',
        )
        voice = fixture_file(
            'synthetic-voice.md', 'Use short sentences. Label fictional examples clearly.\n'
        )
        review = fixture_file(
            'synthetic-review.json',
            json.dumps(
                {
                    'findings': [
                        {
                            'before': 'teh',
                            'after': 'the',
                            'reason': 'Typo in the synthetic example.',
                        }
                    ]
                }
            ),
        )
        source_id = studio(
            0,
            'source',
            'add',
            '--name',
            'Synthetic ExampleDB source',
            '--file',
            evidence,
            '--purpose',
            'reference',
            '--purpose',
            'voice-sample',
        )['id']
        profile = studio(
            0,
            'profile',
            'create',
            '--name',
            'Synthetic author',
            '--guide-file',
            voice,
            '--sample',
            source_id,
        )['id']
        article = studio(
            0,
            'article',
            'create',
            '--title',
            title,
            '--mode',
            'existing',
            '--author',
            'Synthetic Author',
            '--profile',
            profile,
            '--research',
            'supplied-only',
        )['id']
        studio(0, 'article', 'attach', '--id', article, '--source', source_id)
        for kind in ('original', 'draft'):
            studio(0, 'article', 'save', '--id', article, '--kind', kind, '--file', draft)
        studio(
            0,
            'article',
            'review',
            '--id',
            article,
            '--check',
            'proofread',
            '--status',
            'current',
            '--file',
            review,
        )
        found = hub(0, '--workspace', workspaces[0], 'find', '--kind', 'article', '--query', title)
        assert found['total'] == 1
        shared_id = found['items'][0]['item']
        checked = hub(1, '--workspace', workspaces[1], 'checkout-workspace', '--article', shared_id)
        second = checked['items'][0]['local_id']
        assert (
            workspaces[1] / 'articles' / second / 'ORIGINAL.md'
        ).read_bytes() == draft.read_bytes()
        edited = fixture_file(
            'synthetic-edited-blog.md', draft.read_text().replace('teh sample', 'the sample')
        )
        studio(1, 'article', 'save', '--id', second, '--kind', 'draft', '--file', edited)
        hub(0, '--workspace', workspaces[0], 'checkout-workspace', '--article', shared_id)
        assert (
            workspaces[0] / 'articles' / article / 'DRAFT.md'
        ).read_bytes() == edited.read_bytes()
        studio(0, 'article', 'rename', '--id', article, '--title', renamed)
        # The second clone is now one save behind. A small change there must not
        # become a competing version: it stays local with a distinct status.
        behind = studio(
            1,
            'article',
            'progress',
            '--id',
            second,
            '--stage',
            'review',
            '--next-step',
            'Synthetic note from a clone that is one save behind',
        )
        assert behind['hub_sync']['status'] == 'newer-hub-revision', behind['hub_sync']
        assert '--fork' in behind['hub_sync']['next_step'] and behind['hub_sync']['held'] == 1
        assert hub(0, '--workspace', workspaces[0], 'refresh')['conflicts'] == 0
        assert studio(1, 'status', '--id', second)['hub']['status'] == 'newer-hub-revision'
        # Resuming the shared version never discards that unshared work silently...
        refused = hub(
            1,
            '--workspace',
            workspaces[1],
            'checkout-workspace',
            '--article',
            shared_id,
            expected=1,
        )
        assert 'unshared local edits' in refused
        # ...and the explicit choice keeps it as a local backup.
        hub(
            1,
            '--workspace',
            workspaces[1],
            'checkout-workspace',
            '--article',
            shared_id,
            '--set-aside-local',
        )
        assert (
            json.loads((workspaces[1] / 'articles' / second / 'session.json').read_text())['title']
            == renamed
        )
        backups = list((workspaces[1] / '.hub-history' / second).glob('*/session.json'))
        assert any('one save behind' in path.read_text() for path in backups)
        resumed = studio(
            1,
            'article',
            'note',
            '--id',
            second,
            '--kind',
            'decision',
            '--text',
            'Synthetic note after resuming',
        )
        assert resumed['hub_sync']['status'] == 'shared' and resumed['hub_sync']['held'] == 0
        hub(0, '--workspace', workspaces[0], 'checkout-workspace', '--article', shared_id)
        # Earlier drafts travel with the blog, so "undo" works on either clone.
        history = sorted(
            path.name
            for path in (workspaces[1] / 'articles' / second / 'history').glob('draft-*.md')
        )
        assert history, 'the second clone has no earlier drafts'
        # A source too large to share is refused at intake, naming the limit.
        oversized = fixture_file(
            'synthetic-oversized-source.md', 'Synthetic filler sentence. ' * 45000
        )
        too_large = studio(
            0,
            'source',
            'add',
            '--name',
            'Synthetic oversized source',
            '--file',
            oversized,
            '--purpose',
            'reference',
            expected=1,
        )
        assert 'limited to 1,048,576 bytes' in too_large and 'Nothing was saved' in too_large
        studio(0, 'status', '--id', article)
        studio(0, 'home')
        studio(0, 'editorial', 'board')
        note = fixture_file('synthetic-team-note.md', 'Acceptance-only shared note.\n')
        queued = hub(
            0,
            '--workspace',
            workspaces[0],
            'remember',
            '--title',
            'Synthetic offline note',
            '--file',
            note,
            '--offline',
        )
        assert queued['queued'] >= 1
        synced = hub(0, '--workspace', workspaces[0], 'sync')
        assert synced['queued'] == 0 and synced['status'] == 'shared'
        readme = clones[0] / 'README.md'
        original = readme.read_bytes()
        try:
            readme.write_bytes(original + b'\nSynthetic unsaved checkout edit.\n')
            failure = run(
                'dirty checkout is protected',
                hub_command(0, '--workspace', workspaces[0], 'refresh'),
                homes[0],
                expected=1,
            )
            assert 'local edits' in failure and 'README.md' in failure
        finally:
            readme.write_bytes(original)
        hub(0, '--workspace', workspaces[0], 'refresh')
        hub(1, '--workspace', workspaces[1], 'refresh')
        hub(1, '--workspace', workspaces[1], 'leave')
        hub(1, 'join', '--repo', args.repo)
        for index in (0, 1):
            status = hub(index, '--workspace', workspaces[index], 'status')
            assert status['queued'] == 0 and status['conflicts'] == 0
            pages = [
                path
                for path in clones[index].glob('blogs/*/*/README.md')
                if renamed in path.read_text()
            ]
            assert len(pages) == 1
            assert (pages[0].parent / 'draft.md').is_file()
            assert (pages[0].parent / 'reviews/README.md').is_file()
            assert b'What changed' in (pages[0].parent / 'history.md').read_bytes()
        # Build a legacy-layout fixture from this run's synthetic clone, then
        # exercise the actual migration command with an offline save in its outbox.
        legacy = base / 'legacy-fixture'
        shutil.copytree(workspaces[1] / 'hub', legacy)
        revision = hub(1, '--workspace', workspaces[1], 'status')['revision']
        for words in (
            ['init', '--bare', '--quiet', '--initial-branch=main'],
            ['fetch', '--quiet', str(clones[1] / '.git'), revision],
            ['update-ref', 'refs/heads/main', revision],
        ):
            run(
                'prepare synthetic legacy fixture',
                [
                    'git',
                    '--git-dir=' + str(legacy / 'repository.git'),
                    '-c',
                    'core.hooksPath=' + os.devnull,
                    *words,
                ],
                homes[1],
                raw=True,
            )
        registry_path = registry(homes[1]) / 'registry.json'
        registered = json.loads(registry_path.read_text())
        registered['hubs'][created['hub']]['path'] = str(legacy)
        registered['hubs'][created['hub']].pop('layout')
        config_path = legacy / 'config.json'
        config = json.loads(config_path.read_text())
        config['path'] = str(legacy)
        config.pop('layout')
        config_path.write_text(json.dumps(config))
        registry_path.write_text(json.dumps(registered))
        shutil.move(str(clones[1]), str(base / 'pre-migration-copy'))
        pending = hub(
            1,
            '--hub',
            created['hub'],
            'remember',
            '--title',
            'Synthetic migration queue',
            '--file',
            note,
            '--offline',
        )
        assert pending['queued'] >= 1
        migrated = hub(1, '--hub', created['hub'], 'migrate', '--destination', clones[1])
        assert migrated['status'] == 'migrated' and migrated['queued'] >= 1
        assert (legacy / 'repository.git').exists()
        assert hub(1, '--workspace', workspaces[1], 'sync')['queued'] == 0
        assert (clones[1] / '.git').is_dir()
        report.update(
            status='PASS',
            hub=created['hub'],
            clones=[str(p) for p in clones],
            synthetic_article=shared_id,
            simulated_members='two clones of the same GitHub account',
        )
        record()
        print(
            json.dumps(
                {
                    'status': 'PASS',
                    'steps': len(receipts),
                    'report': str(base / 'report.json'),
                    'repository': args.repo,
                }
            )
        )
        return 0
    except Exception as exc:
        report.update(status='FAIL', error=repr(exc))
        record()
        print(
            json.dumps({'status': 'FAIL', 'report': str(base / 'report.json'), 'error': str(exc)})
        )
        return 1


if __name__ == '__main__':
    sys.exit(main())
