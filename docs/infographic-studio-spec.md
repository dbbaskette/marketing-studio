# Infographic Studio specification

**Status:** proposed direction, ready for product review; not implemented

**Date:** 2026-10-28

**Scope:** a fourth independently runnable studio within Marketing Studio

The [implementation plan](infographic-studio-implementation-plan.md) defines the
delivery gates, task dependencies, acceptance criteria, and GitHub tracking.
Track progress in [the implementation roadmap](https://github.com/dbbaskette/marketing-studio/issues/136),
with eight epics and 32 actionable tasks.

## Product promise

Give Infographic Studio the information, tell it what matters or ask it to suggest
the story, and receive one clear, branded page that communicates the key ideas.
The page can explain concepts and relationships as well as show numerical data.

The central interaction is: **Add information → Choose the story → Review the page
→ Export.** Users can supply a precise direction, request suggestions, or combine
both. Design expertise and a finished outline are not prerequisites.

## First release

The first release creates one static infographic at a time. It includes source
intake, story suggestions, a choice of visual approach, a rendered draft, targeted
revisions, image generation and editing, source checking, and local exports. It runs independently and opens
from Marketing Studio with the shared settings already available.

Multi-page documents, animated graphics, a general drag-and-drop design editor,
automatic publication, and external design-platform synchronization are deferred.
An infographic can be made from a process or concept without numerical data.

## Required assistant and image generation

Infographic Studio requires one of these two configurations:

| Configuration | Planning and revision | Image generation and editing | Additional credential |
| --- | --- | --- | --- |
| Codex | Codex | Codex's built-in image generation | No separate image-generation API key for this route; Codex must be signed in and have access to the image tool. |
| Claude Code with Gemini | Claude Code | An image-capable Gemini model through the Gemini API | A Gemini API key with access to the configured image model, plus Claude Code sign-in. |

Claude Code alone does not meet this studio's image-generation requirement.
Gemini supplies images rather than replacing Claude Code as the assistant. The
shared assistant choice determines the route; do not ask Codex users for a Gemini
key or silently switch providers. Image generation is part of the first release,
even when an individual infographic can be explained entirely with vector shapes.

Setup and the computer check show the selected assistant, image provider, and
whether the required credential and tool capability are available. Installing a
CLI or finding a Gemini key does not establish access to an image-capable model.
Check the actual execution path before starting a build, and explain missing
sign-in, missing key, unsupported image capability, or provider refusal separately.
Users can save a brief while setup is incomplete; starting a build requires a
supported configuration. An unavailable provider leaves the last good revision
intact and offers retry or an explicit configuration change.

For the first release, the server reads `GEMINI_API_KEY` from its launch environment.
Settings shows only whether it is configured and how to configure it. Never store
the value in `studios-config.json`, a project, Git, browser storage, prompts, or
logs; only the server-side Gemini adapter receives it. Record the image model and
non-secret configuration, not the credential. Gemini API usage is separate from
Claude Code usage; show that distinction before the first generation.

Starting or revising a graphic authorizes the necessary image-provider calls for
that action. Opening setup, viewing a preview, and automated verification never
generate a test image. An optional live connection check is a separate explicit
action and must disclose any generation or charge before it runs.

Current capability references: [official OpenAI image-generation documentation](https://learn.chatgpt.com/docs/image-generation),
[Gemini image generation](https://ai.google.dev/gemini-api/docs/image-generation),
and [Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key).
These document provider capabilities; the installed Infographic Studio execution
path must still demonstrate generation and editing during implementation.

## Inputs

The new-infographic form has three steps. Only a working title, some usable
information, and a direction choice are required to start. Audience and output
defaults are visible and editable.

| Step | Fields | Behavior |
| --- | --- | --- |
| 1. Add information | Working title; pasted notes or text; optional Markdown, text, or CSV files | Keep the original source and a captured revision. CSV intake previews column names, units, and selected rows before use. |
| 2. Set the direction | Audience; purpose; desired takeaway; must-show ideas or facts; things to leave out; exact wording to preserve | Choose **I know what to show**, **Suggest the story**, or **Build on my ideas**. A goal does not count as evidence. |
| 3. Choose the page | Page size; brand and variant; optional visual preference | Default to A4 portrait. Offer US Letter portrait and 1080 × 1350 px digital portrait. Show the intended viewing size. |

Optional visual preferences are comparison, process, timeline, key numbers,
concept map, or **Recommend one**. These are ways to communicate, not styles the
user must understand in advance. Brand choices come from the configured brand
skill; Infographic Studio does not hard-code an organization or its assets.

PDF, Word, Google Docs, URLs, and importing another studio's artifact are follow-up
intake adapters. Unsupported files are identified before starting work, with a
suggestion to supply text or CSV. No document is silently treated as fully read.

The initial release uses supplied information only. URLs in pasted text are
references, not permission to fetch. Optional public research comes later through
the [shared synthesis contract](research-synthesis.md), with an explicit source
permission and the infographic's actual purpose and audience.

## Choosing the story

Infographic Studio first extracts candidate ideas, facts, comparisons, steps, and
relationships, with source locations. It distinguishes supplied assertions from
independently corroborated facts. It surfaces contradictory values, missing
units, unclear dates, and qualifications that would change the takeaway.

| Direction | What happens |
| --- | --- |
| I know what to show | Turn the requested content into one proposed story and layout. Point out gaps or crowding; do not replace the user's message silently. |
| Suggest the story | Offer up to three distinct, evidence-supported approaches, each with a thumbnail, takeaway, included ideas, and a short reason for the visual form. |
| Build on my ideas | Preserve the must-show content and offer up to three ways to organize it, with optional additions clearly identified. |

Suggestions might emphasize a comparison, the sequence of a process, or how
concepts connect. They must offer different explanations, rather than the same
content in three color schemes. If the material supports only one useful
approach, show one and explain why. Do not invent data to fill a template.

The story review shows the headline, one-sentence takeaway, planned visual blocks,
supporting facts, qualifications, and anything omitted. The user can edit the
content, choose an approach, or ask for another suggestion before building.

Default content budget: one main takeaway, three to five primary blocks, and
roughly 150–250 visible words including labels and the source footer. This is a
planning target, not a quota. If required material will not fit legibly, ask which
items to combine or remove; never silently drop a must-show item or shrink all
text. A smaller digital canvas may need a shorter story.

## Visual composition

The page has a clear headline, a dominant visual explanation, and a compact source
footer where factual claims require one. A subtitle, key takeaway, or call to
action appears only when it helps the requested purpose. Every page has an
intentional reading order and enough space around its main ideas.

| Information relationship | Preferred visual forms |
| --- | --- |
| Compare categories or options | Aligned comparison, labeled bars, before-and-after |
| Explain a sequence | Numbered process, flow, timeline with supplied dates |
| Emphasize a few measurements | Directly labeled numbers with context and units |
| Show a whole and its parts | Proportional composition when the values support it |
| Explain structure or relationships | Hierarchy, labeled concept map, system diagram |
| Explain an idea without measurements | Annotated illustration or conceptual explainer |

Mixed pages are allowed, with one dominant explanation rather than a collection of
unrelated widgets. Decorative icons must not imply quantities or relationships.
Charts retain units, baselines, dates, denominators, and relevant uncertainty;
differences in units or periods are resolved before comparison. Derived values
store the calculation and its source operands.

**Rendering decision:** retain text, values, chart marks, and connectors as
structured elements. Generate an editable SVG from a validated scene description.
Generated artwork is a first-class part of composition, using the required Codex
or Claude Code with Gemini route. Keep generated assets separate from precise
labels, values, and charts so factual corrections remain possible without
regenerating an entire page. The image adapter supports both initial generation
and edits guided by the previous asset, the chosen brand, and the user's request.

This makes individual corrections possible and gives checks access to the actual
content and geometry. The complete page is never flattened into an image before
review. A raster export remains available for sharing.

## Image brief and generation handoff

**Claude Code acts as the art director; Gemini renders its instructions.** After
story selection, Claude Code must author an extremely specific description of the
image it wants. A generic instruction such as "make an infographic about this"
does not meet the handoff contract. Codex prepares the same explicit brief before
using its built-in image tool, so either route records the visual intent.

The image brief translates the selected story into a concrete page composition
and a self-contained instruction for each generated asset. It specifies:

| Detail | Required description |
| --- | --- |
| Communication goal | Audience, the single takeaway, and what the reader should notice first, second, and third. |
| Canvas | Exact output dimensions, aspect ratio, orientation, background or transparency, safe margins, and crop behavior. |
| Composition | Named regions with normalized bounds, relative sizes, alignment, spacing, focal point, reading order, and areas reserved for text and charts. |
| Subjects and meaning | Every required object, its count, placement, scale, appearance, and relationship to other objects; arrow direction and the meaning of each connection. |
| Art direction | Illustration style, perspective, line weight, shape language, texture, lighting, level of detail, and visual density. Specify flat design explicitly when lighting or perspective is inappropriate. |
| Brand | Resolved color values and their roles, permitted visual motifs, supplied asset identities, and placement constraints. A brand name alone is insufficient instruction. |
| Text and data | Exact approved strings, values, units, and labels; typography hierarchy and placement; which elements the compositor will add and which, if any, belong inside the generated asset. |
| References | Only the selected reference assets, each with a stated role: style, subject, composition, or a previous image to edit. Supply the actual assets, not inaccessible local paths. |
| Exclusions | Objects, extra labels, invented metrics, decorative elements, visual implications, and brand changes that must not appear. |
| Acceptance | Observable requirements for judging the result, linked to required ideas and scene elements. Identify what must remain unchanged during an edit. |

The brief is precise about the intended result without claiming that a generative
model will honor pixel coordinates exactly. Critical positions, labels, numeric
encodings, and final page dimensions remain the compositor's responsibility.
An artwork-only prompt explicitly requests no text or chart marks and reserves
the regions where those elements will be placed. If a visual choice is still
unspecified, Claude Code resolves it consistently with the selected story and
brand before submitting the request; Gemini is not asked to decide the story.

Save both a structured `image-brief.json` and the exact provider-ready prompt for
each attempt in the private project workspace. Bind them to the approved story,
scene revision, brand revision, and reference-asset hashes. The provider request
must be understandable without the prior conversation, repository access, or a
reference to "the document above." Include only the factual context and assets
needed to render that image, never credentials or unrelated source material.

Before generation, validate that required objects and relationships are accounted
for, text and values match the approved story, bounds fit the canvas, and the
artwork instructions agree with the compositor's reserved regions. The user can
inspect the image brief from the story or page review, but writing or separately
approving a technical prompt is not an additional required step.

After generation, the directing assistant inspects the actual returned image and
the composed page against the brief. Verify visual details as well as any visible
text; a provider success response is not evidence that the image follows the
instructions. If image inspection is unavailable, mark visual verification as
incomplete and require manual review rather than claiming it passed. Corrections
name the observed mismatch, the exact requested change, and the elements to
preserve. Send the prior asset with the edit instruction when supported, retaining
the original and its brief. These corrections share the workflow's two-attempt
automatic repair limit; they do not create a separate regeneration loop.

## Review and revision

The workflow stops twice: once to choose the story, and once to review the rendered
page. These are checkpoints on the editing desk, not a return to legacy guided
creation or shared review-level controls. An **Automatic draft** option may skip story selection using the recommended
approach; it still stops at final review. Supplied facts, source permissions, and
must-show requirements apply in either mode. Starting a draft is an explicit job
action; opening a studio or preview starts no provider work.

The review screen presents the full page, actual-size zoom, the story, source
details, and check findings. Useful actions include **Edit words**, **Ask for
changes**, **Try another layout**, **Undo**, and **Approve and export**. A request
can target the whole page or a named block: shorten a label, emphasize an idea,
replace a chart, or remove a decoration. No general design canvas is needed.

Text editing is direct and constrained by the layout. Changing a value, source,
chart, meaning, or geometry reruns the relevant checks and makes approval stale.
Layout changes retain approved wording and data unless the user also requests
content changes. Required wording is locked against automatic rewriting; if it
cannot fit, the user must resolve the conflict. Every build and revision is saved;
an interrupted attempt cannot replace the last complete preview or export.

Checks run before final approval:

- **Coverage:** all must-show ideas and exact wording are present; omissions and
  unresolved gaps are visible.
- **Factual fidelity:** claims and values match their captured sources or stored
  calculations, and important qualifications remain attached.
- **Visual fidelity:** chart values, labels, proportions, units, and relationships
  agree; conceptual relationships are not presented as measured quantities.
- **Layout:** exactly one page at the selected dimensions, no clipping or unintended
  overlap, and no missing fonts or assets. Minimum text is 12 pt for print content,
  9 pt for print source notes, 24 px for digital content, and 18 px for digital
  source notes. Inspect the rendered page as well as the scene geometry.
- **Accessibility and brand:** sufficient text contrast, meaning beyond color,
  readable order, and the chosen brand's fonts, colors, and asset rules.

The minimum text sizes are first-release defaults, not a guarantee of readability
at every viewing distance. A brand may require larger text, never a smaller floor.
Automatic repair is bounded to two attempts. Remaining issues stay visible rather
than causing an endless regeneration loop. Invalid geometry, omitted required
content, contradictory/untraceable factual claims, and failed exports block final
approval. Non-blocking editorial advice can be acknowledged. An unapproved preview
may be downloaded only as a clearly marked draft; it creates no approval record.

## Outputs

An approved revision delivers:

- **PNG** for immediate digital sharing; print presets use 300 dpi and the digital
  preset uses its exact pixel dimensions.
- **A one-page PDF** at the selected dimensions, with text retained as text where
  the export adapter supports it. Print presets are ordinary RGB documents;
  press-ready CMYK, bleed, and PDF accessibility tagging are deferred.
- **Editable SVG**, with text, chart geometry, and source markers preserved.
  Generated artwork remains an embedded raster asset, not editable vector paths. Fonts
  must be available to the receiver; record any embedding or redistribution limits.
- **An accessible text equivalent** containing the reading order, takeaway,
  descriptions of diagrams, underlying chart values, and source references.

Source markers resolve to a readable reference list. Long references can live in
the text companion, with short source names on the page. Source links never include
session keys, local paths, credentials, or private operational records. Internal
source locators remain in the private project record. Source-only research does
not imply local-only processing: assistant and image-generation requests send the
necessary selected content to the configured providers. Identify those providers
before a job starts and send only the inputs needed for the job. Export does not
upload, publish, email, or grant sharing access; sharing elsewhere requires an
explicit destination action.

Approval records the exact revision, content and scene digests, source revisions,
brand revision, dimensions, check results, and export hashes. A later change creates
another revision and requires approval again. A failed export retains the approved
scene and allows export retry without rerunning content generation.

## Marketing Studio integration

Implementation belongs in `studios/infographic/` with its own command, local server,
skill entry, native tests, and independent installer bundle. Marketing Studio owns
the launch entry, shared setup, and shared settings. The [existing architecture](architecture.md)
continues to define the shared infrastructure boundary.

Use Python 3.11 or newer and the standard library for application code, with
vanilla JavaScript and the shared UI kit. Follow the [Golden Gate design](design/golden-gate.md):
material for navigation and toolbars; opaque forms, sources, and infographic
review. The infographic's artwork follows its selected brand, independently of
the application shell.

Reuse compatible source handling, worker execution, brand discovery, review,
history, and loopback security components; keep infographic-specific story and
scene logic inside Infographic Studio. Do not route every graphic through a
Presentation Studio deck or add a second shared settings file.

Read and losslessly update the existing `studios-config.json` under its adjacent
lock. Reject outdated forms that conflict with newer saved values. Reuse shared
assistant, model, reasoning, identity, workspace, and brand choices where applicable.
Page size and infographic layout defaults are studio-specific. Deck delivery
preferences must not turn an infographic export into Google Slides automatically.
The Gemini image model is studio-specific non-secret configuration; its API key
is supplied separately through the server environment.

The existing shared worker adapter in `core/studio_core/shared_runner/agents.py`
explicitly disables Codex image generation. Reusing it unchanged will not satisfy
this specification. Add an Infographic Studio image adapter with scoped access to
the built-in Codex image tool, and a server-side Gemini API adapter for the Claude
Code route. Preserve existing studios' worker confinement. The Gemini adapter can
use standard-library HTTPS and JSON without introducing a Python SDK dependency.

Workspace adoption happens only through explicit setup or launch, preserving
configured workspaces. Actual projects and source material live in a separate
workspace, never this application repository. Merely opening a workspace never
installs or updates software.

## Pipeline and saved contract

Proposed pipeline: **Capture → Extract → Propose → Story review → Specify image
→ Generate artwork and compose → Inspect, check, and repair → Page review →
Export.** Each stage records its inputs and outputs and can be resumed. Stage jobs
cannot approve content or publish it.

A schema-versioned project record connects:

- The brief: audience, purpose, direction mode, requirements, exclusions, format,
  and captured brand choice.
- Sources and facts: stable IDs, source hashes and locations, literal values and
  units, dates, qualifications, and derived calculations.
- Story candidates and the selected story: stable block IDs, reading order,
  fact references, planned visual forms, and recorded omissions.
- The scene: element IDs, dimensions, text runs, chart encodings, coordinates,
  minimum type sizes, asset references, and dependencies on facts and blocks.
- Image briefs: the page composition, per-asset instructions, exact provider-ready
  prompts, reserved regions, acceptance requirements, and pinned story, scene,
  brand, and reference revisions. Edits record the requested delta and what must
  remain unchanged.
- Image jobs: provider and model, prompt and reference-asset hashes, generated
  asset hashes, attempt IDs, edit lineage, provider request IDs when available,
  and usage when reported. Prompts are private project material; keys are never
  recorded. Supplied-only runs disable provider search and grounding tools.
- Revision state: attempt IDs, checks, bounded repair history, user changes,
  approval digests, and immutable export manifests.

All mutation requests carry the expected revision. Stale forms and late worker
results cannot overwrite newer changes. Cancellation and retries preserve previous
revisions and only stop processes owned by that run. Team synchronization, when
added, follows the existing explicit-sharing and ownership conventions; an upload
is not automatically placed in a team repository.

Both image adapters return saved assets through the same studio-owned contract
for generate, edit, status, and cancellation. Validate returned file types and
sizes before composition. Retries are bounded and explicit; a timeout with an
unknown provider outcome is not an invitation to submit repeated billable jobs.
Late image results cannot attach themselves to a newer revision. Cancellation
prevents adoption of a result even if a provider cannot stop an in-flight request.

SVG composition uses the standard library. PNG and PDF require a rendering adapter
with verified font metrics, image support, explicit dimensions, and single-page
output. The implementation spike must select a reusable installed renderer or a
pinned companion and demonstrate those capabilities before committing to export
support. Any new companion goes through the shared pin and packaging mechanism;
runtime code never downloads it. Missing capabilities produce an actionable
computer-check message rather than a silent alternate output.

## Implementation increments and acceptance

1. **Prove image generation and the scene contract.** Demonstrate the actual Codex
   image-tool path and the Claude Code with Gemini API path, including editing and
   detailed image briefs, actual image inspection, and saved asset handoff, in an
   explicitly requested manual acceptance run. Automated
   checks use stand-ins. Use synthetic material to compose a comparison, a process,
   and a conceptual page. Verify text measurement, actual
   font handling, SVG editing, exact PNG dimensions, one-page PDF output, and
   overflow detection. Select and record the export dependency here.
2. **Ship the independent core workflow.** Add text/Markdown/CSV intake, the three
   direction modes, story selection, SVG composition, check results, revision
   requests, both image adapters, and the promised exports. Keep external research optional.
3. **Integrate Marketing Studio.** Add explicit setup and launch, shared settings,
   the native skill and bundle, and standalone lifecycle coverage. Verify the studio
   remains usable without Marketing Studio running.
4. **Extend intake and polish.** Add richer document adapters, optional permissioned
   research, richer artwork controls, and later cross-studio handoffs after
   the initial workflow proves useful.

Acceptance requires successful directed, suggested, and hybrid workflows; a useful
conceptual page with no numerical data; accurate CSV charting; visible handling of
contradictory inputs; refusal of unreadable required content; and a targeted edit
that preserves unaffected wording and facts. Reconnect, interruption, stale edits,
missing renderer, source changes, and export retry must preserve the last good work.
The digital and print presets must retain their exact dimensions and one-page rule.
Provider coverage must include both supported configurations, missing Gemini key,
Codex without an available image tool, invalid credentials, exhausted quota,
generation and edit failures, cancellation, and stale image results. Verify that
keys never reach settings, project artifacts, prompts, logs, or browser responses.
Verify that image work does not broaden the tools available to existing studios.
With stubbed image providers, verify that the brief is self-contained, preserves
required content and brand choices, reserves compositor-owned regions, and is
invalidated by changes to its pinned inputs. A returned image with a missing
required object or an incorrect relationship must trigger a specific correction
or an unresolved review finding, even when the provider reports success. Missing
image-inspection capability must never produce a passed visual check.

Use synthetic fixtures, disposable settings, Git identities, workspaces, and stubbed
providers. Never run paid jobs or touch personal studio state during verification.
Run targeted checks per increment and the full relevant suite once before completion,
using the shared Tart runner on macOS as described in the [testing guide](testing.md).

## Proposed defaults to revisit during product review

The first release assumes static output, a story review before rendering, A4
portrait by default, supplied sources only, Codex or Claude Code with a Gemini API
key, and local PNG/PDF/SVG delivery. The main
product decisions still open are whether digital portrait should be the default,
which richer source adapter comes first, and whether editable PowerPoint or an
external design-platform handoff warrants a later release. These do not block the
initial rendering spike.
