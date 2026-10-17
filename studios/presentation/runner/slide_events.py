"""Read the companion's opt-in progress log while its supervised command runs.

The final JSON result still comes from stdout. The same events written to stderr
are retained by Harness Slides in events.jsonl, so process supervision is unchanged.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import threading


@contextmanager
def watching(folder, each):
    path = Path(folder) / 'events.jsonl'
    stop = threading.Event()
    offset, pending = 0, b''

    def drain():
        nonlocal offset, pending
        try:
            if path.is_symlink():
                return
            with path.open('rb') as stream:
                stream.seek(offset)
                data = stream.read(min(262144, max(0, 4_000_000 - offset)))
            offset += len(data)
            pending += data
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                if len(line) > 65536:
                    continue
                try:
                    found = json.loads(line)
                    if isinstance(found, dict):
                        each(found)
                except (ValueError, OSError):
                    continue
            if len(pending) > 65536:
                pending = b''
        except OSError:
            return

    def follow():
        while not stop.wait(.05):
            drain()
        drain()

    thread = threading.Thread(target=follow, name='slide-progress', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
