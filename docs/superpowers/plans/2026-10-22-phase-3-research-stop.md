# Phase 3, the research stop worth stopping for: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** every research stop shows the brief, the independent check's word and the gaps,
maps findings to the planning questions, prices a research change before it is sent,
keeps research inside the boundary the person chose, and runs no planning job where the
person's own material is all there is.

**Architecture:** one new core module, `core/studio_core/research_view.py`, turns a
published Harness Research bundle into the account a stop shows and words the price of a
research change; each studio's gate payload carries that account and price, and each
page renders it. The core contract tells the author to prefix finding IDs with the
planning question's ID, so mapping needs no schema change. Plan jobs get a brief written
for one investigation; supplied-only deck runs write their plan from the form, and Blog's
supplied-only research becomes a claims-map stage.

**Tech Stack:** Python 3.11 standard library; plain JavaScript pages with no build step;
`unittest`; the studios' `page_harness.js` desk journeys and Blog's
`check-management.cjs`.

**Spec:** `docs/superpowers/specs/2026-10-22-phase-3-research-stop-design.md`. Read it
with this plan. Context: `docs/superpowers/specs/2026-10-21-authoring-workflow-review.md`
(Phase 3) and, for Task 13,
`studios/blog/docs/superpowers/specs/2026-10-21-announcement-writing-design.md` (item 5).

**Before starting:** Phase 2 has merged. Re-read every file and line named here on the
current `main`; Phase 2 renamed labels. Where this plan quotes a label, find the control by
the function it names, not by its words.

## Global Constraints

- Phases 2 to 5 are built in order, each merged before the next starts. Line references are at main
  21a216e: re-read every named file on the phase's own base first. Training matrix row numbers
  named here are a guide; each new row takes the next free number on that base.
- Python 3.11 or newer, standard library only; no frontend build step.
- UI follows `docs/design/golden-gate.md`: material only for navigation, toolbars and
  transient controls; the brief, report and evidence are opaque reading surfaces.
- Full product names in code, docs and commits: Blog Studio, Presentation Studio,
  Training Studio, Marketing Studio, Harness Research.
- Person-facing sentences never say "artifact", "stale" or "lineage", and never show a
  digest or a hash.
- Research logic stays in Harness Research. The studios read its bundle; they do not
  judge evidence.
- At most **8** planning questions on a synthesis run (`PLAN_MOST = 8`); legacy runs keep
  30 (`QUESTIONS = 30`).
- Form questions: at most 8 lines, each at most 300 characters.
- Tests use disposable settings, workspaces, Git identities and data folders
  (`PRESENTATION_STUDIO_DATA`, `HOME`), scripted workers and synthetic bundles. No
  provider job, no network.
- Training Studio: a change to status, approval, inputs or readiness adds a row to the
  state-transition matrix in
  `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  (section A7) and a `test_row_NN` test. Next row: 119.
- Presentation Studio: a file ported from Training Studio is recorded in `vendor.json`.
- Guidance that needs a script change raises `minimum_runtime` in that studio's
  `guidance/manifest.json` and its `VERSION` together. Blog guidance passes
  `python3 studios/blog/scripts/measure_guidance.py --check`; Training guidance passes
  `validate_package.py`.
- Commit messages are plain sentences; end each with the attribution line the session
  gives.

## Review Focus

1. A bundle that cannot be read at the gate (missing `output.json`, a changed file, a
   draft): the stop shows the report as today and no account, and never throws.
   Tests in Task 1 (`None`) and Tasks 5, 8, 11 (gate payload has `research: None`).
2. A finding ID that begins with a question ID but no `--` (`instance-minimum` vs question
   `instance-min`) must not map. Test in Task 1.
3. A deck or training started before this phase (no `research_sources`, no
   `research_questions`, no contract) keeps its old plan job, scope and queue. Tests in
   Tasks 3 and 4.
4. A claims map whose passage differs from the source only in whitespace or line breaks
   passes; one with a changed word fails, and the second failure stops the stage with a
   sentence. Test in Task 13.
5. A price with no recorded cost (Codex reports no dollars; a first try) says so plainly
   and never prints "$0.00" or "0 seconds". Test in Task 1.

---

## Task 1: The account of the research, and the price of a change (core)

**Files:**
- Create: `core/studio_core/research_view.py`
- Modify: `core/studio_core/research_contract.py` (`Workflow.run`, the author payload's
  `return` text, about line 300)
- Test: `tests/test_research_view.py` (new), `tests/test_research_contract.py`

**Interfaces (Produces):**
- `research_view.JOIN = '--'`
- `research_view.answered_by(finding_id: str, question_ids) -> str | None`
- `research_view.account(folder, questions=()) -> dict | None`, where `folder` is the
  published `research/` folder (it holds `output.json`) and `questions` is an iterable of
  `{'id': str, 'question': str}`. Returns `None` when `read_bundle(folder)` raises.
  Otherwise:
  `{'brief': str, 'report': str, 'evidence': str,
    'check': {'accepted': bool, 'said': str, 'coverage': str|None, 'usefulness': str|None,
              'note': str, 'unread': [{'source', 'title', 'access_error'}]},
    'read': str, 'sources': {'yours': int, 'public': int, 'partial': [{'title', 'note'}]},
    'findings': [{'id', 'title', 'summary', 'gaps': [str], 'question': str|None}],
    'gaps': [str], 'questions': [{'id', 'question', 'findings': [str]}],
    'unplanned': [str]}`
- `research_view.CHECKED`, `research_view.UNCHECKED` (sentences below)
- `research_view.series(items) -> str` ("a", "a and b", "a, b and c")
- `research_view.price(attempts_by_name: dict, redone=(), drafted=True) -> dict`:
  `{'rounds', 'jobs', 'seconds', 'dollars', 'most', 'drafted', 'redone', 'words'}`
- `research_contract.IDS_FOR_QUESTIONS` (the sentence below)

- [ ] **Step 1: Write the failing tests** in `tests/test_research_view.py`. Build a
  synthetic bundle with a helper `bundle(folder, findings, review, sources, sections=(),
  brief=())` that writes `brief.md`, `report.md`, `evidence.md`, `facts.json` and an
  `output.json` whose `artifacts` hold each file's real SHA-256 (owner and schema as
  `research_contract.OWNER` and `2`, `status: 'complete'`, the same `digest` in both).
  Tests:
  - `test_the_account_leads_with_the_brief_and_the_check_s_word`: `account(folder)['brief']`
    is the brief's text; `check['said'] == research_view.CHECKED`; `check['note']` is the
    assessment note with its whitespace collapsed.
  - `test_every_gap_is_listed_once_in_order`: two findings sharing one gap text plus a report
    block `{'kind': 'gap'}` give `gaps` of two items, finding gaps first.
  - `test_sources_are_counted_by_permission_and_partial_ones_named`: two `selected`, one
    `public` with `context: 'partial'` and `context_note: 'Pages 1 to 4 only.'` give
    `read == '3 sources: 2 of yours, 1 public.'` and `partial == [{'title': 'Public page',
    'note': 'Pages 1 to 4 only.'}]`; one source alone gives `'1 source: 1 of yours.'`.
  - `test_findings_answer_the_question_their_id_begins_with`: questions `instance-min` and
    `instance`; findings `instance-min--capacity`, `instance--count`, `instance-minimum`,
    `other`. `questions[0]['findings'] == ['instance-min--capacity']`;
    `questions[1]['findings'] == ['instance--count']`; `unplanned == ['instance-minimum',
    'other']`. `answered_by('instance-min', ['instance-min']) == 'instance-min'`.
  - `test_an_unread_original_is_named_with_its_access_error`: review `originals` with
    `read_original: False` and `access_error: 'Not served.'` appears in `check['unread']`
    with the source's title.
  - `test_no_account_without_a_readable_complete_bundle`: missing folder, a changed
    `brief.md` (hash mismatch) and `status: 'draft'` each return `None`.
  - `test_the_price_names_rounds_cost_and_what_is_made_again`: attempts
    `{'research:author-1': [{'started_at': '2026-10-22T10:00:00Z', 'seconds': 1800,
    'dollars': 6.0}], 'research:review-1': [{'started_at': '2026-10-22T10:30:00Z',
    'seconds': 1080, 'dollars': 3.8}]}` and `redone=('the outline', 'the look samples')`
    give `words == 'Asking for changes runs the research again from its last report: up to
    3 rounds of writing and checking. Its last try took 48 minutes and $9.80. Then it
    makes again: the outline and the look samples.'`.
  - `test_a_price_with_nothing_recorded_says_so`: `price({})['words'] == 'Asking for changes
    runs the research again from its last report: up to 3 rounds of writing and checking.
    No time or money was recorded for its last try.'`; with `drafted=False` the first
    sentence is `'Asking for changes runs the research again: up to 3 rounds of writing and
    checking.'`; seconds recorded and dollars `None` give `'Its last try took 2 minutes.'`
    and no `$`.
  In `tests/test_research_contract.py`, add to `WorkflowCase` subclasses:
  - `test_the_author_is_told_to_name_findings_for_their_questions`: with
    `self.task['planning_questions'] = [{'id': 'q-one', 'question': 'Why?'}]`, the author
    payload's `return` contains `research_contract.IDS_FOR_QUESTIONS`; without
    `planning_questions` (or with an empty list) it does not.

