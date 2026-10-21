---
name: Technical deep dive
summary: Problem, approach, trade-offs, what was measured, what is still open.
---
# Technical deep dive

A long read for practitioners who want to understand how something works and why it
was built that way. It earns trust by showing its reasoning and its numbers.

## Shape

1. **Opening**: the problem in concrete terms, why the obvious approaches fall short,
   and what the piece will show. A reader should know in the first screen whether this
   is their problem.
2. **Context**: the constraints that shaped the design: scale, latency, cost, compatibility,
   team. Only what the later decisions depend on.
3. **Approach**: the design, from the whole to the parts. Diagrams or code where they
   carry meaning; prose where they do not. Each section states a decision and the
   alternative it was chosen over.
4. **Trade-offs**: what got worse, what was given up, and where the design does not apply.
5. **What was measured**: the method, the setup, the numbers and their spread. A result
   without its conditions is not a result.
6. **What is still open**: unsolved parts, next experiments, questions for readers.

## Length and register

1,500 to 3,000 words, with headings a reader can jump between. Precise and plain;
technical terms defined on first use; confident where the evidence is, and explicit
where it is not.

## A reader expects

- Decisions with their alternatives, not just a description of the end state.
- Numbers with conditions and units.
- Enough detail to reproduce the thinking, not necessarily the whole system.

## Does not belong

- A product pitch in the conclusion.
- Hand-waving where a measurement was possible.
- Benchmarks against unnamed or misconfigured competitors.
