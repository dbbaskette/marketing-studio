# Validate investigation packets before their author finishes

Report validation and collection acceptance have different contracts. The report
saver permits extra fact/citation fields; collection rejects them. Checking sources
alone left a late `Unknown fact field: kind` failure after an otherwise completed
investigation. Use the pinned helper's actual collection commands in an isolated,
throwaway preflight case while the author can still correct its submission.

The host copies only already verified job captures, registers scratch receipts and
checks packet acceptance. These scratch records are never production invocation
records, checkpoints or approvals. Production collection and independent review
still run normally. Keep the existing safe source-date alias; do not erase unknown
fact metadata or turn an inference into a fact. Narrow investigator instructions to
evidence fields; synthesis alone receives report/prose instructions.

| Submission | Expected result | Verification |
| --- | --- | --- |
| Fact has kind or another unknown field | Current author receives collection refusal and can resubmit | Pinned-helper/native worker regression |
| Citation has an unknown field | Refuse inside the submission, before collection adoption | Pinned helper matrix |
| Unknown source field or conflicting dates | Existing corrective feedback retained | Source metadata checks |
| Missing author, source, quote, wrong permission or altered capture | Never accept or broaden permission | Existing and new boundary cases |
| Valid corrected evidence | Same invocation finishes; production collection and review accept it | Native transport |
| Unavailable or timed-out collection checker | Refuse acceptance explicitly; never silently fall back to report-only validation | Fault injection |
| Legacy serial report or composition | Existing report validation and frozen evidence checks retained | Shared and native synthesis suites |
| JSON-only transport sees a bad packet | Its existing bounded correction sees the helper refusal | Transport regression |

Verification: use synthetic captures and the locked real helper. Run the complete
shared suite and the affected research transport/synthesis suites for each studio
in disposable Tart storage. Reuse passing UI/material-generation evidence for the
unchanged application paths. No live provider request, personal research retry,
installation, or running-service change is part of verification.

Status: implementation in progress.
