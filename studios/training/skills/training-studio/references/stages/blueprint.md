# Blueprint

Design backward from the learner's task to observable success, then the teaching. Follow the example's headings, IDs and line prefixes.

## Frame and sizing

Give the audience, purpose, time, task and format. A workshop adds a realistic scenario. For a comparison, name both sides. For a level, add `Level: 301` and prerequisites. A lesson usually fits five objectives and 45 minutes; a course has two to six modules. Beyond that propose a split. Honor the approved objectives, order and time budget.

## Objectives and modules

Use `### O<n> — <behavior> [<level>]`. Levels are recall, explain, apply and handle. Under each `## M<n> — <title> (<minutes> min)` put one item per line:

- `Objectives: O1, O2`.
- `- K1.1: <claim> [R:<finding-id>]`. Cite supported findings and preserve applicable conditions.
- Use `[stated]` for attributed positioning, local policy or an explicit exercise assumption. Put an unsupported technical capability under `[unsupported]` and in Open gaps.
- `Misconception: "<belief>" Correction: <correction> [R:<finding-id>]`. A correction may cite a contradicted finding.
- `Hook:` consequence. `Example:` worked observation. `Ask:` question for the participant. `Listen for:` evidence of understanding. Research questions guide the author.
- Workshops add `Activity: <minutes> min. <task>. Output: <product>. Good answer: <criteria>`. Label simulations. Put a material research limit in the learner decision or instructor preflight, or omit the dependent claim.

## Assessment, practice and gaps

Under Assessment plan give each objective a fresh case: `- O1: Check: <question> | Observe: <behavior>`. Budget time to attempt, explain and debrief.

Under Practice plan use `- <scenario-id>: <mode>. Objectives: O2, O3. <role>`. Modes are roleplay, pitch, tutor and questionnaire. Use roleplay or pitch for handle objectives. List existing scenarios when supplied; omit the section if scenarios were skipped.

Under Open gaps name every unresolved question affecting instruction, unsupported key point ID and resulting omission.

## Gate 3

Write `blueprint.md`, run `training.py save blueprint --built` and `training.py check`, then fix failures. Present the gate. On approval run `training.py approve blueprint` for each applicable level.
