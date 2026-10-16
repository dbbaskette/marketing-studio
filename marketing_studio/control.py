"""Private same-user CLI control, so repeated open commands reuse the running app."""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import threading


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
    def __init__(self, data, handle):
        self.path = address(data)
        self.handle = handle
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
            with client:
                client.settimeout(2)
                try:
                    with client.makefile('rb') as stream:
                        raw = stream.readline(4097)
                    if len(raw) > 4096:
                        raise ValueError('The CLI request is too large.')
                    action = json.loads(raw)
                    if not isinstance(action, dict) or action.get('command') not in ('open', 'setup') \
                            or action.get('studio') not in (None, 'blog', 'presentation', 'training'):
                        raise ValueError('Choose a supported studio command.')
                    self.handle(action)
                    result = {'opened': True}
                except Exception as failure:
                    result = {'error': str(failure)}
                try:
                    client.sendall(json.dumps(result).encode() + b'\n')
                except OSError:
                    pass

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
