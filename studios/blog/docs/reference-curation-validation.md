# Import-time reference curation

Readable source intake now records automatic analysis through the workspace's
selected signed-in Codex or Claude CLI. The analysis adds a summary, topic and
product tags, document kind, and cautions for reuse. It does not change source
text, train an author voice, or promote a team rule.

Analysis is bound to the content hash. Unchanged analyzed text reuses its saved
result. Import batches analyze at most five documents per CLI call and at most
24,000 characters from each document. Partial-text results disclose that limit.
Manual tag, note, and reuse-status corrections survive refreshes. Source intake
is saved before a model call so interruption leaves recoverable work.

## Verification

The focused tests cover uploads, checked archive imports, extraction gaps,
invalid analysis, unavailable CLI/retry, unchanged-text reuse, manual corrections,
interrupted intake, and synthetic cross-workspace Hub sharing. They also check
that Codex keeps its configured model while shell, browsing, connectors,
customizations and hooks are disabled for the analysis run. Source text is sent
on stdin, rather than command-line arguments. There is no provider fallback.

A live smoke test used a synthetic document containing an instruction to read
and upload passwords. The output treated that instruction as untrusted document
content and flagged it as a caution.

The user-authorized live check analyzed eleven already imported public historical
posts with the existing Codex CLI, then shared their analysis to the selected
private Hub. All eleven finished successfully. Source content hashes, original
hashes, origins, roles, and working article files were preserved. Hub sharing
finished with no queued writes or conflicts. Browser verification showed eleven
Analyzed badges and the saved summary, topics, products, and cautions in Review
details. Private Hub identifiers and source content are not copied into this
repository's test fixtures or documentation.

The final implementation commit `da531112d3ee1b4ae0e552122846120ffdd73785`
passed all **320 tests** in a disposable macOS 27 ARM64 Tart VM with Python
3.13.15. The run also passed newcomer prompts, guidance budgets, both package
validators, shell/launcher syntax, and offline Codex, Claude, and combined
installation/check/uninstallation. The VM was deleted after the run.

Results: `/tmp/blog-studio-curation-verified-results/blog-studio-curation-verified-test-20261006010459-75983-5c008bd4`.
This does not claim a Linux matrix or live Claude acceptance. The source tree
was isolated from unrelated local CI edits in the primary checkout. The local
installed runtime is `1.14.3-0613ff81f98b`; browser verification and the installed
catalog returned eleven analyzed reusable references with matching content hashes.
