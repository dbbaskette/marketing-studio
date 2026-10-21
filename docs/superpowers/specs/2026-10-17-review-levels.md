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

Decks pause the same way in every studio, by one table in
`studio_core.deck_flow`. The brand defines three checkpoints: draft approval,
the look (picked from the brand's rendered samples), and final acceptance of the
rendered deck. Step by step stops at each. Balanced asks for the draft and the
look in one combined stop (Training Studio's `review:direction`, Presentation
Studio's "Review the direction" at `gate:outline`), then the final. Automatic
draft stops only for the final, and uses the brand's default look, recording
why. The final is always the deck's own gate (Training Studio's `gate:deck`,
for each level as `gate:deck@101`; Presentation Studio's `gate:build`), so the
person's answer there is the one bound to the slides tool's design record;
Training Studio then still shows the scenarios and finished materials in its
final combined review. The policy reads a Training Studio gate without its
level, and `tests/test_review_policy.py` checks it against every gate ID each
studio really lays out, so a renamed or new gate is decided rather than
slipping through by its name. `tests/test_deck_contract.py` runs both studios'
decks through their engines with stand-ins and checks they pause alike.

No gate is continued automatically while a reviewer's critical or major finding
is still open or an audit has a blocker, whatever the level: the studio stops for
the person with those findings shown. Both studios pass what holds a gate to the
policy (`holding`): in Training Studio it keeps what a deck says for the person
when a review of its slides sends it back with a grave finding, and keeps the
deck itself; in Presentation Studio it is passed at `gate:build`, which stops
anyway, so that the rule does not depend on that. A deck that continued past its
own gate under the saved level before this rule shipped is not held again.

When the brand's looks cannot be rendered, the person may knowingly carry on in
the brand's default look at the look checkpoint (or in Balanced's combined stop),
and Automatic draft takes it itself, its receipt saying the samples could not be
rendered and why. Either way the choice is recorded with the brand as unrendered
where it can, and the deck's gate calls it an unreviewed draft of its look.

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