- [ ] **Step 2: Run them to see them fail.**
  Run: `PYTHONPATH=.:tests python3 -m unittest test_research_view test_research_contract -v`
  from the repository root. Expected: `ModuleNotFoundError: research_view` and one failure
  for the new contract test.

- [ ] **Step 3: Implement.** `research_contract.py`:

```python
IDS_FOR_QUESTIONS = ('Planning questions have IDs. A finding that answers one has an ID '
                     "that begins with that question's ID and two hyphens, such as "
                     'instance-min--capacity. Keep each ID within 64 characters.')
```
  In `Workflow.run`, after building the author `payload`, append it when
  `any(isinstance(q, dict) and q.get('id') for q in task.get('planning_questions') or ())`:
  `payload['return'] += ' ' + IDS_FOR_QUESTIONS`.

  `research_view.py`:

```python
"""What a research stop shows, from a published Harness Research bundle, and what a
change to the research costs. Shared by Blog Studio, Presentation Studio and Training
Studio so that all three say the same things in the same words."""
from pathlib import Path

from studio_core import research_contract

JOIN = '--'
CHECKED = ('The independent check accepted the report and the brief: it found their '
           'coverage honest and the brief fit for its use.')
UNCHECKED = 'The independent check has not accepted this research.'


def _line(text):
    return ' '.join(str(text or '').split())


def series(items):
    items = [str(item) for item in items if item]
    if len(items) < 2:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def answered_by(finding_id, question_ids):
    """The planning question a finding answers: the one whose ID the finding's ID is, or
    begins with followed by two hyphens. The longest such ID wins."""
    best = None
    for ident in question_ids:
        if finding_id == ident or str(finding_id).startswith(ident + JOIN):
            if best is None or len(ident) > len(best):
                best = ident
    return best


def _read_words(yours, public):
    total = yours + public
    parts = ([f'{yours} of yours'] if yours else []) + ([f'{public} public'] if public else [])
    return f"{total} source{'' if total == 1 else 's'}: " + ', '.join(parts) + '.'


def account(folder, questions=()):
    try:
        facts, manifest = research_contract.read_bundle(folder)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    folder = Path(folder)
    review = facts.get('review') if isinstance(facts.get('review'), dict) else {}
    assessment = review.get('assessment') if isinstance(review.get('assessment'), dict) else {}
    accepted = manifest.get('status') == 'complete' and bool(review.get('accepted'))
    sources = [s for s in facts.get('sources') or () if isinstance(s, dict)]
    titles = {s.get('id'): s.get('title') or s.get('origin') or s.get('id') for s in sources}
    asked = [{'id': q['id'], 'question': _line(q.get('question'))} for q in questions
             if isinstance(q, dict) and isinstance(q.get('id'), str)]
    ids = [q['id'] for q in asked]
    gaps = []

    def gap(text):
        text = _line(text)
        if text and text not in gaps:
            gaps.append(text)

    findings = []
    for finding in facts.get('findings') or ():
        own = [_line(block.get('text')) for block in finding.get('gaps') or ()
               if isinstance(block, dict) and _line(block.get('text'))]
        for text in own:
            gap(text)
        findings.append({'id': finding['id'], 'title': finding.get('title') or finding['id'],
                         'summary': _line((finding.get('summary') or {}).get('text')),
                         'gaps': own, 'question': answered_by(finding['id'], ids)})
    for sections in (facts.get('sections') or (), facts.get('brief') or ()):
        for section in sections:
            for block in section.get('blocks') or ():
                if isinstance(block, dict) and block.get('kind') == 'gap':
                    gap(block.get('text'))
    yours = sum(s.get('permission') == 'selected' for s in sources)
    public = sum(s.get('permission') == 'public' for s in sources)
    return {
        'brief': (folder / 'brief.md').read_text(encoding='utf-8'),
        'report': (folder / 'report.md').read_text(encoding='utf-8'),
        'evidence': (folder / 'evidence.md').read_text(encoding='utf-8'),
        'check': {'accepted': accepted, 'said': CHECKED if accepted else UNCHECKED,
                  'coverage': assessment.get('coverage'),
                  'usefulness': assessment.get('usefulness'),
                  'note': _line(assessment.get('note')),
                  'unread': [{'source': item.get('source'), 'title': titles.get(item.get('source')),
                              'access_error': _line(item.get('access_error'))}
                             for item in review.get('originals') or ()
                             if isinstance(item, dict) and item.get('read_original') is False]},
        'read': _read_words(yours, public),
        'sources': {'yours': yours, 'public': public,
                    'partial': [{'title': titles.get(s.get('id')), 'note': _line(s.get('context_note'))}
                                for s in sources if s.get('context') == 'partial']},
        'findings': findings, 'gaps': gaps,
        'questions': [{**q, 'findings': [f['id'] for f in findings if f['question'] == q['id']]}
                      for q in asked],
        'unplanned': [f['id'] for f in findings if f['question'] is None],
    }


def price(attempts_by_name, redone=(), drafted=True):
    tried = research_contract.last_rounds(attempts_by_name or {})
    most = research_contract.ROUNDS
    words = ('Asking for changes runs the research again' + (' from its last report' if drafted else '')
             + f': up to {most} rounds of writing and checking.')
    cost = research_contract.took(tried['seconds'], tried['dollars']) if tried else ''
    words += f' Its last try took {cost}.' if cost else ' No time or money was recorded for its last try.'
    if redone:
        words += ' Then it makes again: ' + series(redone) + '.'
    return {**(tried or {'rounds': 0, 'jobs': 0, 'seconds': 0, 'dollars': None}),
            'most': most, 'drafted': drafted, 'redone': list(redone), 'words': words}
```

- [ ] **Step 4: Run the tests to see them pass.** Same command. Expected: OK.
- [ ] **Step 5: Commit.** `git add core/studio_core/research_view.py core/studio_core/research_contract.py tests/test_research_view.py tests/test_research_contract.py`;
  message: "Say what the research found, what its check said and what a change costs, in one place for every studio".

## Task 2: A plan brief for one investigation (Training Studio and Presentation Studio)

**Files:**
- Create: `studios/training/runner/briefs/research-plan-queue.md` (today's
  `research-plan.md`, moved unchanged), `studios/presentation/runner/briefs/research-plan-queue.md`
  (same)
