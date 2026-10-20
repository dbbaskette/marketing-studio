#!/usr/bin/env python3
"""Compare shared-workspace and legacy-Hub history costs with 41 synthetic saves."""

import argparse
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPO / 'tests'),
    str(REPO / 'skills/blog-studio/scripts'),
    str(Path(__file__).parent),
]
from benchmark import measure
from test_shared_studios import TeamTests
from test_editorial_tools import Fixture
from hub_fixtures import FakeProvider
from hub import Registry
from hub_workspace import Workspace
import editorial
import studio
import team_workspace as teams


def command(root, *words):
    args = studio.parser().parse_args(['--root', str(root), *words])
    return getattr(studio, args.group + '_command')(root, args)


def run(shared, reuse=False):
    from hub_store import tree_read_scope

    def measured(operation):
        if reuse:
            with tree_read_scope():
                return measure(operation)
        return measure(operation)

    fixture = TeamTests() if shared else Fixture()
    fixture.setUp()
    try:
        root = fixture.root
        with patch('hub_workspace.active', return_value=None):
            article = command(
                root,
                'article',
                'create',
                '--title',
                'Synthetic storage benchmark',
                '--mode',
                'first-draft',
                '--author',
                'Synthetic Author',
            )
        ident = article['id']
        if shared:
            teams.saved(root, ident)
            adapter = None
        else:
            provider = FakeProvider(fixture.base / 'remotes')
            registry = Registry(fixture.base / 'hubs', provider)
            hub = registry.create('fixture/storage', 'Synthetic storage benchmark')['hub']
            adapter = Workspace(root, registry.hub(hub))
            adapter.publish_selected({'articles': [ident]})
        file = fixture.base / 'draft.md'
        rows = {}
        with patch('hub_workspace.active', return_value=adapter):
            for number in range(1, 42):
                file.write_text(
                    '# Synthetic gateway\n\nRevision '
                    + str(number)
                    + ': a gateway routes a request.\n'
                )

                def save():
                    record = command(
                        root,
                        'article',
                        'save',
                        '--id',
                        ident,
                        '--kind',
                        'draft',
                        '--file',
                        str(file),
                    )
                    sync = (
                        teams.saved(root, ident)
                        if shared
                        else adapter.publish_mutation('article', record)
                    )
                    return {'id': ident, 'sharing': sync}

                saved = measured(save)
                if number in (1, 41):
                    status = [measured(lambda: editorial.board(root)) for _ in range(3)]
                    sync = [
                        measured(lambda: teams.refresh(root) if shared else adapter.hub.sync())
                        for _ in range(3)
                    ]
                    rows[str(number)] = {
                        'save_and_share': saved,
                        'board': status,
                        'sync': sync,
                        'local_bytes': sum(
                            p.stat().st_size
                            for p in root.rglob('*')
                            if p.is_file() and not p.is_symlink()
                        ),
                    }
        return rows
    finally:
        fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-reads', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {
        'scope': 'Synthetic local bare Git transports, no accounts, assistant or Google requests. Timings include profiler overhead; subprocess counts are calls, bytes are logical local file sizes. No physical I/O or provider performance claim.',
        'shared_workspace': run(True, args.reuse_reads),
        'legacy_hub': run(False, args.reuse_reads),
    }
    for kind in ('shared_workspace', 'legacy_hub'):
        for row in result[kind].values():
            row['board_median_seconds'] = statistics.median(
                sample['elapsed_seconds'] for sample in row['board']
            )
            row['sync_median_seconds'] = statistics.median(
                sample['elapsed_seconds'] for sample in row['sync']
            )
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
