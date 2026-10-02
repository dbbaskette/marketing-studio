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

The Google checkpoint helper is included in runtime **1.2.0 and later**. Use the latest trusted installer for new setup. This is a managed
runtime update; routine writing guidance still updates without reinstallation.
Existing workspaces and Team Hubs retain their files and pins. Google snapshots
use the existing portable history format. Codex and Claude installations receive
the same runtime, but each harness's actual Google connection is discovered
separately. Missing capabilities produce a clear local fallback.

## Local Codex and Claude: gcloud setup

Runtime **1.4.0** adds the same user-login approach used by `tanzu-brand`.
You do not create a Cloud project, OAuth client or billing configuration. From
the downloaded installer folder, run the regular shell scripts:

```sh
sh installer/google-setup.sh --install-cli
sh installer/google-setup.sh --login
sh installer/google-setup.sh --check
```

The login command is `gcloud auth login --enable-gdrive-access --force`. It opens
Google consent for Drive access and may change your active gcloud account.
The install step uses existing approved Homebrew; company-managed installations
can supply gcloud instead. No credentials go into Blog Studio or the Team Hub.
Optional `install.sh --google-docs gcloud` guides login after installation;
`--google-docs gcloud-check` only checks access. JSON/noninteractive installs never
start interactive sign-in. Default installation skips Google.

Drive access enables selected HTML/DOCX/text imports as new native Google Docs,
and PDF/Word/text exports. Native Docs read/update is checked separately; API or
organization restrictions may still block it. The adapter cannot promise native
editing just because login succeeds. Existing document writes require a fresh
revision, and every handoff still requires real readback. Comments, sharing and
native template copying continue to use a capable connector.

Uploads keep a local operation receipt for recovery, check the reviewed folder
audience, and never retry an uncertain create automatically. Exports refuse to
overwrite local files. Full usage: [gcloud adapter](../skills/blog-studio/references/google/gcloud.md).

## A round trip

1. Save the article normally, then ask to continue in Google Docs. Choose a folder
   if none is already established. Blog Studio checks the folder's inherited
   audience before placing private content there.
2. The harness uses the selected connector or gcloud adapter to create or update the selected
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
the connected provider or gcloud's user credential store. The skill repository never becomes the team's data store.

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
they do not simulate evidence of real Google operations. The checkpoint helper does not call Google. Runtime 1.4.0 adds the separate
`google_drive.py` transport; connected-provider and gcloud readback both require
task-specific verification.

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

## Formatted Google editing (runtime 1.5)

Google Docs remains the shared editing copy. On return, retain DOCX as the
formatted stored copy, Markdown for readable Git diffs, and native structure for
format verification. A formatting-only return is saved even when prose is unchanged.
Wording updates patch existing paragraphs and verify styles instead of replacing
sections. See [the round-trip workflow](../skills/blog-studio/references/google/roundtrip.md).

Try: “Bring the Google edits back, including heading sizes and spacing. Save the
formatted DOCX snapshot and readable Markdown to our Hub.” Then: “Send these
wording changes back while preserving the team’s Google formatting.”

This requires updating the managed installer to 1.5 once. Automatic guidance
refresh cannot install runtime code. The automatic export bundle currently requires
a single-tab Doc without pending suggestions; multi-tab or structural changes use
the scoped native workflow. DOCX fidelity still needs inspection. No live document
is modified by installing or upgrading.

[Validation evidence and live-test boundaries](google-roundtrip-validation.md).

## Freshness and milestone names (runtime 1.6)

On resume, check the linked Doc and show In sync, Google has changes, Local changes
pending, Both changed, or Not checked. Include Last checked and Last confirmed
saved to Hub. Cached results never establish current freshness; offline/pending
saves are not shown as saved to remote main. Use one stable Doc link and name
meaningful milestones in Google’s version-history UI. Version naming is manual;
labels do not prove freshness. [Details](../skills/blog-studio/references/google/status.md).

Try: “Continue my blog. Check whether Google or our local copy has newer changes,
and tell me when this article was last confirmed saved to the Hub.”

Update the managed installer to 1.6 once for this status command. Older text-only
Google baselines need an inspected formatted return before native freshness checks.

## Find the working Doc from GitHub

Runtime 1.6.1 displays **Open working Google Doc** and the last Google capture
time on each linked blog’s generated GitHub page. Draft and outline links are
labeled separately. The next Hub sync upgrades existing generated pages without
changing canonical article history; manual edits to generated pages remain protected.
After that upgrade, contributing clients need 1.6.1. Google permissions are unchanged.
The timestamp describes the saved capture, not a live freshness check.
