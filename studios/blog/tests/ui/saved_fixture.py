"""Disposable Blog Studio with saved step-by-step blogs, for looking at their saved records.

Serves the real page over a synthetic workspace, synthetic settings and no providers. It loads
static saved-flow fixtures (tests/saved_fixtures.py) into the disposable workspace and prints
the private address and the blogs' IDs; it stops with the process.

    python3 studios/blog/tests/ui/saved_fixture.py              # each kind of saved record
    python3 studios/blog/tests/ui/saved_fixture.py conditions   # an older Team Hub workspace
    python3 studios/blog/tests/ui/saved_fixture.py team         # an identity to record by Take
    python3 studios/blog/tests/ui/saved_fixture.py team-finished  # a finished team blog

The default workspace holds: a saved run with unstructured outline notes, which opens on the
desk; a page run waiting at its gate with the marker the page worker leaves, which opens on
the desk too; a finished run, which keeps its Done card; a blog with a tool task waiting for
the person; and a saved blog whose run record cannot be read, which is read-only.
`conditions` connects the workspace to an older Team Hub: a blog with nothing made is
read-only, one with a draft waits. `team` makes it a team workspace (the team repository is
a stand-in in this process; nothing is fetched) with this computer's identity unreadable.
`team-finished` joins a disposable local team repository (a bare repository in the temporary
folder) and takes a finished saved blog there: it keeps Record in team repository and is
never handed over.
"""

import json
from pathlib import Path
import signal
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isolation  # noqa: E402,F401  (first Blog Studio import: no personal settings)
import management  # noqa: E402
import saved_fixtures  # noqa: E402
import studio  # noqa: E402
from studio_core import preferences, studios_config  # noqa: E402
from test_blog_runner import RunnerCase  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else 'records'
case = RunnerCase('runTest')
httpd = None
try:
    case.setUp()
    root = case.root
    shown = {}
    if mode == 'conditions':
        shown['nothing_made'] = saved_fixtures.load(root, 'brief-only')
        shown['waits'] = saved_fixtures.load(root, 'outline-gate')
        studio.write_json(root / '.team-hub.json', {'schema': 1})
    elif mode == 'team-finished':
        import subprocess

        from studio_sync import support
        from test_desk_team import TeamCase

        team = TeamCase('runTest')
        team.setUp()
        case.addCleanup(team.doCleanups)
        root = team.root
        tree = saved_fixtures.FIXTURES / 'finished-page'
        (ident,) = [path.name for path in (tree / 'articles').iterdir()]
        for path in sorted(tree.rglob('*')):
            if path.is_file():
                relative = path.relative_to(tree)
                if relative.parts[0] == 'articles':
                    relative = Path(*relative.parts[1:])
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_bytes(path.read_bytes())
        support.git(team.found.repo, 'add', '-A')
        subprocess.run(['git', 'commit', '-qm', 'Saved blog'], cwd=team.found.repo, check=True)
        support.git(team.found.repo, 'push', '-q', 'origin', 'HEAD:main')
        import blog_runner

        expected = blog_runner.survey(root, ident)['expected']
        management.dispatch(root, 'team-take', {'id': ident, 'expected': expected, 'confirmed': True})
        shown['finished'] = ident
    elif mode == 'team':
        from studio_sync import support
        import team_workspace

        shown['take'] = saved_fixtures.load(root, 'outline-gate')
        # A team workspace keeps each blog at its top.
        (root / 'articles' / shown['take']).rename(root / shown['take'])
        studio.write_json(
            root / 'hub.json',
            {
                'schema': 1,
                'tool': 'blog-studio',
                'name': 'Synthetic workspace',
                'folder': root.name,
                'branch': 'synthetic',
                'minimum_runtime': '4.9.0',
                'repository': 'synthetic-remote',
            },
        )
        studio.write_json(support.data_root() / 'computer.json', {'schema': 999, 'id': 'a' * 16})
        (case.base / 'team-repo' / '.git').mkdir(parents=True)
        joined = SimpleNamespace(address='synthetic-remote', repo=case.base / 'team-repo')
        team_workspace.space = lambda root: joined
        team_workspace.driver = lambda root, ident: None
    else:
        shown['moves'] = saved_fixtures.load(root, 'unstructured-outline')
        shown['gate'] = saved_fixtures.load(root, 'draft-gate-paused')
        studio.write_json(
            root / '.blog-runs' / (shown['gate'] + '.json'),
            {
                'enabled': True,
                'status': 'waiting-for-approval',
                'error': '',
                'reason': None,
                'started_at': '2026-01-05T09:30:00+00:00',
            },
        )
        shown['finished'] = saved_fixtures.load(root, 'finished-page')
        shown['task'] = saved_fixtures.load(root, 'outline-gate')
        request = {
            'kind': 'repurpose',
            'payload': {},
            'basis': 'synthetic',
            'metadata': {'article': shown['task']},
        }
        studio.write_json(
            root / '.blog-runs/tools' / ('b' * 32 + '.json'),
            {
                'id': 'b' * 32,
                **request,
                'fingerprint': studio.digest(json.dumps(request, sort_keys=True).encode()),
                'guidance': '',
                'status': 'ready',
                'created_at': studio.now(),
                'attempts': 1,
                'engine': 'codex',
                'seconds': 60,
                'result': {'content': 'Synthetic channel copy.', 'notes': ''},
                'error': '',
            },
        )
        shown['read_only'] = saved_fixtures.load(root, 'draft-gate-chat')
        (root / 'articles' / shown['read_only'] / 'derived/blog-run.json').write_text('{not json')
    studios_config.update({'local': {'root': str(root)}})
    preferences.finish(studios_config, lambda _: None)
    httpd, url = management.server(root, shared_setup=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(json.dumps({'url': url, **shown}), flush=True)
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    done.wait()
finally:
    if httpd:
        httpd.shutdown()
        httpd.server_close()
    case.doCleanups()
