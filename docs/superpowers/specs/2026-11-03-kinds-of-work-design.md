# A model and reasoning level for each kind of work

Status: approved 3 November 2026; implemented on `claude/work-kinds`.

## Problem

Shared settings offered three model profiles: Quick (classification and extraction),
Main (everything else) and Complex (dedicated repairs). Research, combining findings,
independent checks and writing all ran on Main, so research could not be made faster
without making the writing people read weaker. A Training Studio run spent $30.92 and
kept timing out on research at Opus 5.5 with high reasoning (#305 has the details).

A training also saves its choices when it starts, so lowering a setting never reached a
training that was already slow; the only way was to start over.

## Decisions

- **Six kinds of work, shared by every studio**, replacing Quick, Main and Complex.
  There are no per-studio overrides. One model mode stays as it was.
- **Starting points.** Quick at low; Research, Combining and Checking at medium; Writing
  and Fixing at high. All are on the shared model unless the person chooses another.
- **Changes apply to new work, plus a stopped run on request**, through Use the current
  model settings. A running job is never changed.

## The kinds

| Kind | What runs on it |
| --- | --- |
| Quick | Classification, extraction, Blog Studio's source classification, Presentation Studio's outline, and Training Studio's `scan`, which drafts a training outline quickly (#297) |
| Research | Research plans and questions, investigators, Blog Studio's research rounds and claims map, and find-text |
| Combining | Harness Research's author (`research:author-N`, `research-author`) and parallel synthesis (`research:synthesize-N`, `research-synthesize`) |
| Checking | The `review` and `research-review` purposes and `research:review-N`, plus Blog Studio's `finish-facts`, `finish-feedback`, `finish-geo` and `geo-report` |
| Writing | Everything not named above: outlines, blueprints, materials, drafts, slides, desk edits, finishing passes and ordinary repairs |
| Fixing | `deck-repair`, the `repair-escalated` purpose and Blog Studio's `repair` purpose |

`model_profiles.kind_of(product, step, purpose)` holds this table. Checking is tested
first, so a re-review after a repair (`build-repair:review` with purpose `review`) is
Checking, not Fixing.

## Settings

- **Format.** `studios-config.json` keeps `models.profiles`. It gains `research`,
  `combining`, `checking`, `writing` and `fixing` beside `quick`. Each still holds
  `selection`, `model` and `effort`.
- **Older names.** `main` and `complex` are still accepted and preserved, so studios not
  yet updated keep working. They are never rewritten.
- **Reasoning on the shared model.** A kind that uses the shared model may set a reasoning
  level of its own. Without one, it uses the shared reasoning.
- **Settings saved before the kinds** (`profiles_of`). The file is read, never rewritten.
  Until a kind is saved:
  - Quick keeps its own choice.
  - Writing takes Main's choice, and Fixing takes Complex's.
  - Research, Combining and Checking take Main's model at medium reasoning. Main's hidden
    reasoning on a shared-model profile was never used, so it is not adopted.

  The page lists which kinds are new, and a save keeps them. No choice the person saved
  is changed. This meets #305's requirement that existing saved profiles are untouched.
- **The Settings screen** shows six cards with plain descriptions. The reasoning menu
  shows unless the kind uses the assistant's default. Its first entry reads "Same as the
  shared reasoning" for a kind on the shared model. The Advanced summary counts the kinds
  that have their own model or reasoning.

## Routing

- **New work.** Blogs, decks and trainings save their choices as **routing policy 3**,
  keyed by kind.
- **Older work.** Work saved under policies 1 and 2 keeps its Quick, Main and Complex
  choices and routes exactly as before (`_legacy`). Unknown policies are still refused.
- **Receipts.** A job's receipt (`model_jobs`) names its kind as its `profile`.

## Use the current model settings (Training Studio)

`runner/model_settings.py` adds `GET` and `POST /api/training-models`.

- **When it is offered.** It is offered (`current_models` in the run view) when the
  training is the person's own, not in conversation, not finished, and not working.
  Unlike Change settings, it does not need a desk training started after #296.
- **Preview.** It lists each kind whose model or reasoning would change, before and after
  (`model_profiles.differences`). It also returns `expected`, a digest of the saved
  choices together with the choices the current settings give.
- **Save.**
  - It re-captures the choices from the training's own agent, model and effort, as at its
    start, and replaces the record's `model_profiles`.
  - It appends to `model_changes` and commits "use the current model settings: …".
  - It is refused when the preview is out of date, the run is working, or nothing changes.
  - It never touches the stop, so its own action (Try again, Give it more time, Carry on)
    stays.
- **The page.** The button sits beside Change settings on the stop card and in the desk
  toolbar. Its sheet lists the changes, says what is kept, and saves with **Use these
  models**.

Presentation Studio and Blog Studio have no stopped-run model refresh yet. They follow
the same core functions (`refreshed`, `differences`) when they get one.

## Testing

All tests use disposable settings and the scripted agent; nothing reaches a provider.

- **Root `test_model_profiles`.**
  - Older policies route as before.
  - Earlier settings carry over, and reading never writes.
  - A kind's own choice wins.
  - A kind on the shared model can set its own reasoning.
  - One model mode is unchanged.
  - Every studio's steps reach their kind.
  - Before and after for a stopped run.
  - Changes are validated and outdated saves refused.
- **Root `test_layout_pass`.** The Advanced summary.
- **Training Studio `test_model_settings`.**
  - The preview, the save and its commit.
  - The stop is kept.
  - A later settings change is offered again.
  - Out-of-date, working and nothing-to-change saves are refused.
  - It is offered on a training Change settings refuses.
  - The page route.
  - The sheet in the page harness.
- **Each studio's routing tests** now expect kinds: Blog Studio's `test_blog_runner`,
  Presentation Studio's `test_engine`, and Training Studio's `test_runner_deck`,
  `test_runner_page` and `test_desk`.
