"""Research for a deck: the plan a worker drafts, the questions harness-research is handed,
each question researched by a worker, and the report the person decides on.

What a caller needs to know
---------------------------
    class Engine(..., research_steps.Researching)   # the engine's research steps

- The plan is research/plan.json (and plan.md to read); the report research/report.md,
  written from each finding the person kept. harness-research keeps its own record in
  .harness-research/.
- Each question still to answer is researched by one worker, several at a time. A finding
  the worker tools accepted is recorded with harness-research at once. A question that fails
  ATTEMPTS times is left unanswered and named in the report; research that answered nothing
  stops the deck.
- Asking for changes at gate:research with questions marked to research again, or added,
  researches only those: each worker is told the line written against its question, or
  that the person added it, and their own words. A note alone researches again the
  questions it names by their IDs, and those not yet settled. A question the person left
  out is never researched again; a finding a changed plan lost always is.
- Where research may look is the form's research_from (`decks.research_from`): your
  documents, your sites and/or the public web. It sets the plan's scope, Harness Research's
  source mode and the task's scope, which names the allowed sites. Every job that saves
  pages is set up with it (`_confined`), so its tools refuse a page outside your sites while
  the public web is off and the worker is told to search your sites first; the pages refused
  are kept in the run's research.outside, and the research stop says how many.
- `Researching` is a part of the engine and is not used alone.
"""
from __future__ import annotations

import contextvars
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError, write_atomic

from runner import briefs, decks, documents, marks, stages, worker_tools
from runner import research as research_cli
from studio_core import research_contract, research_sites, research_view, stops
from runner.jobs import KEPT, Halted, Run, given_up, last_error, sha256_of, text_of, tries
from runner.steps import Work

BUSY_TRIES = 20         # times a finding is offered while another save holds the lock
FROM_FORM = 'Research plan: written from your form'
PLAN = Path('research') / 'plan.json'
PLAN_MD = Path('research') / 'plan.md'
REPORT = Path('research') / 'report.md'
REVIEW = Path('research') / 'review.md'     # what the independent check still objected to
RECORD = Path('.harness-research') / 'research.json'
UNRESOLVED = ('insufficient', 'unavailable')


