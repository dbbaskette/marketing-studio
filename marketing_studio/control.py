"""Private same-user CLI control, so repeated commands reuse and manage the running app.

Only the person's own account can reach the socket (0600, same user). Its replies may
carry the private link, as the terminal that started Marketing Studio would; the CLI
shows it only to a terminal, never to a pipe.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import stat
import threading

COMMANDS = ('open', 'setup', 'state', 'start', 'stop', 'shutdown')
STUDIOS = (None, 'blog', 'presentation', 'training', 'infographic')
FIELDS = frozenset(('command', 'studio', 'force'))


def valid(action):
    return (isinstance(action, dict) and not set(action) - FIELDS
            and action.get('command') in COMMANDS and action.get('studio') in STUDIOS
            and type(action.get('force', False)) is bool)


def interrupt():
    """Stop the way Ctrl-C does, so the main thread closes everything in order."""
    os.kill(os.getpid(), signal.SIGINT)


def address(data):
    path = Path(data) / 'control.sock'
    if len(os.fsencode(path)) < 100:
        return path
    # macOS limits Unix socket paths. Keep long custom data roots usable.
    folder = Path('/tmp') / ('marketing-studio-' + str(os.getuid()))
    folder.mkdir(mode=0o700, exist_ok=True)
    info = folder.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise OSError('The private Marketing Studio control folder is not accessible safely.')
    key = hashlib.sha256(str(Path(data).resolve()).encode()).hexdigest()[:20]
    return folder / (key + '.sock')


def request(data, action):
    path = address(data)
    if not path.exists():
        return None
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise OSError('The Marketing Studio CLI socket is not private to this user.')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(100)
        try:
            client.connect(str(path))
        except (ConnectionRefusedError, FileNotFoundError):
            return None
        client.sendall(json.dumps(action).encode() + b'\n')
        with client.makefile('rb') as stream:
            return json.loads(stream.readline(4097))


class Control:
    def __init__(self, data, handle, shutdown=interrupt):
        """`handle` answers each request with a reply; after a shutdown reply is sent,
        `shutdown` is called from this thread."""
        self.path = address(data)
        self.handle = handle
        self.shutdown = shutdown
        self.stopped = threading.Event()
        # The caller holds the home singleton lock before clearing a stale socket.
        if self.path.exists():
            info = self.path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise OSError('An unmanaged file blocks Marketing Studio CLI control.')
            self.path.unlink()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.socket.bind(str(self.path))
        except BaseException:
            self.socket.close()
            raise
        self.path.chmod(0o600)
        self.socket.listen(4)
        self.socket.settimeout(.2)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while not self.stopped.is_set():
            try:
                client, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            action = None
            with client:
                client.settimeout(2)
                try:
                    with client.makefile('rb') as stream:
                        raw = stream.readline(4097)
                    if len(raw) > 4096:
                        raise ValueError('The CLI request is too large.')
                    action = json.loads(raw)
                    if not valid(action):
                        action = None
                        raise ValueError('Choose a supported studio command.')
                    result = self.handle(action)
                    if result is None:
                        result = {'opened': True}
                except Exception as failure:
                    result = {'error': str(failure)}
                try:
                    client.sendall(json.dumps(result).encode() + b'\n')
                except OSError:
                    pass
            if action and action['command'] == 'shutdown' and 'error' not in result:
                # The reply is out first: the caller learns it was accepted, then it stops.
                self.shutdown()

    def close(self):
        self.stopped.set()
        self.socket.close()
        self.thread.join(timeout=3)
        self.path.unlink(missing_ok=True)
        if self.path.parent != self.path.parent.parent and self.path.parent.parent == Path('/tmp'):
            try:
                self.path.parent.rmdir()
            except OSError:
                pass
