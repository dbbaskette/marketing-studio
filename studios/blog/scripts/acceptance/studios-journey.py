#!/usr/bin/env python3
"""Walk real Blog Studio CLIs through a synthetic shared studios repository; no accounts."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / 'skills/blog-studio/scripts/studio.py'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-directory', type=Path, required=True)
    parser.add_argument('--training-checkout', type=Path)
    args = parser.parse_args()
    base = args.run_directory.resolve()
    base.mkdir(parents=True, exist_ok=False)
    env = {
        **os.environ,
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_AUTHOR_NAME': 'Synthetic Author',
        'GIT_AUTHOR_EMAIL': 'author@example.invalid',
        'GIT_COMMITTER_NAME': 'Synthetic Author',
        'GIT_COMMITTER_EMAIL': 'author@example.invalid',
        'STUDIOS_CONFIG': str(base / 'studios-config.json'),
    }
    steps = []

    def run(command, home='one', fail=False, cwd=None):
        local = {**env, 'BLOG_STUDIO_DATA': str(base / home)}
        done = subprocess.run(
            [str(value) for value in command],
            env=local,
            cwd=cwd or REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
        steps.append(
            {
                'command': [str(value) for value in command],
                'computer': home,
                'exit': done.returncode,
                'expected_failure': fail,
            }
        )
        (base / 'report.json').write_text(json.dumps({'steps': steps, 'passed': False}, indent=2))
        if (done.returncode == 0) == fail:
            raise RuntimeError(done.stderr or done.stdout)
        if fail:
            return done.stderr
        try:
            return json.loads(done.stdout)
        except ValueError:
            return done.stdout

    def cli(root, *words, home='one', fail=False):
        return run([sys.executable, HELPER, '--root', root, *words], home, fail)

    remote = base / 'team.git'
    seed = base / 'seed'
    run(['git', 'init', '--bare', '--initial-branch=main', remote])
    run(['git', 'clone', remote, seed])
    (seed / 'trainings').mkdir()
    (seed / 'trainings/hub.json').write_text('{"schema":1,"tool":"training-studio"}')
    (seed / 'trainings/README.md').write_text('Synthetic training fixture.\n')
    (seed / 'presentations').mkdir()
    (seed / 'presentations/hub.json').write_text('{"schema":1,"tool":"presentation-studio"}')
    run(['git', 'add', '.'], cwd=seed)
    run(['git', 'commit', '-m', 'Seed synthetic studios'], cwd=seed)
    run(['git', 'push', 'origin', 'main'], cwd=seed)
    a = Path(cli(base / 'unused', 'team', 'join', '--repository', remote)['workspace'])
    source = base / 'source.md'
    source.write_text('Fictional service uses a fictional gateway.\n')
    reference = cli(
        a,
        'source',
        'add',
        '--name',
        'Synthetic source',
        '--file',
        source,
        '--purpose',
        'reference',
        '--purpose',
        'voice-sample',
    )
    guide = base / 'voice.md'
    guide.write_text('Use short, direct sentences.\n')
    profile = cli(
        a,
        'profile',
        'create',
        '--name',
        'Synthetic voice',
        '--guide-file',
        guide,
        '--sample',
        reference['id'],
    )
    blog = cli(
        a,
        'run',
        'create',
        '--title',
        'Synthetic shared blog',
        '--audience',
        'New authors',
        '--goal',
        'Explain a fictional gateway',
        '--research',
        'none',
        '--stop',
        'outline',
        '--source',
        reference['id'],
        '--profile',
        profile['id'],
    )
    ident = blog['id']
    draft = base / 'outline.md'
    draft.write_text('# Synthetic outline\nExplain the fictional gateway.\n')
    state = cli(a, 'run', 'status', '--id', ident)
    cli(
        a,
        'run',
        'submit',
        '--id',
        ident,
        '--stage',
        'outline',
        '--expected',
        state['expected'],
        '--file',
        draft,
    )
    state = cli(a, 'run', 'status', '--id', ident)
    cli(a, 'run', 'approve', '--id', ident, '--expected', state['expected'])
    cli(a, 'team', 'publish', '--id', ident)
    b = Path(cli(base / 'unused', 'team', 'join', '--repository', remote, home='two')['workspace'])
    assert (b / ident / 'OUTLINE.md').read_bytes() == draft.read_bytes()
    cli(
        b,
        'article',
        'rename',
        '--id',
        ident,
        '--title',
        'Refused second driver',
        home='two',
        fail=True,
    )
    cli(a, 'team', 'handover', '--id', ident)
    cli(b, 'team', 'take', '--id', ident, home='two')
    cli(b, 'article', 'rename', '--id', ident, '--title', 'Shared rename', home='two')
    cli(a, 'team', 'sync')
    assert cli(a, 'article', 'show', '--id', ident)['title'] == 'Shared rename'
    cli(a, 'team', 'takeover', '--id', ident)
    cli(
        b,
        'article',
        'rename',
        '--id',
        ident,
        '--title',
        'Refused old driver',
        home='two',
        fail=True,
    )
    run(['git', 'remote', 'set-url', 'origin', base / 'offline.git'], cwd=a.parent)
    offline = cli(a, 'article', 'rename', '--id', ident, '--title', 'Saved while offline')
    assert not offline['team_sync']['shared']
    run(['git', 'remote', 'set-url', 'origin', remote], cwd=a.parent)
    assert cli(a, 'team', 'sync')['shared']
    cli(
        a,
        'article',
        'progress',
        '--id',
        ident,
        '--stage',
        'draft',
        '--next-step',
        'Synthetic review',
        '--stop',
        'review',
    )
    cli(a, 'article', 'save', '--id', ident, '--kind', 'draft', '--file', draft)
    cli(a, 'article', 'review', '--id', ident, '--check', 'proofread', '--status', 'unavailable')
    local = a / ident / 'OUTLINE.md'
    local.write_text('Local writing must survive.\n')
    cli(a, 'team', 'sync', fail=True)
    assert local.read_text() == 'Local writing must survive.\n'
    run(['git', 'add', '--', f'blogs/{ident}/OUTLINE.md'], cwd=a.parent)
    run(['git', 'commit', '-m', 'Keep deliberately edited synthetic writing'], cwd=a.parent)
    cli(a, 'team', 'sync')
    if args.training_checkout:
        # Exercise the actual other studio in an isolated process, with only synthetic Git identity.
        script = (
            'from runner import gitstate; s=gitstate.join('
            + repr(str(remote))
            + '); (s.root/"synthetic-training.txt").write_text("Synthetic training.\\n"); gitstate.commit(s,"Keep synthetic training"); assert gitstate.sync(s)["shared"]'
        )
        env['TRAINING_STUDIO_DATA'] = str(base / 'training-data')
        env['PYTHONPATH'] = str(args.training_checkout.resolve())
        # Remove the small seed marker so Training can create its complete versioned marker.
        # Fetch first; the seed clone has no independent commits after its initial push.
        run(['git', 'pull', '--ff-only', 'origin', 'main'], cwd=seed)
        run(['git', 'rm', 'trainings/hub.json'], cwd=seed)
        run(['git', 'commit', '-m', 'Allow Training Studio to lay out its own marker'], cwd=seed)
        run(['git', 'push', 'origin', 'main'], cwd=seed)
        run([sys.executable, '-c', script], cwd=args.training_checkout)
        cli(a, 'team', 'sync')
        assert (a.parent / 'trainings/synthetic-training.txt').is_file()
        assert local.read_text() == 'Local writing must survive.\n'
    cli(a, 'team', 'status')
    assert (a / ident / 'README.md').is_file()
    assert (
        a.parent / 'presentations/hub.json'
    ).read_text() == '{"schema":1,"tool":"presentation-studio"}'
    (base / 'report.json').write_text(
        json.dumps(
            {
                'passed': True,
                'steps': steps,
                'scope': 'Local synthetic remotes and separate computer data folders; no live provider accounts.',
            },
            indent=2,
        )
    )
    print(json.dumps({'passed': True, 'commands': len(steps), 'report': str(base / 'report.json')}))


if __name__ == '__main__':
    main()
