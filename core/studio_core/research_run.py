"""One run of the shared research workflow: research_session.Workflow.run.

A run reads its originals, registers its sources, investigates each area in parallel, reads
more than fifty documents in groups first, synthesizes, and has an independent check review
the result, for up to rc.ROUNDS rounds. What its steps share (the case, the host record of
every invocation, the progress the page is shown and the locks over them) is held by Run.

Every name research_session defines (bytes_of, now, capability, intake_limits, ...) is read
from research_session when called, since callers and tests replace names there.
"""
from __future__ import annotations

import copy
import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import secrets
import threading

from studio_core import research_contract as rc, research_timing, research_sections, research_preview, research_quality
from studio_core import research_reading, research_units
from studio_core import research_session as session


# What a review unit's state in Harness Research (`review-units status`) is shown as (#379).
# Accepted this time and kept from an earlier check both mean it is not reviewed again.
UNIT_SHOWN = {'pending': 'waiting', 'reserved': 'waiting', 'running': 'working', 'finished': 'working',
              'accepted': 'kept', 'kept': 'kept', 'failed': 'failed', 'refused': 'failed',
              'cancelled': 'stopped'}
# Which host phase works in which stage of the page, for the observed number working now.
STAGE_OF = {'investigate': 'gather', 'read': 'gather', 'synthesize': 'combine', 'review': 'check'}
LABEL_MOST = 80   # a unit's name is a question cut to this, never more of the research


def clocked(attempts, now):
    """How long the latest of these host attempts took, or has taken so far: {'attempts',
    'seconds', and 'started_at' while it works}, or {} when none was made."""
    if not attempts:
        return {}
    last = max(attempts, key=lambda attempt: attempt.get('started_at') or '')
    working = not last.get('ended_at')
    seconds = (now - research_timing.stamp(last['started_at'])) if working else last.get('seconds')
    shown = {'attempts': len(attempts)}
    if isinstance(seconds, (int, float)):
        shown['seconds'] = round(max(0, seconds), 1)
    if working:
        shown['started_at'] = last['started_at']
    return shown


def timed_out(error):
    """Whether a job ended because it ran out of its time: a native job's outcome, or a text
    transport's reason."""
    return getattr(getattr(error, 'outcome', None), 'reason', None) == 'timeout' \
        or getattr(error, 'reason', None) in ('timeout', 'time-limit')


class Watched:
    """The run's helper while a check in units runs: every command goes to the helper as it
    is, and what each review-units command says of a unit is shown on the page (#379)."""

    def __init__(self, workflow, run):
        self._workflow, self._run = workflow, run

    def __getattr__(self, name):
        return getattr(self._workflow, name)

    def command(self, root, group, action, value=None, **flags):
        result = self._workflow.command(root, group, action, value, **flags)
        if group == 'review-units':
            self._run.unit_seen(action, value, result)
        return result


def review_context(helper_value, reuse_value, section_value):
    """What a section review was made under: the helper's and reuse's protocols, the section
    guidance and who checks it. A saved review is reused only under the same."""
    return {'schema': 1, 'protocol': research_sections.fingerprint([helper_value, reuse_value]),
        'guidance': research_sections.fingerprint([research_sections.PROTOCOL, section_value]),
        'independence': research_sections.fingerprint((section_value or {}).get('checking'))}


