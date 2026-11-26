"""The independent check of saved research in review units (issue #378).

Harness Research 1.6.0 plans the independent check of one saved dossier as bounded review
units (protocol harness-review-units-v1, its references/review-units.md): each content unit
owns some sources, facts, findings and passages and is given only what they cite; the final
unit owns the whole-dossier assessment and reads the whole dossier. The helper records,
checks and assembles; the host, here, launches a fresh reviewer for each unit, at most three
at a time, registers its identity, hands it only its unit, records how it ended, and stops
it. A unit accepted once is never reviewed again unless what it was given changed; a failed,
refused or stopped unit is retried alone. The assembled review is the ordinary review, kept
where the single review is (review.json in the case), so every reader of a review is
unchanged.

A case uses units only when it started on a Harness Research that offers them: its execution
record then keeps this module's `entry` as `review` (research_session.execution). A case
without the entry keeps the single review, whatever is installed later; a case with it that
finds a Harness Research without units is refused plainly (GONE), never checked the old way.
Called from research_run.Run.check, which all four studios reach.
"""
from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import secrets
import threading

from studio_core import research_contract as rc
from studio_core.research_checks import REVIEW_UNITS as PROTOCOL, unit_problems

CAPABILITY = 'references/review-units-capability.json'
ACTIONS = ('plan', 'assign', 'register', 'accept', 'finish', 'retry', 'stop', 'status', 'assemble')
# How many content units a plan makes at most. Kept in the case's entry, so a plan, and the
# units it keeps, stay the same for the life of the case.
MAX_UNITS = 8
FINAL = 'final'
# The section an active final reviewer is shown under. The pages say 'final' of the author
# of the final brief, so the final review unit is named apart from it.
FINAL_SECTION = 'final-check'
GONE = ('This research began checking its sources in independent units, and the installed '
        'Harness Research no longer offers them. Update Harness Research, then try again. '
        'Saved research is kept.')
UNREADABLE = ('The saved record of how this research is checked cannot be read. Preserve it '
              'for inspection.')
RETURN = ('Independently inspect the exact saved evidence and prose of this one review unit. '
          'Judge only what review_template lists: each owned original, fact, finding and '
          'passage once, and the assessment only when the template has one. Read what the '
          'assignment gives you only as far as the chain of support requires; never answer for '
          'it. Keep schema, protocol, plan, digest, unit, attempt and reviewer exactly as '
          'review_template gives them. Read each capture and supplied original; report access '
          'gaps honestly. Return the filled review_template as one JSON object.')
# Why a unit is reviewed again, by how its last attempt ended.
AGAIN = {'failed': 'The last review of this unit failed; it is reviewed again.',
         'refused': 'The last answer for this unit was refused; it is reviewed again.',
         'cancelled': 'The review of this unit was stopped; it is reviewed again.',
         'finished': 'The last review of this unit ended without an accepted answer; it is reviewed again.'}
ENDED = {'failed': 'The host transport ended before an accepted answer.',
         'refused': 'The answer did not pass its check; nothing was accepted.',
         'cancelled': 'The research was stopped; the host ended this review.'}
UNREAD = 'The independent check did not read every original this unit owns; it is checked again.'
CORRECTED = 'The assembled check of this unchanged dossier needs revision; the whole is checked again.'
ORPHANED = 'No live host invocation holds this attempt; the host confirms it ended.'
# The one next step of Harness Research's status that planning cannot resolve: a plan record
# that is a folder or a link. Said to the person as it is.
BLOCKED = 'Review plan record is not a regular file; preserve and inspect it.'


class Refused(ValueError):
    """A unit's answer that did not pass its check, or that Harness Research refused."""


def capability(runtime):
    """What the installed Harness Research offers of review units: {'protocol',
    'max_reviewers', 'max_units'}, or None when it has none (Harness Research before 1.6.0)."""
    path = Path(runtime) / CAPABILITY
    try:
        if path.is_symlink() or not path.is_file():
            return None
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    limits = value.get('limits')
    if value.get('schema') != 1 or value.get('protocol') != PROTOCOL \
            or value.get('command') != 'review-units' or value.get('state_schema') != 4 \
            or value.get('output_schema') != 2 or not isinstance(limits, dict) \
            or not isinstance(value.get('actions'), list) or not set(ACTIONS) <= set(value['actions']):
        return None
    most, units = limits.get('max_reviewers'), limits.get('max_units')
    if type(most) is not int or not 1 <= most <= 3 or type(units) is not int or units < 1:
        return None
    return {'protocol': PROTOCOL, 'max_reviewers': most, 'max_units': units}


def entry(runtime):
    """The `review` entry a case starts with when the installed Harness Research offers
    review units, else None. It names protocols and the plan's size, never a version or a
    digest, so an update of Harness Research leaves it as it is."""
    found = capability(runtime)
    if found is None:
        return None
    return {'schema': 1, 'protocol': PROTOCOL, 'state_schema': 4, 'output_schema': 2,
            'max_units': min(MAX_UNITS, found['max_units'])}


