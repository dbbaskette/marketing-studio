# Deck handoff: Deck outline waits

Written by the runner from the record of this training. It is written again whenever the blueprint or the settings change.

## Goal

After the deck the audience can:

- Describe what a rolling restart does (O1)
- Explain when a rolling restart keeps capacity (O2)
- Handle the objection that rolling restarts guarantee zero downtime (O3)

## Audience and duration

Audience: solutions engineers who deploy apps but have not had to explain restart behaviour to a customer.
Duration: 25 min

## Use

The deck is both presented and handed out. Every slide must make sense to someone reading it alone, so no slide may depend on its speaker notes for meaning. The notes carry the talk track and timing for a presenter.

## Required elements

- The objectives near the start.
- A check for understanding in each module: M1, Rolling restarts.
- A recap.
- A last content slide that says what to practice next: Main, then a closing slide.

## Sources

Work from the blueprint, the learner guide and the research findings. They are your sources, not the audience's: a slide's `source` cites only what the audience can look up by name, such as a product's documentation, or is left out. Finding, objective and blueprint IDs go in the slide's `provenance`, which only the speaker notes carry.

## Research

Complete. Work from the sources only and start no new research. Anything under the blueprint's open gaps stays out.

## Output

PowerPoint, in the brand example-co (light).

## Teaching and assessment

Use the module timing for explanation, demonstration, learner practice and debrief. A slide count is not a duration plan. Give a self-paced reader a neutral question, visible evidence, time to respond, then visible feedback with rationale on a later slide. Keep learner-facing meaning visible. For every demonstration supply the prop or a labeled simulation. In a lab give setup, commands, expected observations and recovery. Rehearse the attempt before revealing the answer, then allow time to hear reasoning.

### Starting point
Prerequisite: Read status.
Likely mistake: Count B as serving.
Opening check: Which instances can serve now?
If missed: Trace one request to a serving instance before continuing.

### Shared case
Basis: K1.1, K1.2
Situation: Simulated restart during a busy period.
Observations: A serving, B restarting, C serving.
Decision: A and C retain capacity in this example.
Feedback: B is restarting. Trace the request again using only serving instances.
Variation: B is now the only instance.

- O1: Check: What happens to an app's instances during a rolling restart? | Observe: States that instances are replaced in batches.
- O2: Check: Why does a single-instance app lose capacity during a rolling restart? | Observe: Explains the more-than-one-instance condition.
- O3: Check: A customer says rolling restarts guarantee zero downtime. What do you say? | Observe: Corrects the claim without dismissing the customer and agrees a next step.
