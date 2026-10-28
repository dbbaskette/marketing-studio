# Training Studio Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Training Studio skill: a Python helper that tracks one training's artifacts, approvals, exports and readiness in the directory the harness is launched in, and the guidance that takes a topic through research, a blueprint, a learner guide, a brief, a deck and practice scenarios.

**Architecture:** One directory is one training. A standard-library Python CLI keeps a session record, content-addressed history and computed status (`workspace.py`) and runs format checks and a readiness report (`checks.py`). The pipeline is guidance: a router `SKILL.md` that loads one reference per stage. Research is delegated to `harness-research` and decks to `harness-slides`; the helper never calls them or the network.

**Tech Stack:** Python 3.11+ standard library (`argparse`, `hashlib`, `json`, `os`, `pathlib`, `re`, `unittest`). Markdown guidance. No third-party packages.

**Spec:** [docs/superpowers/specs/2026-10-12-training-studio-core-pipeline-design.md](../specs/2026-10-12-training-studio-core-pipeline-design.md), revision 2. Section numbers below refer to it.

---

## How this plan is organised

This is revision 2. It follows an external review of revision 1: four increments in place of seventeen tasks, contracts in place of embedded code, and a state-transition matrix whose rows are tests.

- **Contracts first.** Part A fixes the interfaces, formats and algorithms. Code appears only where it settles a contract.
- **Tests before code, by increment.** Within an increment, write the tests for a contract, then the code. Run the targeted tests named at each milestone. Run the whole suite once at the end of increment 4.
- **Revision 1 is reusable.** Commit `1b5fc03` holds a complete, tested implementation of the previous design inside the old plan (101 tests passing). Recover it with `git show 1b5fc03:docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md`. The parts marked "carry over" below can be lifted from it; everything else is new or changed.
- **No training content in this repository.** Tests use temporary directories. Live acceptance uses directories outside it.
- **Commit at each milestone.** If the host's sandbox refuses a git write, rerun it through the host's permission flow.

## Part A: Contracts

### A1. Files

| File | Responsibility |
| --- | --- |
| `skills/training-studio/scripts/workspace.py` | Session record, artifact map, inputs, saves, history, status, approval, exports, skip, checkpoint, pin, lock |
| `skills/training-studio/scripts/checks.py` | Pure functions: blueprint lint; brief, scenario and Yoodli checks; coverage; readiness |
| `skills/training-studio/scripts/training.py` | Command line: parsing, dispatch, structured errors, the `check` aggregation |
| `skills/training-studio/scripts/validate_package.py` | Required files exist; guidance links resolve; disclosure budgets and the one-hop rule hold; `--measure` prints the table (A9) |
| `skills/training-studio/assets/profiles/yoodli.json` | Yoodli types, fields, prerequisites and limits, with provenance |
| `skills/training-studio/assets/examples/` | `blueprint.md`, `document.md`, `competitive-brief.md`, `product-brief.md`, `scenario.md`, `yoodli.md` |
| `skills/training-studio/SKILL.md`, `agents/openai.yaml`, `references/**` | Guidance (A8) |
| `tests/helpers.py` | Import path, temporary training directory, builders, sample data |
| `tests/test_workspace.py` | The state-transition matrix (A7) |
| `tests/test_checks.py` | Format checks against the examples (A5) |
| `tests/test_cli.py` | The CLI in a subprocess, including readiness |
| `tests/test_package.py` | The package validator |
| `tests/test_disclosure.py` | Each loading set in A9 fits its budget |
| `docs/progressive-disclosure.md` | The measured table of files and loading sets |

### A2. Artifacts, stages and inputs

Stages: `intake`, `research-plan`, `research`, `blueprint`, `document`, `brief`, `deck`, `scenario`, `package`, `done`. Skippable: `document`, `brief`, `deck`, `scenario`.

| Artifact | File | Stage | Inputs |
| --- | --- | --- | --- |
| `intake` | `intake.md` | intake | none |
| `research-plan` | `.training-studio/research-plan.json` | research-plan | `intake` |
| `research` | `.harness-research/research-report.md` | research | `research-plan` |
| `blueprint` | `blueprint.md` | blueprint | `intake`, `research` |
| `document` | `document.md` | document | `blueprint` |
| `brief` | `competitive-brief.md` or `product-brief.md`, by `settings.brief_kind` | brief | `blueprint`, `research`, `setting:brief_kind` |
| `deck` | `deck-link.md` when `settings.deck_target` is `google`, else `deck.pptx` | deck | `blueprint`, `document` (or `research` when document is skipped), `setting:deck_target`, `setting:brand` |
| `scenario:<id>` | `scenario.md` for `main`, else `scenarios/<id>.md` | scenario | none |
| `yoodli:<id>` | `yoodli/<id>.md` | scenario | `blueprint`, `brief`, `scenario:<id>`, `profile` |

**Levels.** `session['levels']` is empty for a plain training, or a sorted list drawn from `101`, `201`, `301`, `401`. In a levelled training every artifact from `blueprint` down exists once per level:

- its name is the base name with `@<level>`, as in `blueprint@301`, `scenario:main@301`, `yoodli:main@301`;
- its file is the base file inside the level's folder, as in `301/blueprint.md`, `301/scenarios/exec-cost.md`, `301/yoodli/exec-cost.md`;
- its inputs are the same-level artifacts. No artifact of one level is an input to another level.

`intake`, `research-plan` and `research` are never qualified. Artifact names are listed shared first, then level by level in ascending order, each level in the order of the table above. A plain training cannot become levelled; levels can be added to or removed from a levelled one. Saving a blueprint updates `session['sizing'][<level or "">]`.

`inputs(root, session, name)` returns one dictionary: each upstream artifact name mapped to the SHA-256 of its file (or `None` if missing), each `setting:<key>` mapped to its value, and `profile` mapped to the SHA-256 of `assets/profiles/yoodli.json`. This dictionary is what `built_from` and `approved.inputs` store.

The `research` input is the exception: it is a fingerprint of the whole bundle, the SHA-256 of the three hashes of the live report, the record `.harness-research/research.json` and the approved copy `research-report.md`. A change to any of the three therefore makes everything built from research stale (rows 7 to 9 of A7).

Two module-level paths in `workspace.py` are resolved from the script's own location: `SKILL_DIR`, the package the helper runs from, and `PROFILE`, the Yoodli profile inside it. Tests point them at temporary copies to exercise rows 15 and 37 of A7.

Scenario discovery, computed on every read, inside each level's folder (or the training directory for a plain training): `scenario.md` is `main`; `scenarios/<id>.md` where `<id>` matches `^[a-z0-9][a-z0-9-]{0,63}$`. Both `scenario.md` and `scenarios/main.md` present is a refusal. Other files under `scenarios/` are reported as ignored, and so is a top-level `scenario.md` or `scenarios/` in a levelled training. Artifact names are the fixed ones plus `scenario:<id>` and `yoodli:<id>` for every ID that is discovered or already recorded in the session, so a removed scenario stays visible.

`yoodli` is an optional stage: off unless `init --yoodli` or `skip yoodli --clear` turns it on, and its artifacts are listed only while it is on. Skip rule: while `yoodli` is on, `brief` and `scenario` cannot be skipped; `yoodli` can be turned on only when both are wanted.

### A3. Status and approval

```python
def _status(root, session, name, known):
    spec = artifact(root, session, name)
    if spec['stage'] in SKIPPABLE and spec['stage'] not in session['settings']['stages']:
        return 'skipped'
    if spec['stage'] in session['unavailable']:
        return 'unavailable'
    current = sha256_file(root / spec['file'])
    if current is None:
        return 'not-started'
    entry = session['artifacts'].get(name)
    if entry is None:
        return 'draft'
    if any(known[upstream] == 'stale' for upstream in spec['upstream']):
        return 'stale'
    if entry['built_from'] != inputs(root, session, name):
        return 'stale'
    approved = entry.get('approved')
    if (approved and approved['sha256'] == current
            and approved['inputs'] == entry['built_from']
            and (name != 'research' or research_intact(root, session))):
        return 'approved'
    return 'draft'
```

`research_intact` is true when the record `.harness-research/research.json` and the copy `research-report.md` both hash to what `session['research']` recorded at approval.

`save(root, name, source=None, built=False, coverage=None)`:

- `source` given: refuse for `research`; validate every input exists; snapshot the on-disk file to history; replace it atomically; record with inputs re-pinned.
- `built=True`: record the on-disk file with inputs re-pinned.
- neither: record the on-disk file and keep `built_from` (pin it only if there is no record yet).
- `coverage` (deck only): validate that every key is an objective in the blueprint and every value is a list of positive integers; store `{deck_sha256, blueprint_sha256, at, objectives}`.
- Saving the blueprint updates `modules` and `size`.

`approve(root, name, accept_stale=None)`:

1. Refuse if the artifact is skipped or unavailable, or its file is missing.
2. Refuse if any upstream artifact is neither approved nor skipped.
3. Record the on-disk content as a hand edit (history snapshot, new hash, inputs kept).
4. If `built_from` differs from the current inputs: refuse without a reason; with one, append `{at, artifact, decision: 'accepted-stale', from, to, reason}` to `decisions` and re-pin.
5. Set `approved = {sha256, inputs, at}`.
6. For `research`: require the record's `schema == 1` and `owner == 'harness-research'` (otherwise findings are `None` with a warning); store `session['research'] = {report_sha256, record_sha256, run}`; copy the report to `research-report.md`; store the findings index; warn about pending questions.

