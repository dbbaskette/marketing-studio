# Shared studio setup

Marketing Studio, Blog Studio, Presentation Studio and Training Studio read the
same settings file and use the same setup page. Completion means choices were
saved and the requested workspace preparation succeeded, not that provider sign-in
or every optional tool is available.

| Starting state | Action | Result | Verification |
| --- | --- | --- | --- |
| No settings or partial settings | Open any independent studio | Complete shared setup form; no provider job starts | `shared_setup_acceptance.journey` |
| Standalone setup open | Finish | Current studio opens its normal home; shared completion recorded | `shared_setup_acceptance.journey` |
| Setup complete in another studio | Open an unconfigured studio later | Shared workspace adopted, normal home opens | `shared_setup_acceptance.journey` |
| Completed global setup, older private defaults | Launch/migrate | Shared choices, including automatic defaults, win; private copies removed | `SharedSetupTests.test_native_runners_consume_live_shared_model_brand_and_preview_choices`, `ConfigTests.test_completed_shared_setup_keeps_empty_defaults_over_legacy_private_choices` |
| Existing workspace, new global root | Open again | Existing workspace retained | `SharedSetupTests.test_launch_adopts_local_defaults_once_and_preserves_existing_workspaces` |
| Invalid config or failed preparation | Finish | Error; no completion marker written | `SharedSetupTests.test_failed_workspace_setup_does_not_mark_global_setup_complete` |
| Another studio changes a setup choice during preparation | Finish | Ask to review settings again | `SharedSetupTests.test_concurrent_change_during_finish_requires_another_review` |
| Marketing Studio setup complete | Independently open any studio | Normal native home, shared model and preview defaults | `native_launch_acceptance.py`, `SharedSetupTests.test_native_runners_consume_live_shared_model_brand_and_preview_choices` |

Shared choices: person, assistant/model/reasoning, local work root or team
repository/branch/sharing, brand repository/release/identity/variant/installed skill,
delivery format, and slide preview method. Work already created retains its own
choices. Native workspace migration never moves existing content.

When no assistant is saved, setup uses the one Marketing Studio was installed for
(`target` in its `installation.json`). Without a single target it uses an installed
assistant, preferring Codex as the installer does, and otherwise Claude Code. The
setup snapshot offers this choice as `assistant_default`; finishing setup saves it.
`marketing-studio doctor` reports a problem when neither assistant is installed or
when the saved or default assistant is missing.

Default brand chooses a brand offered by the installed brand skill; default variant
chooses one of that brand's variants. For example, `tanzu` and `light` offer Tanzu
light branding when starting new work in each studio. These are starting choices,
not a requirement for every project. Existing blogs, presentations and trainings
keep their saved brand. The brand skill repository supplies templates and guidelines;
saving its address does not install or update the skill. Installation remains an
explicit action in a studio's settings. **Where is your brand skill?** offers
**Git repository** and **Installed skill folder** as separate, optional inputs.
A repository address does not require an installed folder. Leave the folder
blank for automatic discovery, or use it to select an existing installation.
The optional release tag is under **Brand skill release options**.

Optional studio controls retain built-in defaults: writing tone, time/spending
limits, parallel work, notifications and update checks. Research scope, author
voice, deck audience, training levels and similar content choices are selected
when starting work. Provider sign-in and installation remain explicit actions;
computer checks explain what is missing.

Run `scripts/ci/shared_setup_acceptance.py` for fresh independent-launch journeys
with disposable homes, synthetic Git identities and background provider/update
actions disabled. It is included in the full suite's acceptance gate.

## Models by task

In **Shared settings → You and your assistant → Models for your work**, choose
**One model** or **By task**. Each profile can inherit the shared model above,
use the assistant's default without model or reasoning flags, or select a model
and reasoning level from dropdowns. **Enter a model ID…** supports custom or
unlisted IDs. Saved IDs remain selectable when a catalog changes or cannot load.
Codex choices come from its read-only CLI model list. Claude Code uses the studios’
existing bundled model reference, with its source and date shown; that list does
not establish availability in your account. **Refresh models** retries a failed
listing without changing saved settings or starting a provider job.
Changing assistants requires reviewing the profiles before saving them.

| Profile | Tasks |
| --- | --- |
| Quick | Presentation Studio classification and extraction; Blog Studio source classification |
| Main | Research planning and questions, synthesis, teaching blueprints, writing, slide construction and ordinary independent review |
| Complex | Dedicated slide repairs in Presentation Studio and Training Studio; returning a Blog Studio review to its draft for repair |

Training Studio currently has no separate model-based extraction step. Its research
and writing use Main, and dedicated slide repairs use Complex. Compilation,
rendering, exporting and other deterministic steps do not start model jobs.
Retries keep the same profile. Review stays on Main even after a Complex repair.
Routing uses structured pipeline steps, never words in your prompt or another
model call. A model that fails is not replaced with another model.

New blogs, presentations and trainings save resolved profiles and the routing
policy in their run record. Later shared edits affect new work. An explicit
work-level assistant/model/reasoning choice that differs from the shared choice
uses that single model for the work. Older records retain their single-model
behavior. Job records distinguish requested choices from actual model/effort;
actual values remain unknown when the CLI does not report them.

Profiles live in the existing `studios-config.json`, under `models`, with schema 1,
mode `single` or `by_task`, assistant binding `agent`, and `profiles.quick`,
`profiles.main`, `profiles.complex`. Each contains `selection` (`inherit`,
`provider_default`, or `explicit`), and optional `model` and `effort`. Every studio
reads this same file; nested saves use its adjacent lock, preserve unrelated
settings, and reject conflicting stale edits.

## Review level

Choose the shared **Review level** under You and your assistant. New browser
runs in Blog Studio, Presentation Studio and Training Studio save this choice.

| Choice | Reviews |
| --- | --- |
| Balanced (default) | Research and the planned direction together, then finished work |
| Automatic draft | Finished work only |
| Step by step | Every existing stage |

Presentation Studio's direction review includes research, editable outline and a
rendered brand sample. Blog Studio includes research with the outline, and the
writing, independent review and requested export package at the final stop.
Training Studio groups all selected levels into one direction review with sample
slides, then one review of the completed documents, decks and scenarios.

Automatic continuation is recorded as policy acceptance, never as your personal
approval. Source scope, validation, visual review, bounded repairs, questions,
spending limits and blocking failures still apply. Publishing and sharing controls
remain explicit. Existing runs and adopted work retain their earlier review flow;
changing settings affects new work only. Conversations without a saved runner
policy continue to use their existing guidance.
