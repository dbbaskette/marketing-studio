# Shared defaults, studio overrides and Marketing Studio settings

Status: design for approval. No production configuration or runner behavior is
changed by this design. The companion inventory and interactive prototype are
part of the proposal. Open the [interactive design preview](../../design/unified-settings-preview.html)
to inspect navigation, scopes, overrides, global limits and first-time setup.

## Outcome

Configure the studios once in Marketing Studio. Independently launched Blog
Studio, Presentation Studio and Training Studio use those choices without needing
Marketing Studio installed or running. A studio may override a specific default;
the person can see its effective value and where it came from. New runs snapshot
their resolved choices; saving defaults does not change active or existing work.

The interface covers every current setup preference and capability, while keeping
topic, audience, author voice, selected sources and approvals with the work itself.
See [the audited inventory](2026-10-16-unified-settings-inventory.md).

## Configuration decision

Keep `~/.config/studios-config.json`, its `STUDIOS_CONFIG` override and adjacent
lock. Do not create a second Marketing Studio config or copy defaults into native
config files. Extend the existing format additively: retain root `schema: 1` and
the existing person/assistant/team/local/brand/render/output/share keys. Add
versioned model profiles, global limits, optional preferences and studio sections. Older runtimes
can still read their legacy global fields, but cannot claim profile/override support.

Illustrative extension (existing global fields omitted):

```json
{
  "schema": 1,
  "models": {
    "schema": 1,
    "mode": "by_task",
    "profiles": {
      "quick": {"selection": "inherit"},
      "main": {"selection": "explicit", "model": "account-model-id", "effort": "medium"},
      "complex": {"selection": "provider_default"}
    }
  },
  "limits": {
    "step_seconds": 600,
    "project_dollars": 20,
    "parallel": 2,
    "retries": 2
  },
  "preferences": {
    "notify": false,
    "look_for_updates": true
  },
  "studios": {
    "blog": {
      "overrides": {},
      "writing": {"tone": "Clear, conversational and specific", "stop": "package"}
    },
    "presentation": {"overrides": {}},
    "training": {"overrides": {}}
  }
}
```

Actual model IDs come from the selected assistant's available catalog. The
example does not prescribe a provider, paid tier or a particular brand. An image
model is a separate, capability-gated preference and never reuses a text model ID
implicitly. Never store API keys, session tokens or OAuth credentials in this file.

### Resolution and persistence

Effective new-work preferences resolve in this order, highest priority first:

1. Explicit choices in the work's own intake/run record.
2. Studio override leaves in the shared file.
3. Global shared defaults.
4. The studio's documented built-in defaults for applicable settings.

An absent override means inherit. An allowed `null` means an explicit automatic
choice, not inheritance. The model `selection` value makes inherit, assistant
default, and explicit model distinct. Reset to shared removes override leaves;
it must not write a copy of the current global value. No settings-file export is
read as another authority or synchronized back.

The resolver returns values plus per-leaf source (`shared`, `studio`, `built_in`),
applicability and validation state. Native adapters translate canonical names
to their current formats (`project_dollars` to `deck_dollars` or
`training_dollars`). Limits are excluded from studio overrides: all runners consume
the global policy, and native limit controls are removed. Blog Studio's one-writer
workspace lock is an implementation invariant, not another editable limit.
Spending is a checkpoint against provider-reported cost, not a guaranteed prepaid
cap; a runner with unknown cost cannot claim dollar enforcement.

Write through one validated path-aware patch API under the existing lock. Extend
the current lossless writer with bounded nested objects and explicit leaf removal.
Keep unknown sections, formatting and unrelated values. Refuse symlink/invalid
settings, unsupported group versions and same-leaf conflicts from outdated forms.
Compare inherited dependencies when creating an override so an outdated form does
not silently pin a value after another studio changed it. Saves are atomic and
retrying an unchanged desired patch is a no-op. Keep permission mode 0600.

Native settings forms default to Save for this studio. Changing global settings is
an explicit Change shared defaults action. Both surfaces use the same resolver
and validation; a standalone studio bundles this code and the shared setup UI.

### Existing installations

