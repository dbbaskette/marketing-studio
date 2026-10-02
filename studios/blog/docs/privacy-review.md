# Data exposure review — October 1, 2026

Reviewed the packaged five-source-skill library (claude-blog: blog/blog-write;
marketingskills: content-strategy/copywriting/copy-editing), nine BlogForge-derived
capabilities, their source/reference inventories, trusted helpers/bootstrap,
installer, Team Hub transport, and optional prompt generator. This is a review
of the local pinned packages, not a live test of every upstream service.

## Findings and changes

| Surface | Finding | Packaged boundary |
| --- | --- | --- |
| claude-blog research/media | Original writer recommends topic/title searches, stock APIs, Gemini and NotebookLM; these can disclose private query/prompt content | Authored parents and every module now apply the private-input boundary before using upstream instructions |
| claude-blog delivery | Original automatic image ladder can send title/tags to external image APIs | No automatic provider ladder; supplied assets/local diagrams or nonconfidential public inputs only |
| marketingskills | CMS, webhooks, distribution and publishing examples are guidance, not bundled execution | Planning does not install a CMS, configure a webhook, or distribute private content |
| BlogForge | Original app invokes configured LLM providers; the skill package copies selected prompts/assets and adapts behavior | Original server, provider clients, publisher and API runtime are omitted; writing uses the existing harness |
| Local helpers/LinkedIn reader | Local file transforms; LinkedIn reads only selected profile fields/authored articles | No network calls or account crawl; contact export excluded |
| Guidance refresh | Fetches trusted private skill repository | Download only; no manuscript/source/profile upload to skill authors |
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

The complete local suite contains 87 tests, including three new privacy
regressions. Package/source hashes and all maintained skill entries are checked.
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

See [the operational boundary](../skills/blog-studio/references/privacy.md) and
[Team Hub usage](team-hub.md). Native Google Docs transfers remain a planned phase.
