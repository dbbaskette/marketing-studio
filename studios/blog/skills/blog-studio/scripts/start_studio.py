"""The installed start command: open the page or check this computer."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

import computer


@contextmanager
def running(data, workspace):
    """Hold a shared lease; setup takes an exclusive one before changing the runtime."""
    data.mkdir(parents=True, exist_ok=True)
    with (data / '.studio-running.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(
                'Blog Studio setup is changing this installation. Try opening it again when setup finishes.'
            ) from exc
        receipts = data / 'running'
        receipts.mkdir(exist_ok=True)
        receipt = receipts / (
            str(os.getpid())
            + '-'
            + hashlib.sha256(str(workspace).encode()).hexdigest()[:12]
            + '.json'
        )
        receipt.write_text(json.dumps({'pid': os.getpid(), 'workspace': str(workspace)}))
        try:
            yield
        finally:
            receipt.unlink(missing_ok=True)
            fcntl.flock(lock, fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Open Blog Studio or check this computer.')
    parser.add_argument('action', choices=('open', 'check'), nargs='?', default='open')
    parser.add_argument(
        '--root', type=Path, help='Writing workspace; remembered for the next launch.'
    )
    parser.add_argument('--home', type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument('--data-root', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument(
        '--no-open',
        action='store_true',
        help='Print the session address without opening a browser.',
    )
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    home = args.home.expanduser().resolve()
    data = (args.data_root or home / '.local/share/blog-studio').expanduser().resolve()
    if args.action == 'check':
        found = computer.report(home)
        print(json.dumps(found, indent=2) if args.json else computer.describe(found))
        return 0
    previous_data = os.environ.get('BLOG_STUDIO_DATA')
    os.environ['BLOG_STUDIO_DATA'] = str(data)
    try:
        settings = data / 'page.json'
        if settings.is_symlink():
            raise ValueError(
                'Page preferences must be a regular file. Keep page.json for diagnosis and run setup repair.'
            )
        kept = json.loads(settings.read_text()) if settings.is_file() else {}
        if not isinstance(kept, dict) or (
            'workspace' in kept and not isinstance(kept['workspace'], str)
        ):
            raise ValueError(
                'The saved workspace in page.json is invalid. Pass --root with your writing folder.'
            )
        from studio_sync.gitstate import current

        joined = current()
        workspace = (
            args.root
            or (joined.root if joined else None)
            or Path(kept.get('workspace', home / 'blogs/.blog-studio'))
        ).expanduser()
        if not workspace.is_absolute():
            raise ValueError('Use an absolute writing workspace path with --root.')
        workspace = workspace.resolve()
        if workspace.is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('Choose a writing workspace outside the installed skill folder.')
        with running(data, workspace):
            # Atomic local preference; no session address, key or provider output is stored.
            temporary = settings.with_name('.page-' + str(os.getpid()) + '.json')
            try:
                temporary.write_text(json.dumps({'workspace': str(workspace)}))
                os.replace(temporary, settings)
            finally:
                temporary.unlink(missing_ok=True)
            print(
                'Blog Studio is starting. Its page opens in your browser.\nLeave this window open while you work. Press Ctrl-C here to stop.',
                flush=True,
            )
            from management import main as serve

            return serve(
                workspace,
                port=args.port,
                open_browser=not args.no_open,
                data_root=data,
                leased=True,
                human=not args.json,
            )
    except (OSError, ValueError, TypeError) as exc:
        print('Blog Studio: ' + str(exc), file=sys.stderr)
        return 1
    finally:
        if previous_data is None:
            os.environ.pop('BLOG_STUDIO_DATA', None)
        else:
            os.environ['BLOG_STUDIO_DATA'] = previous_data


if __name__ == '__main__':
    raise SystemExit(main())
