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
