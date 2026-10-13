# Blog Studio working agreements

Keep verification proportional. Formatting and wording-only changes need content
and link checks, not CI. Behavioral changes use targeted checks at functional
milestones and the existing Tart runner for full verification. Preserve unrelated
working changes and reuse valid evidence for unchanged code.

For sweeping workflow, storage, installer, or synchronization changes, also walk
through the real CLI commands against a disposable test Hub seeded exclusively
with synthetic documents. Cover create/join, source and voice intake, blog saves,
reviews, cross-clone resume/edit, offline queue/retry, status, readable folders,
and protections against overwriting local work. Record commands and outcomes.
A live private GitHub test repository requires user authorization; never use real
team content or provider credentials copied into fixtures. Two clones of one
account do not establish multi-account permission or Google acceptance coverage.
See [the Hub acceptance walkthrough](docs/hub-acceptance.md).

This repository is public: issues, pull requests and release assets are readable
by anyone. Keep unfixed security details, private identifiers and team content
out of them.

Treat `.github/workflows/` as owner-approved. The self-hosted runner service
pins the set of active workflows and each file's hash; adding, enabling or
editing one stops pull request checks until the owner re-approves it. Change
those files only with the owner's explicit go-ahead, and say so at the top of
the pull request. See [changing a workflow file](docs/local-ci.md#changing-a-workflow-file).
