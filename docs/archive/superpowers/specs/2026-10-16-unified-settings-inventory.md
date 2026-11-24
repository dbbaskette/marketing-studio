# Unified setup inventory

Design audit, 2026-10-16. This inventories the current working tree; proposed
behavior is distinguished from existing support. No account, provider job or
installed settings were used in this audit.

## Existing consumers

| Setting or setup action | Current source / consumers | Proposed home and behavior |
| --- | --- | --- |
| Person's name | Shared `person.name`; Presentation Studio settings and Blog Studio author defaults; Training Studio reads shared setup | Shared defaults / General; author identity remains separate from Git identity |
| Assistant | Shared `assistant.agent`; all three studios | Shared defaults / Models; optional per-studio override |
| Model and reasoning | Shared `assistant.model/effort`; Presentation Studio and Training Studio snapshot these at run creation; Blog Studio worker/source analysis read shared assistant settings | Shared defaults / Models; snapshot all resolved choices for each new run, including Blog Studio |
| Models by task | Proposed in Marketing Studio issue 13; no implemented three-profile dispatcher | Models / One model or By task: Quick, Main, Complex; actual routing added to all dispatchers |
| Local or shared Git | Shared `local.root`, `team.repository/branch`, `share`; native workspace records | Workspace; shared defaults for new workspaces, optional per-studio defaults; an existing workspace is never relocated by saving preferences |
| Current workspace, content folder, branch binding | Native workspace metadata; Presentation Studio and Training Studio Git helpers; Blog Studio team/Hub helpers | Workspace status per studio; explicit native connect/change action, never a preference-file rewrite |
| Git identity and authentication | User's existing Git configuration and credential helpers | Connections / Git status; missing identity prompts an explicit scoped setup action; no credentials copied into preferences |
| Brand skill source and release | Shared `brand.repository/release`; native brand installers/upkeep | Brand / Installation options; explicit inspect/install/update actions through existing verified installers |
| Installed brand skill | Shared `brand.skill`; native discovery | Brand / Library; discover choices, display source and availability; manual path remains advanced |
| Brand and variant | Shared `brand.brand/variant`; native brand catalogs; per-work brand snapshots | Brand / Default brand and variant; catalog-backed choices where available, saved unavailable choices remain visible |
| Delivery | Shared `output`; Presentation Studio deck intake, Training Studio copies/deck intake, Blog Studio exports | Delivery / Native files or Google; show the actual documents/deck formats each studio produces |
| Slide preview renderer | Shared `render.previews`; Presentation Studio and Training Studio | Delivery / Match delivery, Local, Google Drive; Blog Studio shows Not applicable |
| Per-job timeout | Presentation Studio and Training Studio private `runner.json` default 900 seconds; Blog Studio workspace `.blog-run-settings.json` default 600 seconds | Global limits; reconcile existing effective values in one review and remove private limit controls after a successful migration |
| Per-project spending limit | Presentation Studio `deck_dollars`, Training Studio `training_dollars`, both default 20 | Global limits / Reported spending checkpoint; existing enforcement in those two studios, Blog Studio shows unavailable until cost reporting is integrated |
| Parallel work | Presentation Studio and Training Studio `parallel`, default 2 | Global limits; one cross-studio assistant-job cap; internal native bounds and Blog Studio one-writer lock remain |
| Automatic retry ceiling | Existing native attempt/repair counters, no unified preference | Global limits; one ceiling, existing stricter bounded repairs retained |
| Notifications | Presentation Studio and Training Studio `notify`, default false; native capability detection | Run controls; shared preference with per-studio capability/status; do not invent Blog Studio notification support |
| Update checks | Presentation Studio and Training Studio `look_for_updates`, default true | Updates; default and per-studio override; checking is distinct from installing |
| Suite/native/companion software installation | Suite installer, native installers, canonical pins, offline bundle metadata | Updates / Installed tools; explicit versioned install/update/rollback; no updates caused by saving settings |
| Blog tone | Blog Studio `.blog-run-settings.json` `tone` | Blog Studio defaults / Writing style, optional per-project override |
| Blog source scope | Blog Studio `research`: none, supplied-only, web-allowed | Blog Studio defaults / Sources; a default is an intake suggestion, not blanket permission to browse or send documents |
| Blog stop point | Blog Studio `stop`: outline, draft, review, package | Blog Studio defaults / Stop after; existing decision gates retained |
| Source analysis assistant | Blog Studio workspace `.curation.json`; shared assistant fallback; per-import analysis choice | Blog Studio defaults / Reference analysis; inherit or explicit assistant binding; disclose which provider receives readable text and retain per-import opt-out |
| Blog author voice, selected source records | Workspace profiles and pinned per-blog voice/source revisions | Remain content choices inside Blog Studio; configuration may hold a default profile reference only after validating the workspace and catalog |
| Google access | Native Google helpers, gcloud/assistant connector access depending on operation | Connections / Google; actual capability checks distinguish Drive, Docs and Slides; a saved preference is not proof of access |
| Local previews | LibreOffice, Poppler/image helpers; native checks | Connections / Slide previews; detect only, installation is explicit and optional |
| Image generation | Harness Slides image provider, separate model and credentials; companion version-dependent API | Connections / Artwork; default off, explicit provider/model preference only when an adapter advertises support; credentials stay in provider-owned storage, paid generation requires the work's own authorization |
| Research engine | Harness Research pin, runtime discovery, optional override environment variable | Connections / Research tools; version and capabilities; runtime override paths remain advanced developer diagnostics |
| Training outputs and levels | Training Studio intake: levels, brief kind, deck target, copies, scenarios/Yoodli | Training Studio defaults may prefill existing supported intake fields; audience/topic/levels/source scope and deliverables stay reviewable per training; no Yoodli account integration invented |
| Presentation audience, slide count, new/existing deck | Presentation Studio intake | Per-deck content choices; optional saved intake presets are future content work, not mandatory setup |
| Writing/training/deck approvals | Native run state and gates | Stay inside each native workflow; no setting bypasses approval, spend boundaries or research scope |

## Code anchors

- Storage and first-run setup: `core/studio_core/studios_config.py`,
  `preferences.py`, `onboarding.py`, `workspace_setup.py`.
- Presentation Studio: `studios/presentation/runner/settings.py`, `setup.py`,
  `decks.py`, `jobs.py`, `agents.py`, `steps/`.
- Training Studio: `studios/training/runner/settings.py`, `setup.py`,
  `pipeline.py`, `engine.py`, `agents.py`, `research.py`.
- Blog Studio: `studios/blog/skills/blog-studio/scripts/blog_runner.py`,
  `blog_worker.py`, `source_curator.py`, `studios_config.py`, `brand_skill.py`,
  `management.py`, `team_workspace.py`, `hub_workspace.py`.
- Installed-tool checks: `marketing_studio/computer.py`, native upkeep,
  `pins/companions.json`, `pins/runtimes.json`.

## Main reconciliation findings

The shared file already exists. Current native saves often change global values
implicitly; they do not implement an inheritance/override interface. The writer
accepts a shallow group of scalar leaves, so nested profiles and overrides need
a deliberately extended, locked path-patch API. Copying effective values into three
private files would lose the distinction between inheritance and an override.

The three runners do not have the same controls. Blog Studio's authoring and
analysis jobs also need a resolved model passed into their existing adapters;
adding form fields alone would not provide stage-based routing. Model selection
belongs to the studio's dispatcher. Harness Research/Slides remain the research
and slide engines; the settings work does not duplicate their execution logic.
