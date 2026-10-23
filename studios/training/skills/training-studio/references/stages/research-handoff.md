# Research handoff

Harness Research owns investigation, synthesis and independent review. If it is
missing, stop and point to https://github.com/dbbaskette/harness-research-skill.
Intake is settled: preserve audience, purpose, scope and source permission. With
sites under Source scope, search them first; save pages only from under them
unless the public web is chosen too, and then use it only for gaps.

## Fresh synthesis research

1. Follow the installed helper's synthesis workflow in `.studio-research/`.
   Pass the actual learner audience and training task in free-text `purpose`,
   separately from scope and source mode. Prioritize concept sequence,
   misconceptions and grounded examples. Research supplies evidence, not a course.
2. Save the connected report and authored brief. A separate invocation reviews
   their exact digest, evidence, coverage and usefulness. Run `synthesis verify`
   and inspect the saved report. Drafts and rejected reviews block authoring.
3. `training.py research-import --case .studio-research` preserves the owned case
   and copies its checked bundle to `research/`. The command records the report
   through the core and indexes stable schema-2 finding IDs for citation checks.
4. Present the normal research gate with source limitations and gaps. Independent
   helper review is not user approval. `training.py approve research` records the
   person's actual decision. Read `research/brief.md` and its evidence for the
   blueprint; retain conditions, counterfacts and unknowns.

Changed bundle bytes invalidate research and downstream inputs. Hash checks prove
saved integrity, not truth or live website currency. Refresh through the original
helper workflow, save a new dossier and obtain a new content-bound review.

Browser runs perform this handoff and use their saved shared review level. Do not
modify a page-driven training through conversation commands.

## Existing legacy research

Keep the original format, runtime and saved guidance. Installing a newer helper
does not convert an existing run.

1. Load Harness Research in this training's directory. Start a guidance task only
   on its first use; record `training.py pin harness-research --task <id>
   --runtime <path>`. On resume, continue its pinned task.
2. Hand over the approved plan: `node "<runtime>/scripts/harness-research.mjs"
   plan --project . --file .training-studio/research-plan.json`. Pin again with
   `--run <the returned run>`. Follow its guidance and record findings as you go.
3. Refresh its `status`, open its report and confirm findings were saved.
   `training.py save research --built` records the report. Present gate 2 using
   the helper's coverage, pending questions and document gaps.
4. `training.py approve research` records the live report, legacy record and
   approved copy. If the findings index is unavailable, report that citation
   checks are unavailable. Never edit `research-report.md` yourself.

On resume and before later gates, refresh legacy helper `status --project .`.
Changed evidence returns research to draft and invalidates downstream work.
For a research top-up, preserve existing question definitions in an extended
plan, save it through the core, and review the added questions. Let the pinned
helper carry unchanged findings; investigate the rest. Repeat the research
review, then rebuild affected blueprints and briefs.

Report blocked network or access honestly. Never describe incomplete research
as current. Then read the blueprint reference.
