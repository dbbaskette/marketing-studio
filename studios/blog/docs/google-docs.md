# Google Docs in Blog Studio

Blog Studio can guide Google Docs work inside your existing harness. Its Google
workflows load only when you supply a Google Doc or request a Google operation.
Your normal writing workflow needs no Google account or extra CLI.

On the page, choose **New blog → A draft → Google Doc** to read an existing
manuscript (every tab) onto the writing desk. Check the text before you start. The
original Doc stays linked, and **Finishing → Before publishing → Send to Google Doc**
sends every change back: words and paragraphs as suggestions, and what the Doc shows no
words for as comments (see [below](#send-desk-changes-to-the-doc)). Reading sends no
Google edits, comments or sharing changes and starts no assistant job. See
[the page workflow](runner.md#start-from-a-google-doc).

A Doc that already holds other people's pending suggestions reads as it is without them,
as well as a Doc with none: its images (with their data, as Google's own export writes
them), smart chips (their text or link), line breaks, footnotes and tables come in, and
page breaks, headers and footers are left out, since a blog is the body. Their suggestions
stay in Google for the Doc's owner to accept or reject; Blog Studio never accepts, rejects
or counts them as its own. An image Google does not send is kept as a visible placeholder.
Anything else the reader cannot take, such as an equation, is named in a plain message;
replace it in the Doc and read it again.

A blog's shared files hold at most 1 MiB of text each, and its draft carries its images as
text. So a Doc's images come in, in order, while their data fits about 600 KiB; every image
after that stays in the Google Doc and shows on the desk as a placeholder, "Image kept in the
Google Doc", with a line saying how many. A read never fails because of image size. A kept
image is never seen as changed or removed when you send or read again; delete its
placeholder on the desk and it is treated as any image removed. Copy and Download leave
kept images out, their placeholder in their place.

Their suggestions are shown, not touched. Each is recorded on this computer when the Doc is
read (what it inserts or removes, and where), and Review mode and the full desk mark it as
**Suggested in the Doc**: inserted words underlined and removed words struck through, in
their own colour. There is no Accept or Reject for them, they are never numbered or
counted with Blog Studio's fixes, and Review mode says how many are pending. Decide them in
Google Docs; the next check against the Doc drops any that were decided there. One whose
words you have since changed on the desk is no longer marked. Copy edit and Humanize are
told what the Doc already suggests, so they do not repeat it; a fix of theirs over the same
words says that accepting it makes the Doc's suggestion moot, and Accept all leaves it for
you. Editing those words by hand is fine too.

| Ask Blog Studio | What happens |
| --- | --- |
| “Start from this Google Doc: [link].” | Saves the original, draft and formatted snapshot; links that same Doc for future edits and suggestions. |
| “Use this Google Doc as a source.” | Imports selected accepted text with its source role, tabs, URL and version. |
| “Put this draft in our review folder.” | Posts only the chosen draft/outline, checks content and structure, and saves a transfer baseline. |
| “Bring back the team's edits.” | Compares Google, local text and the saved baseline; preserves history and asks about conflicting edits. |
| “Leave these comments on the Doc.” | Uses current quoted text and verifies the requested comments; explains any inline-anchor limitation first. |
| “Use our article template.” | Makes a native copy, preserving tab structure, styles and controls before adapting the content. |
| “Give me a PDF/Word copy.” | Exports the selected version and inspects the actual result. |
| “Give Alex comment access.” | Resolves the exact recipient, access and notification intent, then verifies supported permission changes. |

The Google helpers are part of the managed runtime; run the latest trusted
installer once to get new helper behavior, since a guidance refresh cannot
install code. Existing workspaces and Team Hubs retain their files and pins.
Codex and Claude installations receive the same runtime, but each harness's
actual Google connection is discovered separately. Missing capabilities produce
a clear local fallback.

## Local Codex and Claude: gcloud setup

Blog Studio uses the same user-login approach as `tanzu-brand`. You do not
create a Cloud project, OAuth client or billing configuration. From the
downloaded installer folder, run the regular shell scripts with the Google
account you use for your team's Docs:

```sh
sh installer/google-setup.sh --install-cli
sh installer/google-setup.sh --login you@example.com
sh installer/google-setup.sh --check you@example.com
```

The login runs `gcloud auth login you@example.com --enable-gdrive-access --force
--no-activate`. Naming the account adds it without changing the account gcloud
already uses for other work; add `--activate` only if you want to switch. Without
an email, the script signs in only when gcloud has no account yet.

**What you are granting.** Google's consent screen is for the Google Cloud CLI,
not for a Blog Studio app. It asks for what every gcloud sign-in requests (access
to your Google Cloud resources) plus full Google Drive access: seeing, editing,
creating and deleting every Drive file your account can reach. Blog Studio's
helpers use that access only to call the Drive and Docs APIs, read the files you
name, and write to Docs linked to your blogs; they refuse to change any other
Doc. If your organization prefers narrower access, use a connected Workspace
connector instead of this route.

The install step uses existing approved Homebrew; company-managed installations
can supply gcloud instead. No credentials go into Blog Studio or the Team Hub.
In chat, say **“Use you@example.com for Google Docs.”** Blog Studio then remembers
which account that writing workspace uses (only the address, on your computer)
and passes it automatically, without changing gcloud's active account.

Optional `install.sh --google-docs gcloud` guides login after installation;
`--google-docs gcloud-check` only checks access. JSON/noninteractive installs never
start interactive sign-in. Default installation skips Google.

Drive access enables selected HTML/DOCX/text imports as new native Google Docs,
and PDF/Word/text exports. Native Docs read/update is checked separately; API or
organization restrictions may still block it. The adapter cannot promise native
editing just because login succeeds. Existing document writes require a fresh
revision, and every handoff still requires real readback. The configured gcloud
review helper also supports capability-dependent suggestions and comments.
Sharing changes and native template copying require a capable connector.

Uploads keep a local operation receipt for recovery, check the reviewed folder
audience, and never retry an uncertain create automatically. Exports refuse to
overwrite local files. Working files (captures, review plans, receipts) go to a
private `.google-staging` folder inside your workspace, are removed when their
step is saved, and can be cleared at any time with “Clear local caches.”
Full usage: [gcloud adapter](../skills/blog-studio/references/google/gcloud.md).

## Set your team's review preferences

Say **“Use this folder for team reviews: [link]”** or **“Use this as our blog
template: [link].”** You can also explain who the reviews are intended for.
With a selected Team Hub, these become ordinary shared team context. Without a
Hub, keep them local. A preference is not permission to share: Blog Studio checks
existing access before putting a draft there and asks for missing recipient or
access details only when you request a sharing change.

Existing blogs keep their linked Doc. Templates are optional; if your connection
cannot copy one intact, Blog Studio explains that limitation rather than flattening
it. Each author's Google login and connection checks stay on their own computer.
Normal writing and local exports remain available without Google setup.

[Connection contract and supported operations →](google-capabilities.md)

## A round trip

1. Save the article normally, then ask to continue in Google Docs. Choose a folder
   if none is already established. Blog Studio checks the folder's inherited
   audience before placing private content there.
2. The harness uses the selected connector or gcloud adapter to create or update the selected
   editing copy. Local code freezes the outgoing text and records verified
   readback as the common baseline.
3. Edit in Google Docs, then ask Blog Studio to bring the changes back. If only
   Google changed, the returned text becomes a new local revision. If both sides
   changed different passages, the edits are merged and yours stay marked as not
   yet sent. Only a passage that both sides changed is shown to you, and you
   choose its wording.
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

Your Team Hub receives the returned text, the formatted Word snapshot and
fingerprints of the Doc. The raw Google Docs data behind a snapshot, which can
include your reviewers' comment threads and pending suggestions, stays on the
computer that pulled it and is never sent to the Hub. A teammate who opens the
blog from the Hub can check status and pull right away; they do not need that
raw data.

The inspected Codex connector exposes Docs reads, revision-guarded writes,
native copies, exports, comments and sharing. Disposable Codex checks verified
round trips, headings and links, native multi-tab template preservation, and
inspected PDF/Word exports. The configured gcloud review helper also produced a
pending suggestion and a comment visibly anchored in the native editor.
These checks do not establish your current document access, Claude parity, or
a marketing-team pilot. An API comment response alone does not prove an inline
anchor. The inspected share action has no notification switch, so Blog Studio
cannot promise silent sharing through it; actual permission-change acceptance
is still outstanding. Claude capabilities are discovered independently.

If a native feature or required verification is missing, the skill offers an
explicit supported fallback and retains local work. It never silently flattens a
native template, overwrites conflicting text, or broadens access.

## Verification and remaining live work

G0–G3 have executable local checkpoint tests and conditional skill workflows.
These tests cover consistency and preservation with disposable data; they do not
simulate evidence of real Google operations. The checkpoint commands do not call
Google; only the live status check does, read-only, through the separate
`google_drive.py` transport. Connected-provider and gcloud readback both require
task-specific verification.

The authenticated [G4 pilot (#15)](https://github.com/dbbaskette/blog-studio/issues/15)
runs last, along with [Mac setup (#8)](https://github.com/dbbaskette/blog-studio/issues/8),
[live Codex/Claude writing (#9)](https://github.com/dbbaskette/blog-studio/issues/9),
and [multi-member Hub work (#10)](https://github.com/dbbaskette/blog-studio/issues/10).
Reuse the completed disposable Codex round-trip, accepted-text/suggestion,
visible-comment, template and PDF/Word checks for unchanged behavior. Remaining
work is the participating-user workflow, independent Claude discovery, shared
continuation by a second member, and an explicitly selected permission-change
case. The [acceptance record](issue-validation-2026-10-03.md) separates live evidence
from fixtures; the [remaining acceptance map](remaining-acceptance.md) lists what
is still untested. Completing setup documentation performs no live operation.

See the [Google roadmap](google-docs-roadmap.md) for disclosure costs and the
[adapter contract](../skills/blog-studio/references/google/adapter.md) and
[checkpoint contract](../skills/blog-studio/references/google/checkpoints.md) for
implementation details.

## Formatted Google editing

Google Docs remains the shared editing copy. On return, retain DOCX as the
formatted stored copy, Markdown for readable Git diffs, and native structure for
format verification. A formatting-only return is saved even when prose is unchanged.
Wording updates patch existing paragraphs and verify styles instead of replacing
sections. See [the round-trip workflow](../skills/blog-studio/references/google/roundtrip.md).

Try: “Bring the Google edits back, including heading sizes and spacing. Save the
formatted DOCX snapshot and readable Markdown to our Hub.” Then: “Send these
wording changes back while preserving the team’s Google formatting.”

The automatic capture requires a single-tab Doc. Pending suggestions, yours or a
teammate's, do not block it: the returned text is the accepted text only. Docs
with tables, images or footnotes are captured through Google's own Markdown
export, and only while no suggestion is pending; multi-tab or structural changes
use the scoped native workflow. Renaming the Doc or a tab does not count as a
change. DOCX fidelity still needs inspection. No live document is modified by
installing or upgrading.

[Validation evidence and live-test boundaries](google-roundtrip-validation.md).

## Freshness and milestone names

On resume, check the linked Doc and show In sync, Google has changes, Local changes
pending, Both changed, Suggestions pending, or Not checked. Include Last checked and Last confirmed
saved to Hub. Cached results never establish current freshness; offline/pending
saves are not shown as saved to remote main. Use one stable Doc link and name
meaningful milestones in Google’s version-history UI. Version naming is manual;
labels do not prove freshness. [Details](../skills/blog-studio/references/google/status.md).

Try: “Continue my blog. Check whether Google or our local copy has newer changes,
and tell me when this article was last confirmed saved to the Hub.”

Older text-only Google baselines need an inspected formatted return before native
freshness checks.

## Find the working Doc from GitHub

Each linked blog’s generated GitHub page shows **Open working Google Doc** and the
last Google capture time. Draft and outline links are labeled separately. Google
permissions are unchanged. The timestamp describes the saved capture, not a live
freshness check.

## Send desk changes to the Doc

A desk blog started from a Google Doc sends every change back from Review mode (**Send
accepted changes to Google Doc**) or Finishing (**Send to Google Doc**), compared with the
Doc as it was read:

| On the desk | In the Doc |
| --- | --- |
| Words changed | A suggested edit for each separate change in a paragraph, deleting and inserting only the changed words. Text inserted comes in with the desk's bold, italic, underline and links, over the font of the words beside it. |
| A paragraph added, or split | A suggested line break and the new text, after the end of the paragraph before it. The new paragraph takes that paragraph's kind; a different kind (a heading, a list item) is said in a comment. |
| A paragraph removed, or merged | A suggested deletion of its words and its break. Google cannot delete the break that ends a Doc, so the last paragraph is deleted with the break before it instead, where that paragraph has the same settings, which it keeps; otherwise an empty paragraph is left. Either way the comment says so. |
| A link's address, bold, italic or code on words already in the Doc, a heading level | A comment on the words, such as "Link changed: “setup guide” now points to …" or "Make “Key Data Patterns” bold." A suggestion changes words, not the look of words it keeps, so that formatting is the Doc owner's to apply. |
| An image or a table row | A comment on the closest paragraph that can take one, quoting the change. |
| Words in a paragraph where someone else's suggestion waits, or beside an image or chip | A suggestion of ours, placed by the Doc's own indexes around their suggestion and the object; words their suggestion itself changes go as a comment on that paragraph's plain words. Theirs is never accepted, rejected or edited, and holds nothing else. |
| A title other than the Doc's name | A comment: "Suggested title: …". The Doc's name is not body text. |

The plan names how many suggestions and comments go, and nothing is sent until you
confirm. Each suggestion is placed by its paragraph's words and its place in that
paragraph; one the Doc would place with any doubt goes as a comment on the closest
paragraph the Doc shows once instead, quoting the paragraph before and after. Copies are
counted in the Doc's text as it was, without suggestions still waiting. A note about a
paragraph is a comment of its own, never part of a suggestion. A change already sent is
not sent again, and a change in a paragraph with a suggestion still waiting for the Doc's
owner goes next time; while one of this blog's suggestions that the desk has since edited
again still waits, nothing is sent, so no suggestion repeats or undoes another. Someone
else's suggestion, or one the owner already rejected, holds nothing. A note with no free
paragraph nearby goes with the next send.

## Send proofreading for team review

Say **“Proofread”**, then **“Push as suggestions.”** For a blog linked to a Google
Doc, proofreading records its corrections as proposals and leaves your local
draft as it is; the draft changes when you pull what the team accepted, so a
rejected proposal never has to be undone. Blog Studio refreshes the linked Google
Doc first, reconciles changes, and rechecks affected findings. A teammate's own
pending suggestion does not stop your review; only the paragraph it sits in is
skipped until they settle it.
When native suggestions are available, selected replacements become pending
suggested edits with explanatory comments. Otherwise, the comment workflow below
keeps them as review proposals. Broader feedback becomes comments. Native writes
use a revision guard; ordinary comments are checked against current content before
and after posting. Ordinary “Push to Google Docs” still applies edits.

After the team reviews in Google, say **“Pull from Google Docs.”** Accepted text
returns to Markdown; DOCX preserves the formatted export, while native snapshots
retain pending suggestions and comments separately. Pull never accepts or rejects
a suggestion. Complex structures may require a scoped native conversion rather
than the bounded paragraph renderer. If neither suggestions nor comments are
available, Blog Studio retains the review locally.

If posting is interrupted, ask again: Blog Studio continues with the comments
that are still missing instead of starting over, and it tells you plainly when
nothing reached Google. Live Google account validation is separate from fixture
tests.

Developer evidence and remaining live checks: [suggestion validation](google-suggestions-validation.md).

## When Google suggestions are unavailable

Keep using **“Push as suggestions.”** If your connector lacks the needed option,
Blog Studio can use its already configured gcloud connection. If native suggestions
are still unavailable, it posts readable review comments and tells you which mode
was used. Ordinary document comments appear in **All Comments**, with the section,
current wording, proposed wording and reason; they do not have Accept/Reject buttons.
Minor fixes in one paragraph can share a comment while keeping individual numbers.

Say **“Show review edits”**, then **“Apply edits 2 and 4”** to choose changes.
Edit numbers keep counting across reviews of the same blog, so a number always
means one edit. Blog Studio checks current wording, applies only your selection,
verifies formatting, and resolves completed comments. A resolved comment alone
never means approval. Numbered edits can be applied from the computer that
posted the review. Afterward, say **“Pull from Google Docs.”** A hosted
connector's missing option does not require changing the document's settings.

## Start from a blog already in Google Docs

Say **“Start from this Google Doc: [link].”** Blog Studio imports accepted text as
your draft, preserves the original and formatted DOCX snapshot, and makes that
same document the working Google copy. Then **“Proofread”** and **“Push as
suggestions”** send your selected proposals back to the original Doc.

Importing does not edit Google or create a duplicate document. Repeating the
request resumes the saved blog and preserves local edits. **“Use this as a
source”** still adds reference material without changing the working Doc.

Automatic formatted intake supports single-tab Docs; unsupported content or
ambiguous tabs need resolution before a linked baseline can be established.
