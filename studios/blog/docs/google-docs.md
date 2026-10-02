# Google Docs in Blog Studio

Blog Studio can guide Google Docs work inside your existing harness. Its six
Google capabilities load only when you supply a Google Doc or request a Google
operation. Your normal writing workflow needs no Google account or extra CLI.

| Ask Blog Studio | What happens |
| --- | --- |
| “Use this Google Doc as a source.” | Imports selected accepted text with its source role, tabs, URL and version. |
| “Put this draft in our review folder.” | Posts only the chosen draft/outline, checks content and structure, and saves a transfer baseline. |
| “Bring back the team's edits.” | Compares Google, local text and the saved baseline; preserves history and asks about conflicting edits. |
| “Leave these comments on the Doc.” | Uses current quoted text and verifies the requested comments; explains any inline-anchor limitation first. |
| “Use our article template.” | Makes a native copy, preserving tab structure, styles and controls before adapting the content. |
| “Give me a PDF/Word copy.” | Exports the selected version and inspects the actual result. |
| “Give Alex comment access.” | Resolves the exact recipient, access and notification intent, then verifies supported permission changes. |

Use the **1.2.0 installer** for the new checkpoint helper. This is a managed
runtime update; routine writing guidance still updates without reinstallation.
Existing workspaces and Team Hubs retain their files and pins. Google snapshots
use the existing portable history format. Codex and Claude installations receive
the same runtime, but each harness's actual Google connection is discovered
separately. Missing capabilities produce a clear local fallback.

## A round trip

1. Save the article normally, then ask to continue in Google Docs. Choose a folder
   if none is already established. Blog Studio checks the folder's inherited
   audience before placing private content there.
2. The harness uses its connected provider to create or update the selected
   editing copy. Local code freezes the outgoing text and records verified
   readback as the common baseline.
3. Edit in Google Docs, then ask Blog Studio to bring the changes back. If only
   Google changed, the returned text becomes a new local revision. If both sides
   changed, Blog Studio shows the differences and asks which result to keep.
4. The original, previous drafts, selected voice/sources and guidance pins remain.
   Changed manuscript reviews become stale. A chosen merge that has not reached
   Google remains visibly unsent. A selected private Team Hub shares the baseline
   and snapshots so another member can continue the same workflow.

Google comments and suggestions remain separate from accepted manuscript text.
No suggestion is accepted or rejected automatically. Sharing, commenting and
resolving threads do not approve publication.

## Boundaries and known capability limits

Only selected content goes to Google. Internal source material, voices, rules,
background and interviews are not added to a Doc by default. Credentials stay in
the connected provider. The skill repository never becomes the team's data store.

The inspected Codex connector exposes Docs reads, revision-guarded writes,
native copies, exports, comments and sharing. Exposure is not live validation:
accepted-text rendering, native fidelity and permissions still need the deferred
pilot. API comment evidence does not prove an inline anchor. The inspected share
action has no notification switch, so Blog Studio cannot promise silent sharing
through that action. Claude capabilities are discovered independently.

If a native feature or required verification is missing, the skill offers an
explicit supported fallback and retains local work. It never silently flattens a
native template, overwrites conflicting text, or broadens access.

## Verification and remaining live work

G0–G3 now have executable local checkpoint tests and six conditional skill
workflows. These tests cover consistency and preservation with disposable data;
they do not simulate evidence of real Google operations. The helper does not
call Google: connected provider operations and readback belong to the harness.

The authenticated [G4 pilot (#15)](https://github.com/dbbaskette/blog-studio/issues/15)
runs last, along with [Mac setup (#8)](https://github.com/dbbaskette/blog-studio/issues/8),
[live Codex/Claude writing (#9)](https://github.com/dbbaskette/blog-studio/issues/9),
and [multi-member Hub work (#10)](https://github.com/dbbaskette/blog-studio/issues/10).
It must verify a disposable Doc round trip, accepted text versus suggestions,
visible comment location, full native template fidelity, actual PDF/Word output,
and requested permissions/notifications in each connected harness. No sign-in or
live Google mutation was needed to implement this batch.

See the [Google roadmap](google-docs-roadmap.md) for disclosure costs and the
[adapter contract](../skills/blog-studio/references/google/adapter.md) and
[checkpoint contract](../skills/blog-studio/references/google/checkpoints.md) for
implementation details.