class Run:
    """One call of research_session.Workflow.run, with what its steps share."""

    def __init__(self, workflow, root, task, invoke, sources, *, limit, progress, allowed,
                 cancelled, readable, restart_stopped, section_policy, section_context, impact,
                 input_snapshot, creator_review, reading, earlier, review_units=None):
        self.workflow, self.root, self.task, self.sources = workflow, root, task, sources
        self.given_invoke = invoke   # the studio's own; self.invoke records each call first
        self.limit, self.progress, self.allowed, self.cancelled = limit, progress, allowed, cancelled
        self.readable, self.restart_stopped = readable, restart_stopped
        self.section_policy, self.section_context, self.impact = section_policy, section_context, impact
        self.input_snapshot, self.creator_review, self.reading = input_snapshot, creator_review, reading
        self.earlier = earlier
        # The case's review-units entry: its check is done in units (research_units.Check),
        # held in `checking` while one runs. None: the single review.
        self.review_units, self.checking = review_units, None
        # What the page is shown of each review unit, by id, in plan order (#379); and of the
        # final brief while sections are combined: None until combining reaches it.
        self.units_shown, self.final_shown = {}, None
        self.host_lock = threading.RLock()    # over the host record of invocations
        self.state_lock = threading.RLock()   # over the progress the page is shown

    def go(self):
        """The run, step by step: the checked bundle, as rc.read_bundle returns it."""
        self.prepare()
        self.open_case()
        self.open_collection()
        # Each check reads an original again only when it may have changed (Originals).
        self.originals = session.Originals([s['original_path'] for s in self.sources if s.get('original_path')])
        self.reuse_review_context()
        if self.section_policy:
            self.reuse_sections()
        finished = self.finished_already()
        if finished is not None:
            return finished
        self.correct_for_creator()
        self.read_in_groups()
        # Every source each investigator is given, with each field it must return (#303).
        self.outlines = {area['id']: rc.source_outline(self.given[area['id']], self.workflow.runtime)
                         for area in self.areas}
        # And the exact shape the synthesis and the review return.
        self.synthesis_outline = rc.synthesis_outline(self.workflow.runtime)
        self.review_outline = rc.review_outline(self.workflow.runtime)
        for number in range(1, rc.ROUNDS + 1):
            checked = self.round(number)
            if checked is not None:
                return checked
        raise rc.ReviewRefused(rc.objections(self.case), rc.ROUNDS, rc.grouped(self.case))

    def prepare(self):
        """Everything said before anything is registered: the helper, the saved policy, an
        unconfirmed earlier invocation, the areas, the case's name and the run's size."""
        workflow, root, task, sources = self.workflow, self.root, self.task, self.sources
        self.capability = session.capability(workflow.runtime)
        if self.capability is None:
            raise ValueError('This workflow needs the complete Harness Research 1.1 collection runtime.')
        # Stop ends a helper command this run starts itself while it is running.
        workflow.cancelled = workflow.helper.cancelled = self.cancelled
        self.earlier = self.earlier if isinstance(self.earlier, dict) else {}
        if task.get('research_policy') and not research_quality.valid_policy(task['research_policy']):
            raise ValueError('Restore the saved focused research policy before continuing.')
        if session.unresolved(root):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')
        if self.review_units is not None:
            # A case that started checking in units goes on in units, or is refused plainly.
            if not research_units.valid(self.review_units):
                raise ValueError(research_units.UNREADABLE)
            if research_units.capability(workflow.runtime) is None:
                raise ValueError(research_units.GONE)
        if self.section_policy and self.impact:
            from studio_core import research_impact
            research_impact.context_current(root, task, self.impact)
        self.areas = session.section_streams(task) if self.section_policy else session.streams(task, self.limit)
        inputs = [[s.get('file'), s.get('origin'), s.get('permission'),
            hashlib.sha256(s['text'].encode()).hexdigest(),
            hashlib.sha256(session.bytes_of(s['original_path'])).hexdigest() if s.get('original_path') else None]
            for s in sources]
        self.basis = session.case_basis(root, task, inputs, self.capability, self.areas, self.earlier.get('capability'))
        # What an older Marketing Studio keyed sections and reviews with counts as the same, and
        # each is keyed anew as it is met.
        self.earlier_context = self.earlier.get('section_context')
        # Said here, before anything is registered, and never after the work has begun.
        chosen_count = sum(source.get('permission', 'selected' if source.get('offered', True) else 'public') == 'selected'
                           for source in sources)
        if not self.reading and chosen_count > research_reading.GROUP:
            raise ValueError(session.TOO_MANY.format(count=chosen_count, most=research_reading.GROUP))
        most, count = session.intake_limits(workflow.runtime)['entries'], session.intake_entries(sources)
        if count > most:
            raise ValueError(session.OVER_INTAKE.format(most=most, count=count))

    def open_case(self):
        """The case with its sources registered, and the host record of its invocations."""
        self.case, self.offered = self.workflow.asset(self.root, self.task, self.sources, self.basis)
        self.host_file = '.harness-research/studio-execution.json'
        host_path = rc.inside(self.case, self.host_file)
        self.host = json.loads(session.bytes_of(host_path)) if host_path.exists() else {'schema': 1, 'started': session.now(), 'attempts': []}
        if any(not attempt.get('ended_at') for attempt in self.host['attempts']):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')

    def invoke(self, phase, guidance, payload, offered, fetch):
        """The studio's invoke, with each call recorded in the host record before it starts
        and after it ends, or as not confirmed to have ended."""
        payload = copy.deepcopy(payload)
        payload.setdefault('_execution', {}).setdefault('invocation', 'research-invocation-' + secrets.token_hex(16))
        invocation = payload['_execution']['invocation']
        unit = payload['_execution'].get('unit')   # a review unit's, shown as its section
        attempt = {'phase': phase, 'invocation': invocation, 'worker': payload['worker'],
                   'stream': payload['_execution'].get('stream'),
                   'section': payload['_execution'].get('section') or (research_units.section(unit) if unit else None),
                   'started_at': session.now(), 'status': 'working', **({'unit': unit} if unit else {})}
        with self.host_lock:
            self.host['attempts'].append(attempt)
            rc.write(self.case, self.host_file, json.dumps(self.host))
        confirmed = True
        try:
            self.report()
            return self.given_invoke(phase, guidance, payload, offered, fetch)
        except BaseException as error:
            confirmed = getattr(error, 'terminal_confirmed', True)
            raise
        finally:
            with self.host_lock:
                attempt['status'] = 'finished' if confirmed else 'termination-unconfirmed'
                if confirmed:
                    attempt['ended_at'] = session.now()
                    attempt['seconds'] = max(0, research_timing.stamp(attempt['ended_at']) - research_timing.stamp(attempt['started_at']))
                rc.write(self.case, self.host_file, json.dumps(self.host))
            self.report()

    def open_collection(self):
        """The helper's collection for this case, started, resumed or begun again, and the
        progress the page is first shown."""
        task, case, limit = self.task, self.case, self.limit
        self.request = {'schema': 1, **{k: task[k] for k in rc.TASK_FIELDS},
                   'execution_mode': 'parallel' if limit > 1 else 'sequential',
                   'max_investigators': min(3, max(1, limit)),
                   'workstreams': [{'id': a['id'], 'questions': [q.get('question') or q.get('text') or q.get('id')
                        if isinstance(q, dict) else str(q) for q in a['questions']]} for a in self.areas]}
        self.state_file = case / '.harness-research/collection.json'
        if not self.state_file.exists():
            status = self.workflow.command(case, 'collection', 'init', self.request)
        else:
            status = self.workflow.command(case, 'collection', 'status')
            if status['status'] == 'stale':
                raise ValueError('Saved research inputs changed. Refresh sources explicitly; earlier work is kept.')
            if status['status'] == 'paused' and self.allowed():
                status = self.workflow.command(case, 'collection', 'resume')
            if status['status'] == 'stopped':
                if not self.restart_stopped:
                    raise ValueError('This collection was stopped. Its checked work is kept; explicitly retry research to start a new generation.')
                status = self.workflow.command(case, 'collection', 'invalidate', self.request)
        held = json.loads(session.bytes_of(self.state_file))
        if any(a.get('started_at') and not a.get('ended_at') for s in held['workstreams'] for a in s['attempts']):
            raise ValueError('An earlier research invocation has no confirmed terminal observation. Confirm it ended before retrying; saved evidence is kept.')
        kept = {s['id'] for s in status['workstreams'] if s['status'] == 'accepted'}
        self.tracked = {'schema': 1, 'phase': 'investigate', 'round': 1, 'round_limit': rc.ROUNDS, 'streams': [
            {'id': a['id'], 'questions': self.request['workstreams'][i]['questions'],
             'status': 'kept' if a['id'] in kept else 'waiting'} for i, a in enumerate(self.areas)]}

    def report(self, phase=None, stream=None, state=None):
        """Tell the page where the run is: its phase, an area's state, the agents at work and
        the time taken."""
        tracked, host = self.tracked, self.host
        with self.state_lock:
            if phase: tracked['phase'] = phase
            for area in tracked['streams']:
                if area['id'] == stream:
                    area['status'] = state
                    if state != 'kept': area.pop('evidence', None)
            with self.host_lock:
                timing = research_timing.account(host['started'], host['attempts'])
                active = [{'id': a['worker'], 'phase': a['phase'], 'stream': a.get('stream'),
                           'section': a.get('section'),
                           'status': a.get('status', 'working'), **({'unit': a['unit']} if a.get('unit') else {})}
                          for a in host['attempts'] if not a.get('ended_at')]
                self.units_timed(tracked, host['attempts'])
            unconfirmed = sum(a['status'] == 'termination-unconfirmed' for a in active)
            tracked['agents'] = {'count': None if unconfirmed else len(active),
                                 'unconfirmed': unconfirmed, 'active': active}
            tracked['counts'] = self.counts(tracked, active, unconfirmed)
            if timing['incomplete']:
                timing.update(active_seconds=None, assistant_seconds=None)
            tracked['timing'] = timing
            if phase in ('stopped', 'paused', 'invalidated') or self.cancelled():
                for area in tracked['streams']: area.pop('evidence', None)
            if phase == 'complete': tracked['checked_result_seconds'] = timing.get('elapsed_seconds')
            self.progress(copy.deepcopy(tracked))

    # What the page is shown of each unit of work (#379): the areas gathered, the sections
    # combined, the final brief, and each review unit with the final whole-research check;
    # how long each took from the host's own record of its attempts, and how many work now.
    # Names and numbers only: never evidence, prose or review text.

    def units_timed(self, tracked, attempts):
        """Each area's, section's, final brief's and review unit's attempts and time, from the
        host record (held under host_lock)."""
        now = research_timing.stamp(session.now())
        def by(test):
            return [attempt for attempt in attempts if attempt.get('started_at') and test(attempt)]
        for area in tracked['streams']:
            for key in ('attempts', 'seconds', 'started_at'): area.pop(key, None)
            area.update(clocked(by(lambda a: a['phase'] == 'investigate' and a.get('stream') == area['id']), now))
        for row in tracked.get('combining') or ():
            for key in ('attempts', 'seconds', 'started_at'): row.pop(key, None)
            row.update(clocked(by(lambda a: a['phase'] == 'synthesize' and a.get('section') == row['id']), now))
        if self.final_shown is not None:
            tracked['final_brief'] = {'status': self.final_shown, **clocked(
                by(lambda a: a['phase'] == 'synthesize' and a.get('section') == 'final'), now)}
        if self.units_shown:
            tracked['review_units'] = [
                {**{key: unit[key] for key in ('id', 'kind', 'label', 'status')},
                 **clocked(by(lambda a, ident=unit['id']: a['phase'] == 'review' and a.get('unit') == ident), now),
                 **({'attempts': unit['attempt']} if unit.get('attempt') else {})}
                for unit in self.units_shown.values()]

    def counts(self, tracked, active, unconfirmed):
        """For each stage with units: how many work now (observed: the host's live jobs, never
        the configured limit; None when a job's end is unconfirmed), wait, are kept and failed."""
        rows = {'gather': tracked['streams'],
                'combine': [*(tracked.get('combining') or ()),
                            *([tracked['final_brief']] if tracked.get('final_brief') else [])],
                'check': tracked.get('review_units') or []}
        shown = {}
        for stage, units in rows.items():
            if not units:
                continue
            working = sum(STAGE_OF.get(agent['phase']) == stage for agent in active)
            shown[stage] = {'working': None if unconfirmed else working, 'total': len(units),
                            **{state: sum(unit.get('status') == state for unit in units)
                               for state in ('waiting', 'kept', 'failed', 'stopped')}}
        return shown

    def unit_label(self, unit):
        """A review unit's name a person can read: the question of the area it checks, or
        the whole research for the final unit."""
        if unit.get('kind') == 'final' or unit.get('id') == research_units.FINAL:
            return 'the whole research'
        questions = {area['id']: area['questions'] for area in self.tracked['streams']}
        named = [questions[area] for area in unit.get('areas') or () if questions.get(area)]
        if not named:
            return 'one part of the research'
        first = str(named[0][0])
        first = first if len(first) <= LABEL_MOST else first[:LABEL_MOST - 1].rstrip() + '…'
        more = len(named) - 1
        return first + (f' (and {more} more area{"" if more == 1 else "s"})' if more else '')

    def unit_seen(self, action, value, result):
        """What one review-units command said of the units, shown on the page when it
        changed what the page shows."""
        with self.state_lock:
            before = copy.deepcopy(self.units_shown)
            listed = result.get('units') if isinstance(result, dict) else None
            if isinstance(listed, list) and listed and all(isinstance(u, dict) and u.get('id') for u in listed):
                # A status or plan lists every unit of the plan: shown in its order.
                self.units_shown = {unit['id']: {
                    'id': unit['id'], 'kind': 'final' if unit.get('kind') == 'final' or unit['id'] == research_units.FINAL else 'content',
                    'label': self.unit_label(unit), 'status': UNIT_SHOWN.get(unit.get('status'), 'waiting'),
                    'attempt': unit.get('attempt') if type(unit.get('attempt')) is int else None}
                    for unit in listed}
            else:
                ident = (value or {}).get('unit') if isinstance(value, dict) else None
                ident = ident.get('id') if isinstance(ident, dict) else ident
                shown = self.units_shown.get(ident)
                if shown is not None:
                    if action == 'register':
                        shown['status'] = 'working'
                        number = ((result or {}).get('registration') or {}).get('number')
                        if type(number) is int: shown['attempt'] = number
                    elif action == 'accept':
                        shown['status'] = 'kept'
                    elif action == 'finish' and value.get('outcome') in ('failed', 'refused', 'cancelled'):
                        shown['status'] = UNIT_SHOWN[value['outcome']]
                    elif action == 'retry':
                        shown['status'] = 'waiting'
                elif action == 'stop':
                    for unit in self.units_shown.values():
                        if unit['status'] == 'working': unit['status'] = 'stopped'
            changed = self.units_shown != before
        if changed:
            self.report()

    def final_progress(self, state, error=None):
        """What section combining says of the final brief: waiting, working, kept, or ended
        by `error` (failed, or stopped by a stop), shown on the page."""
        how = None
        if error is not None:
            state, how = ('stopped', 'stopped') if self.stopped_by(error) else \
                ('failed', 'timed-out' if timed_out(error) else 'failed')
        with self.state_lock:
            self.final_shown = state
            if how:
                sections = self.tracked.get('combining') or []
                self.ended_in('final-brief', how, kept=sum(row.get('status') == 'kept' for row in sections),
                              total=len(sections))
        self.report()

    def stopped_by(self, error):
        """Whether `error` is a stop or pause rather than a failure."""
        return isinstance(error, (InterruptedError, KeyboardInterrupt)) or type(error).__name__ == 'Stopped' \
            or bool(self.cancelled()) or not self.allowed()

    def ended_in(self, part, how, *, kept, total, label=None, parts=1):
        """Where this run ended, said once for every studio (research_transport.ended_words):
        the final brief or a review unit, how, and what is kept."""
        from studio_core import research_transport
        self.tracked['ended_in'] = {
            'part': part, 'how': how, **({'label': label} if label else {}), 'kept': kept, 'total': total,
            'said': research_transport.ended_words(part, how, label=label, parts=parts, kept=kept, total=total)}

    def units_ended(self, error):
        """A check in units that ended early: which unit, how, and the checks kept."""
        units = list(self.units_shown.values())
        if not units:
            return
        stopped = self.stopped_by(error)
        if stopped:
            for unit in units:
                if unit['status'] == 'working': unit['status'] = 'stopped'
        ended = [unit for unit in units if unit['status'] == ('stopped' if stopped else 'failed')] \
            or [unit for unit in units if unit['status'] in ('failed', 'stopped', 'working')]
        kept = sum(unit['status'] == 'kept' for unit in units)
        if not ended:
            return
        final = all(unit['kind'] == 'final' for unit in ended)
        named = [unit for unit in ended if unit['kind'] != 'final']
        with self.state_lock:
            self.ended_in('whole-check' if final else 'review-unit',
                          'stopped' if stopped else 'timed-out' if timed_out(error) else 'failed',
                          label=named[0]['label'] if len(named) == 1 else None,
                          parts=len(named), kept=kept, total=len(units))

    def require(self):
        """Go on only while the originals are unchanged, the run is not stopped and it is
        allowed: otherwise the collection is stopped or paused, and the run ends."""
        case, checking = self.case, self.checking
        if self.originals.changed():
            if checking: checking.stop()
            self.workflow.command(case, 'collection', 'stop')
            self.report('invalidated')
            raise ValueError('A selected original changed during research. Earlier evidence is kept; capture and approve its new revision.')
        if self.cancelled():
            # A check in units is stopped by itself: the collection stays complete, and the
            # units it accepted are kept for when it goes on.
            if checking: checking.stop()
            else: self.workflow.command(case, 'collection', 'stop')
            self.report('stopped')
            raise InterruptedError('Research stopped; accepted evidence is kept.')
        if not self.allowed():
            if checking: checking.stop()
            self.workflow.command(case, 'collection', 'pause')
            self.report('paused')
            raise InterruptedError('Research paused; accepted evidence is kept.')

    def reuse_review_context(self):
        """Under a section policy that reuses reviews: whether the saved review context is the
        one this run works under, and this run's context saved for the next."""
        self.reuse_context = None
        self.context_unchanged = True
        section_policy, section_context, earlier = self.section_policy, self.section_context, self.earlier
        if section_policy and section_policy.get('reuse'):
            # Unchanged-save review is the installed helper's: an update keeps a review that
            # passed, since what it reviewed is unchanged. The context names protocols only.
            self.reuse_context = '.harness-research/studio-review-context.json'
            context = review_context(rc.stable(self.capability), rc.stable(research_sections.reuse_capability(self.workflow.runtime)
                                                                  or section_policy['reuse']), section_context)
            accepted_contexts = [context]
            if isinstance(earlier.get('capability'), dict):
                accepted_contexts += [review_context(earlier['capability'], earlier.get('reuse'), value)
                                      for value in (section_context, self.earlier_context) if value is not None]
            context_file = rc.inside(self.case, self.reuse_context)
            self.context_unchanged = context_file.exists() and json.loads(context_file.read_bytes()) in accepted_contexts
            rc.write(self.case, self.reuse_context, json.dumps(context))

    def reuse_sections(self):
        """Keep each section whose inputs are unchanged, and save what this run works from."""
        from studio_core import research_impact
        case, task, section_context, earlier_context = self.case, self.task, self.section_context, self.earlier_context
        research_impact.reuse(self.workflow, self.root, case, task, self.areas, self.impact, section_context, self.require,
                              earlier_context, tuple(value.get('scope_identity')
                                                     for value in (section_context, earlier_context) if value))
        if self.input_snapshot:
            rc.write(case, '.harness-research/studio-inputs.json', json.dumps(self.input_snapshot))
            rc.write(case, '.harness-research/studio-task-context.json', json.dumps({key: task[key] for key in rc.TASK_FIELDS if key != 'planning_questions'}))
        rc.write(case, '.harness-research/studio-section-context.json', json.dumps(section_context))

    def finished_already(self):
        """The bundle when the saved research was accepted under an unchanged context and still
        verifies, else None. Keeps the saved review and dossier for the rounds."""
        case = self.case
        previous = case / '.harness-research/synthesis.json'
        self.prior = json.loads(session.bytes_of(previous)) if previous.exists() else {}
        if self.context_unchanged and (self.prior.get('review') or {}).get('accepted'):
            verified = self.workflow.helper.command(case, 'verify')
            if verified.get('status') == 'complete':
                self.report('complete')
                return rc.read_bundle(rc.output_root(case))
        self.review, self.dossier = (self.prior.get('review') or {}), self.prior.get('dossier')
        return None

    def correct_for_creator(self):
        """A user-triggered retry repairs a previous rejected draft once. Merely opening the
        creator decision form never invalidates kept contributions."""
        case, review = self.case, self.review
        if (self.creator_review and review and not review.get('accepted')
                and not research_quality.coverage(review)['unread']
                and all(row['status'] == 'accepted' for row in self.workflow.command(case, 'collection', 'status')['workstreams'])):
            registry = self.workflow.command(case, 'collection', 'assemble')
            affected = sorted(session.corrections(review, registry, sectioned=bool(self.section_policy)))
            if self.section_policy: research_sections.invalidate(case, review, affected)
            for stream in affected:
                self.workflow.command(case, 'collection', 'retry', {'workstream': stream, 'reason': 'The creator explicitly requested another correction attempt.'})

    def read_in_groups(self):
        """More than fifty documents are read in groups first, one agent to a group, and each
        area's investigator is then offered only the documents its notes rank highest. Sets
        what each area is given, and how many sources each may cite."""
        root, offered, areas = self.root, self.offered, self.areas
        self.given = {area['id']: offered for area in areas}
        self.cited_most = None
        if not research_reading.needed(offered):
            return
        if not self.reading:
            raise ValueError(session.TOO_MANY.format(count=len(research_reading.selected(offered)), most=research_reading.GROUP))
        chosen = research_reading.selected(offered)
        every = research_reading.groups(chosen)
        place = {source['file']: n for n, source in enumerate(sorted(chosen, key=lambda one: one['file']), start=1)}
        waiting = research_reading.waiting(root, offered, areas)
        spans = [{'from': place[group[0]['file']], 'to': place[group[-1]['file']], 'status': 'waiting'} for group in waiting]
        with self.state_lock:
            self.tracked['reading'] = {'total': len(chosen), 'read': len(chosen) - sum(len(g) for g in waiting),
                                       'groups': spans, 'of': len(every)}
        if waiting:
            self.report('read')
        missed = []
        with ThreadPoolExecutor(max_workers=min(3, max(1, self.limit))) as pool:
            futures = [pool.submit(contextvars.copy_context().run, self.note, number, group, spans[number],
                                   len(chosen), len(waiting))
                       for number, group in enumerate(waiting)]
            for future in as_completed(futures):
                try: future.result()
                except BaseException as error: missed.append(error)
        if missed:
            # Groups that finished keep their notes; a retry reads only the rest.
            self.report('needs-attention')
            raise missed[0]
        self.require()
        plan = research_reading.assign(root, offered, areas)
        rc.write(self.case, '.harness-research/studio-reading.json', json.dumps(plan))
        found = [source for source in offered if source not in chosen]
        by_file = {source['file']: source for source in chosen}
        self.given = {area['id']: [by_file[file] for file in plan['assignment'][area['id']]] + found for area in areas}
        # The independent check reads every cited original, so what all areas cite together
        # stays within one agent's fifty too.
        self.cited_most = max(1, research_reading.GROUP // len(areas))
        with self.state_lock:
            self.tracked['reading'].update(unused=len(plan['unused']), dropped=sum(plan['dropped'].values()))
        self.report('investigate')

    def note(self, number, group, span, total, workers):
        """One reader's notes on one group of documents, kept once they pass their check."""
        self.require()
        worker = 'reader-' + secrets.token_hex(12)
        with self.state_lock: span['status'] = 'working'
        self.report()
        wanted = research_reading.spec(group, self.areas)
        payload = {'task': self.task, 'worker': worker, 'areas': research_reading.labels(self.areas),
            'documents': wanted['documents'], 'return': research_reading.GUIDANCE,
            '_execution': {'phase': 'read', 'round': 1, 'stream': f'group-{number + 1:02d}',
                'workers': workers, 'mode': 'reading', 'invocation': 'research-invocation-' + secrets.token_hex(16),
                'span': [span['from'], span['to'], total], 'reading': wanted}}
        try:
            text, _ = self.invoke('read', research_reading.GUIDANCE, payload, group, False)
            problems = research_reading.check(text, wanted)[0]
            if problems: raise ValueError(' '.join(problems))
            self.require()
            research_reading.keep(self.root, group, self.areas, json.loads(text), worker)
        except BaseException:
            with self.state_lock: span['status'] = 'failed'
            self.report()
            raise
        with self.state_lock:
            span['status'] = 'read'
            self.tracked['reading']['read'] += len(group)
        self.report()

    def round(self, number):
        """One round: investigate each area not yet accepted, synthesize, and have the result
        checked. The checked bundle when the research is complete, else None."""
        pending = self.investigate(number)
        registry, base, offered_final = self.assemble()
        worker = self.synthesize(number, pending, registry, base, offered_final)
        return self.check(number, registry, worker, offered_final)

    def investigate(self, number):
        """Every area not yet accepted, investigated in parallel: the areas that were pending."""
        self.require()
        self.tracked['round'] = number
        status = self.workflow.command(self.case, 'collection', 'status')
        accepted = research_preview.restored(self.case, json.loads(session.bytes_of(self.state_file)), self.basis)
        with self.state_lock:
            for row in self.tracked['streams']:
                row.pop('evidence', None)
                if row['id'] in accepted: row['evidence'] = accepted[row['id']]
        pending = []
        for area in self.areas:
            saved = next(s for s in status['workstreams'] if s['id'] == area['id'])
            if saved['status'] == 'accepted': self.report(stream=area['id'], state='kept')
            else: pending.append((area, saved))
        # Do not paint a fresh investigation when only synthesis prose needs repair.
        if pending: self.report('investigate')
        failures = []
        with ThreadPoolExecutor(max_workers=min(3, max(1, self.limit))) as pool:
            futures = [pool.submit(contextvars.copy_context().run, self.collect, area, saved, number, len(pending))
                       for area, saved in pending]
            for future in as_completed(futures):
                try: future.result()
                except BaseException as error: failures.append(error)
        if failures:
            self.report('needs-attention')
            raise failures[0]
        self.require()
        return pending

    def collect(self, area, saved, number, workers):
        """One investigator's evidence for one area, registered and accepted once it passes."""
        workflow, case, task = self.workflow, self.case, self.task
        cited_most = self.cited_most
        self.require()
        self.report(stream=area['id'], state='working')
        worker = 'investigator-' + secrets.token_hex(12)
        invocation = 'research-invocation-' + secrets.token_hex(16)
        if saved['status'] not in ('pending', 'reserved'):
            workflow.command(case, 'collection', 'retry', {'workstream': area['id'], 'reason': 'Retry this unaccepted area.'})
        registered = workflow.command(case, 'collection', 'register',
            {'workstream': area['id'], 'investigator': worker, 'invocation': invocation})
        registration = registered['registration']
        payload = {'task': task, 'worker': worker, 'questions': area['questions'],
            'return': session.EVIDENCE + (' ' + research_quality.FOCUSED_GUIDANCE +
                f' Return at most {task["research_policy"]["facts_per_area"]} essential facts '
                f'and {task["research_policy"]["sources_per_area"]} cited sources for this area.'
                if task.get('research_policy') else '') + (
                f' Cite at most {cited_most} sources for this area: the ones that carry the most.'
                if cited_most else ''), 'source_outline': self.outlines[area['id']],
            'previous_review': self.review, 'previous_dossier': self.dossier,
            '_execution': {'phase': 'investigate', 'round': number, 'stream': area['id'],
                'workers': workers, 'mode': 'evidence', 'invocation': invocation,
                'research_policy': task.get('research_policy')}}
        terminal = {'workstream': area['id'], 'investigator': worker, 'attempt': registration['number']}
        try:
            text, captures = self.invoke('investigate', (workflow.runtime / 'references/investigate.md').read_text(),
                                         payload, self.given[area['id']], task['source_mode'] != 'selected')
            require_cancelled = self.cancelled()
            workflow.command(case, 'collection', 'finish', {**terminal, 'outcome': 'completed',
                'note': 'The host transport returned from this isolated invocation.'})
            if require_cancelled:
                workflow.command(case, 'collection', 'stop')
                raise InterruptedError('Stopped research cannot adopt a late response.')
            value = json.loads(text)
            research_quality.evidence(value, task.get('research_policy'))
            if not isinstance(value.get('sources'), list) or not isinstance(value.get('facts'), list):
                raise ValueError('Return captured sources and facts as arrays.')
            if cited_most and len(value['sources']) > cited_most:
                raise ValueError(f'Cite at most {cited_most} sources for this area; {len(value["sources"])} were returned. '
                                 'Keep the ones that carry the most.')
            value, problems = rc.source_metadata(value, workflow.runtime)
            if problems: raise ValueError(' '.join(problems))
            value, problems, _ = rc.citation_sources(value, captures)
            problems += rc.uncaptured(value['sources'], captures)
            if problems: raise ValueError(' '.join(problems))
            captured = {s['file']: s for s in captures}
            for source in value['sources']:
                original = captured[source['file']]
                with workflow.lock:
                    for key, path_key in (('file', 'path'), ('original_file', 'original_path')):
                        if original.get(path_key):
                            old = source.get(key) or original.get('original')
                            if old:
                                file = 'sources/collection/' + area['id'] + '/' + str(registration['number']) + '/' + old
                                rc.write(case, file, session.bytes_of(original[path_key]))
                                source[key] = file
                    if source['permission'] == 'public':
                        workflow.command(case, 'asset', 'source', {'id': 'source-' + secrets.token_hex(12),
                            'role': 'discovered', 'origin': source['origin'], 'permission': 'public',
                            'outcome': 'captured', 'capture_file': source['file'], 'accessed_at': session.now()})
            workflow.capture_sources(case, terminal, value['sources'], registered)
            gaps = session.evidence_gaps(value)
            packet = {'schema': 1, 'request_digest': registered['request_digest'],
                'generation': registered['generation'], **terminal, 'sources': value['sources'],
                'facts': value['facts'], 'limitations': [], 'gaps': gaps}
            self.require()
            workflow.command(case, 'collection', 'accept', packet)
            with self.state_lock:
                for row in self.tracked['streams']:
                    if row['id'] == area['id']: row['evidence'] = research_preview.evidence(packet, self.basis)
                if 'first_finding_seconds' not in self.tracked:
                    with self.host_lock:   # sibling workers append attempts
                        timing = research_timing.account(self.host['started'], self.host['attempts'])
                    self.tracked['first_finding_seconds'] = timing.get('elapsed_seconds')
            self.report(stream=area['id'], state='kept')
        except BaseException as error:
            # invoke returns/raises only after the transport confirms termination.
            # Completed observations must not be overwritten by a conflicting outcome.
            # Read under the helper lock: a sibling worker's helper command may be
            # rewriting the collection state at this moment.
            with workflow.lock:
                state = json.loads(session.bytes_of(self.state_file))
                attempt = next(s for s in state['workstreams'] if s['id'] == area['id'])['attempts'][-1]
                if not attempt.get('ended_at') and getattr(error, 'terminal_confirmed', True):
                    workflow.command(case, 'collection', 'finish', {**terminal,
                        'outcome': 'cancelled' if self.cancelled() else 'failed',
                        'note': 'The host transport ended before a checked packet was accepted.'})
            self.report(stream=area['id'], state='failed' if getattr(error, 'terminal_confirmed', True) else 'termination-unconfirmed')
            raise

    def assemble(self):
        """The registered evidence: (the helper's registry, the evidence base a synthesis
        keeps unchanged, the sources the synthesizer and the check are offered)."""
        case = self.case
        registry = self.workflow.command(case, 'collection', 'assemble')
        if not registry['facts']:
            for area in self.areas:
                self.workflow.command(case, 'collection', 'retry', {'workstream': area['id'], 'reason': 'No cited facts were collected; review source access before retrying.'})
            self.report('needs-attention')
            raise ValueError('The investigators found no cited facts. Captured work and gaps are kept; review source access and the approved scope.')
        base = {'schema': 2, **{k: self.task[k] for k in rc.TASK_FIELDS}, 'sources': registry['sources'], 'facts': registry['facts']}
        offered_final = [{'title': s['title'], 'origin': s['origin'], 'file': s['file'],
            'permission': s['permission'], 'text': rc.inside(case, s['file']).read_text(),
            'path': rc.inside(case, s['file']),
            **({'original': s['original_file'], 'original_path': rc.inside(case, s['original_file'])}
               if s.get('original_file') else {})} for s in base['sources']]
        return registry, base, offered_final

    def synthesize(self, number, pending, registry, base, offered_final):
        """This round's dossier, by section, kept from an unfinished check, or written by one
        synthesizer: the worker that wrote it."""
        runtime, task = self.workflow.runtime, self.task
        if self.section_policy:
            self.dossier, worker = research_sections.combine(self.case, task, self.areas, registry, base,
                offered_final, self.invoke, round=number,
                guidance=(runtime / 'references/synthesize.md').read_text(),
                policy={**self.section_policy, 'workers': self.limit}, require=self.require,
                notify=self.section_progress, context=self.section_context, earlier=self.earlier_context,
                final=self.final_progress)
            self.require()
        elif (number == 1 and not pending and self.context_unchanged
              and research_quality.coverage(self.review)['unread']
              and isinstance(self.dossier, dict) and self.prior.get('author')
              and not session.check_frozen(self.dossier, {'evidence_base': base})):
            # Saved non-sectioned runs also resume an unfinished check without
            # paying a synthesizer to rewrite the same validated dossier.
            worker = self.prior['author']
        elif (number == 1 and not pending and self.context_unchanged and self.unfinished_units()
              and isinstance(self.dossier, dict) and self.prior.get('author')
              and not session.check_frozen(self.dossier, {'evidence_base': base})):
            # A check in units that stopped or failed goes on with the dossier it checks,
            # so every unit it accepted is kept.
            worker = self.prior['author']
        else:
            worker = 'synthesizer-' + secrets.token_hex(12)
            self.report('synthesize')
            payload = {'task': task, 'worker': worker, 'evidence': base, 'gaps': registry['gaps'],
                'synthesis_outline': self.synthesis_outline,
                'previous_dossier': self.dossier, 'previous_review': self.review, 'return': session.COMPOSE + rc.IDS_FOR_QUESTIONS,
                '_execution': {'phase': 'synthesize', 'round': number, 'mode': 'compose', 'evidence_base': base}}
            text, _ = self.invoke('synthesize', (runtime / 'references/synthesize.md').read_text(), payload, offered_final, False)
            self.require()
            self.dossier = json.loads(text)
        if session.check_frozen(self.dossier, {'evidence_base': base}):
            raise ValueError('Synthesis changed registered evidence; investigator work is kept.')
        return worker

    def unfinished_units(self):
        """Whether the saved dossier has a check in units begun and not assembled."""
        if self.review_units is None or self.prior.get('review') or not self.prior.get('digest'):
            return False
        status = self.workflow.command(self.case, 'review-units', 'status')
        return status.get('plan') is not None and status.get('planned_digest') == self.prior['digest']

    def section_progress(self, values):
        """What section synthesis reports of its sections, shown to the page."""
        with self.state_lock:
            self.tracked['combining'] = values
            if any(row.get('preview') for row in values) and 'first_readable_seconds' not in self.tracked:
                with self.host_lock:   # section workers append attempts
                    timing = research_timing.account(self.host['started'], self.host['attempts'])
                self.tracked['first_readable_seconds'] = timing.get('elapsed_seconds')
        self.report('synthesize')

    def check(self, number, registry, worker, offered_final):
        """The dossier saved and independently checked: the checked bundle when complete,
        else None once the areas to correct are set to be investigated again."""
        workflow, case, task, dossier = self.workflow, self.case, self.task, self.dossier
        research_quality.prose(dossier)
        dossier.update({k: task[k] for k in rc.TASK_FIELDS})
        rc.write(case, 'dossier.json', json.dumps(dossier))
        status = workflow.helper.command(case, 'save', 'dossier.json', worker, **(
            {'reuse_context': self.reuse_context} if self.reuse_context else {}))
        if status.get('save_result') == 'no-change' and status.get('status') == 'complete':
            verified = workflow.helper.command(case, 'verify')
            if verified.get('status') == 'complete':
                self.report('complete')
                return rc.read_bundle(rc.output_root(case))
        self.report('review')
        output = rc.output_root(case)
        if self.review_units is not None:
            # In units (#378): the assembled review is kept where the single review is.
            # What the check's review-units commands say of each unit is shown on the page.
            helper, self.workflow = self.workflow, Watched(self.workflow, self)
            self.checking = research_units.Check(self, number, offered_final)
            try:
                review, status = self.checking.go()
            except BaseException as error:
                self.units_ended(error)
                self.report()
                raise
            finally:
                self.checking, self.workflow = None, helper
            self.review = review
            rc.write(case, 'review.json', json.dumps(review))
        else:
            reviewer = 'reviewer-' + secrets.token_hex(12)
            payload = {'task': task, 'worker': reviewer, 'dossier': dossier, 'review_template': status['review_template'],
                **{key: (output / (key + '.md')).read_text() for key in ('report', 'brief', 'evidence')},
                'review_outline': self.review_outline,
                'return': 'Independently inspect the exact saved evidence and prose. Return complete review JSON. Read each capture and supplied original; report access gaps honestly. ' + rc.REVIEWED,
                '_execution': {'phase': 'review', 'round': number}}
            text, _ = self.invoke('review', (workflow.runtime / 'references/review-synthesis.md').read_text(), payload, offered_final, False)
            self.require()
            review = self.review = json.loads(text)
            rc.write(case, 'review.json', text)
            status = workflow.helper.command(case, 'review', 'review.json', reviewer)
        if status.get('status') == 'complete':
            verified = workflow.helper.command(case, 'verify')
            if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
                raise ValueError('The checked research changed before handoff.')
            self.report('complete')
            return rc.read_bundle(output)
        if self.creator_review:
            from studio_core import research_decisions
            flags = research_decisions.flags(rc.read_bundle(output, complete=False)[0])
            if flags:
                self.tracked['review_coverage'] = research_quality.coverage(review)
                self.tracked['review_flags'] = len(flags)
                self.tracked.pop('correction', None)
                self.report('creator-review')
                raise research_decisions.CreatorReview(len(flags))
        cause = rc.unreadable_originals(review, dossier)
        said = (self.readable(cause) if self.readable else '') if cause else None
        if cause and said is not None:
            raise rc.CheckCouldNotFinish(rc.objections(case), number - 1, cause, said or None)
        coverage = research_quality.coverage(review)
        if coverage['unread']:
            # Unread evidence is not a failed claim. Preserve the exact dossier:
            # the legacy single-reviewer contract cannot reuse partial attestations.
            self.tracked['review_coverage'] = coverage
            self.tracked.pop('correction', None)
            self.report('check-incomplete')
            raise research_quality.IncompleteCheck(coverage)
        affected = sorted(session.corrections(review, registry, sectioned=bool(self.section_policy)))
        if self.section_policy: research_sections.invalidate(case, review, affected)
        for stream in affected:
            workflow.command(case, 'collection', 'retry', {'workstream': stream, 'reason': 'The independent review requested evidence correction.'})
            self.report(stream=stream, state='waiting')
        notes = [item['note'] for item in review.get('facts', [])
                 if item.get('verdict') not in ('supported', 'pending') and item.get('note')]
        assessment = review.get('assessment') or {}
        if assessment.get('note'): notes.append(assessment['note'])
        with self.state_lock:
            self.tracked['correction'] = {'areas': affected, 'notes': notes}
        self.report('needs-revision')
        return None
