"""Confined built-in Codex image execution; collect bytes from its owned output folder."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from .base import result, save_asset
from ..contracts import MAX_ASSET_BYTES, Invalid
from ..provider_capabilities import codex_image_command, private_child_environment
from ..validation import identifier, image_size, require, text

_ACTIVE = {}
_ACTIVE_LOCK = threading.Lock()


def stop_owned(prefix):
    """Stop only groups this process created beneath the exact owned job root."""
    prefix = Path(prefix)
    with _ACTIVE_LOCK:
        for folder, (process, stop) in tuple(_ACTIVE.items()):
            if folder == prefix or folder.is_relative_to(prefix):
                stop.set()
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def execute(command, prompt, folder, seconds, stop=None):
    """Bounded private event files and process-group lifetime; no shell invocation."""
    folder = Path(folder)
    stop = stop or threading.Event()
    stdout, stderr = folder / 'events.jsonl', folder / 'stderr.txt'
    with stdout.open('xb') as out, stderr.open('xb') as err:
        process = subprocess.Popen(command, cwd=folder, env=private_child_environment(os.environ),
                                   stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True)
        state = 'complete'
        with _ACTIVE_LOCK:
            _ACTIVE[folder] = process, stop
        try:
            def send():
                try:
                    process.stdin.write(prompt.encode())
                    process.stdin.close()
                except (BrokenPipeError, OSError, ValueError):
                    pass
            writer = threading.Thread(target=send, daemon=True)
            writer.start()
            deadline = time.monotonic() + seconds
            while process.poll() is None:
                if stop.is_set():
                    state = 'cancelled'
                    break
                if time.monotonic() >= deadline:
                    state = 'unknown'
                    break
                if stdout.stat().st_size > 64_000_000 or stderr.stat().st_size > 4_000_000:
                    state = 'failed'
                    break
                time.sleep(.05)
            if stop.is_set():
                state = 'cancelled'
        finally:
            # End only the process group created by this call, including leaked descendants.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            writer.join(timeout=1)
            with _ACTIVE_LOCK:
                _ACTIVE.pop(folder, None)
    raw = stdout.read_bytes()
    require(len(raw) <= 64_000_000, 'The image worker exceeded its event output limit.')
    return {'state': state, 'returncode': process.returncode, 'events': raw.decode('utf-8', errors='replace')}


class Codex:
    def __init__(self, folder, *, run=execute, seconds=300, model=None, effort=None, stop=None):
        require(type(seconds) is int and 1 <= seconds <= 600, 'Choose an image timeout of 1–600 seconds.')
        self.folder, self.run, self.seconds, self.model, self.effort, self.stop = Path(folder), run, seconds, model, effort, stop

    def readiness(self):
        import shutil
        installed = shutil.which('codex') is not None
        return result('codex', 'readiness', None, state='unverified' if installed else 'unavailable',
                      reason=None if installed else 'assistant-missing')

    def generate(self, *, attempt_id, brief):
        return self._request('generate', attempt_id, brief, [])

    def edit(self, *, attempt_id, brief, reference_assets):
        require(bool(reference_assets), 'Reference-guided editing needs an original owned image.')
        return self._request('edit', attempt_id, brief, reference_assets)

    def _request(self, operation, attempt_id, brief, references):
        require(identifier(attempt_id) and isinstance(brief, dict) and text(brief.get('prompt'), limit=60_000),
                'Use an owned attempt and a complete saved image brief.')
        require(self.folder.is_dir() and not any(p.is_symlink() for p in (self.folder, *self.folder.parents)),
                'Start image work only in an owned regular job directory.')
        output = self.folder / 'generated_images'
        require(not output.exists() and not output.is_symlink(), 'Image attempts need an unused output directory.')
        files = []
        require(len(references) <= 5, 'Use at most five owned image references.')
        for index, reference in enumerate(references):
            require(isinstance(reference, dict) and type(reference.get('data')) is bytes,
                    'Attach staged image bytes rather than arbitrary local paths.')
            raw, mime = reference['data'], reference.get('mime')
            image_size(raw, mime)
            path = self.folder / ('reference-' + str(index) + ('.png' if mime == 'image/png' else '.jpg'))
            with path.open('xb') as stream:
                stream.write(raw)
            files.append(path)
        command = codex_image_command(self.folder, files)
        from studio_core.runtime import assistant_command
        command[0] = assistant_command('codex') or 'codex'
        for key, value in (('-m', self.model), ('-c', 'model_reasoning_effort=' + json.dumps(self.effort) if self.effort else None)):
            if value is not None:
                require(text(value, limit=200) and not value.startswith('-') and '\n' not in value,
                        'Choose a bounded explicit assistant configuration.')
                command[-1:-1] = [key, value]
        try:
            done = self.run(command, brief['prompt'], self.folder, self.seconds, self.stop)
        except FileNotFoundError:
            return result('codex', operation, attempt_id, state='unavailable', reason='assistant-missing')
        except (OSError, ValueError):
            return result('codex', operation, attempt_id, state='unknown', reason='timeout')
        if done['state'] in ('cancelled', 'unknown'):
            return result('codex', operation, attempt_id, state=done['state'], reason='stopped' if done['state'] == 'cancelled' else 'timeout')
        if done['returncode']:
            events = done.get('events', '').lower()
            reason = 'sign-in-required' if any(w in events for w in ('not logged in', 'unauthorized', 'please run /login')) else (
                'quota' if any(w in events for w in ('usage limit', 'rate limit', 'quota')) else 'image-tool-unavailable')
            return result('codex', operation, attempt_id, state='failed', reason=reason)
        try:
            require(output.is_dir() and not output.is_symlink(), 'The installed Codex did not expose saved built-in image output.')
            paths = list(output.iterdir())
            require(0 < len(paths) <= 4, 'The built-in image tool did not return a bounded set of files.')
            assets = []
            for path in paths:
                require(path.suffix.lower() in ('.png', '.jpg', '.jpeg') and path.is_file() and not path.is_symlink()
                        and path.stat().st_size <= MAX_ASSET_BYTES, 'The generated image file is unsafe or oversized.')
                raw = path.read_bytes()
                assets.append(save_asset(self.folder, raw, 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'))
            usage = None
            for line in done.get('events', '').splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'turn.completed':
                    used = event.get('usage') or {}
                    usage = {'cost': None, 'currency': None, 'input_tokens': used.get('input_tokens'),
                             'output_tokens': used.get('output_tokens')}
            return result('codex', operation, attempt_id, state='complete', assets=assets, usage=usage)
        except (ValueError, OSError, TypeError):
            return result('codex', operation, attempt_id, state='failed', reason='image-tool-unavailable')

    def status(self, *, attempt_id):
        return result('codex', 'status', attempt_id, state='unknown')

    def cancel(self, *, attempt_id):
        if self.stop is not None:
            self.stop.set()
        return result('codex', 'cancel', attempt_id, state='unknown', reason='stopped')
