# Blog Studio capability coverage

The page and skill use the same article/profile/source files, version checks,
Git decisions and worker queue. Specialized conversation methods are not all
independent executable CLI commands. This matrix defines intentional coverage;
it does not claim every low-level CLI flag is a browser control.

| User task | Page | Skill/CLI contract |
| --- | --- | --- |
| Write, outline, explore ideas, use an outline | Home | Guided runs, `run` |
| New blog from files: each file's role, three angles or the point, Write as | Home → New blog from my files | `upload` entries with `purpose`, `source-role`, `run create --mode from-files [--point]`, `examples` in the worker payload, the `from-example` check |
| Import Google Doc, local Word/Markdown/text | Polish a document | Google start/capture, source/article intake |
| Polish, proofread, humanize, fact check, revise | Manuscript → Polish | Located editor review, article reviews |
| Choose/adjust edits and comments; save locally | Choose changes → Finish | Version-bound editor proposals and draft save |
| Send explicit Google feedback | Finish → Send feedback | Reserved, guarded Google suggestion/comment plans |
| Learn/edit/confirm/audition/export/retire voices | More tools → Author voices | Existing profile revisions and voice guidance |
| Add published posts as voice samples from a list of links | More tools → Author voices → Add published posts | `library voice-links --file LIST --author NAME`, then `--import`; the library's `urls` import, byline check and voice-sample classification |
| Apply a voice revision to this article | Voice → Use this revision | Explicit article voice pin; no default mutation |
| Interview → reviewed outline → requested draft | More tools / creation → Interview me | Existing interview notes, outline and from-outline runner |
| Compare/restore manuscript checkpoints | More tools → Saved manuscript revisions | `article restore` and `author_workflow.restore` |
| Reconcile local/Google accepted text | More tools → Compare Google and local text | `google pull --id ID`, then explicit `--accept PREVIEW --expected VERSION --comparison HASH --confirmed`; same three-way compare/accept and fresh read before local save |
| Channel copy, target counts, named variants | More tools → Repurpose; Saved channel copies | Repurposing guidance and existing article derive; lazy per-copy editing with version guards |
| Retrieval/citation readiness | More tools → Improve clarity… | Existing GEO guidance, located evidence review |
| Title/opening/benefit/optional CTA alternatives | More tools → Improve a title or opening | Copywriting guidance, existing selection/editor |
| Report-only pre-publish checks | More tools → Pre-publish | `prepublish --id ID` |
| Advisory topic overlap | More tools → Check topic overlap | `plan --topic TOPIC`, local library index |
| Board, due dates, owners, ready/published decisions | Blogs → Library and team tools | `editorial` commands; explicit decisions |
| Source search, collections, analysis, retire/undo | Reference library | `library`/`source`, explicit per-operation analysis |
| Team workspace, driver, handover, offline retry | Status / team tools | `team`, existing Git decision/sync model |
| Shared settings, brand, models, review policy | Settings → Shared settings | Shared config with adjacent lock and displayed-value checks |
| Installation maintenance | Status → Installation maintenance | `marketing-studio doctor/update/rollback/uninstall`; explicit actions |
| Diagnostics, raw snapshots, migration and cache maintenance | Intentional terminal/conversation operations | `readiness`, `cache`, Hub and Google helper contracts |
| Remote CMS, analytics, notifications, Word tracked changes, Windows | Separately scoped proposals | [Optional extensions](optional-extensions.md); unavailable, not implied by import |

Opening tools performs reads only. Model tasks require Generate/Prepare; completed
output requires a separate save. Google comparison reads only; accepting changes
writes locally. Google send remains a distinct confirmed operation. Contextual
job records are private to this computer; generated results become normal shared
artifacts only when explicitly saved under the workspace's sharing preference.

## Compact command outcomes

Existing full JSON is unchanged. Put global `--compact` before the command for a
bounded schema-1 envelope with `status`, `saved`, `shared`, `warnings`, `next_step`
and basic identity. List envelopes contain at most 20 metadata rows and an honest
`total`/`truncated`; omit the flag for full data. No manuscript or history is
included. `saved: null` means not established by this envelope, including failures;
it never asserts that a partially failed operation left no files. A local save
and a failed/offline share remain distinguishable. No provider retry is automatic.

Exit 0 means the command returned its result, not that a remote share completed.
Exit 1 is an operation failure; inspect status/local files before repeating a
mutation. Exit 2 is invalid usage and runs nothing. Busy results explain retry
and preserve the lock file. The [generated command inventory](commands.md) is
checked against the parser, with `--help` giving exact flags and required values.

## Supported Google surface

| Operation | Implemented route and limit | Evidence |
| --- | --- | --- |
| Start from a Doc | Preview/confirm single-tab accepted text, original and formatted baseline | Synthetic page/transport tests |
| Pull/reconcile | Three-way comparison, explicit conflict resolution, fresh revision guard, local save only | Synthetic compare/accept/stale/pending-review tests |
| Comments / wording suggestions | Existing guarded send, explicit fallback, readback/recovery | Synthetic tests; historical live observations are scoped in [Google capabilities](google-capabilities.md) |
| Direct edits | Separate low-level explicit operation; never reconciliation | Capability/access must be checked in current session |
| Formatted content | Snapshot fidelity retained; unsupported structure stops/falls back explicitly | Fixture coverage; no general layout/parity guarantee |
| Tables/images with pending suggestions, paragraph insertion/deletion | Only supported preserved read paths; no general native editing promise | Separate extension boundary |

Google remains optional. A remembered account, installed CLI or fixture success
does not prove access, OAuth restrictions or current live-provider support.