- Modify: `studios/training/runner/briefs/research-plan.md`,
  `studios/presentation/runner/briefs/research-plan.md` (rewritten),
  `studios/training/runner/pipeline.py` (`plan_work`, `work` at about line 1947),
  `studios/training/runner/worker_tools.py` and `studios/presentation/runner/worker_tools.py`
  (`PLAN_MOST`, `check_research_plan`, `check_plan`),
  `studios/presentation/runner/research_steps.py` (`_plan_work`), `studios/presentation/vendor.json`
- Test: `studios/training/tests/test_runner_briefs.py`, `test_runner_worker_tools.py`,
  `test_runner_pipeline.py`; `studios/presentation/tests/test_briefs.py`,
  `test_runner_worker_tools.py`, `test_runner_research.py`

**Interfaces:**
- Produces: `worker_tools.PLAN_MOST = 8`; `check_research_plan(plan, most=QUESTIONS)`;
  the artifact spec key `'most'` read by `check_plan`; Training
  `pipeline.plan_work(..., sources=None, synthesis=False, asked=())`; brief names
  `'research-plan'` (synthesis) and `'research-plan-queue'` (legacy).

- [ ] **Step 1: Failing tests.**
  - Training `test_runner_worker_tools.py`: `test_a_synthesis_plan_holds_at_most_eight_questions`:
    `check_plan(json.dumps({'topic': 'T', 'items': nine}), {'scope': 'public-web', 'most': 8})`
    has the problem `'"items" must hold 1 to 8 questions.'`; with `most` absent nine pass.
    Same test in Presentation's file.
  - Training `test_runner_pipeline.py`: `test_a_contract_plan_job_uses_the_one_investigation_brief`:
    `plan_work(root, found, None, None, [], synthesis=True)` has
    `work.guidance == briefs.guidance('research-plan')` and its prepared artifact spec
    `'most': 8`; `synthesis=False` uses `briefs.guidance('research-plan-queue')` and no
    `'most'`.
  - Presentation `test_runner_research.py`: `test_a_contract_plan_job_uses_the_one_investigation_brief`:
    `_plan_work` for a record with `research_contract` gives the new brief and `'most': 8`;
    a record without it, the queue brief.
  - Both brief tests: `test_the_synthesis_plan_brief_speaks_of_one_investigation`: the brief
    contains `'Ask at most 8 questions.'` and `'One investigation answers them together'`,
    and does not contain `'researched on its own'` or `'30'`.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_runner_briefs test_runner_worker_tools test_runner_pipeline`;
  `cd studios/presentation/tests && python3 -m unittest test_briefs test_runner_worker_tools test_runner_research`.
- [ ] **Step 3: Implement.** `git mv` each `research-plan.md` to `research-plan-queue.md`,
  then write the new `research-plan.md` in each studio. Training's text (Presentation's
  says "presentation" and "talk" where this says "training" and "lesson", and drops the
  levels sentence):

```markdown
# Draft what the research must answer

You are drafting the questions research will answer for a training, before it runs. One
investigation answers them together, and an independent check then reviews what it wrote,
so ask what the training must be able to teach, not every fact it might use. You work
alone, with only the tools named in this guidance.

## What you are given

Your task says what the training is about, who it is for, what it is for, its levels if it
has any, which kinds of source may be used, and any questions the person asked. Call
`list_inputs` to see whether anything more was provided, and read it with `read_input`.
Keep every question the person asked, in their words. If you are revising an earlier
draft, change what they asked for and keep the ID of every question you keep.

## What to ask

Cover what applies: the facts the training rests on, with versions and dates; what people
get wrong; what learners must already know; the objections the topic meets; the cases and
numbers that illustrate it; and, only when the training compares two things, the
dimensions that matter and where each side is stronger. Weight the mix to the purpose and
toward the deepest level.

## How to ask

- Ask at most 8 questions. A short training needs fewer.
- Ask one thing per question, neutrally, in words a source can answer with a passage.
- Do not build what you believe into a question. The research decides what is true.
- If the topic names a set, ask the question that establishes its members.

## The format

Hand back one JSON object, with nothing before or after it:

    {"topic": "Rolling restarts", "items": [{"id": "instance-min",
      "question": "How many instances does an app need to keep capacity during a rolling restart?",
      "public_query": "rolling restart minimum instances capacity"}]}

- `id` is lowercase letters, digits and hyphens, named for its subject, at most 40
  characters. Findings are named after it.
- `public_query` is a few plain, non-confidential search words, or `null` when only
  supplied documents may be used.

## Hand back

1. Call `submit_artifact` with the name your task gives and the JSON as its text.
2. If it comes back with problems, fix them and hand it back again.
3. When it is accepted, call `submit_review` with short notes for the person who will
   approve the questions: what you chose to leave out and why.
```

  `worker_tools.py` (both): `PLAN_MOST = 8`; `check_research_plan(plan, most=QUESTIONS)`
  uses `most` in the count check and its message; `check_plan` passes
  `spec.get('most', QUESTIONS)`. Training `plan_work`: new keywords
  `synthesis: bool = False, asked=()`; choose `briefs.guidance('research-plan' if synthesis
  else 'research-plan-queue')`; when `synthesis`, add `'most': worker_tools.PLAN_MOST` to the
  artifact spec. `pipeline.work` passes `synthesis=bool(found.session.get('research_contract')
  or <the run record's research_contract>)` (read the record the engine passes; if `work`
  cannot see it, add a `synthesis` keyword to `work` and pass
  `bool(record.get('research_contract'))` from `engine._draft`). Presentation `_plan_work`
  does the same from `record.get('research_contract')`. `vendor.json`: add an entry for
  `runner/briefs/research-plan-queue.md` (from Training's same path) and update the
  revision of `runner/briefs/research-plan.md` to the Training commit that adds the new
  brief.
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Brief a contract run's research plan for one investigation, and keep the queue's brief for older runs".

## Task 3: Where research may look, on Presentation Studio's form, kept by the plan

**Files:**
- Modify: `studios/presentation/runner/decks.py` (form check about lines 129-155; intake
  text about line 288), `studios/presentation/runner/research_steps.py` (`_plan_work`),
  `studios/presentation/skills/presentation-studio/scripts/desk/app.js` (`aboutStep`,
  the sent body about line 3046, the draft defaults about line 2659)
- Test: `studios/presentation/tests/test_decks.py`, `test_runner_research.py`, `test_desk.py`

**Interfaces:**
- Produces: `decks.RESEARCH_SOURCES = ('documents', 'both')`; `form['research_sources']`
  (`'documents'`, `'both'`, or absent); the page's `draft.researchSources` (0 documents,
  1 both).