class Researching:
    """The engine's research steps."""

    def _research_report(self, root: Path, run: Run, step: stages.Step) -> None:
        """Ask harness-research where the research stands and write the report for the
        gate. Research that answered nothing stops the deck."""
        clock = time.monotonic()
        if self._load(root).get('research_contract'):
            tool = self.research()
            # Verify with the helper version that did the research, while it is retained.
            tool = research_contract.matching(tool, self._load(root)['research_contract']) or tool
            verified = tool._json('synthesis', 'verify', '--project', str(root / research_contract.CASE))
            if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
                raise WorkspaceError('Research needs independent review before authoring can continue.')
            with self.files:
                facts, manifest = research_contract.publish(root / research_contract.CASE, root / 'research')
                record = self._load(root)
                record['research'] = {**(record.get('research') or {}),
                                      'contract': 2, 'digest': manifest['digest']}
                self._done(root, step, clock, 'keep the reviewed research bundle', record)
            return
        with self.files:
            self.research().status(root)
            record = self._load(root)
            verdicts = self._verdicts(root)
            unread = [ident for ident, verdict in verdicts.items() if verdict == 'pending']
            if verdicts and len(unread) == len(verdicts):
                why = next((last_error(record, f'research:{ident}') for ident in unread
                            if last_error(record, f'research:{ident}')), '')
                self._problem(root, 'research', 'failed', (
                    f'None of the {len(verdicts)} research questions could be answered. '
                    f'{why}').strip(), 'The research plan you approved is kept.')
                raise Halted()
            write_atomic(root / REPORT, self._report_text(root, record))
            (record.get('research') or {}).pop('again', None)
            self._done(root, step, clock, 'keep the research report', record)

    def _keep_objections(self, root: Path, refusal, groups: list) -> None:
        """Write every objection the independent check still had, under its group, where
        the person can read them all: research/review.md."""
        lines = ['# Independent research check', '',
                 f'After {refusal.rounds} rounds of correction the independent check still '
                 'objected. Each objection names the fact, finding or passage it concerns.']
        for group in groups or [{'title': 'Objections', 'items': list(refusal.objections)}]:
            lines += ['', f"## {group['title'][:1].upper()}{group['title'][1:]}", '']
            lines += [f'- {item}' for item in group['items']]
        with self.files:
            write_atomic(root / REVIEW, '\n'.join(lines) + '\n')
            self._commit(root, 'keep the objections of the independent research check')

    def _report_text(self, root: Path, record: dict) -> str:
        """The report the person reads and the outline is drafted from: what the research
        settled and did not, what the person left out, then each finding kept, with its
        answer, what is not known and the passages it quotes."""
        items = self._findings_shown(root, record)
        left = [item for item in items if item['left_out']]
        kept = [item for item in items if not item['left_out']]
        total = len(kept)
        supported = sum(item['status'] == 'supported' for item in kept)
        lines = ['# Research report', '',
                 f"{supported} of {total} question{'' if total == 1 else 's'} "
                 f"{'has' if supported == 1 else 'have'} an answer the sources support."]
        unresolved = [item for item in kept if item['status'] in UNRESOLVED]
        unread = [item for item in kept if item['status'] == 'pending']
        if unresolved:
            lines += ['', f'Not settled ({len(unresolved)}):']
            lines += [f"- {item['id']}: {item['question']} ({item['status']})"
                      for item in unresolved]
        if unread:
            lines += ['', f'Not researched ({len(unread)}):']
            for item in unread:
                why = last_error(record, 'research:' + item['id']) or 'no reason was kept'
                lines.append(f"- {item['id']}: {item['question']} ({why})")
        if left:
            lines += ['', f'Left out by you ({len(left)}):']
            lines += [f"- {item['title']}" for item in left]
        for item in kept:
            if item['status'] == 'pending':
                continue
            lines += ['', f"## {item['title']} (`{item['id']}`)", '', item['question'], '',
                      f"Status: {item['status']}."]
            # A headline that is the summary's first sentence is said once, in the summary.
            spaced = ' '.join(item['summary'].split())
            headline = '' if spaced.startswith(item['headline']) else item['headline']
            for said in (headline, item['summary']):
                if said and said not in lines[-1]:
                    lines += ['', said]
            if item['limits']:
                lines += ['', f"Not known: {item['limits']}"]
            if item['sources']:
                lines += ['', 'Sources:']
                lines += [f"- {source['title'] or source['origin']} ({source['origin']}): "
                          f"\"{' '.join(source['quote'].split())}\""
                          for source in item['sources']]
        return '\n'.join(lines) + '\n'

    @staticmethod
    def _questions(root: Path) -> dict:
        plan = home.read_json(root / PLAN, None)
        items = plan.get('items') if isinstance(plan, dict) else None
        return {item['id']: str(item.get('question') or '') for item in items or ()
                if isinstance(item, dict) and isinstance(item.get('id'), str)}

    def _verdicts(self, root: Path) -> dict:
        """Each question of the approved plan, with its verdict or 'pending'."""
        if self._load(root).get('research_contract'):
            try:
                facts, _ = research_contract.read_bundle(root / research_contract.CASE / 'research')
                return {f['id']: 'supported' for f in facts['findings']}
            except (OSError, ValueError):
                return {'synthesis': 'pending'}
        record = home.read_json(root / RECORD, None)
        results = (record or {}).get('results') if isinstance(record, dict) else None
        results = results if isinstance(results, dict) else {}
        return {ident: self._status(results.get(ident)) for ident in self._questions(root)}

    @staticmethod
    def _status(result) -> str:
        """A kept finding's verdict, or 'pending' where it has none a person can read."""
        status = result.get('status') if isinstance(result, dict) else None
        return status if isinstance(status, str) and status else 'pending'

    def _findings_shown(self, root: Path, record: dict) -> list[dict]:
        """Each question of the plan with what the research found, for the page: its title,
        status, one-sentence answer, what is not known and the passages quoted. A finding
        kept before headlines were asked for is given its summary's first sentence."""
        if record.get('research_contract'):
            try:
                facts, _ = research_contract.read_bundle(root / 'research')
            except (OSError, ValueError):
                return []
            questions = self._questions(root)
            return [{'id': f['id'], 'title': f['title'],
                     'question_id': research_view.answered_by(f['id'], questions),
                     'question': questions.get(research_view.answered_by(f['id'], questions), ''),
                     'status': 'supported',
                     'headline': f['summary']['text'], 'summary': f['summary']['text'],
                     'limits': '\n'.join(b['text'] for b in f['conditions'] + f['gaps']),
                     'unknown': '\n'.join(b['text'] for b in f['gaps']),
                     'left_out': f['id'] in ((record.get('research') or {}).get('left_out') or []),
                     'sources': [{'title': next(s['title'] for s in facts['sources'] if s['id'] == c['source']),
                                  'origin': next(s['origin'] for s in facts['sources'] if s['id'] == c['source']),
                                  'quote': c['quote']} for fact in facts['facts']
                                 if fact['id'] in f['support'] + f['counter']
                                 for c in fact['citations']]} for f in facts['findings']]
        found = home.read_json(root / RECORD, None)
        results = found.get('results') if isinstance(found, dict) else None
        results = results if isinstance(results, dict) else {}
        left = set((record.get('research') or {}).get('left_out') or ())
        shown = []
        for ident, question in self._questions(root).items():
            result = results.get(ident) if isinstance(results.get(ident), dict) else {}
            summary, limits = str(result.get('summary') or ''), str(result.get('limits') or '')
            headline = result.get('headline') if isinstance(result.get('headline'), str) else ''
            evidence = result.get('evidence')
            known = limits.strip().rstrip('.').lower() in ('', 'none')
            shown.append({
                'id': ident, 'title': marks.title(ident), 'question': question,
                'status': self._status(result),
                'headline': headline or marks.first_sentence(summary), 'summary': summary,
                'limits': '' if known else limits,
                'unknown': '' if known else marks.first_sentence(limits),
                'left_out': ident in left,
                'sources': [{'title': str(passage.get('title') or ''),
                             'origin': str(passage.get('origin') or ''),
                             'quote': str(passage.get('quote') or '')}
                            for passage in (evidence if isinstance(evidence, list) else ())
                            if isinstance(passage, dict)]})
        return shown

    @staticmethod
    def _named(ident: str, note: str | None) -> bool:
        return bool(note) and re.search(
            rf'(?<![a-z0-9-]){re.escape(ident)}(?![a-z0-9-])', note.lower()) is not None

    @staticmethod
    def _own_words(gate: dict) -> str | None:
        """What the person wrote themselves at gate:research. A request with marks keeps it
        as `free`, beside the note the runner wrote from the marks."""
        return gate.get('free') if isinstance(gate.get('again'), dict) else gate.get('note')

    @classmethod
    def _told(cls, gate: dict, ident: str) -> str | None:
        """What a worker researching `ident` is told the person said: that they added the
        question, or the line they wrote against it, then their own words; or their note
        at the gate."""
        if gate.get('state') != 'changes':
            return None
        again = gate.get('again')
        if isinstance(again, dict) and ident in again:
            line = again[ident] or ''
            if ident in (gate.get('added') or ()):
                said = 'The person added your question after reading the research.'
            else:
                said = ('The person asked for your question to be researched again'
                        + (f'. What they said about it:\n\n{line}' if line else '.'))
            if gate.get('free'):
                said += ('\n\nThey also wrote this, which may or may not be about your '
                         f"question:\n\n{gate['free']}")
            return said
        note = cls._own_words(gate)
        return ('The person looked at the research and asked for this, which may or may '
                f'not be about your question:\n\n{note}') if note else None

    def _research(self, root: Path, run: Run, step: stages.Step) -> None:
        """Hand the approved plan to harness-research, then research each question still
        to answer, several at a time. A question that fails three times is left for the
        report to name."""
        record = self._load(root)
        if record.get('research_contract'):
            plan = home.read_json(root / PLAN, {})
            form = record.get('form') or {}
            looks = self._research_from(root, record)
            offered = self._offered(root, looks)
            task = {'topic': record.get('title') or form.get('title') or plan['topic'],
                    'audience': form.get('audience') or 'Presentation audience',
                    'purpose': research_contract.purpose(
                        'a presentation', form.get('goal') or 'explain this topic',
                        'Prioritize key messages, evidence worth explaining visually, and '
                        'counterarguments.'),
                    # Where research may look, sites named, for a deck that saved its
                    # research_from; an older deck keeps its scope word for word.
                    'scope': 'Evidence, limitations and alternatives for the presentation goal: '
                             + (form.get('goal') or record.get('title') or 'explain the topic')
                             + ('. ' + research_sites.scope_text(looks)
                                if 'research_from' in form else ''),
                    'planning_questions': plan.get('items', []),
                    'notes': form.get('notes') or '',
                    'requested_changes': record.get('gates', {}).get('gate:research', {}),
                    # Asked for at the research stop: the sources read again.
                    'refresh': ((record.get('gates') or {}).get('gate:research') or {})
                    .get('refresh') is True,
                    # Pages from your sites are public captures: documents and sites is
                    # mixed, sites alone public.
                    'source_mode': research_sites.source_mode(looks)}
            try:
                research_contract.native(self, root, run, task, offered, 'presentation')
            except WorkspaceError as refusal:
                outcome = getattr(refusal, 'outcome', None)
                if outcome is not None:
                    # One job of the research did not finish: more time for a job that ran
                    # out of it, the money stop for one that spent what the deck may, and
                    # where to look for an agent that could not be used.
                    if outcome.reason == 'limit' and outcome.budget:
                        self._spend_stop(root, 'The research')
                    elif stops.agent_stopped('', outcome, outcome.detail) is not None:
                        self._problem(root, 'research', 'failed', stops.agent_stopped(
                            self._title(record.get('agent')), outcome, outcome.detail), KEPT,
                            action=stops.agent_action(outcome))
                    elif outcome.reason == 'timeout':
                        self._out_of_time(root, 'research', 'The research', record, 1)
                    else:
                        self._problem(root, 'research', 'failed', str(refusal), KEPT)
                    raise Halted()
                if getattr(refusal, 'objections', None) is None:
                    raise
                if getattr(refusal, 'cause', None):
                    # The check could not read an original it must attest to: no correction
                    # can change that, so Try again waits until the original can be read.
                    named = ''.join(f"\n- {item.get('title') or item.get('source')}: "
                                    f"{item.get('access_error') or 'no reason given'}"
                                    for item in refusal.cause)
                    self._problem(root, 'research', 'failed', str(refusal), (
                        'The draft report and the research plan you approved are kept. Try '
                        'again works once the original can be read:' + named),
                                  detail={'unreadable': list(refusal.cause)})
                    raise Halted()
                # The check still objected after its last round: stop at the research step
                # with its objections, so that the person reads them and Try again says
                # what it re-runs. Each is listed under its group in research/review.md.
                groups = getattr(refusal, 'groups', None) or []
                self._keep_objections(root, refusal, groups)
                listed = ''.join(f"\n- {group['title']} ({group['note']})" for group in groups) \
                    or ''.join('\n- ' + note for note in refusal.objections)
                self._problem(root, 'research', 'failed', str(refusal), (
                    'The draft report and the check’s objections are kept: every objection is '
                    f'listed under its group in {REVIEW}. The research plan you approved is '
                    'kept.' + listed))
                raise Halted()
            with self.files:
                # The objections of an earlier try are answered: none is left to read.
                (root / REVIEW).unlink(missing_ok=True)
                self._done(root, step, time.monotonic(), 'complete independent research review')
            return
        with self.files:
            record = self._load(root)
            handed, lost = record.get('research') or {}, []
            if not handed.get('run') or handed.get('plan') != sha256_of(root / PLAN):
                before = self._verdicts(root)
                status = self.research().plan(root, root / PLAN)
                # A finding harness-research did not keep for the changed plan, as when a
                # file it rests on changed, is researched again.
                lost = [ident for ident, verdict in self._verdicts(root).items()
                        if verdict == 'pending' and before.get(ident, 'pending') != 'pending']
                # What the person left out stays with a changed plan.
                record['research'] = {**handed, 'run': status.get('run'),
                                      'plan': sha256_of(root / PLAN)}
                self._store(root, record)
                self._commit(root, 'hand the approved questions to research')
            gate = record['gates'].get('gate:research') or {}
            # Two kinds of `again`: the gate's is what the person marked; `research.again`
            # is the runner's own list of the questions this request still has to research.
            asked = record['research'].get('again')
            if gate.get('state') == 'changes' and (asked or {}).get('at') != gate.get('at'):
                verdicts = self._verdicts(root)
                out = set(record['research'].get('left_out') or ())
                kept = [ident for ident in verdicts if ident not in out]
                marked = gate.get('again')
                if isinstance(marked, dict) and marked:
                    left = [ident for ident in kept if ident in marked]
                else:
                    # Only the person's own words are looked through for IDs: the note the
                    # runner wrote from marks names the questions left out.
                    said = self._own_words(gate)
                    left = [ident for ident in kept
                            if self._named(ident, said)
                            or verdicts[ident] in ('pending', *UNRESOLVED)] or kept
                left += [ident for ident in lost if ident in kept and ident not in left]
                record['research']['again'] = {'at': gate.get('at'), 'left': left}
                for ident in left:
                    tries(record, f'research:{ident}')
                    entry = record['steps'].get(f'research:{ident}')
                    if entry:
                        entry['failed'] = 0
                self._store(root, record)
            asked = record['research'].get('again')
            verdicts = self._verdicts(root)
            todo = [ident for ident in (asked['left'] if asked else
                                        [i for i, v in verdicts.items() if v == 'pending'])
                    if not given_up(record, f'research:{ident}')]
        if not todo:
            with self.files:
                self._done(root, step, time.monotonic(), 'every question is researched')
            return

        def one(ident: str) -> None:
            if self._may_go(root):
                self._question(root, run, ident, self._told(gate, ident))

        if self.at_once <= 1 or len(todo) == 1:
            for ident in todo:
                one(ident)
            return
        with ThreadPoolExecutor(max_workers=self.at_once) as pool:
            for pending in [pool.submit(contextvars.copy_context().run, one, ident)
                            for ident in todo]:
                pending.result()

    def _question(self, root: Path, run: Run, ident: str, told: str | None) -> None:
        """One try at one research question. An accepted finding is recorded at once."""
        name = f'research:{ident}'
        record = self._load(root)
        question = self._questions(root).get(ident, '')
        plan = home.read_json(root / PLAN, {}) or {}
        query = next((item.get('public_query') for item in plan.get('items') or ()
                      if isinstance(item, dict) and item.get('id') == ident), None)
        looks = self._research_from(root, record)
        offered = self._offered(root, looks)
        fetch = research_sites.fetches(looks)
        task = ('Research this question for a presentation.\n\n'
                f'Question ID: {ident}\nQuestion: {question}\n'
                + (f'Search words to start from: {query}\n' if query else '')
                + ('The documents the person supplied are saved for you already. Read them'
                   + (' as well as the web.\n' if fetch else '.\n') if offered else '')
                + (f'Where research may look: {research_sites.scope_text(looks)}\n'
                   if 'research_from' in (record.get('form') or {}) else '')
                + f'\nThe presentation:\n{self._about(record)}')
        if told:
            task += f'\n\n{told}'
        error = last_error(record, name)
        if error:
            task += (f'\n\nAn earlier try at this job did not work: {error}\nTake care not to '
                     'end the same way.')
        work = Work(briefs.guidance('research-question'), task, 'research',
                    {'finding': ident, 'fetch': fetch, 'ask': False, 'sources': offered})
        outcome, handed, started_at, folder = self._job(root, run, name,
                                                        f'Researching the question {ident}',
                                                        work, deck=False)
        if outcome.reason == 'stopped':
            return self._stopped(root, name, outcome, started_at)
        if handed['finding'] is None:
            return self._failed(root, name, f'Research the question {ident}', outcome,
                                started_at, self._why_not(handed, outcome.detail),
                                question=True)
        refused = None
        with self.files:
            try:
                self._keep_sources(root, handed)
                self._record(root, ident, handed['finding'])
            except WorkspaceError as refusal:
                refused = str(refusal)
            else:
                record = self._load(root)
                self._tried(record, name, started_at, outcome.seconds, 'kept',
                            **self._cost(outcome))
                again = (record.get('research') or {}).get('again') or {}
                if ident in again.get('left', []):
                    again['left'].remove(ident)
                self._store(root, record)
                self._commit(root, f'keep the finding for {ident}')
        if refused:
            return self._failed(root, name, f'Research the question {ident}', outcome,
                                started_at, refused, question=True)
        shutil.rmtree(folder, ignore_errors=True)

    @staticmethod
    def _keep_sources(root: Path, handed: dict) -> None:
        """Copy the sources a finding quotes into the deck's own sources folder, where
        harness-research reads them. They stay on this computer."""
        quoted = {passage.get('file') for passage in handed['finding'].get('evidence') or []}
        inside = (root / 'sources').resolve()
        for source in handed['sources']:
            if source.get('file') not in quoted:
                continue
            for name, path in ((source.get('file'), source.get('path')),
                               (source.get('original'), source.get('original_path'))):
                if not name or path is None:
                    continue
                target = (root / name).resolve()
                if inside not in target.parents or target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)

    def _record(self, root: Path, ident: str, finding: dict) -> None:
        handed_to = (self._load(root).get('research') or {}).get('run')
        for left in range(BUSY_TRIES, 0, -1):
            try:
                self.research().record(root, handed_to, ident, finding)
                return
            except research_cli.Refused as refusal:
                if not refusal.busy or left == 1:
                    raise
                time.sleep(0.25)

    # --- where research may look: your documents, your sites and/or the public web ---------

    def _research_from(self, root: Path, record: dict) -> dict:
        """Where this deck's research may look, in studio_core.research_sites' shape: its
        form's research_from, or for a deck begun before it, what its research_sources or its
        plan's scope said (decks.research_from)."""
        form = record.get('form') or {}
        plan = home.read_json(root / PLAN, None)
        given = form.get('route') == 'document' or bool(documents.listed(root))
        return decks.research_from(form, plan.get('scope') if isinstance(plan, dict) else None,
                                   given) or {'documents': True, 'sites': [], 'web': False}

    @staticmethod
    def _offered(root: Path, looks: dict) -> list:
        """The person's documents, offered to research only when it may use them."""
        return documents.sources(root)[1] if looks['documents'] and documents.listed(root) else []

    @staticmethod
    def _web_words(looks: dict) -> str:
        """Where on the web the plan's questions may be looked up, in a few words."""
        named = ', '.join(research_sites.shown(site) for site in looks['sites'])
        if looks['sites'] and looks['web']:
            return (f'pages from under these sites first: {named}; then the public web, only for '
                    'what those sites leave open')
        if looks['sites']:
            return f'pages from under these sites only: {named}'
        return 'the public web'

    def _confined(self, root: Path, record: dict, work):
        """A job that saves pages, kept to where this deck's research may look: the choice
        goes into its job.json, where save_source checks every hop, redirects included, and
        the worker is told to search your sites first. Any other job is as it was."""
        if not work.prepared.get('fetch'):
            return work
        looks = self._research_from(root, record)
        told = research_sites.guidance(looks)
        return replace(work, guidance=work.guidance + ('\n\n' + told if told else ''),
                       prepared={**work.prepared, 'research': looks})

    def _keep_outside(self, root: Path, refused: list) -> None:
        """Keep, for the research stop, the pages a job could not save because they were
        outside your sites."""
        if not refused:
            return
        with self.files:
            record = self._load(root)
            research = dict(record.get('research') or {})
            kept = list(research.get('outside') or [])
            known = {entry.get('url') for entry in kept}
            kept += [entry for entry in refused if entry.get('url') not in known][:100 - len(kept)]
            if len(kept) == len(research.get('outside') or []):
                return
            record['research'] = {**research, 'outside': kept}
            self._store(root, record)
            self._commit(root, 'note the pages research could not save from outside your sites')

    @staticmethod
    def _about(record: dict) -> str:
        form = record.get('form') or {}
        return '\n'.join([f"Title: {record.get('title') or form.get('title')}",
                          f"Audience: {form.get('audience') or 'not given'}",
                          f"Goal: {form.get('goal') or 'not given'}",
                          f"Length: {form.get('minutes') or 'not given'} minutes"
                          if form.get('minutes') else 'Length: not given'])

    def _plan_work(self, root: Path, record: dict, request: dict | None,
                   error: str | None) -> Work:
        name = 'research-plan'
        looks = self._research_from(root, record)
        listed = documents.sources(root)[0] if looks['documents'] and documents.listed(root) else []
        web = self._web_words(looks)
        allowed = (f'{web}, and these documents the person supplied. Ask what the '
                   'documents can answer as well as what the web can:\n'
                   + '\n'.join(f"- {source.get('title') or source.get('id')}"
                               for source in listed)) if listed else f'{web}.'
        only = not research_sites.fetches(looks)
        if only:
            allowed = ('only the documents the person supplied. Ask what these can answer, and give no question any search words:\n'
                       + '\n'.join(f"- {source.get('title') or source.get('id')}" for source in listed))
        task = ('Draft the research questions for this presentation.\n\n'
                f'{self._about(record)}\n'
                f'Sources that may be used: {allowed}\n\n'
                f'Hand the questions back with submit_artifact under the name "{name}".')
        asked = (record.get('form') or {}).get('research_questions') or []
        if asked and not request:
            task += ('\n\nThe person asked these questions. Keep each in the plan, in their words:\n'
                     + '\n'.join('- ' + q for q in asked))
        earlier = text_of(root / PLAN)
        if request and request.get('note'):
            task += ('\n\nYou are revising an earlier draft. What the person asked for:\n\n'
                     f"{request['note']}")
            if earlier:
                task += f'\n\nThe earlier draft:\n\n{earlier}'
        if error:
            task += (f'\n\nAn earlier try at this job did not work: {error}\nTake care not to '
                     'end the same way.')
        prepared = {'inputs': {'intake': text_of(root / 'intake.md') or ''},
                    'artifacts': {name: {'kind': 'research-plan', 'scope': research_sites.plan_scope(looks),
                                         'sources': listed}},
                    'ask': True}
        synthesis = bool(record.get('research_contract'))
        if synthesis:
            prepared['artifacts'][name]['most'] = worker_tools.PLAN_MOST
        return Work(briefs.guidance('research-plan' if synthesis else 'research-plan-queue'), task, 'write', prepared, name)

    @staticmethod
    def _keep_plan(root: Path, record: dict, text: str) -> None:
        write_atomic(root / PLAN, text if text.endswith('\n') else text + '\n')
        plan = json.loads(text)
        lines = ['# Research plan', '', str(plan.get('topic') or ''), '']
        for item in plan.get('items') or ():
            lines.append(f"- **{item.get('id')}**: {item.get('question')}"
                         + (f" (search: {item['public_query']})"
                            if item.get('public_query') else ''))
        write_atomic(root / PLAN_MD, '\n'.join(lines).rstrip() + '\n')

    def _drop_questions(self, root: Path, record: dict, dropped) -> None:
        """Take the questions the person dropped out of the plan, as they asked, with no
        worker. A plan is never left with none."""
        plan = home.read_json(root / PLAN, None)
        items = plan.get('items') if isinstance(plan, dict) else None
        if not isinstance(items, list):
            raise WorkspaceError('There is no research plan to drop a question from.')
        dropped = set(dropped)
        kept = [item for item in items
                if not (isinstance(item, dict) and item.get('id') in dropped)]
        if not kept:
            raise WorkspaceError(marks.ALL_DROPPED)
        self._keep_plan(root, record, json.dumps({**plan, 'items': kept}, indent=2,
                                                 ensure_ascii=False))

    def _add_questions(self, root: Path, record: dict, texts) -> list[str]:
        """Add the questions the person wrote to the plan, as they wrote them and with no
        search words. Returns their IDs. A plan that would be refused is not written."""
        if not texts:
            return []
        plan = home.read_json(root / PLAN, None)
        if not isinstance(plan, dict) or not isinstance(plan.get('items'), list):
            raise WorkspaceError('There is no research plan to add a question to.')
        most = worker_tools.PLAN_MOST if record.get('research_contract') else worker_tools.QUESTIONS
        if len(plan['items']) + len(texts) > most:
            raise WorkspaceError(f'A plan holds at most {most} '
                                 'questions.')
        taken = [item.get('id') for item in plan['items'] if isinstance(item, dict)]
        added = []
        for text in texts:
            ident = marks.new_id(text, taken + added)
            # Shaped as the plan's checks shape every question. The others are written back
            # as they were, so harness-research keeps their findings.
            plan['items'].append({'id': ident, 'question': text, 'public_query': None,
                                  'claim': None})
            added.append(ident)
        checked = worker_tools.check_research_plan(plan, most=most)
        if checked['status'] == 'failed':
            raise WorkspaceError(' '.join(checked['problems']))
        self._keep_plan(root, record, json.dumps(plan, indent=2, ensure_ascii=False))
        return added

    def _research_plan(self, root: Path, run: Run, step: stages.Step) -> None:
        record = self._load(root)
        # Research that reads only the person's documents, and any research of a desk deck,
        # is planned from the form, with no job: a desk deck has no stop to see a plan at.
        if (record.get('research_contract')
                and (decks.on_desk(record)
                     or not research_sites.fetches(self._research_from(root, record)))
                and not self._request(record, step.name)):
            self._plan_from_form(root, run, step)
            return

        def keep(record, handed):
            self._keep_plan(root, record, self._text(handed, 'research-plan'))
            if record.get('research_contract'):
                record['research'] = {**(record.get('research') or {}), 'plan_from': 'assistant'}
                self._store(root, record)

        self._agent(root, run, step,
                    lambda record, request, error: self._plan_work(root, record, request,
                                                                   error),
                    keep, 'keep the research plan')


    def _plan_from_form(self, root: Path, run: Run, step: stages.Step) -> None:
        with self.files:
            record = self._load(root)
            form = record.get('form') or {}
            looks = self._research_from(root, record)
            fetches = research_sites.fetches(looks)
            goal = form.get('goal') or record.get('title') or 'explain this topic'
            asked = form.get('research_questions') or [
                ('What is known that serves this goal: ' if fetches else
                 'What do the supplied documents say that serves this goal: ') + goal + '?']
            items = []
            for text in asked:
                ident = marks.new_id(text, [item['id'] for item in items])
                items.append(dict(id=ident, question=text, public_query=None, claim=None))
            listed = documents.sources(root)[0] if looks['documents'] and documents.listed(root) \
                else []
            plan = dict(topic=record.get('title') or form.get('title'), purpose='planning',
                        scope=research_sites.plan_scope(looks) if fetches else 'supplied-only',
                        sources=listed if fetches else documents.sources(root)[0], items=items)
            checked = worker_tools.check_research_plan(plan, most=worker_tools.PLAN_MOST)
            if checked['problems']:
                raise WorkspaceError(checked['problems'][0])
            self._keep_plan(root, record, json.dumps(plan, indent=2, ensure_ascii=False))
            record['research'] = {**(record.get('research') or {}), 'plan_from': 'form'}
            self._done(root, step, time.monotonic(), 'write the research plan from the form', record)
