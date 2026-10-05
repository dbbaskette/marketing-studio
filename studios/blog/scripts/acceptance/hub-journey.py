#!/usr/bin/env python3
"""Opt-in live private-Hub CLI walkthrough using synthetic content only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='New private GitHub owner/repository to create')
    parser.add_argument('--run-directory', required=True, type=Path, help='New absolute directory for isolated homes and receipts')
    parser.add_argument('--join-existing', action='store_true', help='Use the same authorized private test Hub for another isolated run')
    parser.add_argument('--resume', action='store_true', help='Resume failed setup before any synthetic documents were saved')
    parser.add_argument('--live', action='store_true', help='Authorize creating the named private repository and posting synthetic fixtures')
    args = parser.parse_args()
    if not args.live:parser.error('--live is required; this creates a private remote repository')
    base = args.run_directory.expanduser()
    if not base.is_absolute():parser.error('Use an absolute run directory')
    if base.exists():
        if not args.resume:parser.error('Use a new run directory, or --resume for failed setup')
        previous = json.loads((base / 'report.json').read_text())
        if previous['repository'] != args.repo or previous['status'] == 'PASS' or any(step['step'].startswith('studio ') for step in previous['steps']):
            parser.error('Only failed setup for this same repository may be resumed; later runs need manual inspection')
    source = Path(__file__).resolve().parents[2]
    original_home = Path.home()
    base.mkdir(parents=True, mode=0o700, exist_ok=args.resume)
    receipts = []
    report = {'repository': args.repo, 'content': 'synthetic only', 'status': 'running', 'steps': receipts}
    def record():
        (base / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    def run(label, argv, home, expected=0, raw=False):
        env = dict(os.environ, HOME=str(original_home), GH_HOST='github.com',
                   GH_CONFIG_DIR=os.environ.get('GH_CONFIG_DIR', str(original_home / '.config/gh')))
        env.pop('GH_DEBUG', None)
        result = subprocess.run([str(v) for v in argv], env=env, capture_output=True, text=True, timeout=120)
        receipts.append({'step': label, 'command': [str(v) for v in argv], 'exit_code': result.returncode})
        record()
        if (result.returncode == 0) != (expected == 0):
            raise RuntimeError(label + ': unexpected result\n' + result.stderr + result.stdout)
        if expected:return result.stdout + result.stderr
        return result.stdout if raw else json.loads(result.stdout)
    def fixture(name, text):
        path = base / name;path.write_text(text);return path
    try:
        homes = [base / name for name in ('author-a', 'author-b')]
        for home in homes:
            run('install isolated ' + home.name, [sys.executable, source / 'installer/install.py', 'install',
                '--home', home, '--source', source / 'bootstrap/blog-studio', '--target', 'both', '--offline', '--yes', '--json'], home)
        def hub(index, *words):
            home = homes[index]
            return run('hub ' + ' '.join(str(w) for w in words[:2]),
                [sys.executable, home / '.local/share/blog-studio/current/scripts/hub.py', '--registry', home / '.local/share/blog-studio/hubs', *words], home)
        def studio(index, *words):
            home = homes[index]
            return run('studio ' + ' '.join(str(w) for w in words[:2]),
                [sys.executable, home / '.local/share/blog-studio/current/scripts/studio.py', '--root', workspaces[index], *words], home)
        created = hub(0, *(['join', '--repo', args.repo] if args.join_existing else ['create', '--repo', args.repo, '--name', 'Synthetic Blog Studio acceptance Hub']), '--destination', homes[0] / 'blogs' / args.repo.split('/')[1])
        joined = hub(1, 'join', '--repo', args.repo, '--destination', homes[1] / 'blogs' / args.repo.split('/')[1])
        assert created['hub'] == joined['hub']
        workspaces = [Path(value['workspace']) for value in (created, joined)]
        clones = [Path(value['clone']) for value in (created, joined)]
        for home, clone in zip(homes, clones):
            assert clone == home / 'blogs' / args.repo.split('/')[1]
            assert (clone / '.git').is_dir()
        title = 'Synthetic ExampleDB tutorial ' + base.name
        renamed = 'Synthetic ExampleDB walkthrough ' + base.name
        draft = fixture('synthetic-blog.md', '# Synthetic ExampleDB tutorial\n\nThis fictional product is only an acceptance fixture.\n\n## Prerequisites\n\nUse a disposable example.\n\n## Steps\n\nRead teh sample configuration and verify it.\n')
        evidence = fixture('synthetic-source.md', '# Synthetic source\n\nExampleDB is fictional. No real performance or product claims are made.\n')
        voice = fixture('synthetic-voice.md', 'Use short sentences. Label fictional examples clearly.\n')
        review = fixture('synthetic-review.json', json.dumps({'findings': [{'before': 'teh', 'after': 'the', 'reason': 'Typo in the synthetic example.'}]}))
        source_id = studio(0, 'source', 'add', '--name', 'Synthetic ExampleDB source', '--file', evidence,
            '--purpose', 'reference', '--purpose', 'voice-sample')['id']
        profile = studio(0, 'profile', 'create', '--name', 'Synthetic author', '--guide-file', voice, '--sample', source_id)['id']
        article = studio(0, 'article', 'create', '--title', title, '--mode', 'existing',
            '--author', 'Synthetic Author', '--profile', profile, '--research', 'supplied-only')['id']
        studio(0, 'article', 'attach', '--id', article, '--source', source_id)
        for kind in ('original', 'draft'):
            studio(0, 'article', 'save', '--id', article, '--kind', kind, '--file', draft)
        studio(0, 'article', 'review', '--id', article, '--check', 'proofread', '--status', 'current', '--file', review)
        found = hub(0, '--workspace', workspaces[0], 'find', '--kind', 'article', '--query', title)
        assert found['total'] == 1
        shared_id = found['items'][0]['item']
        checked = hub(1, '--workspace', workspaces[1], 'checkout-workspace', '--article', shared_id)
        second = checked['items'][0]['local_id']
        assert (workspaces[1] / 'articles' / second / 'ORIGINAL.md').read_bytes() == draft.read_bytes()
        edited = fixture('synthetic-edited-blog.md', draft.read_text().replace('teh sample', 'the sample'))
        studio(1, 'article', 'save', '--id', second, '--kind', 'draft', '--file', edited)
        hub(0, '--workspace', workspaces[0], 'checkout-workspace', '--article', shared_id)
        assert (workspaces[0] / 'articles' / article / 'DRAFT.md').read_bytes() == edited.read_bytes()
        studio(0, 'article', 'rename', '--id', article, '--title', renamed)
        studio(0, 'status', '--id', article)
        studio(0, 'home')
        studio(0, 'editorial', 'board')
        note = fixture('synthetic-team-note.md', 'Acceptance-only shared note.\n')
        queued = hub(0, '--workspace', workspaces[0], 'remember', '--title', 'Synthetic offline note', '--file', note, '--offline')
        assert queued['queued'] >= 1
        synced = hub(0, '--workspace', workspaces[0], 'sync')
        assert synced['queued'] == 0 and synced['status'] == 'shared'
        readme = clones[0] / 'README.md';original = readme.read_bytes()
        try:
            readme.write_bytes(original + b'\nSynthetic unsaved checkout edit.\n')
            failure = run('dirty checkout is protected', [sys.executable, homes[0] / '.local/share/blog-studio/current/scripts/hub.py',
                '--registry', homes[0] / '.local/share/blog-studio/hubs', '--workspace', workspaces[0], 'refresh'], homes[0], expected=1)
            assert 'local edits' in failure
        finally:readme.write_bytes(original)
        hub(0, '--workspace', workspaces[0], 'refresh')
        hub(1, '--workspace', workspaces[1], 'refresh')
        hub(1, '--workspace', workspaces[1], 'leave')
        hub(1, 'join', '--repo', args.repo)
        for index in (0, 1):
            status = hub(index, '--workspace', workspaces[index], 'status')
            assert status['queued'] == 0 and status['conflicts'] == 0
            pages = [path for path in clones[index].glob('blogs/*/*/README.md') if renamed in path.read_text()]
            assert len(pages) == 1
            assert (pages[0].parent / 'draft.md').is_file()
            assert (pages[0].parent / 'reviews/README.md').is_file()
            assert b'What changed' in (pages[0].parent / 'history.md').read_bytes()
        # Build a legacy-layout fixture from this run's synthetic clone, then
        # exercise the actual migration command with an offline save in its outbox.
        legacy = base / 'legacy-fixture'
        shutil.copytree(workspaces[1] / 'hub', legacy)
        revision = hub(1, '--workspace', workspaces[1], 'status')['revision']
        for words in (['init', '--bare', '--quiet', '--initial-branch=main'],
                      ['fetch', '--quiet', str(clones[1] / '.git'), revision],
                      ['update-ref', 'refs/heads/main', revision]):
            run('prepare synthetic legacy fixture', ['git', '--git-dir=' + str(legacy / 'repository.git'),
                '-c', 'core.hooksPath=' + os.devnull, *words], homes[1], raw=True)
        registry_path = homes[1] / '.local/share/blog-studio/hubs/registry.json'
        registry = json.loads(registry_path.read_text())
        registry['hubs'][created['hub']]['path'] = str(legacy)
        registry['hubs'][created['hub']].pop('layout')
        config_path = legacy / 'config.json';config = json.loads(config_path.read_text())
        config['path'] = str(legacy);config.pop('layout')
        config_path.write_text(json.dumps(config));registry_path.write_text(json.dumps(registry))
        shutil.move(str(clones[1]), str(base / 'pre-migration-copy'))
        pending = hub(1, '--hub', created['hub'], 'remember', '--title', 'Synthetic migration queue', '--file', note, '--offline')
        assert pending['queued'] >= 1
        migrated = hub(1, '--hub', created['hub'], 'migrate', '--destination', clones[1])
        assert migrated['status'] == 'migrated' and migrated['queued'] >= 1
        assert (legacy / 'repository.git').exists()
        assert hub(1, '--workspace', workspaces[1], 'sync')['queued'] == 0
        assert (clones[1] / '.git').is_dir()
        report.update(status='PASS', hub=created['hub'], clones=[str(p) for p in clones],
                      synthetic_article=shared_id, simulated_members='two clones of the same GitHub account')
        record();print(json.dumps({'status': 'PASS', 'steps': len(receipts), 'report': str(base / 'report.json'), 'repository': args.repo}))
        return 0
    except Exception as exc:
        report.update(status='FAIL', error=repr(exc));record()
        print(json.dumps({'status': 'FAIL', 'report': str(base / 'report.json'), 'error': str(exc)}));return 1


if __name__ == '__main__':sys.exit(main())