- [ ] **Step 1: Failing tests.**
  - `test_decks.py`: `test_research_from_a_document_says_where_it_may_look`: a document
    route with `research: True` and no `research_sources` is saved with
    `research_sources == 'documents'`; `'both'` is kept; `'web'` is refused with
    `'Choose where research may look: your documents only, or your documents and the public web.'`;
    a scratch route saves no `research_sources`; the intake text's research section reads
    `'yes (your documents only)'` or `'yes (your documents and the public web)'`.
  - `test_runner_research.py`: `test_documents_only_research_plans_with_no_search_words`: a
    contract record with `form.research_sources == 'documents'` gives a plan job whose task
    says `'only the documents the person supplied'` and whose artifact spec has
    `'scope': 'supplied-only'`; `'both'` keeps `'public-web'`; a record without the key
    (a deck started before) keeps `'public-web'` and the public-web sentence.
  - `test_runner_research.py`: `test_the_research_task_keeps_the_boundary`: after a
    documents-only plan is kept, `_research` hands `research_contract.native` a task with
    `source_mode == 'selected'` (patch `research_contract.native` to capture the task).
  - `test_desk.py` (page harness): `test_research_from_a_document_asks_where_it_may_look`:
    on the document route with research ticked the snapshot contains
    `'Where may research look?'`, `'Your documents only'`,
    `'Your documents and the public web'`; the start request body has
    `research_sources: 'documents'` by default and `'both'` after choosing the second.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_decks test_runner_research test_desk`.
- [ ] **Step 3: Implement.** In `decks.py`, when `research` and `route == 'document'`:
  `sources = sent.get('research_sources') or 'documents'`; refuse anything not in
  `RESEARCH_SOURCES` with the sentence above; `checked['research_sources'] = sources`.
  Intake: `'yes (your documents only)'` / `'yes (your documents and the public web)'` /
  `'yes'` (scratch). In `_plan_work`, `only = (record.get('form') or {}).get('research_sources') == 'documents'`;
  when `only`, `allowed = 'only the documents the person supplied. Ask what these can answer, and give no question any search words:\n' + titles`
  and the artifact spec `'scope': 'supplied-only'`. `check_plan`'s `_question` already sets
  `public_query` to `None` for that scope (`worker_tools.py:465`). In `app.js` `aboutStep`, when `draft.route === 'document' &&
  draft.research`, add after the chip
  `choice('Where may research look?', ['Your documents only', 'Your documents and the public web'], draft.researchSources || 0, (index) => { draft.researchSources = index; }, 'research-sources', 'With your documents only, nothing about them is searched for on the public web.')`;
  the scratch hint gains `'Research uses the public web.'`. Send
  `research_sources: draft.route === 'document' && draft.research ? (draft.researchSources === 1 ? 'both' : 'documents') : undefined`.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Ask where a deck's research may look, and keep a confidential document out of public searches".

## Task 4: The plan from the form where the person's documents are all there is (deck studios)

**Files:**
- Modify: `studios/presentation/runner/decks.py` (`research_questions`),
  `studios/presentation/runner/research_steps.py` (`_research_plan`, new `_plan_from_form`,
  `_plan_work` hands the person's questions), `studios/presentation/runner/engine.py`
  (`_timeline` label), Presentation `desk/app.js` (the questions field);
  `studios/training/runner/pipeline.py` (`check_form`, new `plan_from_form`, `plan_work`'s
  `asked`), `studios/training/runner/engine.py` (start: keep `research_questions`;
  `_draft`: write the plan for supplied-only contract runs and accept it under policy),
  Training `desk/app.js` (the questions field beside the sources choice, about line 4407;
  the body about line 4501);
  `studios/training/docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`
  (matrix row 119)
- Test: Presentation `test_decks.py`, `test_runner_research.py`, `test_desk.py`;
  Training `test_runner_pipeline.py`, `test_runner_engine.py`, `test_review_levels.py`,
  `test_desk.py`, `test_workspace.py` (`test_row_119`)

**Interfaces:**
- Consumes: Task 2's `PLAN_MOST`, `plan_work(..., asked=())`; Task 3's `research_sources`.
- Produces: `form['research_questions']: list[str]` (both studios); Training
  `record['research_questions']`; Presentation `record['form']['research_questions']`;
  `FROM_FORM = 'Research plan: written from your form'`; the default question
  `'What do the supplied documents say that serves this goal: {goal}?'`;
  Presentation `_plan_from_form(root, run, step) -> None`; Training
  `pipeline.plan_from_form(root, found, asked: list[str]) -> str` (plan JSON text).

- [ ] **Step 1: Failing tests.**
  - Both form checks: `test_the_research_questions_are_kept_as_written`: lines stripped,
    blank lines dropped, `9` lines refused with `'Ask research at most 8 questions.'`, a
    301-character line refused with `'Keep each research question to 300 characters.'`.
  - Presentation `test_runner_research.py`: `test_a_documents_only_deck_writes_its_plan_from_the_form`:
    a contract record with `research_sources: 'documents'` and two questions runs the
    `research-plan` step with a scripted engine whose agent must not be called (assert the
    stand-in records no job); `research/plan.json` has `scope: 'supplied-only'`, two items
    with IDs from `marks.new_id` and the questions as written, `public_query: None`;
    the timeline row for `research-plan` has `label == FROM_FORM`. With no questions,
    one item whose question is the default sentence with the form's goal.
  - Presentation: `test_web_research_hands_the_person_s_questions_to_the_plan_job`: with
    `research_sources: 'both'` and one question, `_plan_work`'s task contains
    `'The person asked these questions. Keep each in the plan, in their words:\n- <q>'`.
  - Presentation: `test_a_deck_without_research_sources_still_runs_its_plan_job`.
  - Training `test_runner_engine.py`: `test_a_documents_only_training_writes_its_plan_from_the_form`
    (no plan job; plan file written; `workspace.statuses(...)['research-plan'] == 'draft'`
    under Step by step, so the plan gate waits; the job count is zero).
  - Training `test_review_levels.py`: `test_balanced_accepts_a_plan_written_from_the_form`:
    under Balanced the plan is accepted under the saved policy (status `approved`, decision
    `by` the policy) and the next stop is the direction review; under Automatic the same.
  - Training `test_workspace.py`: `test_row_119` covering the row below through the
    engine's public calls.
  - Training: `test_a_public_web_training_still_drafts_its_plan`: `source_scope:
    'public-web'` runs the plan job with `asked` handed in.
  - Both `test_desk.py`: the field `'What should the research answer? (optional)'` with the
    hint `'One question a line, at most 8.'` is shown when research runs, and its lines are
    sent as `research_questions`.
- [ ] **Step 2: Run to fail.** Presentation: `cd studios/presentation/tests && python3 -m unittest test_decks test_runner_research test_desk`;
  Training: `cd studios/training/tests && python3 -m unittest test_runner_pipeline test_runner_engine test_review_levels test_workspace test_desk`.
- [ ] **Step 3: Implement.**
  - A shared check in each studio's form code (same body in both):

```python
def research_questions(sent) -> list[str]:
    given = sent.get('research_questions') or []
    if isinstance(given, str):
        given = given.splitlines()
    if not isinstance(given, list) or not all(isinstance(line, str) for line in given):
        raise WorkspaceError('Write the research questions one a line.')
    lines = [' '.join(line.split()) for line in given if line.strip()]
    if len(lines) > 8:
        raise WorkspaceError('Ask research at most 8 questions.')
    if any(len(line) > 300 for line in lines):
        raise WorkspaceError('Keep each research question to 300 characters.')
    return lines
```
  - Presentation `_research_plan`: if `record.get('research_contract')` and
    `form.get('research_sources') == 'documents'`, call `_plan_from_form` and return.
    `_plan_from_form` builds `{'topic': title, 'purpose': 'planning', 'scope':
    'supplied-only', 'sources': documents.sources(root)[0], 'items': [...]}` with
    `marks.new_id(text, taken)` IDs, `public_query: None`, `claim: None`; checks it with
    `worker_tools.check_research_plan(plan, most=worker_tools.PLAN_MOST)`; keeps it with
    `_keep_plan`; marks the step done with `self._done(root, step, time.monotonic(),
    'write the research plan from the form', record)` and sets
    `record['research']['plan_from'] = 'form'`. The gate keeps its present policy
    behaviour. `_timeline` sets `row['label'] = FROM_FORM` for `research-plan` when
    `(record.get('research') or {}).get('plan_from') == 'form'`.
  - Presentation `_plan_work`: when `form.get('research_questions')`, append the
    person's-questions sentence.
  - Training: `check_form` stores `research_questions`; the engine's start saves
    `record['research_questions'] = form['research_questions']`. In `_draft`, when
    `it.id == 'research-plan'`, `record.get('research_contract')` and `found.scope ==
    'supplied-only'`: write `pipeline.plan_from_form(root, found, record.get('research_questions') or [])`
    to `pipeline.PLAN`, `workspace.save(root, 'research-plan', built=True)`, record the
    step as kept with no job (`self._tried(record, it.id, home.now(), 0, 'kept')`), then,
    when `review_policy.level(record) != 'step_by_step'`, `workspace.accept_policy(root,
    'research-plan', record['review_policy'])`; commit `'write the research plan from the
    form'`. Otherwise pass `asked=record.get('research_questions') or ()` to `plan_work`.
  - Matrix row 119 (append after 118):
    `| 119 | Contract research from the person's documents only (Training source scope supplied-only) | Start with up to 8 questions, or none | No plan job runs. The plan is written from the questions (or one about the goal), with no search words. Balanced and Automatic accept it under the saved policy, so Balanced's first stop is the direction review; Step by step stops at the plan. Public-web and both scopes still draft the plan, keeping the person's questions. Covered by test_row_119 in test_workspace.py and test_review_levels.py. |`
  - Both pages: the textarea `research-questions` under the research choice, shown when
    research will run (Presentation: research ticked; Training: always, as the plan reads
    it), sent as an array of lines.
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Write the research plan from the form when the person's documents are all research may read".

