"""Explicit optional research jobs. Private checkpoints survive page disconnects."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import secrets
import threading
import time
from studio_core import activity_log
from studio_core import research_contract as rc, research_session, research_sources, research_text
from studio_core import public_fetch, source_documents, research_sites
from . import research, settings, sources as project_sources
from .activity import ending
from .assistant_failure import AssistantFailure
from .author import Author
from .contracts import Invalid
from .validation import identifier, require


def reads(project, source_mode):
    """What research reads of an infographic: its task, apart from the working title, and its
    captured sources. An edit that leaves this alone (a rename) leaves running research be."""
    from .contracts import digest
    task = {key: value for key, value in research.task(project, source_mode).items() if key != 'topic'}
    return digest({'task': task, 'sources': sorted((s['id'], s['sha256']) for s in project['sources'])})


def unchanged(project, state):
    """Whether the infographic still asks research what this saved research was made for."""
    if 'reads' in state:
        return reads(project, state['task']['source_mode']) == state['reads']
    return project['revision'] == state['project_revision']


class Jobs:
    def __init__(self, store, *, author=None, runtime=None, fetch=None):
        self.store, self.author, self.runtime = store, author, runtime
        self.fetch = fetch or public_fetch.fetch
        self.lock = threading.RLock()
        self.active = {}
        self.working = {}       # ident -> {token: a running research job and its lines}

    # What each research job is, in the words every studio uses for its research.
    DOING = {'discovery': 'Finding public references', 'investigate': 'Investigating the sources',
             'synthesize': 'Combining the evidence into the research report',
             'review': 'Independently checking the research'}

    def running(self, ident):
        """The research jobs running now for one infographic, as (id, job) pairs."""
        with self.lock:
            return list((self.working.get(ident) or {}).items())

    def workers(self, ident):
        """The research jobs running now for one infographic, as the page polls them."""
        return activity_log.live(self.running(ident))

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
            shown = {k: state[k] for k in ('state', 'request', 'project_revision', 'progress', 'problem', 'kept') if k in state}
            shown['elapsed_seconds'] = round((state.get('ended') or time.time()) - state['started'])
            shown['workers'] = self.workers(ident)
            if state['state'] in ('working', 'pausing', 'paused', 'stopping') and state.get('ended') is None and ident not in self.active:
                shown.update(state='needs-attention', problem='The previous research host ended without a terminal observation. Its evidence is kept. Do not repeat uncertain invocations; inspect or restore their terminal records first.')
            return shown

    def start(self, ident, expected_revision, reference, *, retry=False):
        # Read and pin all source choices before starting a provider or acquiring a job slot.
        project = self.store.read(ident); self.store.expect(project, expected_revision)
        prepared = research_sources.prepare_start(self.store.root, reference, primary=bool(project['sources'])) if reference else None
        with self.lock:
            if ident in self.active:
                return self.read(ident)
            previous, saved = self._state(ident)
            require(not saved or saved.get('ended') is not None, 'An earlier research host has no confirmed terminal outcome. Do not start another request until it is recovered.')
            require(previous is None or not research_session.unresolved(previous), 'An earlier research invocation has no confirmed terminal observation. Recover it before starting another request.')
            if retry:
                require(saved is not None and unchanged(project, saved), 'The infographic changed. Start research for its current brief.')
                require(saved['state'] not in ('working', 'pausing', 'paused', 'stopping'), 'An earlier host invocation needs terminal recovery before retrying.')
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
                # The helper counts by its protocol only: an update of it is the same request.
                key = research_session.digest([self.store.owner, ident, project['revision'], task,
                    prepared['id'], prepared['revision'], rc.stable(contract),
                    {**execution, 'capability': rc.stable(execution['capability'])}])
                base = self.folder(ident); rc.write(base, '.gitignore', '*\n')
                root = rc.inside(base, key)
                if (root / 'state.json').exists():
                    rc.write(base, 'current.json', json.dumps({'request': key}))
                    return self.read(ident)
                inputs = research_sources.install(prepared, root)
                state = {'schema': 1, 'owner': self.store.owner, 'project': ident, 'project_revision': project['revision'],
                    'request': key, 'contract': contract, 'execution': execution, 'task': task,
                    'reads': reads(project, research_sites.source_mode(choice)),
                    'inputs': inputs, 'choice': choice, 'configuration': settings.snapshot()['assistant'],
                    'state': 'working', 'progress': {'phase': 'investigate', 'streams': []},
                    'problem': '', 'started': time.time(), 'ended': None}
                rc.write(base, 'current.json', json.dumps({'request': key}))
            installed = research_session.capability(runtime) if runtime is not None else None
            require(installed is not None, rc.NOT_INSTALLED)
            # A retry goes on with the installed helper, whichever version research started
            # on. What the state held before is kept once: an older case is named by it.
            if installed != state['execution']['capability']:
                state['execution'].setdefault('earlier', {'capability': state['execution']['capability']})
                state['execution']['capability'] = installed
                state['contract'] = rc.capability(Path(runtime)) or state['contract']
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
            # Only an edit to what research reads stops it: a rename leaves it running.
            if not unchanged(project, state) or self.store.owner != state['owner']: return False
            # Validate current local originals without refetching Google or a website.
            for source in project['sources']:
                project_sources.read(self.store, project, source)
            return True
        def cancelled(): return stop.is_set() or not current()
        def call(phase, payload, guide):
            require(not cancelled(), 'Research stopped or its infographic changed. Saved work is kept.')
            left = int(2700 - (time.monotonic() - started))
            require(left > 0, 'Research reached its total 45-minute limit. Checked evidence is kept.')
            # What this job does is shown while it runs, and kept in the Activity log after.
            lines, token = activity_log.Lines(), secrets.token_hex(6)
            label = self.DOING.get(phase, 'Researching')
            job = {'label': label, 'started_at': activity_log.now(), 'lines': lines}
            with self.lock:
                self.working.setdefault(ident, {})[token] = job
            ended, detail = 'failed', None
            try:
                answer = author.research(phase, payload, guide, seconds=min(450, left), stop=stop,
                                         web=phase == 'discovery', activity=lines.append)
                ended = 'finished'
                return answer
            except AssistantFailure as failure:
                ended, detail = ending({'state': 'failed', 'reason': failure.reason}), str(failure)
                raise
            except BaseException:
                ended = 'stopped' if stop.is_set() else 'failed'
                raise
            finally:
                with self.lock:
                    (self.working.get(ident) or {}).pop(token, None)
                try:
                    self.store.keep_activity(ident, activity_log.entry(
                        label, 'research:' + str(phase), job['started_at'], ended, lines, detail))
                except Exception:   # a log that cannot be written never changes the research
                    pass
        try:
            _, offered = research_sources.sources(root, state['inputs'])
            project = self.store.read(ident)
            for source in project['sources']:
                text = project_sources.read(self.store, project, source)
                capture = {'file':'sources/project-' + source['id'] + '.txt', 'title':source.get('name') or source['id'],
                    'origin':(source.get('provenance') or {}).get('url') or 'Supplied infographic material: ' + (source.get('name') or source['id']),
                    'permission':'selected', 'text':text}
                if source['kind'] in ('pdf', 'docx'):
                    original = 'sources/primary-' + source['id'] + '.' + source['kind']
                    rc.write(root, original, rc.inside(self.store.root / 'projects' / ident, source['file']).read_bytes())
                    capture.update(original=original, original_path=rc.inside(root, original))
                offered.append(capture)
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
                allowed=lambda: not paused.is_set() and current(), cancelled=cancelled, restart_stopped=True,
                earlier=state['execution'].get('earlier') or {'capability': state['execution']['capability']})
            require(current() and not stop.is_set(), 'The infographic changed before research could be used. Checked research is kept.')
            save(state='complete', ended=time.time())
            # Verified research is kept in the Document Library for other projects. Keeping it
            # never fails or delays the research: the research above is already complete.
            save(kept=self._keep(ident, root))
        except BaseException as error:
            save(state='paused' if paused.is_set() and not stop.is_set() else 'stopped' if stop.is_set() else 'failed',
                problem=str(error), ended=time.time())
        finally:
            with self.lock: self.active.pop(ident, None)

    def _keep(self, ident, root):
        try:
            from studio_core.document_library.research import keep_research
            project = self.store.read(ident)
            done = keep_research(studio='infographic', case=research_session.case_for(root), project={
                'id': ident, 'title': project['brief']['title'], 'revision': project['revision']})
        except Exception:   # never raised into the research
            return {'state': 'failed', 'problem': 'The research could not be kept in the Document Library.'}
        shown = {'state': done.get('state')}
        if done.get('state') == 'kept':
            shown.update(document=done.get('document'), revision=done.get('revision'))
        else:
            shown['problem'] = str(done.get('problem') or 'It could not be kept.')[:500]
        return shown

    def control(self, ident, action, *, acknowledge_warnings=False):
        with self.lock:
            root, state = self._state(ident)
            require(state is not None, 'Start research for this infographic first.')
            active = self.active.get(ident)
            if action in ('stop', 'pause'):
                require(active is not None, 'This host has no active invocation to stop. Saved evidence is kept.')
                active[0 if action == 'stop' else 1].set()
                state['state'] = 'stopping' if action == 'stop' else 'pausing'
                rc.write(root, 'state.json', json.dumps(state))
                return self.read(ident)
            if action in ('preview', 'use'):
                require(state['state'] == 'complete', 'Wait for independently reviewed research before using it.')
                project = self.store.read(ident)
                require(unchanged(project, state), 'This infographic changed. Reload it before saving.')
                runtime = Path(self.runtime) if self.runtime else rc.runtime_for(state['contract'])
                preview = research.prepare(research_session.case_for(root), expected_task=state['task'], runtime=runtime)
                if action == 'preview':
                    return preview
                # Use research: its findings are added as a source in one step; the page then
                # asks for facts and a story from them. Extraction gaps are the person's to
                # acknowledge, as for any source: until they do, the preview is returned instead.
                require(type(acknowledge_warnings) is bool, 'Choose whether to acknowledge the gaps explicitly.')
                if preview.get('warnings') and not acknowledge_warnings:
                    return {'preview': preview, 'warnings': preview['warnings'], 'needs_acknowledgement': True}
                from . import intake
                return {'project': intake.adopt(self.store, ident, preview['id'], expected_revision=project['revision'],
                                                acknowledge_warnings=acknowledge_warnings)}
            if action in ('retry', 'resume'):
                require(active is None, 'Wait for current research invocations to finish before resuming.')
                # What research reads is unchanged (a rename leaves it so): go on against the
                # infographic's current revision.
                project = self.store.read(ident)
                require(unchanged(project, state), 'The infographic changed. Start research for its current brief.')
                return self.start(ident, project['revision'], None, retry=True)
            raise Invalid('Choose pause, stop, resume, retry, preview or use research.')

    def stop(self):
        with self.lock:
            for stop, _ in self.active.values(): stop.set()