`export(root, name, file=None, unavailable=None)` applies to `document`, `brief` and `yoodli:<id>`. The default file is the source path with `.docx`. It stores `{file, source_sha256, sha256, at}` or `{unavailable: reason, at}`. Export state is `current`, `outdated` (the source hash or the export's own hash no longer matches), `missing` (no record, or the file is gone) or `unavailable`.

### A4. Command line

All commands print JSON. A refusal, malformed JSON, a missing or unreadable file and a permission error all print `{"error": "..."}` and exit 2. `--dir PATH` before the command selects another directory.

| Command | Flags |
| --- | --- |
| `init` | `--title T` (required), `--levels 101,301` (omit for a plain training), `--brief-kind product\|competitive` (default `product`), `--deck-target pptx\|google`, `--brand B`, `--approval chat\|page` (default `chat`) |
| `status` | none. Output adds `scenarios` (`found`, `ignored`) and each artifact's `export` state |
| `save ARTIFACT` | `--from FILE` or `--built` (mutually exclusive), `--coverage FILE` |
| `approve ARTIFACT` | `--accept-stale REASON` |
| `export ARTIFACT` | `--file PATH` or `--unavailable REASON` |
| `skip STAGE` | `--reason R`, `--unavailable`, `--clear` |
| `checkpoint` | `--stage`, `--level`, `--next`, `--question` or `--no-question`, `--gate ARTIFACT`, `--approval chat\|page`, `--deck-target`, `--brand`, `--brief-kind`, `--levels` or `--add-level` (levelled trainings only). It returns `review`, the review file of the artifact at the gate |
| `pin SKILL` | `--task`, `--runtime`, `--run`, `--level` (one `harness-slides` task per level) |
| `check` | `--complete`, `--all`. Exit 1 if any check failed; with `--complete`, exit 1 unless ready. Lists only the checks that did not pass unless `--all` is given |

`check` output:

```json
{
  "checks_passed": false,
  "ready": false,
  "blocking": ["document is draft", "document.coverage failed", "No scenario file found"],
  "limitations": ["deck unavailable: harness-slides is not installed"],
  "passed": 4,
  "checks": [{"check": "document.coverage", "status": "failed", "basis": "declared",
              "problems": ["O2 is not covered by any section."]}],
  "practice": {"exercised": ["O2", "O3"], "not_exercised": ["O1"]},
  "warnings": []
}
```

`status` returns one status per artifact as a flat map, the stages marked unavailable as `unavailable_stages`, and a `research` summary once research is approved: its approval time, run and the count of findings by status. Neither command returns the session record or its event log. `approve` also returns `failing_checks`, the checks failing at that moment.

A decision moves the training on. When `approve`, `accept` or `skip` finishes the step the training is at, or a later one, the training moves to the next step that still has work: the shared stages, every level's blueprint together, then each level's own stages, lowest level first, then the package. Skipped, unavailable and finished steps are passed over. `stage`, `level` and `next_step` are set, and the decision returns `said`, what was decided, beside `next_step`. A step with more to approve stays, and `next_step` names what is left. Approving an earlier artifact again moves nothing. `--levels` never drops a level with work in it; `--add-level` adds one, and a training past its blueprints goes back to the blueprint stage for it.

Readiness (spec 6.7):

- Every artifact of a wanted stage must be `approved`; otherwise `blocking` gets `<artifact> is <status>`.
- A wanted scenario stage with no scenario file is blocking.
- A failed check is blocking. A check that could not run is blocking, unless it belongs to a skipped or unavailable stage.
- A pending question is blocking.
- An artifact approved with `--accept-stale` is a limitation, with its reason.
- An `outdated` export is blocking. When the scenario stage is wanted, the brief's export must be `current`; if it is `unavailable`, that is a limitation reading "Yoodli handoff incomplete: no brief export"; if `missing`, it is blocking.
- Skipped and unavailable stages, and other `missing` or `unavailable` exports, are limitations.
- `ready` is true when `blocking` is empty.

### A5. Formats and checks

Every format has an example under `assets/examples/`. The example is the template the guidance links to and the fixture the tests read.

**Blueprint.** As revision 1, with three changes. In a levelled training the `## Frame` section has a line `Level: 301`, which must match the level of the folder; a mismatch or a missing line fails `blueprint.structure`. When two levels state the same objective, ignoring case and spacing, `check` adds a warning naming both. The assessment line is `- O1: Check: <question> | Observe: <what practice should show>`. The section `## Practice plan` replaces `## Interactive plan`; each line is `- <scenario-id>: <mode>. Objectives: O2, O3. <note>`, and the section is optional. Checks: `blueprint.structure`, `blueprint.objectives`, `blueprint.key-points`, `blueprint.citations`. In a levelled training every check name carries its level, as in `blueprint.structure@301` and `yoodli:main.fields@301`. A practice-plan line with an unknown mode or objective fails `blueprint.structure`. Carry over the parser and lint from revision 1 and drop the per-module mode requirement.

**Research plan.** `research-plan.items`: the plan is a JSON object with `purpose` `planning`, a known `scope`, no `input_files`, and 1 to 30 items, each with a unique lowercase ID and question text.

**Document.** As revision 1. The check is renamed `document.coverage` and its result carries `"basis": "declared"`.

**Brief.** Title `# Competitive brief: <title>` or `# Product brief: <title>`. Numbered sections, in order:

| # | Competitive | Product | Evidence section |
| --- | --- | --- | --- |
| 1 | Executive summary | Executive summary | no |
| 2 | Comparison | What it is and where it fits | yes |
| 3 | Differentiators | Capabilities | yes |
| 4 | Limitations | Limitations | yes |
| 5 | Qualification questions | Qualification questions | yes |
| 6 | Objections and responses | Objections and responses | yes |
| 7 | Unknowns | Unknowns | no |
| 8 | Sources | Sources | no |

An evidence section names its findings in `<!-- findings: licensing migration-effort -->` under its heading.

- `brief.sections`: every section for the kind is present, in order, and not empty.
- `brief.findings`: every evidence section names at least one finding; each exists in the findings index and is `supported`, except that section 6 may also name `contradicted` findings. `unavailable` when there is no findings index.

**Scenario.** Title `# Scenario: <name>`. Required sections: `## Situation`, `## Learner role`, `## AI role`, `## Opening`, `## Success criteria`. Optional: `## Mode`, `## Concerns and pushback`, `## Questions`, `## Constraints`, `## Session settings`. Success criteria are list items, numbered by their order from 1.

- `scenario:<id>.sections`: required sections present and not empty; at least one success criterion; `Mode`, if present, is one of the four modes.

**Yoodli scenario.** First line after the title: `<!-- scenario: <id> -->`. Headings and fenced `text` blocks as revision 1: `## Roleplay name`, `## Type`, `## Description`, `## Context`, `## Personas` with `### Persona N` and `#### Name`, `Role`, `Demeanor`, `Background`, `Behaviors`, `## Objections`, `## Goals` with `### Goal N` and `#### Name`, `Type`, `Explanation`, `Achieved`, `Missed`, then `## AI assets`, `## Knowledge-based goal source`, `## Settings`. Under each `### Goal N`, outside the blocks: `<!-- criterion: 2 -->` (required, one or more numbers) and `<!-- assesses: O3 -->` (optional).

- `yoodli:<id>.fields`: required fields present; every persona has all five fields; the type equals `profile.mode_types[mode]` for the scenario's mode; goal types are in the profile; no duplicate heading path; no unterminated fence.
- `yoodli:<id>.limits`: every limited field is within its limit, and every count the file states is the real one. The result carries `counts`.
- `yoodli:<id>.mapping`: every success criterion number in the scenario file appears in some goal's `criterion` comment; no goal names a criterion out of range; every `assesses` objective exists in the blueprint.

**Coverage and practice.**

- `deck.coverage`: `unavailable` unless a review is recorded and its `deck_sha256` and `blueprint_sha256` match the current files; then failed for any objective with no slides. Carries `"basis": "reviewed"`.
- `practice` (not a check): the objectives named by `assesses` comments across all Yoodli scenarios, and those not named. A `handle` objective that no scenario exercises adds a warning.

### A6. Yoodli profile

```json
{
  "schema": 1,
  "profile": "yoodli",
  "types": ["Custom", "Tutor", "Pitch", "Objection Handling", "Questionnaire", "Interview"],
  "mode_types": {"roleplay": "Objection Handling", "pitch": "Pitch", "tutor": "Tutor", "questionnaire": "Questionnaire"},
  "persona_fields": ["Name", "Role", "Demeanor", "Background", "Behaviors"],
  "persona_required_types": ["Objection Handling", "Pitch"],
  "goal_types": ["Binary", "Rated", "Compound", "Knowledge-Based", "Screenshare"],
  "prerequisites": [
    "Builder: a role that can create roleplays in the organisation",
    "Roleplay Agent: organisation access and the Conversational Roleplay feature"
  ],
  "roleplay_agent": {
    "creates_custom_goals": false,
    "files_max": 5,
    "urls_max": 1,
    "source": "https://support.yoodli.ai/en/articles/15960287-create-roleplays-with-roleplay-agent"
  },
  "limits": {
    "context_chars": {"value": 10000, "source": "https://support.yoodli.ai/en/articles/9048809-yoodli-release-notes", "retrieved": "2026-10-12", "verified": null}
  }
}
```

`limits` has an entry of the same shape (`value`, `source`, `retrieved`, `verified`) for `personas_max`, `goal_explanation_chars`, `goal_achieved_chars` and `goal_missed_chars`, with the sources in Appendix A of the spec. `verified` is the date a limit was confirmed in the live builder, `null` until then. The check functions take the profile as an argument, so tests pass both a profile with every limit verified and one with none. The "provisional" warning appears when any limit used is unverified.

Before writing the profile, re-read the Roleplay Agent and AI Assets pages cited in the review and record only what they state.

### A7. State-transition matrix

Each row is one test in `tests/test_workspace.py` or, where it names `check`, `tests/test_cli.py`. Rows that name the page are in `tests/test_desk.py`. "Approved chain" means intake, research-plan, research, blueprint and document built and approved in order.

| # | Given | When | Then |
| --- | --- | --- | --- |
| 1 | Approved chain | `blueprint.md` edited by hand | blueprint `draft`; document `stale` |
| 2 | Row 1, then blueprint approved | `save document --built`, bytes unchanged | document `draft`, not `approved` |
| 3 | Row 1, then blueprint approved | plain `save document` | document still `stale` |
| 4 | Row 1, then blueprint approved | `approve document` | refused |
| 5 | Row 1, then blueprint approved | `approve document --accept-stale R` | `approved`; decision holds old inputs, new inputs and R |
| 6 | Approved chain | intake edited and approved; `approve research-plan --accept-stale R` | plan `approved`; research `approved`; blueprint `stale` |
| 7 | Research approved | `research-report.md` edited | research `draft`; blueprint `stale` |
| 8 | Research approved | `.harness-research/research.json` changed | research `draft` |
| 9 | Research approved | live report changed | research `draft`; blueprint `stale` |
| 10 | Research record with `schema` 2 or another `owner` | `approve research` | findings `None`; warning returned |
| 11 | Deck approved | brand changed | deck `stale`; document and brief unchanged |
| 12 | Deck approved as `deck.pptx` | deck target set to `google` | deck `not-started` |
| 13 | Brief approved as product | brief kind set to `competitive` | brief `not-started` |
| 14 | `yoodli:main` approved | `scenario.md` edited | `scenario:main` `draft`; `yoodli:main` `stale`; document and brief unchanged |
| 15 | Two Yoodli scenarios approved | the profile file changes | both `stale`; nothing else changes |
| 16 | No scenario files | `scenarios/exec-cost.md` created | `scenario:exec-cost` `draft` and `yoodli:exec-cost` `not-started` are listed |
| 17 | `yoodli:exec-cost` approved | its scenario file deleted | scenario `not-started`; Yoodli `stale`; both still listed |
| 18 | `scenario.md` and `scenarios/main.md` both exist | `status` | refused as ambiguous |
| 19 | `scenarios/Draft Notes.md` and `notes.md` exist | `status` | the first is listed as ignored; neither is an artifact |
| 20 | Deck saved with coverage | deck replaced | `deck.coverage` `unavailable` |
| 21 | Deck saved with coverage | blueprint changed | `deck.coverage` `unavailable` |
| 22 | Coverage file names an unknown objective, or slide 0 | `save deck --coverage` | refused; nothing recorded |
| 23 | Document export recorded | `document.md` edited | export `outdated` |
| 24 | Export recorded | export file deleted | export `missing` |
| 25 | Brief export recorded unavailable, scenario wanted | `check` | limitation "Yoodli handoff incomplete"; not blocking |
| 26 | Blueprint with M1 and M2 saved | blueprint saved with M1 only | `modules` is `['m1']`; `size` is `lesson` |
| 27 | Document approved | `document.md` deleted | document `not-started`; `ready` false |
| 28 | Everything approved, stage `done` | an approved file edited | `ready` false |
| 29 | Yoodli on | `skip brief` or `skip scenario` | refused |
| 30 | Yoodli and brief skipped | `skip yoodli --clear` | refused until brief is restored |
| 31 | Deck marked unavailable, everything else approved | `check --complete` | `ready` true; deck listed under limitations |
| 32 | Blueprint only | `check` | `checks_passed` true; `ready` false; blocking names the missing artifacts |
| 33 | Lock held by a live process | any command that changes state | refused; record unchanged |
| 34 | Lock left by a process that no longer exists | a command that changes state | succeeds |
| 35 | `session.json` is not JSON, or lacks a required key | any command | `{"error": …}`, exit 2; file unchanged |
| 36 | A managed file is a symbolic link | `save` | refused |
| 37 | The directory is, or contains, the skill package the helper runs from | `init` | refused |
| 38 | A deliverable's name is already taken | `init` | refused, naming the files |
| 39 | Upstream is `draft` | `approve` | refused, naming the upstream artifact |
| 40 | Hand edit after a save | `approve` | edit recorded; `approved`; history holds both versions |
| 41 | A hand edit that was never saved | `save --from` | history holds the hand edit and the new version |
| 42 | Levels 101 and 301, both approved through the document | `301/blueprint.md` edited | `blueprint@301` `draft`; `document@301` `stale`; every 101 artifact unchanged |
| 43 | Levels 101, approved through the document | `checkpoint --levels 101,301` | the 301 artifacts are listed as `not-started`; every 101 artifact unchanged |
| 44 | Levels 101 and 301 approved through the brief | the research bundle changes and research is approved again; then `approve blueprint@101 --accept-stale R` and `approve brief@101 --accept-stale R` | `document@101` is `approved` again with no approval of its own; every 301 artifact below research is still `stale` |
| 45 | A plain training | `checkpoint --levels 101` or `--add-level 101` | refused |
| 46 | Any directory | `init --levels 101,501` | refused, naming the valid levels |
| 47 | Level 101 with `101/scenario.md` and `101/scenarios/exec-cost.md`, and a top-level `scenario.md` | `status` | `scenario:main@101` and `scenario:exec-cost@101` are listed; the top-level file is reported as ignored |
| 48 | Levels 101 and 301; 101 complete, 301 not started | `check --complete` | `ready` false; blocking names the 301 artifacts |
| 49 | Levels 101 and 301 whose blueprints state the same objective | `check` | a warning names both levels; no check fails |
| 50 | `301/blueprint.md` whose frame says `Level: 201` | `check` | `blueprint.structure@301` fails |
| 51 | Everything approved | `checkpoint --question Q` | `ready` false until `--no-question` |
| 52 | A stale artifact approved with `--accept-stale R` | `check` | limitations name the artifact and R |
| 53 | A research plan with 31 items, a bad ID, empty text or `input_files` | `check` | `research-plan.items` fails |
| 54 | `deck.pptx` that is not a PowerPoint file | `save deck` | refused; nothing recorded |
| 55 | Levels 101 and 201 | `pin harness-slides --level` for each | two pins, one per level |
| 56 | A Yoodli file stating "12 of 10,000 characters" for a 666-character field | `check` | the limits check fails |
| 57 | A levelled training with a top-level `scenarios/x.md` | `check` | a warning names the file |
| 58 | A new training | `init` without `--yoodli` | no Yoodli stage and no Yoodli artifacts |
| 59 | Yoodli off, a scenario file present | `skip yoodli --clear` | `yoodli:<id>` is listed as `not-started` |
| 60 | Yoodli off | `skip brief` while scenarios are wanted | allowed; scenario files do not need the brief |
| 61 | Yoodli off; everything else approved | `check --complete` | `ready` true; no Yoodli limitation; practice taken from the practice plan |
| 62 | Row 61 | `skip yoodli --clear` | `ready` false until each Yoodli scenario is built and approved |
| 63 | A stale document | its text is replaced from a file as an edit (a Google Docs pull) | history keeps the old version; the document is still `stale` |
| 64 | A training started with no copies asked for | everything approved | `exports` and `google_docs` are empty; `ready` true with no limitation |
| 65 | Copies do not include `word` | `export document` | refused, naming `checkpoint --copies`; nothing recorded |
| 66 | Yoodli on, no copies asked for | `status` | `exports` lists the brief and each Yoodli file, not the document |
| 67 | Copies include `google`; document and brief approved, no Doc made | `check --complete` | `ready` true; limitation "is not in a Google Doc" for each |
| 68 | Copies include `google`; document pushed | `document.md` changed and approved | `google_docs` says `outdated`; `check` blocks until it is pushed again |
| 69 | Document approved, no copies | `checkpoint --copies word`, then `--copies` alone | export `missing`, then not listed; no artifact changes status |
| 70 | Yoodli on, copies are `google` only | `status`; `export brief` | `exports` is empty; the export is refused |
| 71 | Row 70; everything approved, no Doc made | `check --complete` | blocked: the brief is not in a Google Doc and is the file to upload; the document is a limitation |
| 72 | Row 71 | the document and brief are pushed | `ready` true, no limitation, no `.docx` anywhere |
| 73 | Research saved, not approved | `status` | `research` gives the run and the counts from the live record, `approved_at` null; the same again once approved research changes |
| 74 | A new training, or a record written before approval could move | `init` without `--approval`; `status` | `approval` is `chat`; `gate` null; `requests` empty |
| 75 | Approval `chat` | `checkpoint --approval page` | `approval` is `page`; the event says who moved it |
| 76 | Approval `page` | `checkpoint --approval chat` from the command line; the same from the page | refused, naming the page; then `chat` |
| 77 | Approval `page`, a draft | `approve A`, with or without `--accept-stale` | refused, saying it is decided on the page and how the user opens it; nothing approved, no review written |
| 78 | Approval `page` | `approve intake` | approved, `by: chat` |
| 79 | Approval `page` | `skip S --reason R`; `skip S --clear` on a stage left out | refused; stages unchanged |
| 80 | Approval `page` | `skip S --unavailable --reason R`; `skip S --clear` on a stage still wanted | allowed: a report, not a decision |
| 81 | Approval `page` | a `revise` or `rebuild` recorded as made in chat | refused; no request |
| 82 | A draft at its gate | a decision with `by: page`; one from the command line | `by` is on the approval and in the event log: `page`, or `chat` |
| 83 | A stale artifact, its inputs approved | decision `accept` without a reason; with one | refused; `approved`, the reason and `by` kept |
| 84 | A draft | decision `revise` without a note; with one | refused; nothing approved, `requests` gains `{artifact, kind, note, at}` |
| 85 | A draft | decision `rebuild`, with or without a note | nothing approved; a request is opened |
| 86 | An open request | plain `save`, or an edit pulled from elsewhere; `save --built` or `--from` | still open; closed |
| 87 | An open request | the artifact is approved | closed |
| 88 | A question pending and a gate recorded | any decision | `pending_question` and `gate` cleared; `said` says what was decided, with a long note shortened; `next_step` is the same, unless the training moved on (row 99) |
| 89 | A draft at its gate | any decision, on the page or in chat | a dated entry in `reviews/<artifact>.md`, the note quoted; the file is made if missing and never written through a link |
| 90 | A draft at its gate on the page | decision `skip` with a reason | the artifact's stage is skipped for every level; without a reason, refused |
| 91 | A stage left out | decision `restore` on the page | the stage is wanted again |
| 92 | The page showed one version; the file then changed | `approve` or `accept` naming the version seen | refused; nothing approved |
| 93 | A draft | `checkpoint --gate A`; `checkpoint --no-question` | `status` reports `gate` A; then null |
| 94 | Any | `checkpoint --gate` naming something that is not an artifact | refused; nothing recorded |
| 95 | Everything approved | a change or a rebuild is asked for | `check --complete` is blocked until the request closes |
| 96 | Approval `page`, a draft at its gate | the page approves it | `approve` from the command line was refused; `status` shows `approved`, the gate and question cleared, `by: page` |
| 97 | Approval `chat` | any decision sent from the page | refused until approval is moved to the page |
| 98 | A question recorded and no gate | the page lists the training | the first artifact in pipeline order that is a draft or stale is at the gate; a recorded gate wins; with neither, nothing waits |
| 99 | A draft at the stage the training is at, or a later one | `approve` or `accept`, finishing its stage | the training moves to the next stage with work in it, passing over skipped, unavailable and finished ones; `next_step` says what to do there; `said` says what was decided |
| 100 | Two scenario files at the scenario stage | one approved | `stage` unchanged; `next_step` names the one still to approve |
| 101 | Levels 101 and 301 | each blueprint approved, then each of 101's stages, then 301's | the training stays at `blueprint` until both are approved, then moves through 101, then 301, then to `package` |
| 102 | The training at the brief | the document approved again after an edit | `stage` unchanged; `next_step` says what was decided and what comes next |
| 103 | The training at the deck | `skip deck`; then `skip deck --clear`; a request or another stage skipped | moves on to the scenarios; the rest move nothing |
| 104 | Row 99, or row 101 after the blueprints | the old guidance's `checkpoint --no-question --stage <next> --next "<step>"` | `status` unchanged |
| 105 | Level 101 with a file in `101/` | `checkpoint --levels 301` | refused, naming the file, `--add-level` and how to drop the level; record unchanged |
| 106 | Level 101 and 301, no file in `301/` | `checkpoint --levels 101,201` | levels are 101 and 201 |
| 107 | Levels 101 and 301 | `checkpoint --add-level 201` at research; `--add-level 401` at the package; `--levels` with `--add-level` | levels added, nothing else changes at research; at the package, the training goes back to `blueprint` at 401; refused |
| 108 | An artifact at the gate | `checkpoint --gate A` | returns `review`, its review file; null with no gate |
| 109 | Word copies wanted, pandoc on the path | `export A`; then the source is edited and `export A` again | pandoc is run with `--sandbox` into a scratch folder; the `.docx` is written beside the source and recorded; export `current` each time |
| 110 | Word copies wanted | `export A` with no pandoc, a pandoc that fails or never finishes, or one without `--sandbox` and a source that names a picture | export `unavailable`, with a plain reason; no `.docx` left behind. A `.docx` made another way is recorded instead, unless it is the copy already recorded against an older source |
| 111 | The home folder; a folder holding `skills/training-studio/SKILL.md`, or inside one | `init` | refused, each in words of its own; no record written |
| 112 | A stale artifact; a missing reason; an upstream not approved | `approve A`; `approve A --accept-stale` or `skip S` with no `--reason`; `approve A` | refused, naming what changed and `--accept-stale --reason`, then `--reason`, then the artifact to approve first. On the page the same refusals name no flag |
| 113 | No shared setup, or only partially saved choices | Launch Training Studio independently | Complete shared setup is shown; no provider job starts |
| 114 | Shared setup completed in any studio | Launch Training Studio | Existing workspace retained or shared location adopted; normal home opens without another setup |
| 115 | Companion at its minimum; a newer stable release is cached for its repository and meets its `>=` requirement | Check available versions, then explicitly update | Check offers the newer target without installing; update resolves and records its exact commit and checksum. Newer installed versions are preserved. Covered by `RequirementTests.test_newer_allowed_release_is_offered_without_installing_or_fetching` in `test_runner_upkeep.py` and the suite's `test_companion_versions.py`. |
| 116 | Shared Quick, Main and Complex model profiles | Start training, research, repair a deck, then change shared defaults | New work saves resolved profiles; research and ordinary review use Main, dedicated repair uses Complex, explicit work overrides remain single model, and settings changes leave the saved run unchanged. Covered by `ModelProfileTests` in `test_runner_engine.py`, `RepairTests.test_repair_uses_complex_but_independent_review_keeps_main`, and suite `test_model_profiles.py`. |
| 117 | Shared review level saved on new browser runs; legacy runs have none | Research, generate all levels, review direction, request changes, resume, review final materials | Balanced groups all levels at two revision-bound reviews; Automatic draft retains final review only; Step by step and legacy keep existing gates. Automatic acceptance preserves input checks and records review-policy provenance. Changed inputs reject old combined decisions. Covered by `test_review_levels.py` and suite `test_review_policy.py`. |

| 118 | New schema-2 research or explicit conversation import; original runs retain schema 1 | Investigate, independently review, approve research, consume stable finding IDs, then alter a capture | The purpose-led bundle must be complete with matching digest and file hashes. Drafts block authoring; changed evidence invalidates approval and downstream inputs. Stop preserves the draft without recording a failure. Covered by `test_synthesis_integration.py` and suite `test_research_contract.py`. |
| 120 | Contract research from supplied documents only | Start with up to 8 questions or none | Write the plan from the form with no planning job and no search words. Balanced and Automatic approve under the saved policy; Step by step waits at the plan. Public web still runs the plan worker. Covered by test_row_120 and FormPlanPolicyTests. |

| 121 | Approved file, its Doc edited elsewhere | Bring the Doc’s changes in | File holds the Doc’s text, not approved; downstream out of date. Covered by `PullTests.test_row_121_a_doc_edited_elsewhere_is_brought_in`. |
| 122 | File and Doc both changed | Bring in, then choose | Both kept until chosen; theirs saved as an edit or ours pushed with force; later changes refuse the old choice. Covered by `PullTests.test_row_122_both_changed_keeps_both`. |

| 123 | Grouped run with no review layout, direction approved | Survey after upgrade | Direction stays approved and old grouping is retained; briefs are not queued twice. Covered by `test_row_123_a_run_past_its_direction_review_keeps_it`. |

| 124 | Grouped run preparing or building a level | Offer Finish this level | Hidden during shared preparation; offered during building, with the final combined review visible and waiting for all levels. Covered by `test_row_124_finish_level_waits_for_building` and `test_combined_reviews_have_beads`. |
| 125 | Work continuing after a page decision | Reach the next person stop | Keep decision feedback during work, then retire it in the existing stop commit without adding audit noise or leaving files uncommitted. Covered by `test_row_125_reaching_the_next_stop_keeps_the_existing_audit_commit`. |
| 126 | A new training with a deck; one saved before its deck's delivery was asked | Start it from the form or `init`, then `checkpoint --delivery` before and after the first outline | Asked once: a talk (`live`) by default, or read on its own (`reading`); an older training reads as `reading` and keeps it; the brand is exported and the looks drawn for that delivery, and the outline check holds to it; a change after the first outline is refused. Covered by `DeliveryRowTests.test_row_126_delivery` and `test_row_126_delivery_is_chosen_once`. |
| 127 | A new deck; a slides tool with a design session | Start without and with "Walk through each slide's design" on the form; open a training saved before it | Off by default: the deck is approved on its outline and its look, with no design session, and needs only what a deck without one needs. On: the design session runs as before and needs its capabilities. An older training reads as off; a deck already written keeps what it was written with; a redesign the person asks for still draws from a design. Covered by `WalkthroughRowTests.test_row_127_walkthrough` and `WalkthroughTests` in `test_runner_deck.py`. |
| 128 | Synthesis research at its stop, decided on the page | Ask for changes with **Bring the evidence up to date** | The research request records `refresh`, with "Bring the evidence up to date." when no words were given; the research runs again with Harness Research's refresh section and new captures; any other artifact refuses it. Covered by `RefreshRequestTests.test_row_128_a_research_request_may_bring_the_evidence_up_to_date` and `test_bringing_the_research_up_to_date_reaches_the_author`. |
| 129 | A new training; your sites shared in the studios config, or none; a run saved before the choice | Start it from the form with Research from: your documents, your sites and/or the public web, a site ticked off or added for this training; change the shared list after the start | A new form has the public web on and your sites off. Nothing that applies is refused ("Choose where research may look: …") and nothing is made; a site added on the form is checked by the runner (`/api/research-site`) and saved nowhere; a site that is not a public https base address is refused naming it. The run pins `research_from` with the exact sites; the shared list is read and never written, and a later change to it leaves the run as it was. Documents wait for the person's documents as before. An older run's `supplied-only`, `public-web` or `both` reads as documents, the public web, or both; intake brought in from a conversation is read without regard to case, and sites it cannot read are refused, never widened to the web. The plan and research task name the allowed sites; Harness Research's `source_mode` is `mixed` for documents and sites, `public` for sites alone. Covered by `test_row_129_*` in `test_runner_research_sites.py`. |
| 130 | Research running with your sites on and the public web off | A worker saves a page outside the sites, through a redirect off them, on a lookalike host or a neighbouring path | Refused before anything is fetched, naming the sites (and where a redirect led); every hop is checked and sent without its fragment; pages under a site are saved; with the public web on too, any public page is; private addresses stay refused. The research stop says how many pages were outside the sites, naming them. Covered by `test_row_130_*` in `test_runner_research_sites.py` and `test_row_130_the_research_stop_names_the_sites_a_refused_page_was_outside` in `test_desk.py`. |
| 131 | Approved file, unchanged here, its Doc edited elsewhere | Look for changes in Google Docs | The copy shows Changed in Google Docs and offers Bring the Doc’s changes in; nothing else changes until it is brought in (row 121). Covered by `CheckTests.test_row_131_a_doc_edited_elsewhere_is_found_when_asked`. |
| 132 | Research planned or done, research reads documents | Add a document | Kept and listed as not read yet; research, approvals and readiness unchanged. Covered by `test_row_132_a_document_added_after_the_plan_is_kept_and_not_read`. |
| 133 | A document added after the research | Update the research | The research request records refresh and the added names; research and everything made from it are out of date and made again under the run's level (row 128). Covered by `test_row_133_updating_the_research_reads_the_added_documents`. |
| 134 | Review the finished materials, Balanced | Ask for changes to a learner guide | The first drafts approval stays; the guide and what is written from it are written again and come back to this review; a deck drawn again is accepted on its outline by the policy and stops at its own gate first. Covered by `test_row_134_a_final_change_keeps_the_first_drafts_approval`. |
| 135 | A copy whose Doc Google cannot find | Make a new Google Doc | The old link is removed and a new Doc is made from the file as it stands; the copy is made. Covered by `test_row_135_a_missing_doc_is_made_again`. |
| 136 | A conversation training brought in, its plan not started, documents in sources/ | Bring it in | Documents are marked all added with their count; research does not wait for them again. Covered by `test_row_136_a_brought_in_training_with_documents_does_not_wait_for_them`. |
| 137 | A new training; this computer's Harness Research has no synthesis, or cannot be read | Start it from the form | Refused with "Research needs Harness Research 1.0 or newer on this computer, and the one here cannot do it. Update Harness Research, then start again." Nothing is made: no folder, record, remembered training or commit, and the shared studios config is not written. A training brought in from a conversation is not a start and is not refused. Covered by `test_row_137_a_training_is_not_started_without_synthesis`. |
| 138 | A new training from the desk start | Start, with documents added before it | Run schema 4, `flow: 'desk'` in the run and the session, no `review_policy` or `review_layout` in either, and the shared studios config is not written even with the form's default chip; intake approved by the page; nothing is researched until the documents are all added; the start promises no stops. Covered by `DeskStartTests.test_row_138_a_desk_start_saves_no_review_level` and `test_a_desk_start_writes_no_shared_level`. |
| 139 | A desk run at any gate, outline or look | The engine reaches it | Continued with `by: 'desk'`, an event `continued-on-the-desk` and a receipt in `review_events` (`level: None`); no stop, no `review:*` step and no grave finding holding it; a deck's look is the brand's default, its receipt saying "You chose the brand's default look at the start: {name}."; `person_statuses` reads a plan or material so accepted as `draft`. A saved run keeps its gates and review screens at every level. Covered by `DeskWorkspaceTests.test_row_139_a_desk_acceptance_is_not_the_person_s`, `DeskRunTests.test_row_139_a_desk_training_reaches_its_end_with_no_stop`, `test_a_desk_deck_is_continued_in_the_default_look` and `DeskStartTests.test_saved_runs_keep_their_gates`. |
| 140 | A desk run with no Harness Research synthesis | Start it from the desk | Refused with row 137's sentence, the one refusal of every start: "Research needs Harness Research 1.0 or newer on this computer, and the one here cannot do it. Update Harness Research, then start again." Nothing is made: no folder, record, remembered training or commit. Covered by `DeskStartTests.test_row_140_a_desk_start_needs_synthesis`. |
| 141 | A part of a desk training's guide, brief or plan (Ready or a draft), with something built from the material | Typed into on the desk, against the revision the form saw | Saved into the material's file with `workspace.save(edit=True, via='save')` and the page's session on the event; what it was built from is unchanged; it is accepted on the desk again, so a Ready material reads `draft` in `person_statuses`; what is built from it is held. A form that saw an older revision of that part is refused with "This draft changed since you opened it. Reload to see the latest.", and Sources with "Sources is kept from the findings cited. Change the references in the text instead."; neither saves anything. Saves are not committed one by one: they are committed together as "edit <label> on the desk", at most once a minute while typing, and always first, in a commit of their own, before a job, a Mark ready, an Update, a Keep as it is, a Send or a Pause/Resume/Stop/Try again, and when the person leaves the desk (`/api/drafts/share`, which then shares under the team's share setting). A desk training whose index is written still has no driver, and the computer that drove it there may still change it on the desk; a teammate is refused with who ran it. A lone edit is committed after a minute and on close, even during another step, without committing unfinished worker output. Recovery preserves the original History, input pins, approval and save metadata, including the global order and duplicate occurrences of interleaved saves. Takeover sets aside unshared typing before ending local work. A finished desk saved before ownership was recorded needs an explicit Take over; no computer identity is inferred from an author name. Covered by `DeskTypingTests.test_row_141_a_typed_save_keeps_the_inputs_and_holds_what_is_below`, `test_typed_saves_are_committed_together`, `test_typing_is_committed_at_most_once_a_minute`, `test_edits_are_committed_before_a_job` and `test_a_locked_part_cannot_be_typed_in`, `test_recovery_keeps_each_edit_s_history_and_identity`, `test_interleaved_saves_keep_the_global_audit_order_across_flush_and_restart` and `test_typing_flushes_during_a_step_keep_half_made_output_out_of_commits` in `test_drafts.py`, and `DeskTeamTests.test_a_finished_desk_training_is_still_its_person_s`, `test_takeover_sets_aside_uncommitted_typing_with_its_history`, `test_takeover_during_a_step_keeps_typing_and_discards_only_worker_output`, `test_takeover_after_interleaved_saves_keeps_the_entire_audit` and `test_a_pr1_finished_training_requires_an_explicit_claim_and_keeps_local_edits` in `test_runner_page.py`. |
| 142 | A guide or brief on the desk; a section note, Write again, selection or whole-material note | Queue a change while no other desk change is active | The training runs one worker at a time after the start's current step. Each section is checked inside the whole material; Sources is never rewritten by a worker and only supplied reference numbers may be cited. A result lands only on unchanged part text, including selection edits; typing during the job is committed first and preserved. A landed edit saves through the desk with `via='rewrite'`, `revise-all` or `selection`, keeps the old text in History, records fact guards and names dropped references. A dropped reference may land while its unused Sources diagnostic still blocks readiness. Whole notes run sections in order; Stop lets the current section finish and leaves remaining sections unchanged. A second job is refused. Covered by `DraftJobTests.test_row_142_a_section_note_changes_only_its_section`, `test_a_result_for_a_changed_part_is_set_aside`, `test_a_selection_replaces_only_the_passage`, `test_a_cited_finding_joins_sources`, `test_the_whole_guide_note_goes_in_order_and_stops` and `test_one_desk_job_at_a_time_and_retry_route` in `test_draft_jobs.py`. |
| 143 | A part of a desk training's guide, brief or plan, with earlier versions in its History | Restore one | Its text is saved into the material's file through the same path as a save, the save event saying `via: 'restore'`; the text it replaced is then the newest version, labelled "Restored". History is read from the training's history files and save events, with no second store. Covered by `DeskHistoryTests.test_row_143_a_restore_is_a_version` and `test_the_desk_keeps_its_versions_in_the_history_files` in `test_drafts_history.py`. |
| 144 | A desk run with a deck; the guide typed into and accepted on the desk | The run carries on | The deck is held (`drafts.held` is `{'deck@101'}`): its steps, gates and copies are left out of the survey, so nothing of it is written or drawn again and no problem is raised; its card says "Built from an earlier guide." and a card whose own input is held says "Waiting for the plan to be updated or kept.". A saved run's deck is put back through its steps, as before. Covered by `DeskHoldTests.test_row_144_a_guide_edit_holds_the_deck`, `test_a_card_below_a_held_one_waits` and `test_saved_runs_still_remake`. |
| 145 | A held material on a desk run | Update, from the page | `run['drafts']['updates'][name]` records `{at, by: 'page', scope}` in a commit "update <label> from <what>"; the material is made again whole through its own steps and nothing else is; the update closes in the commit that lands it, and nothing is held. Refused with "This is up to date." for a name not held, with "A change is already being made to this training. Wait for it, or stop it." while an update or desk job is under way, while an input of its own is held ("Update or keep the level 101 blueprint first."), for a material no step of its own makes again (a scenario the person wrote, the research plan, the research: "{Label} is not made again by the studio. Keep it as it is, or change it yourself.", which can still be kept), for a scope before scoped updates exist, and on a saved run with the desk's refusal. Covered by `DeskHoldTests.test_row_145_update_remakes_only_what_was_held`, `test_an_update_waits_for_the_one_under_way`, `test_what_the_studio_does_not_make_again_is_only_kept`, `test_an_update_names_no_scope_yet`, `test_a_card_below_a_held_one_waits` and `test_saved_runs_still_remake`. |
| 146 | A held material | Keep as it is, with or without a reason | Inputs set to the current ones; `kept-as-is` decision; Ready stays Ready, and a material accepted on the desk is accepted there again, moving the stage on; readiness lists it as a limitation; refused while an input is held, with "This is up to date." for a material not out of date, and in a plain sentence for one with nothing to keep. From the page it commits "keep <label> as it is", nothing is held and no step of it runs. Covered by `DeskWorkspaceTests.test_row_146_keep_as_it_is_takes_the_new_inputs`, `test_keep_as_it_is_refuses_what_is_up_to_date`, `test_keep_as_it_is_says_plainly_there_is_nothing_to_keep`, `test_keeping_on_the_desk_moves_the_stage_on` and `DeskHoldTests.test_row_146_keep_as_it_is_from_the_page`. |
| 147 | A draft material on a desk run, nothing held, no grave finding | Mark ready with the hash it was shown / a changed hash | `workspace.decide(…, 'approve', by='page', seen=…)`: approved `by: 'page'`, `person_statuses` reads it `approved`, and a commit "mark <label> ready"; refused with "{Label} has changed since it was opened. Read the new version before deciding." when the hash differs, with nothing committed. A held material is refused with "{Label} is built from an earlier {what}. Update it or keep it as it is first." (a held material is never Ready, and readiness waits for it); a saved run refuses it with the desk's sentence. An edit afterwards is a draft again. On the desk a copy follows Mark ready, not the desk's acceptance (`drafts.copied`: Ready, or sent with Send to a Google Doc, which makes a draft's Doc at once). Covered by `DeskReadyTests.test_row_147_mark_ready_is_the_person_s_approval`, `test_a_held_material_is_not_marked_ready`, `test_mark_ready_is_the_desk_s_alone`, `DeskCopyTests.test_copies_follow_mark_ready_on_the_desk` and `MakingTests.test_on_the_desk_a_copy_follows_mark_ready_or_a_send`. |
| 148 | A level with several cards on the desk | Mark this level ready | Each card not Ready is marked in `drafts.ORDER` (blueprint, guide, brief, deck, scenarios, Yoodli layouts), each its own decide with its `seen`; it stops at the first that cannot be and names why (a deck with a grave finding or audit blocker open: "Settle what needs you on {label} before marking it ready."; a changed version: the core's sentence), returning `{'marked', 'stopped'}`, in one commit "mark level <level> ready". Covered by `DeskReadyTests.test_row_148_a_level_is_marked_ready_in_order` and `test_a_level_stops_at_a_material_that_changed_since_it_was_opened`. |
| 149 | A desk run whose materials were accepted on the desk | Survey, until every material is Ready | `package` is not due (left out of the survey) while any material is only the desk's draft, so no index is written and `assess.run_checks` (read from `person_statuses`) is not ready; once the last is marked ready, the index is written with no stop and the training is finished. A saved run writes its index as before. Covered by `DeskReadyTests.test_row_149_the_index_is_written_once_everything_is_ready`, `test_the_desk_s_acceptance_never_lets_the_package_run`, `test_saved_runs_still_write_their_index` and `DeskRunTests.test_row_139_a_desk_training_reaches_its_end_with_no_stop`. |
| 150 | A Training Studio desk run after research | Add documents after reading the price, then Update the research | Add the documents, widen public-web research to include them, and request a research refresh. Mark new or changed findings; each level’s plan and brief, and decks without guides, are held without remaking them. Active work or an unreadable document refuses the batch before research; existing documents stay and corrected filenames may be retried. Saved flows keep their existing document action. Covered by `SourceTests.test_row_150_a_source_added_after_research_updates_it`, `test_a_deck_without_a_guide_is_held_without_being_drawn`, the other `test_drafts_sources.py` tests, and `TrainingDeskScreenTests.test_add_a_source_says_its_price_first`. |
| 156 | A guide or brief with a Google Doc changed in Google, on the desk or saved before it | Bring the Doc's changes in, or choose the Doc's version when both changed | Saved as an edit as before (what it was built from unchanged), the save event saying `via: 'google'`; History's newest version is the text before it, labelled "Before Google's text"; the both-changed choice is as before. Covered by `SavedTrainingTests.test_row_156_a_google_pull_lands_as_a_version` in `test_drafts_history.py`. |
| 157 | A finished saved training, with nothing waiting | Open on the desk | The run and session gain `flow: 'desk'`; the original review policy and layout are recorded with the opening time. Page approvals and policy approvals covered by a matching page-approved final review stay Ready; other policy approvals become drafts. Scenarios have no practice inputs. Reopening writes nothing, and a waiting run is refused. Covered by `OpenSavedTrainingTests.test_row_157_a_finished_training_opens_on_the_desk_as_it_was`, `test_policy_approval_without_final_review_is_a_draft`, `test_a_training_still_waiting_cannot_be_opened`, `test_opening_twice_writes_nothing_more` and `test_an_opened_training_s_scenarios_are_not_held` in `test_drafts.py`. |
| 158 | A desk run; a scenario's practice plan line changed | Survey | That scenario held with "The plan for this practice changed"; a saved run's scenario is never held. Covered by `PracticePlanTests.test_row_158_a_desk_scenario_knows_its_practice_plan`, `test_a_saved_training_s_scenario_has_no_inputs` and `DeskHoldTests.test_row_158_the_practice_plan_holds_its_scenario`. |
| 159 | A desk training, and a saved one | The page asks a review route of the desk training (`/api/decide`, `/api/review`, `/api/outline`, `/api/look`, `GET /api/gate`), or a desk route of the saved one (`GET /api/drafts`, `/api/drafts/ready`, `level-ready`, `update`, `keep`, `send`) | 409 with "This training is on the desk. Change it there." and "This training is not on the desk. Use its own screen, or open it on the desk once it is finished." respectively; nothing is decided, written or committed, and each still answers its own routes. A desk training's research takes no document once its documents are all added (409 with the research's settled sentence); a saved one still keeps it unread (row 132). Covered by `DeskPageTests.test_row_159_desk_and_review_routes_refuse_each_other` and `test_a_desk_training_takes_no_document_after_its_research`. |
| 161 | A desk run's step | Fails three times / runs out of time three times | No gate: the run stops on the problem with its action (`retry`, or `more-time`), the session's gate unchanged, and what came before it still continued on the desk. Running out of money stops a desk run as it stops any run. Covered by `DeskRunTests.test_row_161_a_failed_step_on_the_desk_is_a_problem_not_a_gate`. |
| 162 | A desk run whose guide or brief cites a `[n]` that is not in Sources, or lists a Sources entry nothing cites; and a saved run with the same text | Check readiness, or mark everything ready | On the desk `document.citations@<level>` or `brief.citations@<level>` fails: the training is not ready and no index is written, and the desk's needs line names it in plain words ("The level 101 learner guide's references need fixing."). The saved run has no citations outcome and its readiness is unchanged. Covered by `DeskCitationTests.test_row_162_a_desk_training_s_references_hold_back_its_readiness` and `test_row_162_a_saved_training_with_the_same_text_is_unaffected`. |
| 163 | A desk change is queued and selected by the runner | Stop it before the runner starts the worker | The change remains stopped and no worker or rewrite save starts. Covered by `DraftJobTests.test_row_163_stop_after_queue_selection_prevents_worker_start`. |
| 164 | A person-owned scenario on a Training Studio desk | Ask to lay it out in the person's words | A layout job uses the existing scenario worker's person-owned branch, preserving the wording instruction and whole-file revision guard. Rewrite remains refused. Covered by `DraftJobTests.test_row_164_own_scenario_layout_uses_existing_words_path`. |
| 165 | A guide on the Training Studio desk | Write the whole guide again | One existing document worker rewrites the whole guide, guarded by the whole-file basis, saving via rewrite with History retained. This is separate from a whole note's sequential section jobs. Covered by `DraftJobTests.test_row_165_write_whole_guide_uses_one_document_job`. |
| 166 | A drawn deck on the Training Studio desk | Send a note on one slide, or Apply a review finding | Only its section is redrawn, with the other slides frozen; the deck is rendered and the changed slides reviewed, with findings kept as priced proposals and no automatic repair round. The deck is Draft. Skip records that a finding was read; a grave finding still holds Mark ready. An outdated form and a note on a section being drawn are refused. Covered by `SlideNoteTests.test_row_166_a_slide_note_redraws_its_section_only`, `test_review_finding_apply_makes_a_priced_note`, `test_skipping_a_grave_finding_still_blocks_ready`, `test_a_note_makes_a_ready_deck_a_draft_and_refuses_an_old_form`, `test_a_note_on_a_section_being_drawn_waits`, and `test_a_note_arriving_after_survey_is_handed_in_before_it_is_done` in `test_drafts_deck.py`. |
| 167 | A drawn deck on the Training Studio desk | Edit a slide's words | The outline and drawing change together when they pass the outline and section checks; the deck is rendered and saved without a worker, and returns to Draft. Words that do not fit save nothing. Words pinned by an approved design first require the separate explicit approval in row 169; no design approval is invented. Rendering or save failure keeps the previous deck, and concurrent changes are preserved. Covered by `SlideWordsTests.test_row_167_words_that_fit_are_patched_with_no_worker` and `test_words_that_do_not_fit_save_nothing`, and the design, failure and concurrent-edit tests in `JudgedSlideWordsTests`. |
| 168 | A drawn deck on the Training Studio desk | Edit speaker notes | The outline and drawing keep the same notes, and the deck is rendered and saved without a worker. Covered by `SlideWordsTests.test_row_168_speaker_notes_need_no_worker`. |
| 169 | A drawn deck whose approved design binds the edited words | Propose changed words, then answer the displayed design question | The proposal leaves all training files unchanged. Only a separate answer to the current Harness Slides question approves the changed design. Words that fit are patched and saved without a worker, using a new durable project made active with the deck save. Cancel, changed inputs, failed fit or failed render preserve the previous deck and project. Legacy projects stay at their original location; assets, later outline approvals and teammates without local drawings use the shared recorded project. Cover subtitles update approved focal copy through the same explicit question. Title edits derive copy from the edited outline so title fallbacks stay current and independent focal statements and subtitles remain unchanged; covered by `ApprovedWordsTests.test_row_169_title_fallback_then_first_subtitle_uses_current_approved_copy` and its content/subtitle cases. Covered by `ApprovedWordsTests.test_row_169_bound_title_requires_an_explicit_current_design_answer`, its cancellation/failure/concurrency tests, `ApprovedWordsPageTests`, `ApprovedWordsAssetTests`, and `PublicationTests`. |
| 170 | A deck on the Training Studio desk built from an earlier guide or plan | Update from its changed input | Only slides serving changed guide sections or changed objectives are worded again, and unchanged slides are copied in full; only affected sections are drawn when their approved design and drawing inputs remain unchanged. Changes to inputs before or during the outline job refresh its scope and discard an outdated result; the scope remains available until the deck is saved, including on retries after a drawing failure. Added or removed objectives require the whole outline. If no slide serves the changed guide sections, offer Keep as it is. Covered by `GuideUpdateTests.test_row_170_update_from_the_guide_rewords_only_the_slides_that_serve_it`, the glossary, objective and frozen-slide tests, and the desk preview test. |
| 171 | A drawn deck on the Training Studio desk | Try another look, then explicitly use a sampled look | Samples leave the chosen look and saved deck untouched; applying a current choice redraws every section and leaves a Draft. Covered by `SlideHistoryLookTests.test_row_171_another_look_redraws_the_whole_deck`. |
| 172 | A slide on the Training Studio desk | Save words or restore History | Prior words are shared under deck/versions; the drawing and picture remain local under work/deck/versions. Restore uses the kept drawing or the word chain without a worker, and becomes History itself. Safe IDs accepted by earlier desk versions retain History and speaker-note editing, covered by `DeckOutlineTests.test_row_172_saved_legacy_slide_ids_keep_history_and_notes`. Changed approved wording requires the exact current design question and a separate explicit person response before publication. Covered by `SlideHistoryLookTests.test_row_172_a_slide_keeps_its_words_and_drawing_as_versions` and `ApprovedHistoryTests`. |
| 173 | Requested slide words do not fit the existing drawing | Explicitly choose Redraw after the refusal | Publish the requested outline words and any explicitly approved design together, then redraw only the affected section. No redraw starts merely from a fit refusal; failure or cancellation of design approval leaves the active deck untouched. Covered by `SlideRestoreContinuationTests.test_row_173_explicit_redraw_installs_the_requested_words_before_the_composer`. |
| 174 | A slide's words on the Training Studio desk | Select a passage and choose Rephrase, Shorten, Expand, Fix, or Ask | Only that exact passage changes, concurrent edits are preserved, and History says Selection. Approval, cancellation and discard retire the pending selection result; a queued selection prevents conflicting Outline changes. Bound wording presents the actual design question and waits for a separate person response. Covered by `SlideSelectionTests` and `ApprovedReviewFixTests.test_selection_waits_for_the_actual_design_answer`, `DeckReviewLifecycleTests`, and `SelectionSettlementRoutesTests`. |
| 175 | A drawn deck on the Training Studio desk | Revise with a whole-deck note; Stop while a section is running | Progress counts sections. Stop cancels the active composer and waits for termination; only completed sections stay, waiting sections do not run, and a later explicit redraw still works. Covered by `SlideReviewFixTests.test_whole_deck_note_finishes_every_section` and `test_whole_deck_note_draws_all_sections_and_stop_keeps_the_rest`, plus `DeckActiveStopTests` with disposable subprocesses. |
| 176 | The Training Studio desk's Outline | Add slides with objectives and speaker notes, edit titles, move or remove slides, read the price, then Save | The preview identifies changed sections before saving; unchanged sections stay drawn. New IDs follow Harness Slides' 5–41-character outline rule, including generated collision suffixes; saved IDs remain readable. Objective coverage is validated, earlier slides enter History, and design-bound outlines await an explicit design answer. Covered by `DeckOutlineTests`, `ApprovedReviewFixTests.test_outline_waits_for_design_approval_before_saving`, and `TrainingDeskScreenTests.test_outline_prices_edits_and_preserves_them_when_saving_fails`, `DeckReviewConflictTests`, and `DeckReviewLifecycleTests.test_added_slide_waits_for_design_approval_and_keeps_existing_sections`. |
| 177 | Held materials on the Training Studio desk | Update everything below for one level, or Update every level from Sources | One priced chain runs in material order within each level, including materials newly held when an earlier update lands. Nothing starts before the explicit action; deck updates retain their slide scope and design approval rules. A failed update retains the chain for Retry. Covered by `UpdateChainTests.test_row_177_update_every_level_runs_level_by_level`, the single-level, scoped-deck and retry tests, and the bulk-update page journeys. |
| 178 | A Training Studio desk update chain is queued or working | Stop updates | Drop updates not yet started and leave those materials held. A worker already under way may finish; its landing does not enqueue further updates. Stop and worker admission share the files lock. Saved runs and teammate ownership retain their existing rules. Covered by `UpdateChainTests.test_row_178_stop_leaves_the_rest_held`, the worker and admission-race tests, and authenticated desk/teammate route tests. |
| 179 | A Training Studio desk deck change is queued, drawing, or paused between sections | Add a source | Refuse before writing documents or starting research until the deck change finishes or is stopped; completed and stopped changes allow the source. Covered by `SourceTests.test_row_179_a_paused_deck_change_refuses_a_source_until_finished` and `test_row_179_queued_deck_changes_refuse_before_worker_registration`. |
| 180 | A Training Studio desk research refresh is requested but not yet settled | Request a deck change | Refuse before committing edits, changing a deck, or starting a worker; Stop and cancellation remain available. Once research settles, normal held-material rules apply. Covered by `SourceTests.test_row_180_pending_source_refresh_refuses_deck_changes_before_writes` and the deck-first row 179 tests. |
| 181 | A Training Studio desk research refresh is pending, including after a failed attempt | Update a deck or update everything below | Refuse before committing pending edits or starting an update chain; after successful retry, ordinary held-material updates and Stop work. Covered by `SourceTests.test_row_181_research_refresh_blocks_deck_and_bulk_updates_until_retry`. |
| 182 | A saved training with a later document is opened on the Training Studio desk, with a deck change waiting or drawing | Update the research | Refuse before recording the research request until the deck change finishes or stops. Saved trainings not opened on the desk retain their existing admission. Covered by `SourceTests.test_row_182_opened_saved_training_blocks_research_during_deck_notes` and `test_row_182_saved_research_update_keeps_its_original_admission`. |
| 183 | A Training Studio desk has a queued deck update, bulk update, or desk job | Add a source or update the research | Both refuse before recording or starting research, including before worker registration; completion or Stop allows a later research request. Saved-flow admission is unchanged. Covered by the three `SourceTests.test_row_183_*` journeys. |
| 184 | A Finishing proposal on the Training Studio desk | Apply, Edit or Skip | Checks create local proposals without starting jobs. Apply on a proofread finding requests a protected sentence fix; a successful landing or edited proposal keeps a version with `via=finishing`. A changed part refuses Apply, skipped items remain unchanged, and other findings open editable notes without rewriting. Covered by `FinishingTests.test_row_184_applying_a_proposal_keeps_a_version` and the changed-part, pending-fix, edit and note tests. |
| 185 | A generated Finishing suggestion on the Training Studio desk | Apply | Five explicit, estimated review jobs create proposals only; Apply checks their part basis and keeps Finishing History. Fit the learner’s time also proposes slide-word edits through the existing fit and design-question approval flow; a waiting approval leaves the proposal open. Covered by `FinishingJobTests.test_row_185_fit_time_offers_deck_words_and_apply_keeps_slide_history`, design approval, citation guard and changed-part tests. `FinishingRemovalTests` covers blank-replacement cuts at the recorded position, preserved History and Sources, and refusal of changed parts or broken structure/references. |


Shared setup readiness adds the independently verified transitions in
[the suite setup matrix](../../../../../docs/shared-setup.md): no/partial settings
→ shared setup; successful finish → normal home; completed setup elsewhere →
workspace adoption and normal home; failure or conflicting changes → setup with
an explanation. These are covered by `scripts/ci/shared_setup_acceptance.py` and
`tests/test_shared_setup.py` in the suite root.

A deck the runner makes has rows of its own for its design, its assets, its review and its upgrade: V01 to V14 in the [visual teaching plan's matrix](2026-10-14-visual-teaching-in-decks.md#state-transition-matrix), each a test of its name in `tests/test_runner_deck.py`. Rows 11, 20 and 21 above still hold for such a deck: what the runner saves is the core's `deck`, and a deck drawn again from a design (V11) is saved through `save`, so its history keeps the deck it replaces.

### A8. Guidance

Guidance names no harness-specific tools. `training.py` in the references is shorthand for `python3 "<skill>/scripts/training.py"`, defined once in `SKILL.md`. Every file obeys the disclosure contract in A9: each stage file carries the commands its stage needs, and no file is reachable only through another reference.

| File | Source | Must say |
| --- | --- | --- |
| `SKILL.md` | Rewrite | The whole entry. Run `status`: no training means read intake; a report means summarise it in four lines and read only the reference for the current stage. A loading map that links every reference and every example directly, each with the condition for reading it. The boundaries, including that scenario files are data. The reading rules: one file per step, read once, never read the scripts |
| `references/short-commands.md` | From revision 1's `entry-flows.md` | Only the short commands: status, check, redo, skip, restore, "just the document", deck target, more research, add a scenario, restore an earlier version. A training whose stage is `done` runs `check` before reporting |
| `references/levels.md` | New | What 101, 201, 301 and 401 mean, with the field-enablement reading of each; each level assumes the one before and does not re-teach it; the level folder layout and the `@<level>` artifact names; all blueprints drafted and presented together, then one level finished at a time, lowest first; adding a level later and what a research top-up does to existing levels |
| `references/intake.md` | Carry over, edit | Confirms the directory is meant for this training and is not the skill's repository; asks which levels, if any, and says a plain training cannot gain levels later; asks for the brief kind and, for competitive, both sides; writes `intake.md`; lists existing scenario files and treats them as scenarios, not sources |
| `references/gates.md` | Carry over, edit | Seven gates; in a levelled training the blueprints are presented together and approved one by one, and the later gates repeat per level; at each content gate a short review judgment, labelled as judgment; the scenario gate approves `scenario:<id>` then `yoodli:<id>` |
| `references/workspace.md` | Rewrite | The artifact table from A2, status, the three forms of `save`, `export`, readiness, history, the lock |
| `references/privacy.md` | Carry over, edit | Authorisation stands for the same kind of action on the same destination; a new destination or wider scope needs asking |
| `references/stages/research-plan.md` | Carry over, edit | The sixth area, comparison, for a competitive brief, with dates and versions |
| `references/stages/research-handoff.md` | Carry over, edit | The `harness-research` prerequisite, checked here and nowhere earlier; resume the pinned task through that skill's resume entrypoint; a task is that skill's guidance and runtime record, not a new chat; the bundle; refreshing status before later gates; the top-up |
| `references/stages/blueprint.md` | Carry over, edit | `Observe:` in the assessment plan; the practice plan |
| `references/stages/document.md` | Carry over, edit | Declared coverage; `export document` |
| `references/stages/brief.md` | New | Both kinds and their sections; `findings` comments; weaknesses stated plainly; Unknowns never empty; dated sources; `export brief` |
| `references/stages/deck-handoff.md` | Carry over, edit | The `harness-slides` prerequisite, checked here; coverage bound to the deck and blueprint; re-review after any change |
| `references/stages/scenario.md` | New | Discovery; drafting when none exists; never overwriting a user's file; copying in a named file; conflicts explained; building the Yoodli output; the gate. Names the mode file and profile reference to read, which `SKILL.md` also links |
| `references/stages/package.md` | Carry over, edit | `check --complete`; files ready to upload from export state; limitations; coverage labelled by basis |
| `references/modes/*.md` | Carry over, edit | How to draft a scenario and its goals in each mode |
| `references/profiles/yoodli.md` | Rewrite | Field mapping from a scenario; goal comments; counts from `check`; Builder as the baseline; what the Roleplay Agent cannot do; prerequisites; the brief's export as the knowledge file; limits provisional until verified |

### A9. Disclosure contract

Spec 9.1. Budgets are estimated tokens: `(characters + 3) // 4`.

| Item | Budget |
| --- | --- |
| The `description` in `SKILL.md` frontmatter | 100 |
| `SKILL.md` | 1,000 |
| Any file under `references/` | 1,000 |
| Any file under `assets/examples/` | 1,200 |

`validate_package.py` defines the loading sets once, as `LOADING_SETS`, and `tests/test_disclosure.py` reads them from there:

| Set | Files | Budget |
| --- | --- | --- |
| `short-command` | `SKILL.md`, `references/short-commands.md` | 2,000 |
| `start` | `SKILL.md`, `references/intake.md` | 2,000 |
| `stage:<name>`, one per stage reference | `SKILL.md`, `references/stages/<name>.md`, `references/gates.md`, and that stage's example where it has one | 3,500 |
| `levelled-blueprint` | `SKILL.md`, `references/stages/blueprint.md`, `references/levels.md`, `references/gates.md`, `assets/examples/blueprint.md` | 4,000 |
| `scenario:<mode>`, one per mode | `SKILL.md`, `references/stages/scenario.md`, `references/modes/<mode>.md`, `references/profiles/yoodli.md`, `references/gates.md`, `assets/examples/scenario.md`, `assets/examples/yoodli.md` | 6,000 |

Structural rules the validator enforces:

- Every file under `references/` and `assets/examples/` is linked from `SKILL.md` itself.
- A reference links to a guidance or example file only if `SKILL.md` links to it too.
- No file exceeds its budget.

`validate_package.py --measure` prints each file's estimate, each loading set's total against its budget, and the library total.

Measured on the revision 1 prototype, for calibration: `SKILL.md` 639, the largest reference 923, the largest example 927, the heaviest set 5,620, the library 13,642. Entry then took two files and 1,289.

## Part B: Increments

### Increment 1: State contracts

**Files:** `tests/helpers.py`, `tests/test_workspace.py`, `skills/training-studio/scripts/workspace.py`

- [x] **Step 1: Test setup.** Write `tests/helpers.py`: the import path, `TrainingCase` with a temporary directory at `self.root`, `write`, `build(*names)` (write and `save --built`), `approved(*names)` (build then approve), a sample `harness-research` record and its findings index, and a stand-in profile file path. Carry over from revision 1 and rename `brief` to `intake`.
- [x] **Step 2: Record, lock and structured errors.** Write tests for rows 33 to 38 of A7, then `init`, `load` with structural validation, `store`, atomic write and the lock.
- [x] **Step 3: Artifact map, levels, discovery and inputs.** Write tests for rows 16 to 19, 26, 43 and 45 to 47, then `artifact`, `artifact_names`, `scenarios` and `inputs`, including the `@<level>` names and the research fingerprint.
- [x] **Step 4: Saves and history.** Write tests for rows 22, 40 and 41, then `snapshot`, `record` and `save`, including deck coverage validation.
- [x] **Step 5: Status.** Write tests for rows 1, 3, 11 to 15, 17 and 42, then `statuses` and `status` exactly as A3.
- [x] **Step 6: Approval.** Write tests for rows 2, 4 to 10, 39 and 44, then `approve` and `research_intact`.
- [x] **Step 7: Exports, skip, checkpoint, pin.** Write tests for rows 23, 24, 29 and 30, then `export`, `export_states`, `skip`, `checkpoint` and `pin`.

**Milestone.** Run `python3 -m unittest discover -s tests -p 'test_workspace.py' -v`. Every row of A7 that does not mention `check` passes. Then commit:

```bash
git add tests skills/training-studio/scripts/workspace.py
git commit -m "Add the workspace helper with lineage-bound approval"
```

### Increment 2: Formats and checks

**Files:** `skills/training-studio/assets/**`, `skills/training-studio/scripts/checks.py`, `tests/test_checks.py`

- [x] **Step 1: Examples.** Write the six example files for one coherent lesson. Use a competitive topic for `competitive-brief.md` and a single product for `product-brief.md`. Mark each as illustrative and unresearched. Carry over `blueprint.md` and `document.md` from revision 1 with the A5 changes.
- [x] **Step 2: Profile.** Re-read the two Yoodli pages named in A6, then write `assets/profiles/yoodli.json`.
- [x] **Step 3: Blueprint and document.** Carry over the revision 1 tests and code for the blueprint lint and document coverage. Apply the A5 changes and add tests for a practice-plan line with an unknown mode and with an unknown objective.
- [x] **Step 4: Brief.** Write tests, then `check_brief(text, kind, findings)`: both examples pass; a missing section, sections out of order, an empty Unknowns, an evidence section with no findings, an unknown finding, an unsupported finding, a `contradicted` finding allowed only in section 6, and `unavailable` with no findings index.
- [x] **Step 5: Scenario.** Write tests, then `parse_scenario(text)` and `check_scenario(text, label)`: the example passes; each required section missing; no success criteria; an unknown mode; mode defaults to `roleplay`.
- [x] **Step 6: Yoodli scenario.** Write tests, then `fenced_fields`, `check_yoodli(text, profile, scenario, objectives, label)`: the example passes with real counts; a persona with only a name; a duplicate heading; an unterminated fence; a type that does not match the mode; a criterion not carried; a criterion out of range; an unknown objective; each limit exceeded; the provisional warning present with an unverified profile and absent with a verified one.
- [x] **Step 7: Deck coverage and practice.** Write tests, then `deck_coverage` with its hash binding and `practice(blueprint, yoodli_texts)`, including the warning for an unexercised `handle` objective.

**Milestone.** Run `python3 -m unittest discover -s tests -p 'test_checks.py' -v`. All pass, and every example passes its own check. Then commit:

```bash
git add tests skills/training-studio/assets skills/training-studio/scripts/checks.py
git commit -m "Add format checks for the blueprint, brief, scenario and Yoodli output"
```

### Increment 3: Command line, readiness and guidance

**Files:** `skills/training-studio/scripts/training.py`, `skills/training-studio/scripts/validate_package.py`, `tests/test_cli.py`, `tests/test_package.py`, `tests/test_disclosure.py`, `docs/progressive-disclosure.md`, `skills/training-studio/SKILL.md`, `skills/training-studio/agents/openai.yaml`, `skills/training-studio/references/**`

- [x] **Step 1: Command line.** Write subprocess tests for each command in A4, the structured-error contract (row 35) and a two-module course fixture taken from intake to `ready`. Then write `training.py`. Carry over the argument parser from revision 1 and extend it.
- [x] **Step 2: Readiness.** Write tests for rows 20, 21, 25, 27, 28, 31, 32 and 48 to 50, then `readiness(...)` in `checks.py` and the `check` aggregation, exactly as A4.
- [x] **Step 3: Disclosure checks first.** Write `tests/test_disclosure.py` and the validator tests for A9: an oversized file, a reference not linked from `SKILL.md`, a reference linking to a file `SKILL.md` does not, and each loading set within budget. Then add `LOADING_SETS`, the budgets, the one-hop rule and `--measure` to `validate_package.py`. Carry over the rest of the validator and its tests from revision 1 and update the list of required files to A1 and A8.
- [x] **Step 4: Guidance.** Write every file in A8. For each "carry over" file, start from the revision 1 text and apply the listed changes. Keep each file to one stage or one concern, and run the validator after each file so a budget overrun is caught while the file is fresh. When a file is over budget, cut it; do not raise the budget.

**Milestone.** Run `python3 -m unittest discover -s tests -v` and `python3 skills/training-studio/scripts/validate_package.py`. All pass and the validator prints `ok`. Run it again with `--measure` and save the table as `docs/progressive-disclosure.md`. Compare the command table in `references/workspace.md` with `training.py --help`. Then commit:

```bash
git add tests skills/training-studio docs/progressive-disclosure.md
git commit -m "Add the command line, readiness report and guidance"
```

### Increment 4: Packaging and acceptance

**Files:** `README.md`, `AGENTS.md`, `docs/acceptance.md`

- [x] **Step 1: README and working agreements.** Write `README.md` with requirements, the link command for each supported harness (`~/.claude/skills/` for Claude Code, `~/.agents/skills/` for Codex), usage, and the layout of a training directory. Write `AGENTS.md`: no training content here, proportional verification, no dependencies, a format lives in four places, harness-neutral guidance, one file for Yoodli limits, research and decks are delegated.
- [x] **Step 2: Full automated verification.** Run `python3 -m unittest discover -s tests -v` and the validator. Confirm `git status` shows no caches or training bookkeeping. Commit.
- [ ] **Step 3: Install.** Ask the user to run the link command for the harness they will use, then confirm the linked validator prints `ok`.
- [ ] **Step 4: Live acceptance, with the user.** In directories outside this repository, on the harness the user intends to use: one lesson through all seven gates on a small public topic; a hand edit after the document gate; an interruption and resume at a pending gate; a scenario file the user writes themselves; a second training asked for as "just the document"; and one run with supplied documents only. Record each outcome in `docs/acceptance.md`, including refusals and failed checks. On the resume, also record which guidance files the assistant read, and compare them with the `stage:<name>` loading set in A9.
- [ ] **Step 5: Yoodli.** The user builds one roleplay in Yoodli's Builder from a `yoodli/<id>.md` and reports, field by field, whether the name matched and the value was accepted. Record it. Set `verified` on each limit that was confirmed and correct any that differed, changing the profile, its guidance and the example together.
- [ ] **Step 6: Record and commit.** List problems found and follow-ups in `docs/acceptance.md`, run the suite, and commit.

Steps 3 to 5 need the user and their accounts. Do not simulate them.

**Guidance dry run (done).** Before live acceptance, an independent agent followed the skill end to end with only the guidance, using stand-ins for research and the deck. Its 18 findings led to rows 51 to 57 of A7 and to the guidance changes listed in Appendix C of the spec. It does not replace steps 3 to 5.

## Spec coverage

| Spec section | Where |
| --- | --- |
| 4 Pipeline and rules | A2, A3, A8 |
| 5.1 Intake | A4 `init`, A8 `intake.md` |
| 5.2 Research plan | A8 `research-plan.md` |
| 5.3 Research handoff and bundle | A3 `approve`, A7 rows 7 to 10, A8 `research-handoff.md` |
| 6.1 Layout, start and resume | A7 rows 37 and 38, A8 `SKILL.md` and `intake.md` |
| 6.2 Session record | Increment 1 step 2 |
| 6.3 Artifacts, inputs, discovery, levels | A2, A7 rows 11 to 19 and 42 to 47 |
| 7.5 Levels | A2, A5, A7 rows 42 to 50, A8 `levels.md` |
| 6.4 Status and approval | A3, A7 rows 1 to 6, 39, 40 |
| 6.5 Exports | A3 `export`, A7 rows 23 to 25 and 64 to 72 |
| 6.6 History | A7 rows 40 and 41 |
| 6.7 Helper and readiness | A4, A7 rows 27, 28, 31, 32 |
| 6.8 Robustness | A7 rows 33 to 36 |
| 7 Blueprint | A5, Increment 2 step 3 |
| 8.1 Document | A5 |
| 8.2 Brief | A5, Increment 2 step 4, A8 `brief.md` |
| 8.3 Deck | A3 `save`, A5, A7 rows 20 to 22 |
| 8.4 Scenarios | A2, A5, A8 `scenario.md` |
| 8.5 Yoodli scenario | A5, A6, A8 `profiles/yoodli.md` |
| 8.6 Package | A4, A8 `package.md` |
| 9 Skill package | A1, A8, Increment 3 steps 3 and 4 |
| 9.1 Progressive disclosure | A4 compact output, A8, A9, Increment 3 step 3, Increment 4 step 4 |
| 10 Failure handling | A4, A7, A8 |
| 11 Testing and acceptance | A7, Increments 1 to 4 |