## Task 5: Presentation Studio's research stop shows the brief, the check and the questions

**Files:**
- Modify: `studios/presentation/runner/engine.py` (`_show_research`, about line 2695),
  `studios/presentation/runner/research_steps.py` (`_findings_shown` under the contract),
  Presentation `desk/app.js` (`researchPanel`, `findingCard`, `paintFindings`)
- Test: `studios/presentation/tests/test_runner_research.py`, `test_runner_page.py`,
  `test_desk.py`

**Interfaces:**
- Consumes: `research_view.account`.
- Produces: the research gate payload `{'text', 'items', 'contract': bool,
  'research': account | None}`; each contract item gains `'question'` (the planning
  question's text or `''`) and `'question_id'`.

- [ ] **Step 1: Failing tests.**
  - `test_runner_research.py`: `test_a_contract_research_gate_carries_the_account`: with
    a synthetic published bundle under `research/` (reuse the fixture style of
    `tests/synthesis_fixture.py`) and `research/plan.json` holding `instance-min`, the
    payload's `research['brief']` is the brief, `research['questions'][0]['findings'] ==
    ['instance-min--capacity']`, and the matching item's `question` is that question's
    text. No value in the payload (searched recursively) equals the manifest's digest.
  - Same file: `test_an_unreadable_bundle_leaves_the_report_alone`: changed `brief.md`
    gives `research: None` and the report text as before.
  - `test_desk.py`: `test_the_research_stop_leads_with_the_brief_and_the_check`: the gate
    snapshot holds, in order, the brief's first line, `research_view.CHECKED`, the
    check's note, `'What the research could not settle'` with the gap, `'3 sources: 2 of
    yours, 1 public.'`, `'Your questions'` with the question and the finding title,
    `'Also found'`; it does not contain `'answered by the sources'` or `'0 to look at'`;
    the counts read `'2 findings'` and `'1 left out'` after one Leave out.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_runner_research test_runner_page test_desk`.
- [ ] **Step 3: Implement.** `_show_research` adds `'contract': bool(record.get('research_contract'))`
  and, for contract runs, `'research': research_view.account(root / 'research', questions)`
  where `questions = [{'id': i, 'question': q} for i, q in self._questions(root).items()]`.
  `_findings_shown` (contract branch) sets `question`/`question_id` from
  `research_view.answered_by`. In `app.js`, `researchPanel`: when `gate.research`, render
  (in this order) a reading surface with the brief (`markdown.js` renderer), a
  `'What the independent check said'` part (`check.said`, `check.note`, each unread
  original as `'<title>: <access_error>'`), `'What the research could not settle'` with
  `gaps` and the partial sources, the `read` line, `'Your questions'` (each question with
  its findings' titles or `'The research did not answer this.'`), then the finding cards
  under `'Also found'` for `unplanned`, then `fullText` folds for the report and
  `'The evidence and the check’s notes'`. The counts become `[findings, 'finding',
  'findings'], [left, 'left out']`. `findingCard` shows `item.question` only when set.
  Legacy runs (`!gate.contract`) render as today.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Show a deck's research brief, its check and its questions at the research stop".

## Task 6: Triage at Presentation Studio's direction review

**Files:**
- Modify: `studios/presentation/runner/engine.py` (`_decided` direction branch, a new
  `_leave_out`, `_gate_view` Balanced branch), Presentation `desk/app.js` (`outlinePanel`)
- Test: `studios/presentation/tests/test_review_levels.py`, `test_engine.py`, `test_desk.py`

**Interfaces:**
- Consumes: Task 5's `researchPanel` pieces and payload.
- Produces: a direction decision `decide(path, 'gate:outline', 'changes', None,
  {'direction_target': 'gate:research', 'left_out': [ids]}, expected)` that records
  `record['research']['left_out']`, reopens the outline and the looks, and runs no
  research job; `shown['leave_out_price'] = {'words': str}`.

- [ ] **Step 1: Failing tests.**
  - `test_review_levels.py`: `test_leaving_findings_out_at_the_direction_review_redraws_only_the_outline`:
    under Balanced at the direction review, the decision above with one finding left out
    stores it, sets the outline step and the look step fresh, leaves `research` and
    `research-report` done, and starts no research job (scripted engine records the job
    names; none begins with `research:`). Leaving out every finding is refused with
    `marks.ALL_LEFT_OUT` ("Keep at least one finding: the outline is drafted from them.").
  - Same: `test_the_direction_review_shows_the_research_account`: the Balanced gate view
    has `research['research']` (the account) and `leave_out_price['words']` starting
    `'Leaving findings out redraws the outline and the look samples without researching again.'`
  - `test_desk.py`: `test_the_direction_review_triages_the_research`: the Balanced outline
    gate shows the brief and the finding cards with `'Leave out'`; leaving one out and
    sending posts `direction_target: 'gate:research'` with `left_out`, and the sheet shows
    the leave-out price words. The raw `'Research findings'` document part is gone.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_review_levels test_engine test_desk`.
- [ ] **Step 3: Implement.** In `_decided`, when `combined`, `target == 'gate:research'`,
  `decision == 'changes'`, no note and the marks hold only `left_out`: call
  `self._leave_out(root, record, marked['left_out'], at, by)` and return
  `('leave research findings out of the direction', ())`. `_leave_out` writes
  `record['research'] = {**research, 'left_out': ids}`, calls `self._fresh` for the outline
  step and every step after it in `_reopened(record, 'gate:outline')`, writes the research
  report again with `_report_text`, and keeps `gate:research` approved. Price words:
  `'Leaving findings out redraws the outline and the look samples without researching again.'`
  plus `' They last took <took>.'` from `attempts(record, 'outline')` and the look step's
  attempts summed with `research_contract.took`, or nothing when none were recorded.
  `_gate_view` Balanced branch keeps `shown['research'] = self._show_research(...)` (now
  with the account) and adds `leave_out_price`. In `outlinePanel`, replace
  `documentPart('Research findings', …)` with the Task 5 panel (finding cards writable);
  the direction decision sends the leave-outs with `direction_target: 'gate:research'`.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Let the direction review leave findings out without researching again".

## Task 7: A research change priced, and per-finding requests that say what they run (Presentation Studio)

**Files:**
- Modify: `studios/presentation/runner/engine.py` (`_show_research`, `_gate_view`),
  Presentation `desk/app.js` (`findingCard`, the research request sheet, the direction
  review's research request form about line 4160)
- Test: `studios/presentation/tests/test_runner_page.py`, `test_desk.py`

**Interfaces:**
- Consumes: `research_view.price`.
- Produces: research gate payload `research_price` (the `price` dict); the Balanced
  direction view's `research['research_price']`.

- [ ] **Step 1: Failing tests.**
  - `test_runner_page.py`: `test_the_research_gate_prices_a_change`: with recorded
    `research:author-1` and `research:review-1` tries, the gate's `research_price['words']`
    equals the Task 1 sentence with `'Then it makes again: the outline.'` at
    `gate:research`, and `'… the outline and the look samples.'` at the Balanced direction
    review (labels from `WORDS`/stage labels of done steps in `_reopened`).
  - `test_desk.py`: `test_asking_about_a_finding_says_the_whole_research_runs_again`: on
    a contract gate the per-finding control reads `'Ask about this finding'`, its field
    `'What is wrong with “<title>”?'`, and the request sheet shows `research_price.words`
    above the send button; on a legacy gate the control reads `'Research again'` and no
    price is shown.
  - `test_desk.py`: `test_the_direction_review_prices_its_research_request`.
- [ ] **Step 2: Run to fail.** `cd studios/presentation/tests && python3 -m unittest test_runner_page test_desk`.
- [ ] **Step 3: Implement.** `_show_research` adds, for contract runs,
  `'research_price': research_view.price({name: entry.get('tries') or [] for name, entry in record['steps'].items() if isinstance(entry, dict)}, redone, drafted=self._drafted(root))`
  with `redone` the labels of done steps in `self._reopened(record, 'gate:research')`
  other than research steps. `app.js`: under `gate.contract`, rename the per-finding
  control and its field as above; put `make('p', 'quiet', gate.research_price.words)` in
  the research request sheet and the direction review's research form. If Phase 2 added a
  general price line to this sheet, show the research words in its place.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Price a change to a deck's research before it is sent, and say it runs the whole research".

## Task 8: Training Studio's research stop shows the brief, the check and the questions

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk.py` (`gate`),
  `studios/training/runner/engine.py` (`_report`'s review line, about line 3372),
  Training `desk/app.js` (`checkedNote`, the gate's research part, the direction review's
  plan part)
- Test: `studios/training/tests/test_desk.py`, `test_runner_engine.py`

**Interfaces:**
- Consumes: `research_view.account`.
- Produces: `desk.gate(path, 'research')['research']` (account or `None`); the plan gate
  and the direction review show the plan as questions (`document()` kind `questions`).

- [ ] **Step 1: Failing tests.**
  - `test_runner_engine.py`: `test_the_research_review_line_names_the_check_not_a_digest`:
    after `_report` on a contract run, the review appended for `research` reads
    `research_view.CHECKED` followed by the check's note, and contains no `'Digest'` and
    not the manifest digest.
  - `test_desk.py`: `test_the_research_gate_carries_the_account`: `desk.gate(path,
    'research')['research']['questions']` maps the plan's questions; a training with no
    bundle has `research: None`.
  - `test_desk.py` (page): `test_the_research_stop_leads_with_the_brief_and_the_check`:
    the snapshot holds the brief, the check's sentence and note, the gaps, the `read`
    line, `'Your questions'`; it does not contain `'No automatic checks apply here'` or
    the gate's `sha256`.
  - `test_desk.py` (page): `test_the_direction_review_shows_the_plan_s_questions`: the
    research plan in the Balanced direction review lists its questions.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_desk test_runner_engine`.
- [ ] **Step 3: Implement.** `desk.gate`: when `name == 'research'` and
  `(root / 'research/output.json').is_file()`, add `'research': research_view.account(root
  / 'research', questions)` with `questions` from `desk.questions(<plan text>)['questions']`
  (or `[]`); otherwise `'research': None`. `_report`: the review line becomes
  `account['check']['said'] + (' ' + account['check']['note'] if account['check']['note'] else '')`
  (fall back to `research_view.CHECKED` when the account is `None`). `app.js`: at the
  research gate with `found.research`, render the Task 5 panel's parts in Training's own
  helpers in place of `checkedNote`; the gate never prints `found.sha256`. The direction
  review renders the research plan part through the same `kind: 'questions'` renderer the
  plan gate uses.
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Show a training's research brief, its check and its questions at the research stop".

## Task 9: A research change priced with what it makes again, and the objections a click away (Training Studio)

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/workspace.py` (new
  `downstream`), `studios/training/runner/engine.py` (new `research_price`; the stop's
  problem payload names its objections file), `studios/training/runner/page.py` (`gate`),
  Training `desk/app.js` (`FORMS.revise` sheet at research; the stop card)
- Test: `studios/training/tests/test_workspace.py`, `test_runner_engine.py`,
  `test_runner_page.py`, `test_desk.py`

**Interfaces:**
- Consumes: `research_view.price`, `research_view.series`.
- Produces: `workspace.downstream(root, session, name) -> list[str]` (made artifacts whose
  `upstream` chain reaches `name`, in `artifact_names` order); `Engine.research_price(path)
  -> dict | None`; `page.gate(...)['research_price']`; problem `'objections':
  'reviews/research.md'`.

- [ ] **Step 1: Failing tests.**
  - `test_workspace.py`: `test_downstream_lists_what_is_built_from_research`: with levels
    101 and 201, a made blueprint, guide and brief at each, `downstream(root, session,
    'research')` lists every blueprint, document and brief (and deck when made) and not
    `intake` or `research-plan`; nothing made gives `[]`.
  - `test_runner_engine.py`: `test_a_research_change_is_priced_with_what_it_makes_again`:
    `research_price(path)['words']` ends with `'Then it makes again: the 101 blueprint,
    the 101 learner guide, the 201 blueprint and the 201 learner guide.'` (labels by
    `workspace.label`; check the exact label words against `label()` and write the test to
    them).
  - `test_desk.py` (page): `test_the_research_request_sheet_says_what_it_runs`: opening the
    request sheet at the research gate shows `research_price.words`; other gates show no
    research sentence.
  - `test_desk.py` (page): `test_a_research_stop_opens_every_objection`: a failed research
    problem with `objections: 'reviews/research.md'` shows `'Read every objection'`, which
    reads that file through the page's file request and shows its text.
- [ ] **Step 2: Run to fail.** `cd studios/training/tests && python3 -m unittest test_workspace test_runner_engine test_runner_page test_desk`.
- [ ] **Step 3: Implement.** `downstream`: walk `artifact_names(root, session)`, keep a name
  when its `upstream` (recursively) includes `name` and `sha256_file` of its file is not
  `None`. `Engine.research_price(path)`: load the record; `None` unless
  `record.get('research_contract')`; attempts as at `engine.py:3862`; `redone =
  [workspace.label(n) for n in workspace.downstream(root, session, 'research')]`; return
  `research_view.price(attempts, redone, drafted=<a saved synthesis case exists>)`.
  `page.gate` adds `research_price` for `name == 'research'`. `_review_refused` puts
  `'objections': 'reviews/research.md'` in the problem; the stop card adds the button as
  Presentation's does (`desk/app.js:3496-3505` there).
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Say what a change to a training's research runs and makes again, and open the check's objections from the stop".

## Task 10: Blog Studio keeps its research setting and says what will run

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js` (Home card entry,
  about line 165; "Ready to start", about line 179), `studios/blog/scripts/ci/check-management.cjs`
- Test: `check-management.cjs` journeys

**Interfaces:**
- Consumes: `sPipeline(draft)`, `sResearches(draft)`, `studio.settings.defaults.research`
  (confirm the field name in `api('run-settings')`'s answer).
- Produces: `sResearchWords(draft) -> string`.

- [ ] **Step 1: Failing journeys** in `check-management.cjs`:
  - `home card takes the research default`: with Settings research `web-allowed`, the
    write-from-brief card's draft has `research === 'web-allowed'`; Explore ideas, Revise
    and Review cards have `'none'`; from-files keeps `'supplied-only'`.
  - `ready to start says what research will run`: the card reads `'No research.'` for
    `none`; `'Research reads only the 2 sources you ticked.'` for supplied-only with two;
    `'Research reads the sources you ticked and the public web.'` for web-allowed;
    `'No research: no source is ticked.'` for supplied-only with none. The old
    `'Research uses only the sources you allow.'` is gone.
- [ ] **Step 2: Run to fail.** `node studios/blog/scripts/ci/check-management.cjs`.
- [ ] **Step 3: Implement.** In the entry branch, replace `studio.draft.research='none'` with
  `studio.draft.research=['ideas','revise','review'].includes(entry)?'none':(studio.settings?.defaults?.research||'supplied-only')`.
  `sResearchWords(draft)`: from `sPipeline(draft).includes('research')` and the ticked
  source count, return the four sentences above. Use it in "Ready to start".
- [ ] **Step 4: Run to pass.** Same command.
- [ ] **Step 5: Commit:** "Start a blog with the research setting it has, and say what research will run".

## Task 11: Blog Studio's research stage shows the brief, the check and the price

**Files:**
- Modify: `studios/blog/skills/blog-studio/scripts/blog_runner.py` (`document()` about
  line 2272; `survey()` adds `research_price`), `scripts/synthesis_research.py` (the
  returned `notes`, lines 337-339), `assets/management/runner.js` (the stage aside about
  line 252; `sChanges` about line 263), `studios/blog/scripts/ci/check-management.cjs`
- Test: `studios/blog/tests/test_blog_runner.py`, `test_run_recovery.py`,
  `check-management.cjs`

**Interfaces:**
- Consumes: `research_view.account`, `research_view.price`.
- Produces: `document(root, ident, 'research')['research']` (account or `None`);
  `survey(root, ident)['research_price']` when the research stage has a saved version.

- [ ] **Step 1: Failing tests.**
  - `test_blog_runner.py`: `test_the_research_stage_view_carries_the_account`: a run with a
    published synthetic bundle in `research/` returns the brief and the check sentence in
    `document(...)['research']`, maps planning questions parsed from
    `derived/blog-research-plan.md` (Task 12's format; write the file in the test), and no
    value equals the digest. Without a bundle: `research is None`.
  - `test_blog_runner.py`: `test_the_research_notes_say_what_the_check_said`: the research
    result's `notes` is the check's sentence and note, not the old constant (assert
    `'retained in research/'` is absent).
  - `test_run_recovery.py`: `test_a_research_change_is_priced`: with recorded research job
    seconds and dollars, `survey()['research_price']['words']` names the rounds, the cost
    and `'Then it makes again: the outline and the draft.'` for a run whose outline and
    draft are saved.
  - `check-management.cjs`: `research stage shows the brief and the check` (the aside shows
    the brief, `CHECKED`, the note, gaps and questions; `'No assistant note was
    submitted'` is absent at research); `asking for research changes shows the price`
    (choosing the research stage in the request sheet shows `research_price.words`;
    another stage does not).
- [ ] **Step 2: Run to fail.** `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest test_blog_runner test_run_recovery`; `node studios/blog/scripts/ci/check-management.cjs`.
- [ ] **Step 3: Implement.** `document()`: when `stage == 'research'` and
  `run.get('research_contract')`, add `'research': research_view.account(directory /
  'research', planning_questions(<plan text>))`. `survey()`: when the run has the contract
  and the research stage is saved, `research_price = research_view.price(<the run's
  research job attempts as Phase 1 records them>, [STAGE_WORDS-style labels of later saved
  stages], drafted=True)`; label words come from `STAGES[name][0]` lower-cased with
  "the". `synthesis_research`: after `publish`, build the account and return
  `notes = account['check']['said'] + (' ' + note if note else '')`. `runner.js`: at the
  research stage with `shown.research`, render the brief, the check, the gaps, the `read`
  line and the questions in place of the "Worth a look" part; in `sChanges`, when
  `held.stage === 'research'` and `found.research_price`, show its words above the send
  button, updating on select change.
- [ ] **Step 4: Run to pass.** Same commands.
- [ ] **Step 5: Commit:** "Show a blog's research brief and its check at the research stage, and price a change to it".

## Task 12: A research plan module for a tool-less worker, and one research system documented (Blog Studio)

**Files:**
- Create: `studios/blog/skills/blog-studio/references/modules/blog-research-plan.md`,
  `studios/blog/skills/blog-studio/references/modules/blog-legacy-research.md`
- Modify: `scripts/blog_runner.py` (`GUIDES['research-plan']`, new
  `planning_questions(text)`), `scripts/synthesis_research.py` (task
  `planning_questions`), `references/modules/blog-deep-research.md`,
  `docs/estimates/blog-studio-token-inventory.json` (re-recorded),
  `studios/blog/docs/commands.md` if the command reference changes
- Test: `studios/blog/tests/test_blog_runner.py`, `test_synthesis_integration.py`

**Interfaces:**
- Produces: `blog_runner.planning_questions(text: str) -> list[dict]` reading lines
  `- **<id>**: <question>` (IDs `^[a-z0-9][a-z0-9-]{0,39}$`, at most 8 kept, in order,
  duplicates dropped); the synthesis task's `planning_questions`.

- [ ] **Step 1: Failing tests.**
  - `test_blog_runner.py`: `test_the_research_plan_job_uses_its_own_module`:
    `GUIDES['research-plan'] == 'modules/blog-research-plan.md'` and the job's guidance
    text contains `'You have no tools.'` and `'at most 8 questions'`.
  - `test_blog_runner.py`: `test_planning_questions_are_read_from_the_plan`: the text
    `'- **why-now**: Why now?\n- **Bad id**: x\n- **cost**: What does it cost?'` gives
    `[{'id': 'why-now', 'question': 'Why now?'}, {'id': 'cost', 'question': 'What does it cost?'}]`;
    nine valid lines give eight.
  - `test_synthesis_integration.py`: `test_the_author_is_given_the_plan_s_questions`: the
    author payload's `task['planning_questions']` holds the parsed questions and its
    `return` contains `research_contract.IDS_FOR_QUESTIONS`.
  - `test_blog_runner.py`: `test_the_research_module_documents_the_synthesis_path_only`:
    `blog-deep-research.md` does not contain `'deep_research.py'` commands (assert
    `'deep_research.py research'` absent) and contains
    `'modules/blog-legacy-research.md'`; the legacy module contains the commands.
- [ ] **Step 2: Run to fail.** `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest test_blog_runner test_synthesis_integration`.
- [ ] **Step 3: Implement.** `blog-research-plan.md` (short; for a writing job with no
  tools): what the job is given (the brief, the point, the audience, the ticked sources by
  name, the boundary), what to ask (the central argument's evidence, mechanisms, the
  strongest objections, versions and dates), "Ask at most 8 questions", "You have no
  tools. Do not research; one investigation answers these together afterwards", and the
  return format `- **<id>**: <question>`, one a line, IDs lowercase letters, digits and
  hyphens, at most 40 characters. `blog-deep-research.md`: keep the intro, "New synthesis
  research" and the import command; replace the legacy sections (from "Select questions
  and scope" through the end of the legacy commands) with one line: "A blog whose research
  was saved before synthesis research continues with
  [the legacy research commands](blog-legacy-research.md); load that only for such a
  blog." Move those sections, unchanged, into `blog-legacy-research.md`. Update any route
  in the token inventory that lists `blog-deep-research.md` to add the legacy module only
  where the legacy route needs it. Run `python3 studios/blog/scripts/measure_guidance.py`
  to record, then `--check`. In `synthesis_research`, set
  `task['planning_questions'] = blog_runner.planning_questions(payload['documents'].get('research-plan') or '')`
  (import inside the function if a cycle arises).
- [ ] **Step 4: Run to pass.** Same command, plus `python3 studios/blog/scripts/measure_guidance.py --check`
  and `python3 studios/blog/scripts/command_reference.py --check`.
- [ ] **Step 5: Commit:** "Give Blog Studio's research plan a brief for a worker with no tools, and document one research system".

## Task 13: A claims map instead of research for supplied material (Blog Studio)

This is Task 5 of `studios/blog/docs/superpowers/plans/2026-10-21-announcement-writing.md`;
mark it there as done by this plan.

**Files:**
- Create: `studios/blog/skills/blog-studio/references/modules/blog-claims-map.md`,
  `studios/blog/skills/blog-studio/scripts/claims_map.py`
- Modify: `scripts/blog_runner.py` (`STAGES`, `GUIDES`, `RESEARCH_STAGES`, `create()`
  pipeline about line 1115, `job()`'s one-correction path), `scripts/blog_worker.py`
  (`POLICY`), `assets/management/runner.js` (`STAGE_WORDS`, `DOING`, `sPipeline`),
  `studios/blog/scripts/ci/check-management.cjs`,
  `docs/estimates/blog-studio-token-inventory.json`
- Test: `studios/blog/tests/test_blog_runner.py`, `test_run_recovery.py`,
  `check-management.cjs`

**Interfaces:**
- Produces: stage name `'claims-map'`, file `derived/blog-claims-map.md`, label
  `'Claims in your material'`; `claims_map.problems(content: str, sources: list[dict]) ->
  list[str]` where each source is `{'id': str, 'text': str}`; line format
  `- **<claim>** — <source name> (`<source id>`): "<exact passage>"`.

- [ ] **Step 1: Failing tests.**
  - `test_blog_runner.py`: `test_supplied_only_research_maps_claims_instead`: a
    write-from-brief run with supplied-only research and two ticked facts sources has
    pipeline `['claims-map', 'outline', 'draft', 'review', 'package']`; web-allowed keeps
    `['research-plan', 'research', 'outline', …]`; supplied-only with no ticked source
    has neither; a from-files run is unchanged.
  - `test_blog_runner.py`: `test_a_claims_map_passage_must_be_in_its_source`:
    `claims_map.problems` passes a passage that differs only in whitespace and line
    breaks; fails `'The passage for "<claim>" is not in <source id>.'` for a changed word;
    fails `'"<id>" is not one of the sources this blog reads.'` for an unknown ID; fails
    `'List at least one claim, one a line, as the guidance shows.'` for no claim lines.
  - `test_blog_runner.py`: `test_a_claims_map_gets_one_correction`: a scripted worker whose
    first answer fails the check and whose second passes is accepted; two failures stop
    the stage with `'The claims map quoted passages that are not in your material: '`
    followed by the first problem.
  - `test_blog_runner.py`: `test_balanced_continues_past_the_claims_map`: under Balanced
    the claims map is accepted by the review policy and the run goes on to the outline;
    under Step by step it waits.
  - `test_run_recovery.py`: `test_continue_without_research_drops_the_claims_map`: the
    `skip-research` action removes `claims-map` from the pipeline.
  - `test_blog_runner.py`: `test_later_stages_receive_the_claims_map`: the outline job's
    `payload['documents']['claims-map']` is the map, and `POLICY` contains `'claims-map'`.
  - `check-management.cjs`: `supplied-only research shows the claims map in the stops`.
- [ ] **Step 2: Run to fail.** `cd studios/blog/tests && HOME=$TMPDIR/h python3 -m unittest test_blog_runner test_run_recovery`.
- [ ] **Step 3: Implement.**
  - `STAGES['claims-map'] = ('Claims in your material', 'derived/blog-claims-map.md',
    'List each claim the supplied material makes, with the source that makes it and its
    exact passage. Judge none of them and do not research.')`;
    `GUIDES['claims-map'] = 'modules/blog-claims-map.md'`;
    `RESEARCH_STAGES = ('research-plan', 'research', 'claims-map')`.
  - `create()`: after `research = research_scope(...)` and the from-files rule,
    `pipeline = [] if research == 'none' else ['claims-map'] if research == 'supplied-only' else ['research-plan', 'research']`.
  - `claims_map.py`:

```python
"""Check a claims map: every claim quotes its source exactly."""
import re

LINE = re.compile(r'^- \*\*(?P<claim>.+?)\*\* — .*?\(`(?P<source>[^`]+)`\): "(?P<passage>.+)"\s*$')


def _flat(text):
    return ' '.join(str(text).split())


def problems(content, sources):
    texts = {source['id']: _flat(source.get('text') or '') for source in sources}
    found, said = 0, []
    for line in content.splitlines():
        match = LINE.match(line.strip())
        if not match:
            continue
        found += 1
        ident, claim = match['source'], match['claim']
        if ident not in texts:
            said.append(f'"{ident}" is not one of the sources this blog reads.')
        elif _flat(match['passage']) not in texts[ident]:
            said.append(f'The passage for "{claim}" is not in {ident}.')
    if not found:
        said.append('List at least one claim, one a line, as the guidance shows.')
    return said
```
  - `job()`: for `found['next'] == 'claims-map'`, check `claims_map.problems(result['content'],
    payload['sources'])`; on problems retry once with `validation_error` and
    `previous_output` exactly as the editor review path does (`blog_runner.py:1944-1968`);
    a second failure raises `ValueError('The claims map quoted passages that are not in your material: ' + said[0])`.
  - `POLICY += "\nWhen documents['claims-map'] is supplied, it lists the claims the author's own material makes and where. State those claims as the material does, and add no claim it does not make."`
  - `blog-claims-map.md`: what the job is given, the line format above with one example,
    "Quote the passage exactly as the source has it", "Judge none of them, and say nothing
    is confirmed or unconfirmed", "You have no tools". Record the budget.
  - `runner.js`: `STAGE_WORDS['claims-map'] = 'the claims in your material'`,
    `DOING['claims-map'] = 'Mapping the claims in your material'`; `sPipeline` returns
    `['claims-map']` for supplied-only with ticked sources outside from-files.
  - Mark Task 5 of the announcement plan: replace its checkboxes with a line "Done in
    `docs/superpowers/plans/2026-10-22-phase-3-research-stop.md`, Task 13."
- [ ] **Step 4: Run to pass.** Same command, plus `node studios/blog/scripts/ci/check-management.cjs`
  and `python3 studios/blog/scripts/measure_guidance.py --check`.
- [ ] **Step 5: Commit:** "Map the claims in a blog's own material instead of researching them".

## Task 14: Docs and the full check

**Files:**
- Modify: `docs/research-synthesis.md` (the account, the ID convention, the price);
  `studios/training/docs/runner.md`, `docs/how-it-works.md`; `studios/presentation/docs/runner.md`,
  `README.md`; `studios/blog/skills/blog-studio/references/guided-runs.md`,
  `references/page-tools.md`, `studios/blog/README.md`, `studios/blog/docs/runner.md`,
  `studios/blog/CHANGELOG.md` (Unreleased); Training and Presentation guidance that
  describes the research plan (`references/stages/research-plan.md`,
  `references/routes.md`, `references/workspace.md`) only where it now says something
  untrue. If a guidance change relies on this phase's scripts, raise that studio's
  `guidance/manifest.json` `minimum_runtime` and `VERSION` together.

- [ ] **Step 1:** Update the docs above. Training: `validate_package.py`. Blog:
  `measure_guidance.py --check`, `command_reference.py --check`.
- [ ] **Step 2: Full check, once.**
  - Root: `PYTHONPATH=.:tests python3 -m unittest discover -s tests -v` (includes
    `test_research_view`, `test_research_contract`, `test_ui_consistency`).
  - Presentation: `cd studios/presentation && python3 scripts/ci/run_tests.py --jobs 4 && python3 skills/presentation-studio/scripts/validate_package.py`.
  - Training: `cd studios/training && python3 scripts/ci/run_tests.py --jobs 4 && python3 skills/training-studio/scripts/validate_package.py`.
  - Blog: `python3 studios/blog/scripts/ci/run_tests.py --jobs 6`, `node studios/blog/scripts/ci/check-management.cjs`,
    `cd studios/blog && ruff format --check . && ruff check .`.
  - The synthesis integration suites with `STUDIO_TEST_RESEARCH_RUNTIME` pointing at a local
    Harness Research checkout, scripted workers only.
  - Prefer the shared Tart runner on macOS for the whole suite:
    `bash scripts/ci/tart-macos.sh --dry-run`, then without `--dry-run`.
  - Compare any failure with a clean `git archive origin/main` export before calling it
    pre-existing.
- [ ] **Step 3: Commit:** "Document the research stop: the account, the questions, the price and the boundary".
