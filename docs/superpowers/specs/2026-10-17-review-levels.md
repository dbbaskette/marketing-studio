# Shared review levels

Approved in chat: replace repeated intermediate approvals with shared Balanced
(default), Automatic draft, and Step by step choices. Save a versioned policy
with new runs; old runs without one remain Step by step. A settings change never
changes an active run. Invalid saved policies stop rather than grant autonomy.

Balanced Presentation Studio reviews research, outline and the rendered brand
sample together, then the rendered deck. Blog Studio reviews research with the
outline, then the completed writing, review and requested export package.
Training Studio reads the research plan first (a short read, and the cheapest
decision there is), then reviews research and the planned training/deck
directions for all levels together, then the completed materials for all levels
together. Automatic draft omits the research plan and the direction review.
Step by step preserves the pipeline. A training may also choose its own level on
the start form; the shared level is its default. The research-plan stop is what
Balanced means, not a new version of the saved policy: it applies to any Balanced
training that has not reached its research plan yet, including one started
earlier, and a run already past its plan is unaffected.

Every studio's drawn deck comes to the person under every level: Presentation
Studio's `gate:build`, Blog Studio's final package and Training Studio's
`gate:deck` (for each level, as `gate:deck@101`) are never continued by the
policy. Training Studio then shows the scenarios and the finished materials in
its final combined review. The policy reads a Training Studio gate without its
level, and `tests/test_review_policy.py` checks it against every gate ID each
studio really lays out, so a renamed or new gate is decided rather than slipping
through by its name.

No gate is continued automatically while a reviewer's critical or major finding
is still open or an audit has a blocker, whatever the level: the studio stops for
the person with those findings shown. In Training Studio this keeps what a deck
says for the person when a review of its slides sends it back with a grave
finding, and keeps the deck itself.

Retain source scopes, provider permissions, budgets, missing-information stops,
validation, rendering, visual review, bounded repairs, human change requests,
work ownership, conflict detection, and explicit publishing/sharing commands.
Automatic continuation is recorded as policy acceptance, not human approval.
Reviews bind to exact contents and inputs; edited work must be checked again.
Display the saved mode and all material covered by combined reviews, with
changes available for any covered stage. No active test is restarted or migrated.

Risks: downstream Training Studio dependencies require accepted inputs; distinguish
policy acceptance in receipts. Multi-level work needs grouped boundaries rather
than one pair per level. Changed input hashes must invalidate prior decisions.
Automatic draft can cost more before the first review; existing limits still stop it.
