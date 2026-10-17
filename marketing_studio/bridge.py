"""Compatibility entry point using each studio's existing Python interfaces.

Runs in a child interpreter: no studio modules enter Marketing Studio's process.
Workspace setup is durable, so the independent launcher can use it afterward.
"""
import argparse
import json
import os
import signal
import sys
from pathlib import Path


# This entry point runs by file path, before either product package is imported.
_CORE = Path(__file__).resolve().parents[1] / 'core'
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
from studio_core.workspace_setup import configure


def prepare_blog(root):
    """Keep native private defaults so the independent launcher opens its home page."""
    import studio
    import blog_runner
    from hub_store import acquire_lock, release_lock
    studio.initialize(root)
    found = blog_runner.settings(root)
    if found['configured']:
        return
    lock = acquire_lock(studio.inside(root, '.blog-runner.lock'), wait=0)
    if lock is None:
        raise ValueError('Blog Studio is open in setup. Finish or close that page before preparing it here.')
    try:
        blog_runner.settings(root, {**found['defaults'], 'shared_before': found['shared_before']})
    finally:
        release_lock(lock)


def serve_blog(root):
    # Use the native page server and runner; only the parent-facing announcement differs.
    import management
    import blog_runner
    import studio
    from hub_store import acquire_lock, release_lock
    from start_studio import running
    data = Path(os.environ.get('BLOG_STUDIO_DATA', '~/.local/share/blog-studio')).expanduser()
    with running(data, root):
        studio.initialize(root)
        lock = acquire_lock(studio.inside(root, '.blog-runner.lock'), wait=0)
        if lock is None:
            raise ValueError('Blog Studio is already running for this workspace. Use its page.')
        runner, httpd = None, None
        try:
            runner = blog_runner.engine(root)
            httpd, url = management.server(root, shared_setup=True)
            # Blog Studio generates its own key. It travels only over the private pipe.
            print(json.dumps({'link': url}), flush=True)
            runner.start()
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if runner:
                runner.close()
            if httpd:
                active = getattr(httpd, 'active_root', None)
                if active:
                    blog_runner.engine(active).close()
                if getattr(httpd, 'team_runner_lock', None) is not None:
                    release_lock(httpd.team_runner_lock)
                httpd.server_close()
            release_lock(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('studio', choices=('blog', 'presentation', 'training'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
    shared = handoff['shared']
    if args.studio == 'blog':
        scripts = args.root / 'skills/blog-studio/scripts'
        sys.path.insert(0, str(scripts if scripts.is_dir() else args.root / 'scripts'))
        from studio_sync import gitstate
        # The native installed launcher remembers its own workspace as well.
        data = Path(os.environ.get('BLOG_STUDIO_DATA', '~/.local/share/blog-studio')).expanduser()
        previous = data / 'page.json'
        space = gitstate.current()
        if space is None and previous.is_file():
            if previous.is_symlink():
                raise ValueError('Blog Studio page preferences must be a regular file.')
            kept = json.loads(previous.read_text()).get('workspace')
            if kept:
                root = Path(kept).expanduser()
                if not root.is_absolute():
                    raise ValueError('Blog Studio needs an absolute workspace path.')
            else:
                root = configure(gitstate, shared, args.studio).root
        else:
            root = (space or configure(gitstate, shared, args.studio)).root
        prepare_blog(root)
        if args.prepare:
            print(json.dumps({'prepared': True}), flush=True)
            return 0
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        return serve_blog(root) or 0
    sys.path.insert(0, str(args.root))
    from runner import gitstate, setup, studio
    if args.prepare and gitstate.current() is not None:
        print(json.dumps({'prepared': True}), flush=True)
        return 0
    # The native startup takes its singleton lock before serving. Setup needs the same
    # lease, so a launch cannot change an already-running studio's workspace.
    with studio.only_runner():
        setup.migrate()
        configure(gitstate, shared, args.studio)
    if args.prepare:
        print(json.dumps({'prepared': True}), flush=True)
        return 0
    os.environ[studio.RESTART] = json.dumps({'token': handoff['token']})
    return studio.main(['serve'])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as failure:
        print(json.dumps({'error': str(failure)}), flush=True)
        raise SystemExit(2)
