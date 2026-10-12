# Data exposure review — October 1, 2026 (updated October 12, 2026)

Reviewed the packaged five-source-skill library (claude-blog: blog/blog-write;
marketingskills: content-strategy/copywriting/copy-editing), nine BlogForge-derived
capabilities, their source/reference inventories, trusted helpers, installer,
Team Hub transport, and optional prompt generator. The October 12 update adds
the Google Docs helpers, the editorial desk's reference analysis, and the 2.0
whole-skill install. This is a review of the local package by code reading and
fixtures, not a live test of every upstream service or of Google.

## Findings and changes

| Surface | Finding | Packaged boundary |
| --- | --- | --- |
| claude-blog research/media | Original writer recommends topic/title searches, stock APIs, Gemini and NotebookLM; these can disclose private query/prompt content | Authored parents and every module now apply the private-input boundary before using upstream instructions |
| claude-blog delivery | Original automatic image ladder can send title/tags to external image APIs | No automatic provider ladder; supplied assets/local diagrams or nonconfidential public inputs only |
| marketingskills | CMS, webhooks, distribution and publishing examples are guidance, not bundled execution | Planning does not install a CMS, configure a webhook, or distribute private content |
| BlogForge | Original app invokes configured LLM providers; the skill package copies selected prompts/assets and adapts behavior | Original server, provider clients, publisher and API runtime are omitted; writing uses the existing harness |
| Local helpers/LinkedIn reader | Local file transforms; LinkedIn reads only selected profile fields/authored articles | No network calls or account crawl; contact export excluded |
| Installed skill (2.0) | Guidance and helpers are installed together; nothing is fetched when a task starts | No per-task contact with the skill repository; an update is an explicit installer run |
| Google Docs via gcloud | Sign-in grants the access every gcloud sign-in requests plus full Google Drive access, broader than one document | Access tokens stay in memory and go only to Google's Drive and Docs hosts; update, suggestion and comment writes are limited to Docs linked in the workspace; the account is remembered per workspace and sign-in does not switch gcloud's active account unless asked |
| Google captures | A pull stores the document's raw Docs JSON, which can include collaborators' comment and suggestion threads | Raw JSON stays on the author's computer (`.google-native/` in the blog folder, current baseline only) and is not shared with the Team Hub; staged captures, plans and receipts live in a workspace staging folder that is cleared after a checkpoint and by "Clear local caches" |
| Editorial desk reference analysis | Summaries and tags send up to 24,000 characters of each readable upload or import through the selected signed-in Codex or Claude CLI to its provider | Off until a CLI is chosen for the workspace; the upload and import dialogs state this and carry a per-operation checkbox; opening the desk does not turn it on |
| Team Hub | Intentional content transfer to selected private GitHub repo | Identity/privacy verified; public/replaced hubs block delivery; only selected writing artifacts transfer |
| GitHub CLI environment | An inherited GH_HOST could redirect provider API metadata calls | Host fixed to github.com; API calls specify hostname; debug override removed |
| Prompt generator | Inline page logic and user-triggered clipboard copy | No fetch, telemetry, third-party scripts/fonts, or form submission found |
| Document posting | Explicit document destination is the permitted exception | Only chosen document/content/audience; no implied public-link, extra recipients, or private supporting material |

## What this establishes

No telemetry, hidden content-upload endpoint, alternate model client, or external
writing-analysis service was found in the packaged runtime. Optional external
research/media instructions were reachable in archived sources; their authority
is now explicitly limited at every maintained entry/module. Archives preserve
source hashes for audit rather than pretending those examples were removed.

The local suite includes privacy regressions; package/source hashes and the
maintained skill entry are checked. A test proves that no raw Docs JSON, comment
text or suggestion marker reaches a Team Hub payload.
Behavioral regression tests cover local operations without transport calls,
GitHub host pinning, and no push when a joined hub becomes public. Existing
privacy/identity, unrelated-file exclusion, credential-URL rejection, and LinkedIn
contact exclusion tests remain part of the suite. These are local fixtures.
Instruction boundaries guide harness behavior; they are not a network sandbox
for every tool the host may expose.

Content still passes through the user's existing harness/model provider, and
shared work is stored by GitHub under repository/account policies. Private does
not mean provider-free or per-author isolation: repository members/admins with
access can read the hub, and prior clones/history remain after local leave or
tombstoning. This audit does not attest to providers' retention/training settings,
team membership, credential-helper/proxy configuration, or Google permissions.
Posted documents have the audience and exposure chosen by the user.

Limits of this update: Hubs that synced formatted Google snapshots before 2.0
still hold that raw JSON in their Git history; new revisions stop including it.
The Google consent scope is set by gcloud, not by Blog Studio, and an
organization that needs a narrower grant would supply its own OAuth client,
which is not implemented. Google behavior was checked against fixtures only;
live verification is tracked in
[#11](https://github.com/dbbaskette/blog-studio/issues/11) and
[#15](https://github.com/dbbaskette/blog-studio/issues/15).

See [the operational boundary](../skills/blog-studio/references/privacy.md),
[Team Hub usage](team-hub.md) and [Google Docs](google-docs.md).
