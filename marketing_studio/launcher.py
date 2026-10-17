"""Start at most one child per studio; keep private links in memory only."""
import json
import os
import queue
import re
import secrets
import signal
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

from . import catalog, state
from .errors import WorkspaceError

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 90


def local_link(link):
    try:
        url = urlsplit(link)
        return (url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
                and url.path == '/' and not url.query and not url.username and not url.password
                and re.fullmatch(r'(?:token=)?[A-Za-z0-9_-]{32,128}', url.fragment))
    except (ValueError, TypeError):
        return False


class Launcher:
    def __init__(self, network=None):
        self.network = network
        self.children = {}
        self.lock = threading.RLock()
        self.closed = False

    def running(self, identifier):
        child = self.children.get(identifier)
        return bool(child and child[0].poll() is None)

    def open(self, identifier, preferences, shared):
        with self.lock:
            if self.closed:
                raise WorkspaceError('Marketing Studio is closing. Open it again to launch a studio.')
            if not isinstance(identifier, str) or identifier not in catalog.STUDIOS:
                raise WorkspaceError('Choose one of the studios shown on the home page.')
            if self.running(identifier):
                return self.link(identifier, self.children[identifier][1])
            root = catalog.locate(identifier, preferences.get('paths', {}))
            if root is None:
                raise WorkspaceError('This studio was not found. Install it or set its folder in Settings.')
            token = secrets.token_urlsafe(32)
            env = {**os.environ, 'MARKETING_STUDIO_HANDOFF': json.dumps({'token': token, 'shared': shared}),
                   'PYTHONUNBUFFERED': '1'}
            log = state.data_root() / 'logs' / (identifier + '.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('w') as errors:
                os.chmod(log, 0o600)
                process = subprocess.Popen([sys.executable, str(ROOT / 'marketing_studio/bridge.py'),
                                            identifier, str(root)], env=env, cwd=root,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=errors, text=True, start_new_session=True)
            announced = queue.Queue()

            def collect():
                try:
                    for line in process.stdout:
                        if len(line) > 64000:
                            continue
                        try:
                            found = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(found, dict) and any(key in found for key in ('address', 'link', 'error')):
                            announced.put(found)
                    announced.put({'error': 'The studio stopped before opening. Check its launch log.'})
                finally:
                    process.stdout.close()
            reader = threading.Thread(target=collect, daemon=True)
            reader.start()
            try:
                result = announced.get(timeout=TIMEOUT)
                if result.get('error'):
                    raise WorkspaceError(result['error'])
                link = result.get('link') or (result.get('address', '') + '#token=' + token)
                if not local_link(link):
                    raise WorkspaceError('The studio returned an invalid local address.')
            except BaseException as failure:
                self.stop_process(process)
                reader.join(timeout=2)
                if isinstance(failure, queue.Empty):
                    raise WorkspaceError('The studio took too long to open. Check its launch log and try again.') from failure
                raise
            self.children[identifier] = (process, link)
            return self.link(identifier, link)

    def link(self, identifier, link):
        return self.network.share(identifier, link) if self.network else link

    def prepare(self, preferences, shared):
        """Persist first-run setup for installed studios, without starting their servers."""
        with self.lock:
            prepared = []
            for identifier in catalog.STUDIOS:
                root = catalog.locate(identifier, preferences.get('paths', {}))
                if root is None:
                    continue
                env = {**os.environ, 'MARKETING_STUDIO_HANDOFF': json.dumps(
                    {'token': secrets.token_urlsafe(32), 'shared': shared})}
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / 'marketing_studio/bridge.py'), identifier,
                     str(root), '--prepare'], cwd=root, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    start_new_session=True)
                try:
                    output, _ = process.communicate(timeout=TIMEOUT)
                except BaseException as failure:
                    self.stop_process(process)
                    process.communicate()
                    if isinstance(failure, subprocess.TimeoutExpired):
                        raise WorkspaceError('Workspace setup took too long. Check the repository connection and try again.') from failure
                    raise
                try:
                    result = json.loads(output.splitlines()[-1])
                except (ValueError, IndexError):
                    result = {}
                if process.returncode or not isinstance(result, dict) or result.get('prepared') is not True:
                    message = result.get('error') if isinstance(result, dict) else None
                    message = message or 'Workspace setup failed. Check Git and the studio installation.'
                    raise WorkspaceError(catalog.STUDIOS[identifier][0] + ': ' + message)
                prepared.append(identifier)
            return prepared

    @staticmethod
    def stop_process(process):
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=8)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)

    def close(self):
        with self.lock:
            self.closed = True
            for process, _ in self.children.values():
                self.stop_process(process)
            self.children.clear()
