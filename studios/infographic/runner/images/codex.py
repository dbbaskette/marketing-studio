"""Confined built-in Codex image execution; collect bytes from its owned output folder."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

from .base import result, save_asset
from ..contracts import MAX_ASSET_BYTES
from ..provider_capabilities import codex_image_command, private_child_environment
from ..validation import identifier, image_size, require, text

_ACTIVE = {}
_ACTIVE_LOCK = threading.Lock()


def failure_reason(done, stderr=''):
    """A normalized reason from failed-run diagnostics only, never from the model's prose.

    Returns None for a clean completed turn. Terminal error events count even when the
    process exited 0, so a refused or limited turn is never collected as an image.
    """
    from ..assistant_failure import classify
    failed = any(event.get('type') in ('turn.failed', 'error') for event in _events(done.get('events', '')))
    if not done.get('returncode') and not failed:
        return None
    diagnostics = (stderr + '\n' + '\n'.join(json.dumps(e) for e in _events(done.get('events', ''))
                   if e.get('type') in ('turn.failed', 'error'))).casefold()
    found = classify({**done, 'state': 'complete'}, stderr)
    if found in ('sign-in', 'quota'):
        return {'sign-in': 'sign-in-required', 'quota': 'quota'}[found]
    # An installed Codex that cannot expose its image tool in this execution mode.
    if 'image_generation' in diagnostics or 'image generation' in diagnostics or found == 'incompatible':
        return 'image-tool-unavailable'
    return 'provider-refusal' if found in ('model', 'connection') else 'image-tool-unavailable'


def _events(raw):
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def generated_root():
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'generated_images'


def saved_output(folder, *, root=None):
    """Only a completed worker's exact system-reported thread, never prose paths."""
    from ..workspace import _read
    folder = Path(folder)
    events = _read(folder, 'events.jsonl', 64_000_000).decode('utf-8', errors='replace')
    parsed = []
    for line in events.splitlines():
        try:
            event = json.loads(line)
            if isinstance(event, dict):parsed.append(event)
        except ValueError:
            continue
    threads = [event.get('thread_id') for event in parsed if event.get('type') == 'thread.started']
    require(len(threads) == 1 and isinstance(threads[0], str)
            and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', threads[0])
            and any(event.get('type') == 'turn.completed' for event in parsed)
            and not any(event.get('type') in ('turn.failed', 'error') for event in parsed),
            'A completed owned image thread is required for local recovery.')
    output = Path(root) / threads[0] if root is not None else generated_root() / threads[0]
    require(output.is_dir() and not any(p.is_symlink() for p in (output, *output.parents)),
            'The saved image output is missing or linked.')
    paths = list(output.iterdir())
    require(0 < len(paths) <= 16 and all(p.suffix.lower() == '.png' and p.is_file()
            and not p.is_symlink() and 0 < p.stat().st_size <= MAX_ASSET_BYTES for p in paths),
            'The completed worker has no bounded safe image output.')
    return output


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
    def __init__(self, folder, *, run=execute, seconds=300, model=None, effort=None, stop=None, output_root=None):
        require(type(seconds) is int and 1 <= seconds <= 600, 'Choose an image timeout of 1–600 seconds.')
        self.folder, self.run, self.seconds, self.model, self.effort, self.stop = Path(folder), run, seconds, model, effort, stop
        self.output_root = output_root

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
            prompt = (brief['prompt'] + '\nMake exactly one image-generation request. Do not generate variants, '
                      'self-correct, or run another image request. Return the resulting artifact for review. '
                      'Use the built-in image tool; do not use shell, outside sources or tools to redraw it.')
            done = self.run(command, prompt, self.folder, self.seconds, self.stop)
        except FileNotFoundError:
            return result('codex', operation, attempt_id, state='unavailable', reason='assistant-missing')
        except (OSError, ValueError):
            return result('codex', operation, attempt_id, state='unknown', reason='timeout')
        if done['state'] in ('cancelled', 'unknown'):
            return result('codex', operation, attempt_id, state=done['state'], reason='stopped' if done['state'] == 'cancelled' else 'timeout')
        reason = failure_reason(done, self._stderr())
        if done['returncode'] or reason:
            return result('codex', operation, attempt_id, state='failed', reason=reason or 'image-tool-unavailable')
        return self._collect(operation, attempt_id, done.get('events', ''))

    def _stderr(self):
        """The worker's own bounded diagnostics; never shown, only classified."""
        path = self.folder / 'stderr.txt'
        if not path.is_file() or path.is_symlink():
            return ''
        from ..workspace import _read
        try:
            return _read(self.folder, 'stderr.txt', 4_000_000).decode('utf-8', errors='replace')
        except (OSError, ValueError):
            return ''

    def recover(self, *, attempt_id, operation='generate'):
        """Collect already completed output only; this method never executes a worker."""
        from ..workspace import _read
        events = _read(self.folder, 'events.jsonl', 64_000_000).decode('utf-8', errors='replace')
        saved_output(self.folder, root=self.output_root)
        return self._collect(operation, attempt_id, events)

    def _collect(self, operation, attempt_id, events):
        from ..workspace import _read
        try:
            output = self.folder / 'generated_images'
            if not output.exists():
                output = saved_output(self.folder, root=self.output_root)
            require(output.is_dir() and not any(p.is_symlink() for p in (output, *output.parents)),
                    'The generated image output must be an owned regular directory.')
            paths = list(output.iterdir())
            require(0 < len(paths) <= 16 and all(path.suffix.lower() == '.png' and path.is_file()
                    and not path.is_symlink() for path in paths), 'The generated image output is unsafe or unbounded.')
            # Older workers could iterate. Keep their originals, collect the final saved PNG.
            path = max(paths, key=lambda p: (p.stat().st_mtime_ns, p.name))
        except (ValueError, OSError, TypeError):
            return result('codex', operation, attempt_id, state='failed', reason='image-tool-unavailable')
        try:
            # A present file that is not a bounded valid PNG is a bad asset, not a missing tool.
            assets = [save_asset(self.folder, _read(output, path.name, MAX_ASSET_BYTES), 'image/png')]
        except (ValueError, OSError, TypeError):
            return result('codex', operation, attempt_id, state='failed', reason='invalid-asset')
        usage = None
        for event in _events(events):
            used = event.get('usage') if event.get('type') == 'turn.completed' else None
            if isinstance(used, dict):
                usage = {'cost': None, 'currency': None,
                         **{key: used[key] if type(used.get(key)) is int and used[key] >= 0 else None
                            for key in ('input_tokens', 'output_tokens')}}
        try:
            return result('codex', operation, attempt_id, state='complete', assets=assets, usage=usage)
        except (ValueError, TypeError):
            # Unreadable reported usage stays unknown; it never discards the collected image.
            return result('codex', operation, attempt_id, state='complete', assets=assets)

    def status(self, *, attempt_id):
        return result('codex', 'status', attempt_id, state='unknown')

    def cancel(self, *, attempt_id):
        if self.stop is not None:
            self.stop.set()
        return result('codex', 'cancel', attempt_id, state='unknown', reason='stopped')