def valid(value):
    """Whether a case's `review` entry is one this Marketing Studio reads."""
    return isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1 \
        and value.get('protocol') == PROTOCOL and value.get('state_schema') == 4 \
        and value.get('output_schema') == 2 and type(value.get('max_units')) is int \
        and 1 <= value['max_units'] <= 64


def of(execution):
    """A case's `review` entry, from its execution record, or None (the single review)."""
    return execution.get('review') if isinstance(execution, dict) else None


def section(unit):
    """The section an active reviewer of `unit` is shown under."""
    return FINAL_SECTION if unit == FINAL else unit


def unread_of(review):
    """The sources an assembled review says it did not read the original of."""
    return {item.get('source') for item in review.get('originals') or ()
            if isinstance(item, dict) and item.get('read_original') is False}


def rechecked(case, plan_file, review):
    """The review units a check of the same dossier reviews again after `review` left
    originals unread: each content unit owning one, then the final unit."""
    plan = json.loads(rc.inside(case, plan_file).read_bytes())
    unread = unread_of(review)
    return [unit['id'] for unit in plan['units']
            if unit['kind'] == 'content' and set(unit['owns']['sources']) & unread] + [FINAL]


class Check:
    """One independent check of the saved dossier of `run` (a research_run.Run) in units:
    `go` returns (the assembled review, the helper's result of assembling it)."""

    def __init__(self, run, number, offered):
        self.run, self.number, self.case = run, number, run.case
        self.by_file = {source['file']: source for source in offered}
        runtime = run.workflow.runtime
        self.most = min(3, max(1, int(run.limit)), capability(runtime)['max_reviewers'])
        self.guidance = ((runtime / 'references/review-synthesis.md').read_text() + '\n\n'
                         + (runtime / 'references/review-unit.md').read_text())
        self.lock = threading.RLock()
        self.stopped = False

    def command(self, action, value=None, **flags):
        """One review-units command. Harness Research saying no is raised as Refused, however
        the studio runs the helper (rc.refusal), with what it said; a stop stays a stop."""
        try:
            return self.run.workflow.command(self.case, 'review-units', action, value, **flags)
        except Refused:
            raise
        except Exception as error:
            if rc.refusal(error):
                raise Refused(str(error)) from error
            raise

    def stop(self):
        """Stop the outstanding units through Harness Research: it cancels them and refuses
        their late answers. Each unit's own thread then confirms its end with finish."""
        with self.lock:
            if not self.stopped:
                self.stopped = True
                self.command('stop')

    def go(self):
        status = self.ready()
        content = [unit for unit in status['units']
                   if unit['kind'] == 'content' and unit['status'] not in ('kept', 'accepted')]
        if content:
            self.dispatch(content)
            self.run.require()
            status = self.command('status')
        # The final unit attests the whole, so it is reviewed once every content unit holds.
        final = next(unit for unit in status['units'] if unit['kind'] == 'final')
        if final['status'] != 'accepted':
            self.dispatch([final])
        self.run.require()
        result = self.command('assemble')
        state = json.loads(rc.inside(self.case, '.harness-research/synthesis.json').read_bytes())
        return state['review'], result

    def plan(self):
        return self.command('plan', {'schema': 1, 'max_units': self.run.review_units['max_units'],
                                     'max_reviewers': self.most})

    def ready(self):
        """The status to review from: planned for the saved dossier, with what Harness
        Research's status says to do next done first (its host page): a review that no longer
        checks out, a changed plan file or a stopped check are planned again, after each
        attempt no live invocation holds is confirmed ended."""
        status = self.command('status')
        redone = False
        for _ in range(6):
            phase, step = status.get('phase'), status.get('next_step')
            if step == BLOCKED:
                raise ValueError(step)
            if phase in ('review-invalid', 'needs-plan', 'stopped') or (phase == 'needs-attention' and step):
                self.settle(status)
                status = self.plan()
                continue
            if phase == 'needs-attention':
                raise ValueError('Harness Research cannot use the saved review units: '
                                 + ' '.join(status.get('problems') or ['it gave no reason.']))
            if phase not in ('reviewing', 'ready-to-assemble', 'assembled'):
                raise ValueError(f'Harness Research reports the review units as {phase!r}.')
            self.settle(status)
            if status.get('max_reviewers') != self.most:
                # Planned under another limit (a stopped or failed check continued with more or
                # fewer reviewers): the same plan, taking this run's limit, so registrations
                # are never refused for capacity and never exceed the limit.
                status = self.plan()
                continue
            if not redone and self.again(status):
                redone = True
                status = self.command('status')
                continue
            return status
        raise ValueError('Harness Research did not reach a review plan for the saved dossier.')

    def settle(self, status):
        """Confirm ended every attempt Harness Research holds as running, or cancelled by a
        stop, that no live invocation of this case holds: the run's host record says each
        invocation it started ended (research_run.Run.open_case refuses one that did not)."""
        with self.run.host_lock:
            live = {attempt['worker'] for attempt in self.run.host['attempts'] if not attempt.get('ended_at')}
        for unit in status.get('units') or ():
            if unit.get('status') not in ('running', 'cancelled') or not unit.get('reviewer') \
                    or unit['reviewer'] in live or not unit.get('attempt'):
                continue
            outcome = 'failed' if unit['status'] == 'running' else 'cancelled'
            try:
                self.command('finish', {'unit': unit['id'], 'reviewer': unit['reviewer'],
                                        'attempt': unit['attempt'], 'outcome': outcome, 'note': ORPHANED})
            except Refused:
                pass   # Already confirmed ended; a plan that still cannot go on says why.

    def again(self, status):
        """When the dossier the last assembled check needed revision for is checked again
        unchanged, the units it could not read and the final unit are reviewed again; every
        other unit keeps its receipt. True when any was."""
        saved = rc.inside(self.case, 'review.json')
        try:
            review = json.loads(saved.read_bytes()) if saved.is_file() else None
        except ValueError:
            review = None
        if not isinstance(review, dict) or review.get('accepted') \
                or (review.get('units') or {}).get('plan') != status.get('plan'):
            return False
        # Only while the final unit's accepted answer is still the one that review assembled:
        # once it was retried, this recheck has begun, and what it reviewed since is kept.
        final = next((unit for unit in status['units'] if unit['id'] == FINAL), {})
        if final.get('status') != 'accepted' or final.get('reviewer') not in (review.get('reviewers') or ()):
            return False
        unread = unread_of(review)
        units = {unit['id']: unit['status'] for unit in status['units']}
        again = rechecked(self.case, status['plan_file'], review)
        for ident in again:
            if units.get(ident) != 'reserved':
                self.command('retry', {'unit': ident, 'reason': UNREAD if ident != FINAL or unread else CORRECTED})
        return True

    def dispatch(self, units):
        """Every unit reviewed at once, at most `most` at a time. A unit that fails does not
        stop its peers: each runs, and the first failure is raised once all have ended."""
        failures = []
        with ThreadPoolExecutor(max_workers=self.most) as pool:
            futures = [pool.submit(contextvars.copy_context().run, self.one, unit) for unit in units]
            for future in as_completed(futures):
                try:
                    future.result()
                except BaseException as error:
                    failures.append(error)
        if failures:
            # As a single review that fails, the run stays at its check: the studios offer
            # what a failed check offers (Training Studio: the draft, unverified).
            stopped = [error for error in failures if isinstance(error, InterruptedError)]
            raise (stopped or failures)[0]

    def one(self, unit):
        """One unit reviewed by a fresh reviewer given only its unit, and its answer accepted;
        else its attempt confirmed ended as failed, refused or cancelled."""
        run, ident = self.run, unit['id']
        run.require()
        if unit['status'] not in ('pending', 'reserved'):
            self.command('retry', {'unit': ident, 'reason': AGAIN.get(unit['status'], AGAIN['failed'])})
        reviewer = 'reviewer-' + secrets.token_hex(12)
        invocation = 'research-invocation-' + secrets.token_hex(16)
        registered = self.command('register', {'unit': ident, 'reviewer': reviewer,
                                               'invocation': invocation})['registration']
        terminal = {'unit': ident, 'reviewer': reviewer, 'attempt': registered['number']}
        accepted = False
        try:
            run.require()
            # The assignment as Harness Research prints it. Its --out cannot write under
            # .harness-research, and a file beside the case's own would travel with it.
            assignment = self.command('assign', unit=ident)
            template = assignment['template']
            files = [source['file'] for part in ('owns', 'given') for source in assignment[part]['sources']]
            captures = [self.by_file[file] for file in dict.fromkeys(files)]
            payload = {'task': run.task, 'worker': reviewer,
                       'assignment': {key: value for key, value in assignment.items() if key != 'template'},
                       'review_template': template, 'return': RETURN,
                       '_execution': {'phase': 'review', 'round': self.number, 'mode': 'review-unit',
                                      'unit': ident, 'invocation': invocation}}
            text, _ = run.invoke('review', self.guidance, payload, captures, False)
            run.require()
            try:
                answer = json.loads(text)
            except ValueError:
                raise Refused('The review unit answer is not JSON.') from None
            problems = unit_problems(answer, template, run.workflow.runtime)
            if problems:
                raise Refused(' '.join(problems))
            self.command('accept', answer)   # a refusal is raised as Refused
            accepted = True
        except BaseException as error:
            if not accepted and getattr(error, 'terminal_confirmed', True):
                outcome = ('cancelled' if self.stopped or run.cancelled() or isinstance(error, InterruptedError)
                           else 'refused' if isinstance(error, Refused) else 'failed')
                try:
                    self.command('finish', {**terminal, 'outcome': outcome, 'note': ENDED[outcome]})
                except BaseException:
                    # Nothing in confirming the end replaces what ended it: a stop stays a
                    # stop. The next check confirms it (settle).
                    pass
            raise