Migrate in one resumable transaction with a local recovery record, outside Git.
Preserve the current shared values. Import valid legacy private values into studio
overrides only where the new section has no intentional value. Reconcile legacy
limit differences in the first central review, suggesting the
most restrictive currently configured valid values (including built-in effective
values where not saved). A 600-second legacy Blog Studio timeout therefore suggests
600 globally, rather than being retained as a lower-level override. The review
shows the affected studios before the policy is committed. Remove old private
limit keys only after successful migration, retain a private recovery record, and
refuse partial cleanup on conflict. Workspace-scoped Blog Studio settings
remain a higher-priority legacy workspace layer until an explicit migration is
confirmed for that workspace; they must not become global preferences for every
workspace. Do not try to recover private values already removed by a previous
successful migration. Never overwrite unreadable files or move content.

Settings compatibility is a capability, not inferred from a version label. The
home page flags older installed runners that cannot honor profiles/overrides and
offers an explicit update path. Saving does not install software. Existing run
records remain in single-model mode; their saved models and content choices do not
change as a side effect. Global limit tightening follows the safe-boundary policy
below.

## Models by task

Offer One model and By task. Single-model behavior remains the migration default.
Three shared profiles each select model and effort within the selected assistant:

| Profile | Typical tasks |
| --- | --- |
| Quick | Supplied-fact extraction, source classification and bounded wording changes |
| Main | Research, evidence synthesis, teaching design, drafting, slide construction and ordinary review |
| Complex | Conflicting evidence, difficult technical interpretation or diagrams, focused repairs still unresolved |

Use structured task purposes at existing job boundaries, not keyword matching or
an extra LLM call to choose a model. Ordinary checking/review uses Main; difficult
evidence can use Complex. Independent checking still requires a separate invocation.
Compiling, rendering, copying and packaging already approved output use no model.
Research workers inherit the resolved research job profile through the studio/host
adapter; the helper is not turned into a competing model runner.

Allow profile overrides per studio. Each profile binds to the effective assistant;
changing assistant invalidates incompatible model selections and requires review,
without discarding the saved selection silently. Filter reasoning choices by
model capability. Saved unavailable IDs remain visible and block affected work
with a repair action. Failed discovery leaves the rest of Settings usable. No
automatic expensive fallback or cross-assistant routing.

At run creation snapshot the agent, mode, fully resolved profiles, source/catalog,
policy version and origin of each choice. Blog Studio needs the same snapshot
guarantee already present in the other two runners. Jobs record route, reason,
attempt, requested model/effort and actual values when reported (otherwise unknown).
Escalation is scoped to a structured difficult task or unresolved semantic/design
defect and retains existing budgets, repair counters and cancellation boundaries.

