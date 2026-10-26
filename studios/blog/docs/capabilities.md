# Blog Studio capability coverage

The page and skill use the same article/profile/source files, version checks,
Git decisions and worker queue. Specialized conversation methods are not all
independent executable CLI commands. This matrix defines intentional coverage;
it does not claim every low-level CLI flag is a browser control.

| User task | Page | Skill/CLI contract |
| --- | --- | --- |
| Start from a topic (with three angles), an outline or notes, or a draft | Home → New blog (also an interview's outline, and a saved blog's **Open writing run**) | `desk-create` with `way` (or `article` for a saved draft), `desk-angles`, `desk-retry` |
| Edit on the desk: in place, section notes, a note for the whole draft, selection edits, History, the Outline tab, Add a source | The desk | `desk-save`, `desk-note`, `desk-revise`, `desk-selection`, `desk-first-pass`, `desk-restore`, `GET /api/desk-versions`, `GET /api/desk-images` (the images, read once), `desk-outline-save`, `desk-unremove`, `desk-draft`, `desk-sources`, `desk-stop` |
| Finish a desk blog: humanize, apply a voice, proofread, check facts, headline and opening, feedback, before publishing | Desk → Finishing | `desk-finish` (`finish-humanize`, `finish-voice` with `guide`, `finish-facts`, `finish-headline`, `finish-feedback` jobs), `GET /api/desk-proofread`, `desk-apply`, `desk-skip`, `desk-repurpose`, `desk-google-plan`, `desk-google-send` |
| Write, outline, explore ideas, use an outline, step by step (older blogs, and chat) | The run | Guided runs, `run` |
| Write from files with three angles or the point, step by step (chat; older runs wait at their angles gate) | The run → Choose an angle; None of these | `upload` entries with `purpose`, `source-role`, `run create --mode from-files [--point]`, `run choose`, `examples` in the worker payload, the `from-example` check |
| Each source's role: facts, approved messaging written as the product's own claims, or an example of the kind of post | New blog → Your files → Used as; Upload → Use this file as | Purpose `messaging` or `inspiration`; `stance: messaging` on the payload's sources; `run create --messaging <id>`, `--example <id>` |
| Writing without source IDs or placeholders; what the author must still supply | Desk → Sources and what needs you; Gate → Checked for you; Needs you before publishing | `evidence` and `gaps` beside a draft or handoff (`derived/blog-<stage>-notes.json`), the `reader-facing-note` check, `run submit --gap` |
| How long the post runs | New blog → Sources and settings → Length | `desk-create` `length`; `run create --length style\|short\|deep` |
| Bring a Google Doc, local Word/Markdown/text to the desk | New blog → A draft | `google-preview`, `google-start`, `upload` with `purpose: manuscript`, then `desk-create` |
| Polish, proofread, humanize, fact check, revise a blog edited in the manuscript editor | Manuscript → Polish (its **Polish another document** opens the desk start) | Located editor review, article reviews |
| Choose/adjust edits and comments; save locally | Manuscript → Choose changes → Finish | Version-bound editor proposals and draft save |
| Send explicit Google feedback | Manuscript → Finish → Send feedback; Desk → Finishing → Before publishing | Reserved, guarded Google suggestion/comment plans |
| Voice guides: write one, make one from 3 to 20 samples, edit or retire it | Voice guides (sidebar) → New voice guide; Open | `GET /api/voice-guides`; `tool-action` `job-create` kind `voice-guide`, then `job-apply`; `profile-save`, `profile-retire`; saved as profiles, so learned voices are guides too |
| Show or hide the older voice tools (off by default) | Settings → Advanced → Show the older voice tools | `features.voice` in `.blog-run-settings.json`; while off, the rows marked *(older voice tools)* below are refused with "Voices are switched off in Blog Studio settings." and new blogs write with their tone |
| Choose the kind of post for a new blog | New blog → What are you writing? | `desk-create` `style`; `run create --style` |
| Choose the voice for a step-by-step blog *(older voice tools)* | Interview me → Write as | `run create --profile`; no profile means the default voice, or a manuscript's own voice; desk blogs write with their tone |
| Learn/edit/confirm/audition/export/retire voices *(older voice tools)* | Settings → Voices and styles → Create a voice (also Tools → Voices and styles) | Existing profile revisions and voice guidance |
| Learn/edit/confirm/export/retire styles (kinds of writing) | Settings → Kinds of post → Create a style (also Tools and Home) | `style` commands and the `style-learn` job; starters are editable |
| Mark a library source as a voice *(older voice tools)* or style sample | Create a voice → Posts already in the library → Use as a sample; Create a style → Use as an example | Source purpose in a new source revision; a voice sample names its author |
| Import a LinkedIn export as voice samples *(older voice tools)* | Create a voice → Import a LinkedIn export | One export per upload; About text as author background, articles as samples |
| Add published posts as voice *(older voice tools)* or style samples from a list of links | Create a voice → Add links to posts (voice samples); Create a style → Add links to examples (style samples) | `library voice-links --file LIST --author NAME [--purpose style-sample]`, then `--import`; the library's `urls` import, a byline check for voice samples, and voice- or style-sample classification |
| Learn a voice for every author in the team library *(older voice tools)* | Team library or Voices and styles → Create voices for every author | `library-voices`: one `voice-learn` job per author with two or more readable posts, up to twenty newest posts each; an existing voice gets a new revision; one permission for the batch |
| Say whether two author names are one person *(older voice tools)* | Create voices for every author → Same person as …; Different person; Review details → Author | `library-author-same` renames one author's posts through `curate`, version-checked; `library-author-different` remembers the pair |
| Select every library item the filters match | Team library → Select all on this page; Select all N matching | `library-matching`: the catalog's own filters, up to 500 items |
| Pin a voice revision to a step-by-step blog *(older voice tools)* | Voice → Use this revision; Run → About this blog → Change the voice | Explicit article voice pin, confirmed once an outline or draft exists; no default mutation |
| Interview → reviewed outline → a draft on the desk | Tools → Interview me → Review outline and start a draft | Interview notes and outline; the desk start with `desk-create` `way: outline` |
| Compare/restore manuscript checkpoints | Tools → Saved manuscript revisions | `article restore` and `author_workflow.restore` |
| Reconcile local/Google accepted text | Tools → Compare Google and local text | `google pull --id ID`, then explicit `--accept PREVIEW --expected VERSION --comparison HASH --confirmed`; same three-way compare/accept and fresh read before local save |
| Channel copy, target counts, named variants | Tools → Repurpose; Saved channel copies | Repurposing guidance and existing article derive; lazy per-copy editing with version guards |
| Retrieval/citation readiness | Tools → Improve clarity… | Existing GEO guidance, located evidence review |
| Title/opening/benefit/optional CTA alternatives | Tools → Improve a title or opening | Copywriting guidance, existing selection/editor |
| Report-only pre-publish checks | Tools → Pre-publish | `prepublish --id ID` |
| Advisory topic overlap | Tools → Check topic overlap | `plan --topic TOPIC`, local library index |
| Board, due dates, owners, ready/published decisions | Blogs → Library and team tools | `editorial` commands; explicit decisions |
| Source search, collections, analysis, retire/undo | Team library | `library`/`source`, explicit per-operation analysis |
| Every finished blog and kept file in one library, with role, kind of post and author | Finish; the files card's Keep in the team library | `library.origin_kind`, `kind` and `article` on a source; `library find --role --kind --author` |
| Add files, links and Google Docs to the library; each post's own author | Team library → Add to library | `library-add-preview`, `library-add` (the `urls` import per site with bylines), `library-add-author`, `library-add-samples` through `source-purpose` |
| Filter the library and learn a style or voice from a selection, or start a blog from it | Team library → filters; selection actions | `library-selection`; the desk start with the items as examples |
| Pick facts and examples from the library for a blog; a learned style pre-ticks its samples | Your files → From the library; What are you writing? | `library: [{id, role}]` on `desk-create` and `desk-sources`, or `run create --example <id>`; the library record is unchanged |
| Default voice for blogs run step by step; Interview me in a voice *(older voice tools)* | Settings → Default voice; Interview me → Write as | Personal writing default `voice`; `interview-start` with `profile` and `revision` |
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
