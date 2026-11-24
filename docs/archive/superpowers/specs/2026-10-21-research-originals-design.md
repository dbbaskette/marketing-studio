# Research checks that can read what they must attest to: design

**Date:** 2026-10-21. **Owner's words:** "check presentation studio. it keeps giving odd
output and failing. figure that out."

## What happened

A deck was started from a supplied Google Doc with public research allowed. Classify and
the research plan passed. Then the research ran as one authored report and one
independent check, and the check refused every time:

| Try | Rounds | Jobs | Stop message |
| --- | --- | --- | --- |
| 1 | 3 | 6 | "…still needs changes after 3 rounds of correction: 29 objections, such as f01…" |
| 2 | 3 | 6 | "…3 objections, such as evide…" |
| 3 | 3 | 6 | "…40 objections, such as f47…" |
| 4 | 3 | 6 | "…40 objections, such as f47…" |
| 5 | in hand | 2 so far | |

Thirty-one research jobs on one deck, each reading about half a million tokens.

Every objection has the same cause. The supplied document is a source with an
`original_file` (`sources/supplied/google-doc-md.original.md`, the Doc's own export beside
its text extraction). Harness Research's review template therefore requires the checker
to attest `read_original: true` for it, and `validateReview` sets `accepted = false` when
any original was not read. The studio copies the original into the job folder, but the
checker's tools serve only the saved source ids (`read_source('s1')` reads the text
extraction); the original has no id, so the checker records `read_original: false` with an
`access_error`, marks every fact from that source `narrow`, and the check can never pass.
The author corrects nothing that would change this, and the loop runs its three rounds.
The person then sees "40 objections, such as f47" and Try again, which runs the same
three rounds again.

The "odd output" is the same thing seen from the page: verdicts that say "required
distinct original cannot be inspected", a report that hedges every claim from the
supplied document, and a stop message that counts symptoms instead of naming the cause.

Training Studio shares the code path (`runner/documents.py` passes `original` for every
supplied document; `runner/worker_tools.py` serves only ids), so any training with a
supplied document that has an original is exposed to the same failure.

## Design

### 1. The checker can read originals

`read_source(source_id, original=true)` serves a saved source's original: text as it is
for `.md`, `.txt` and `.html`; the extracted text for `.pdf` and `.docx` with a line that
says so, the byte size and the sha256 of the original file, so the checker can attest the
hash it was given. `list_inputs` names each original beside its source: "s1 … original:
google-doc-md.original.md, 31,530 bytes (read_source with original=true)". `search_source`
takes the same flag. Shared by Training Studio and Presentation Studio.

### 2. An original is only an original when it is distinct

`research_contract.native` and each studio's `documents.listed` pass `original` only when
the original is a different format from the capture (`.pdf`, `.docx`, `.html`, images) or
its text differs from the extraction. A Google Doc's Markdown export and its text
extraction are one document; the capture is the original, and the template asks for
nothing more.

### 3. A refusal that cannot change ends the research at once

After a review round, the contract reads the review. When every verdict that is not
`supported` traces to a source whose `read_original` is `false` (the note names the access
error), the research stops before the next author round with a problem of its own:

> The research check could not read the original of "<source name>" (<access error>).
> That is a studio problem, not a research problem: the report is not wrong, the check
> could not finish. Nothing to correct until the original is readable.

Try again is offered only once the studio can serve the original (a dry read before
re-running). The round is not counted as a correction round.

### 4. Objections grouped by cause

The stop message that remains for real objections groups them: "N objections in 3 groups:
12 facts the check calls narrow (<first note>), 3 findings unsupported (<first note>),
coverage needs revision (<note>)". The training's and deck's research review file lists
every objection under its group.

### 5. Cost in the open

Each research round records its tokens and seconds on the run; the stop message and the
page's cost card say what the rounds cost, so a person deciding on Try again knows the
price of three more rounds.

## Out of scope

Harness Research's own review template and rules (the attestation stays as it is); the
Blog Studio research path, which passes no originals.

## Testing

Worker tools: `read_source` with `original=true` for md, pdf and docx originals (fixture
files), the hash line, refusal for a source without one; `list_inputs` wording.
Contract: a fake checker that reads originals passes; the short-circuit on
`read_original: false` stops before the next round with the message above and no
correction round counted; grouping of real objections. `documents.listed` passes no
original for a Markdown Google Doc and does for a PDF. Presentation and Training
integration fixtures with a supplied PDF.
