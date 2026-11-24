# Announcements that read like announcements: design

**Date:** 2026-10-21. **Owner's words:** "review the blog output from blog studio. we could
probably give it better instructions to get things expanded and a better reading blog."

## What the run produced

The owner wrote an announcement from one internal messaging document, on the files
screen, with "I know the point", the Product announcement style, a tone instead of a
voice, and supplied-only research. Balanced review accepted every stage. The draft:

- **500 words**, at the bottom of the style's 400 to 800, with an abstract "why it
  matters", three capability sections of two short paragraphs each, no example, no proof
  point, although the messaging document carried pillars, proof points and a competitor
  table.
- **Hedged in every paragraph.** "Is designed to", "is described as", "the described",
  "intended", "not confirmed by the supplied evidence", repeated section after section.
  The studio's own review flagged it: "reviewer-facing phrasing interrupts the
  announcement and weakens its conversational voice".
- **Source IDs in the prose.** Every paragraph ends in `[source-…]`, and the package's
  suggested description carries one too. A reader would see them.
- **Editorial placeholders inside the draft** ("[Editorial placeholder: add the confirmed
  release version…]") where the Availability and Next step sections should be.
- **A research stage that added only doubt.** With supplied-only research and one
  messaging document, the research step produced "target dates, not a completed release"
  findings that the outline then carried into every section as boundaries.

Why. The writer gets three instructions at once: the house guide and software-claims
guide say to attribute and qualify every claim, the review guide says to keep source IDs
near assertions, and the style says "confident about what shipped, exact about what did
not". With a pre-release messaging document as the only source, nothing counts as
shipped, so the first two win and the announcement reads like an evidence memo. Nothing
tells the writer that an approved messaging document is the announcement's own claims,
and nothing keeps reviewer-facing material out of reader-facing text.

## Design

### 1. A role for approved messaging

A new upload role, **Approved messaging (the product's own claims)**, purpose
`messaging`, beside Facts and Example. It is for documents the team has approved to say
what the product does: a messaging document, a launch brief, release notes.

| Role | How the writer uses it |
| --- | --- |
| Facts (may be quoted) | Evidence to cite; attributed when the claim is contested or measured |
| Approved messaging | The announcement's own claims, stated in the product's voice, present tense, without attribution; a limit the document itself marks (target, preview, planned) is kept as that limit |
| Example of the kind of post | Shape only, as today |

Enforcement: `inputs()` puts messaging sources in `sources` with `stance: 'messaging'`;
`POLICY` says what the stance means; the fact check treats a claim that the messaging
document makes as supported by it, and flags only claims that no source makes. The
software-claims guide's rule against presenting a roadmap as shipped still applies to
dates and availability, which is where it belongs.

### 2. Reader-facing text carries no notes

The draft and package stages return two things: the **writing**, clean, and **notes**:
`evidence` (claim → source id and passage, for the review and the fact check) and
`gaps` (what the author must supply before publishing, such as the availability date).
Source IDs and editorial placeholders never appear in the writing. The gate shows gaps
under a "Needs you before publishing" heading; the package's handoff lists them. A
mechanical check, `reader-facing-note`, fails the gate's "Checked for you" row when the
draft contains `[source-` or `[Editorial placeholder`.

### 3. Qualify once

Guidance for outline and draft: a limitation is stated once, where it decides something
for the reader (usually Availability), not in every section. With a messaging stance,
the writer does not use attribution hedges ("is described as", "is designed to", "the
messaging describes", "intended to") on the product's own claims; "in preview" and
"planned for" remain, because they are facts. The review treats a qualification repeated
in three or more sections as an editorial finding.

### 4. Depth

A **Length** choice on the run: *Style's own* (default), *Short* (about half), *In depth*
(about twice, with one worked example or proof point per capability). The guidance for a
capability section is explicit: what it does, how it works in one or two sentences, what
the reader can now do, and one concrete example or proof point from the material. The
examples' shape governs register and pacing, as today.

### 5. Research only when it can add something

With supplied-only research and only messaging or facts sources, the research stage is
replaced by a **claims map** step that lists the claims the material makes and which
source makes each; it does not produce "not confirmed" findings about material the
team approved. Web research stays as it is.

### 6. The brief

"The point to make" gets a hint with an example of a specific point, and the research
plan reads the point as the angle. The style's register wins over the house guide's
defaults where they differ in tone; the house guide still decides mechanics.

## Out of scope

Voice learning, styles, the library, the deck path.

## Testing

Runner: messaging stance reaches the payload and the policy; `reader-facing-note` fires
on a source ID or placeholder in the draft; notes carry evidence and gaps; the claims-map
step runs instead of research for supplied-only material; Length changes the guidance.
Page: the role select offers Approved messaging; the gate shows gaps; the Length choice
on both start screens. Guidance budget and command reference checks.