This generalizes [issue 13](https://github.com/dbbaskette/marketing-studio/issues/13)
to all studios; the issue's presentation-only storage proposal is superseded by
shared profiles plus explicit studio overrides if this design is approved.

## One global limits policy

The global policy has maximum assistant-job duration, maximum simultaneous
assistant jobs across all studios on this computer, maximum automatic retries,
and a per-project reported-spending checkpoint. More permissive studio/work
settings cannot exceed it; there are no editable studio limit copies or overrides.
Internal stricter safety invariants (one writer, serialized Drive renders, bounded
repair loops) remain intact and are explained as capabilities rather than knobs.
Deterministic render helpers retain their operation-specific failure timeouts.

A small same-user cross-process lease coordinator enforces the assistant-job
concurrency limit across independently launched studios. Its private runtime
state is separate from the settings file and is never another configuration
source. Claim/release is atomic under its own lock; cancellation and verified dead
owners free slots, queue wait is not billed as execution time, and a live owner is
not evicted merely because a wall-clock lease looks old. Test crash recovery,
process identity reuse and simultaneous independent launches with disposable
processes. Native workspace/render locks remain in force.

Read the current global policy before dispatch. Tightened limits apply at the
next safe job boundary; do not mutate or interrupt a job already in flight as a
side effect of saving. Raising a limit does not silently expand a running work's
saved authorization: its snapshot remains a ceiling until explicitly reviewed.
Existing attempts and reported spend count toward the checkpoint; retries do not
reset them. The UI shows requested/used/unknown values rather than fabricating
cost. If cost is not reported, expose Cost unavailable and retain time/retry/job
limits; do not describe the spending checkpoint as enforced for that runner.

No daily account-wide budget, billing API, provider change or prepaid-cost
promise is introduced. Shared limits are enforced by the three existing studio
runners, not by directing the user to buy another service.

## Setup and capabilities

First launch in any studio offers the same short setup: You and your assistant,
Workspace, Brand and delivery. Optional advanced controls do not block a first
project. Completed shared setup bypasses repeated forms. The Marketing Studio
landing page remains a launcher with three studio cards and a compact readiness
summary, not a content dashboard.

Limits have one global policy page in Marketing Studio, mirrored by the common
standalone setup/settings surface when the umbrella app is absent. Studio pages
show the effective policy read-only with a Change global limits link. Native
private spending, timeout, retry and parallelism controls are removed. Ordinary
studio overrides still cover models, brand, delivery and supported preferences.

Settings navigation: General; Models; Workspace; Brand and delivery; Global limits;
Connections; Updates. A scope bar selects Shared defaults, Blog Studio,
Presentation Studio or Training Studio. On studio pages each setting shows Shared
or Custom, an explicit Customize action and Use shared to remove it. Common
settings are visually consistent; studio-only controls appear in a named section.
The effective value remains visible while inherited. No ambiguous global Save.

Connections centralizes installed assistant, Git, Google, research/slide runtime,
local renderer and artwork status. Distinguish Detected from signed-in/live-checked
and preserve Unknown. Check locally is separate from an explicit provider access
check. Google document access uses the existing gcloud/connector routes as supported
by each operation; do not add Gemini CLI or imply a gcloud token grants every API.
Artwork is optional, off by default and separate from Google document sign-in.
Credentials stay with existing providers. No preview/test action starts a paid job.

Updates shows suite and companion versions, available release information and
explicit install/update/rollback actions; no update occurs on save or launch.
Native runtime override paths and installation folders remain under Advanced.
Notifications and automatic release checks retain per-platform capabilities and
current user choices. Yoodli remains a training output option, not a fictitious
signed-in connection.

## Visual direction

Apply the macos-golden-gate-design skill across the existing web stack: one
integrated sidebar/content boundary and unified toolbar. Restrained translucent
material belongs on navigation, toolbar and transient surfaces. Forms, dense
settings, documents, reviews and ordinary lists use quiet opaque content planes.
Keep discrete studio launch cards and slide choices where the boundary identifies
an object; remove redundant floating frames, per-row shadows and pointer shimmer.

Use the shared UI kit's semantic light/dark tokens: neutral canvas/content,
subordinate chrome, hairline dividers, opaque text and a limited existing accent.
System fonts require no downloads. Controls have coordinated tighter radii,
44-pixel targets where practical, visible focus and explicit selection states.
Narrow layouts reflow rather than hide controls. Reduced transparency, increased
contrast and reduced motion retain the same hierarchy. The effect is Golden
Gate-inspired CSS, not a claim of native system material or physical refraction.

The companion prototype is an interactive, synthetic design preview. Its save,
connection and launch actions affect only in-memory demo state. It is deliberately
separate from production assets and is not a release payload. The same design
language is applied to the current production UI independently of the pending
configuration/routing changes.

## Acceptance

- One setup configures all applicable defaults; each independent studio can host it.
- All inventoried setup controls are either editable centrally, explicitly scoped,
  reported as capability status, or clearly retained as a per-project decision.
- An inherited default follows a later global save; a studio override does not;
  resetting it resumes inheritance without copying values.
- Global limits have one editable authority, no studio overrides or duplicate native
  controls, and apply through all native dispatchers with honest cost availability.
- All three actual dispatchers pass selected model/effort to their CLIs at job
  boundaries, preserve tool permissions, and snapshot/resume existing runs safely.
- Malformed settings, unavailable models, same-leaf conflicts and failed migrations
  preserve the original configuration and work; unrelated fields survive writes.
- Current workspaces, content, approvals, provider authentication and budgets remain
  governed by their native contracts. No install, publish or paid request occurs
  merely because defaults changed.
- The settings interface works at desktop and phone widths with keyboard access,
  dark mode, reduced motion/transparency, understandable applicability and sources.
