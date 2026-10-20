# Optional integration proposals

These are independent designs, outside core setup. No account, provider spend,
external send or platform support is implied. Ordinary Git repositories already
support shared studios; another Hub backend is not a prerequisite.

| Proposal | First bounded task | Acceptance before support is claimed |
| --- | --- | --- |
| Word review | Import one DOCX with tracked changes/comments into an inspection-only report | Explicit accepted-versus-pending choice; preserve original package, authors, anchors, tables and images; fixture matrix plus rendered Word inspection; no silent flattening or acceptance |
| Windows | Independently install/start one studio in a disposable user profile | Native launcher, Python/private Node, path/Unicode/symlink strategy, interrupted install and rollback, process/port ownership; CI on Windows before claiming support |
| GitLab/shared folder | Demonstrate a repository/permission gap with ordinary Git first | Provider adapter only where needed; equivalent driver/claim, fresh-head checks, offline queues and cross-clone local-work protection; no implicit account creation |
| Hosted/other assistants | Run one explicit drafting task with an existing account | Equivalent private settings, time/cost bounds, output contracts, cancellation, local-write ownership and saved approval semantics; no automatic assistant installation |
| Translation | Review one selected manuscript in a specified language | Preserve evidence IDs, voice, quotations/technical terms and separate translated revisions; bilingual review before replacing source wording |

Select and split one proposal into its own implementation issue with these bounds
before building it. Current DOCX text import does not establish Word review.
Scheduled digests, analytics imports, external CMS publication and notifications
likewise require a named task, inputs/audience and separate implementation scope.
