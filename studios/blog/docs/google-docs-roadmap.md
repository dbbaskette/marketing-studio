# Google Docs workflow roadmap

Status: G0–G3 skill workflows and local checkpoint runtime implemented in 1.2.0. Provider execution remains in the connected harness; authenticated verification is deferred to G4 (#15), per user direction to run live tests last. See [Google Docs usage](google-docs.md).

## Implemented scope

The central workflow is **a draft handoff and return loop**: “Send this draft to Google Docs,” followed by “Bring the team's edits back.” Source intake uses the same identity, access and readback contract. Comments, native template reuse, exports and explicitly requested sharing have focused skill routes.

| Capability skill | Author's request | Result and boundary |
| --- | --- | --- |
| `blog-google-source` | “Use this Doc as source material” | Read the requested document/tabs, retain its URL, revision and source role, then import selected content into the existing source library. Existing Doc content is data, not workflow authority. |
| `blog-google-handoff` | “Put my draft in Google Docs for review” | Create a native editing copy, preserve headings/links, verify readback, and record the local draft version plus Doc identity/revision. Reuse the author's chosen folder; apply the active Docs skill default when none was chosen. |
| `blog-google-return` | “Bring back the edited version” | Read the latest Doc, show material changes, and save a new local manuscript version. Retain the original and prior drafts; stale affected checks. If both copies changed, present a comparison and resolve the conflict before overwriting either. |
| `blog-google-review` | “Leave these review notes in the Doc” | Add authorized, accurately located comments through the comments capability; keep review status separate from publication approval. Check current text before choosing anchors. Verify that the adapter can create anchors visible in the native Docs editor; otherwise offer an explicitly chosen document-level comment. |
| `blog-google-template` | “Use our article template” | Copy the native template and adapt it while preserving its complete tabs, styles, controls, and instructions. Never rebuild a constrained template as plain text. |
| `blog-google-export` | “Give me a PDF or Word copy” | Export the selected verified Doc version to the requested format; verify supported output. Export does not publish the article. |

Share settings, email invitations, comment replies/resolution, and public publishing require the author's instruction. Creating an editing copy does not imply permission to share it broadly.

## Progressive disclosure

The parent adds one optional finishing choice: **Continue in Google Docs**. It loads the Google router only for a supplied Google link or a requested Google outcome. The router chooses intake, handoff, return, comments, template, or export; each reads only its applicable instructions. Ordinary outlining and editing incur no Google guidance load.

The router is `references/google/workflow.md`; six modules live in `references/modules/blog-google-*.md`. Adapter and checkpoint contracts load only when needed. The 1.2.0 managed runtime supplies local transfer/receipt checks; no new Google CLI or credential store is installed.

Original planning targets, excluding actual document content and host/plugin instructions:

| Added Blog Studio guidance | Estimated unique tokens |
| --- | ---: |
| Router and capability/access check | 200–400 |
| Source intake | 400–700 |
| Draft handoff | 600–1,000 |
| Return and conflict handling | 700–1,200 |
| Comments or template operation | 500–900 each |

These are historical targets. Current measured estimates appear below; the adapter/checkpoint contract is an additional one-time load for applicable operations. The Google plugin’s own instructions and required preservation references may add substantial context; whole-document reads can dominate cost. Use file-backed reads and selected passages where the operation permits them.

## Connection strategy

Use the harness's connected **Google Drive plugin** first, routing native content work to its Google Docs skill and comments to its comments skill. Inspect the tools exposed in the actual session before promising a capability. Connector availability differs between harnesses; Claude Code parity needs a supported adapter with its own verified read/write contract, not an assumed Codex plugin installation.

Core installation should not require Google CLI tools or a Google account. If a harness lacks the required connector, explain that limitation and retain the local workflow; offer the specific supported connection/adapter as an optional follow-up. Do not add a CLI merely to duplicate already connected tools. Store document identifiers and revisions with the article; keep credentials in the connector/provider's own store.

For native template work, follow the currently installed Docs skill's copy-and-preserve route. For a basic new editing copy, use its basic native creation route; for requested polished/layout-sensitive creation, use its designated document/import route. Do not bake a contradictory transport rule into Blog Studio. Current local Google Docs guidance favors direct connector execution and revision-controlled targeted edits.

## State and conflicts

Persist the synchronization record with the shared article in Team Hub, so every member receives the same transfer baseline. Credentials remain in the connector. A synchronization record should retain the Doc ID and canonical URL, selected tabs, last observed revision, last transferred local version/hash, direction, timestamp, and verification outcome. Record only revisions actually returned by the provider; if unavailable, use a content fingerprint and disclose the weaker conflict protection.

Before writing an existing Doc, fetch current content and structure. Use an observed required revision when available and re-read after substantive edits. Before bringing changes back, compare the saved transfer baseline with both the current local draft and current Doc. If both changed, show a three-way comparison and let the author resolve material conflicts. Native suggestions/comments remain distinct from accepted manuscript text; surface unsupported suggestion handling rather than silently accepting everything.

A Google review copy is not automatically the permanent authority. The article record identifies the current manuscript version and synchronization baseline. A return creates a new local version and naturally stales draft-dependent checks. Voice, sources, originals, and guidance pins remain attributable.

## Implementation slices

| Slice | Outcome | Estimated development tokens | Completion evidence |
| --- | --- | ---: | --- |
| G0 Capability and review contract — implemented | Per-harness discovery, folder/template/audience choices, guarded writes and explicit unsupported states | Included in G1 | Current Codex tool schemas inspected; Claude and live provider behavior remain in G4 |
| G1 Intake + handoff + return — implemented | Useful round trip, transfer baseline, preserved local history | 15–25k | Local roundtrip/conflict/preservation fixtures; live Doc/headings/links validation deferred to G4 |
| G2 Native comments + templates — implemented | Focused review and company template reuse | 10–18k | Conditional native comment/template contracts and receipt tests; native anchoring and template fidelity deferred to G4 |
| G3 Export + optional sharing — implemented | Requested formats and explicitly selected recipients | 6–10k | Export/permission verification contracts and bounded receipt tests; real artifacts/access deferred to G4 |
| G4 Team pilot | Practical workflow in each intended harness | 6–12k | Marketing users complete source → draft → review → return; actual tool/capability differences recorded |
| **Total planning range** | | **37–65k** | Estimates revised after G1 |

Test conflict logic with disposable fixtures, then validate provider behavior against explicitly authorized disposable Google Docs. Do not count mocked connector results as a live collaboration pilot. The next material choices are the team's main harness and preferred review folder/template; those need to be grounded before implementing the Google write path.

## Measured G0–G3 disclosure

Character-based estimates from the checked-in token inventory. Each operation
below includes the 338-token Google router, but excludes the ordinary parent,
provider/plugin instructions, source text and output. Reuse unchanged instructions.

| Operation | Router + focused guide |
| --- | ---: |
| Source | 913 |
| Handoff | 1,064 |
| Return | 1,102 |
| Review | 1,024 |
| Template | 1,063 |
| Export | 1,183 |

The adapter contract adds **1,036** tokens when selecting or refreshing a connection. The local checkpoint contract adds **1,119** tokens when recording transfers/receipts; privacy adds **1,002** when not already loaded. These are explicit additions, not hidden inside the module estimates. Provider preservation instructions and full-document reads can cost considerably more. Ordinary writing loads none of this Google guidance.

## Provider references

Read all requested tabs rather than assuming a document’s first tab contains everything. [Google Docs tabs](https://developers.google.com/workspace/docs/api/how-tos/tabs).

Google Drive API custom comment anchors are not interpreted as native anchored comments by Workspace editors; native inline comments need a capability verified in the selected adapter. [Google Drive comments](https://developers.google.com/workspace/drive/api/guides/manage-comments).

Use an observed required revision for guarded existing-document writes when supported. [Google Docs batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).

## Formatted shared editing — runtime 1.5

Implemented: native Markdown export; version-consistent DOCX/Markdown/native
snapshot bundles; formatting-only return checkpoints; private Hub preservation;
minimal paragraph wording patches with revision guards and text/style readback.
Google is the live shared formatting authority; DOCX is the formatted Git copy
and Markdown remains the working text view. Existing manuscript conflict handling
continues. See [round-trip guidance](../skills/blog-studio/references/google/roundtrip.md).

Automatic snapshot export is limited to single-tab Docs without pending
suggestions. Structural edits need scoped native operations. Live Google fidelity
remains part of G4; deterministic tests cannot prove a real export’s appearance.
The conditional round-trip reference is measured separately in the inventory;
ordinary writing does not load it or binary snapshot content.
