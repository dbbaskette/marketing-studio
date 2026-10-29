"""Explicit optional research jobs. Private checkpoints survive page disconnects."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import threading
import time
from studio_core import research_contract as rc, research_session, research_sources, research_text
from studio_core import public_fetch, source_documents, research_sites
from . import research, settings
from .author import Author
from .contracts import Invalid
from .validation import identifier, require


class Jobs:
    def __init__(self, store, *, author=None, runtime=None, fetch=None):
        self.store, self.author, self.runtime = store, author, runtime
        self.fetch = fetch or public_fetch.fetch
        self.lock = threading.RLock()
        self.active = {}

    def folder(self, ident):
        require(identifier(ident), 'Choose a saved infographic.')
        self.store.read(ident)
        return rc.inside(self.store.root, '.research-runs/' + ident)

    def _state(self, ident):
        base = self.folder(ident)
        if not (base / 'current.json').is_file(): return None, None
        pointer = json.loads((base / 'current.json').read_text())
        key = pointer.get('request')
        require(isinstance(key, str) and len(key) == 64 and all(c in '0123456789abcdef' for c in key), 'The saved research request is unreadable.')
        root = rc.inside(base, key)
        state = json.loads(rc.inside(root, 'state.json').read_text())
        require(state.get('owner') == self.store.owner and state.get('project') == ident, 'This research belongs to another workspace.')
        return root, state

    def read(self, ident):
        with self.lock:
            _, state = self._state(ident)
            if not state: return None
            shown = {k: state[k] for k in ('state', 'request', 'project_revision', 'progress', 'problem') if k in state}
            shown['elapsed_seconds'] = round((state.get('ended') or time.time()) - state['started'])
            if state['state'] in ('working', 'paused', 'stopping') and state.get('ended') is None and ident not in self.active:
                shown.update(state='needs-attention', problem='The previous research host ended without a terminal observation. Its evidence is kept. Do not repeat uncertain invocations; inspect or restore their terminal records first.')
            return shown

    def start(self, ident, expected_revision, reference, *, retry=False):
        # Read and pin all source choices before starting a provider or acquiring a job slot.
        project = self.store.read(ident); self.store.expect(project, expected_revision)
        prepared = research_sources.prepare_start(self.store.root, reference) if reference else None
        with self.lock:
            if ident in self.active:
                return self.read(ident)
            previous, saved = self._state(ident)
            if retry:
                require(saved is not None and saved['project_revision'] == project['revision'], 'The infographic changed. Start research for its current brief.')
                require(saved['state'] not in ('working', 'paused', 'stopping'), 'An earlier host invocation needs terminal recovery before retrying.')
                root, state = previous, saved
                runtime = Path(self.runtime) if self.runtime else rc.runtime_for(state['contract'])
            else:
                require(prepared is not None, 'Choose the current source draft before researching.')
                choice = prepared['research_from']
                task = research.task(project, research_sites.source_mode(choice))
                if prepared['focus']: task['scope'] += '\nResearch focus: ' + prepared['focus']
                contract = rc.snapshot()
                runtime = Path(self.runtime) if self.runtime else rc.runtime_for(contract)
                if self.runtime: contract = rc.capability(runtime)
                execution = research_session.execution(runtime, prepared['workers']) if runtime else None
                require(execution is not None, 'Install the pinned complete Harness Research 1.1 runtime before starting optional research.')
                # Idempotent retries/taps of the same explicit start never create another request.
                key = research_session.digest([self.store.owner, ident, project['revision'], task,
                    prepared['id'], prepared['revision'], contract, execution])
                base = self.folder(ident); rc.write(base, '.gitignore', '*\n')
                root = rc.inside(base, key)
                if (root / 'state.json').exists():
                    rc.write(base, 'current.json', json.dumps({'request': key}))
                    return self.read(ident)
                inputs = research_sources.install(prepared, root)
                state = {'schema': 1, 'owner': self.store.owner, 'project': ident, 'project_revision': project['revision'],
                    'request': key, 'contract': contract, 'execution': execution, 'task': task,
                    'inputs': inputs, 'choice': choice, 'configuration': settings.snapshot()['assistant'],
                    'state': 'working', 'progress': {'phase': 'investigate', 'streams': []},
                    'problem': '', 'started': time.time(), 'ended': None}
                rc.write(base, 'current.json', json.dumps({'request': key}))
            require(runtime is not None and research_session.capability(runtime) == state['execution']['capability'], 'Restore the saved research runtime before retrying.')
            stop, paused = threading.Event(), threading.Event()
            state.update(state='working', problem='', ended=None)
            rc.write(root, 'state.json', json.dumps(state))
            self.active[ident] = (stop, paused)
            thread = threading.Thread(target=self._run, args=(ident, root, state, Path(runtime), stop, paused), daemon=True)
            thread.start()
            return self.read(ident)

    def _run(self, ident, root, state, runtime, stop, paused):
        started = time.monotonic()
        author = self.author or Author(state['configuration'])
        def save(**values):
            with self.lock:
                state.update(values); rc.write(root, 'state.json', json.dumps(state))
        def current():
            project = self.store.read(ident)
            return project['revision'] == state['project_revision'] and self.store.owner == state['owner']
        def cancelled(): return stop.is_set() or not current()
        def call(phase, payload, guide):
            require(not cancelled(), 'Research stopped or its infographic changed. Saved work is kept.')
            left = int(1800 - (time.monotonic() - started))
            require(left > 0, 'Research reached its total 30-minute limit. Checked evidence is kept.')
            return author.research(phase, payload, guide, seconds=min(300, left), stop=stop, web=phase == 'discovery')
        try:
            _, offered = research_sources.sources(root, state['inputs'])
            choice = state['choice']
            if research_sites.fetches(choice):
                # Discovery uses no supplied/private source text. Every returned URL and redirect is host-checked.
                saved = root / 'discovery.json'
                if saved.exists(): discovered = json.loads(saved.read_text())
                else:
                    result = call('discovery', {'topic': state['task']['topic'], 'audience': state['task']['audience']},
                        'Find up to eight primary public reference URLs for this topic. Use generic nonconfidential queries. '
                        + research_sites.guidance(choice) + ' Return only JSON {"urls":["https://..."]}.')
                    require(isinstance(result, dict) and isinstance(result.get('urls'), list) and len(result['urls']) <= 8, 'Discovery needs up to eight reference URLs.')
                    discovered = []
                    scope = research_sites.Scope(choice)
                    for url in dict.fromkeys(result['urls']):
                        if cancelled(): raise InterruptedError('Research stopped.')
                        try:
                            found = self.fetch(url, scope=scope)
                            kind = {'text/plain':'text','text/html':'html','application/pdf':'pdf'}[found['mime'].split(';')[0]]
                            extracted = source_documents.extract(found['raw'], kind)
                            discovered.append({'file':'sources/discovery-' + hashlib.sha256(found['raw']).hexdigest() + '.txt',
                                'origin':found['url'], 'title':found['url'], 'permission':'public', 'text':extracted['text']})
                        except (ValueError, KeyError, OSError) as error:
                            discovered.append({'gap': str(error)})
                    rc.write(root, 'discovery.json', json.dumps(discovered))
                offered += [s for s in discovered if s.get('file')]
            transport = research_text.Transport(runtime, call)
            research_session.Workflow(runtime).run(root, state['task'], transport, offered,
                limit=state['execution']['workers'], progress=lambda value: save(progress=value),
                allowed=lambda: not paused.is_set() and current(), cancelled=cancelled, restart_stopped=True)
            require(current() and not stop.is_set(), 'The infographic changed before research could be used. Checked research is kept.')
            save(state='complete', ended=time.time())
        except BaseException as error:
            save(state='paused' if paused.is_set() and not stop.is_set() else 'stopped' if stop.is_set() else 'failed',
                problem=str(error), ended=time.time())
        finally:
            with self.lock: self.active.pop(ident, None)

    def control(self, ident, action):
        with self.lock:
            root, state = self._state(ident)
            require(state is not None, 'Start research for this infographic first.')
            active = self.active.get(ident)
            if action in ('stop', 'pause'):
                require(active is not None, 'This host has no active invocation to stop. Saved evidence is kept.')
                active[0 if action == 'stop' else 1].set()
                state['state'] = 'stopping' if action == 'stop' else 'paused'
                rc.write(root, 'state.json', json.dumps(state))
                return self.read(ident)
            if action == 'preview':
                require(state['state'] == 'complete', 'Wait for independently reviewed research before using it.')
                project = self.store.read(ident); self.store.expect(project, state['project_revision'])
                runtime = Path(self.runtime) if self.runtime else rc.runtime_for(state['contract'])
                return research.prepare(research_session.case_for(root), expected_task=state['task'], runtime=runtime)
            if action in ('retry', 'resume'):
                require(active is None, 'Wait for current research invocations to finish before resuming.')
                return self.start(ident, state['project_revision'], None, retry=True)
            raise Invalid('Choose pause, stop, resume, retry or preview research.')

    def stop(self):
        with self.lock:
            for stop, _ in self.active.values(): stop.set()
