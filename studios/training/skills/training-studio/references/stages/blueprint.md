# Blueprint

Follow the example. Design backward from the task.

## Frame and sizing

Give audience, task, time, format and prerequisites. Workshops add a scenario. Keep approved objectives, order and timing.

## Objectives and modules

Use `### O<n> — <behavior> [<level>]`. Levels are recall, explain, apply and handle. Under each `## M<n> — <title> (<minutes> min)` put one item per line:

- `Objectives: O1, O2`.
- `- K1.1: <claim> [R:<finding-id>]`. Cite supported findings and preserve applicable conditions.
- Use `[stated]` for attributed positioning, local policy or an explicit exercise assumption. Put an unsupported technical capability under `[unsupported]` and in Open gaps.
- `Misconception: "<belief>" Correction: <correction> [R:<finding-id>]`. A correction may cite a contradicted finding.
- `Hook:` consequence. `Example:` worked observation. `Ask:` question for the participant. `Listen for:` evidence of understanding. Research questions guide the author.
- Workshops add `Activity: <minutes> min. <task>. Output: <product>. Good answer: <criteria>`. Label simulations. Put a material research limit in the learner decision or instructor preflight, or omit the dependent claim.

Use the example's Starting point, Shared case and Job aid sections when applicable. Check each objective against the evidence shown, learner task and success criterion.

## Assessment, practice and gaps

Under Assessment plan give each objective a fresh case: `- O1: Check: <question> | Observe: <behavior>`. Budget time to attempt, explain and debrief.

Under Practice plan use `- <scenario-id>: <mode>. Objectives: O2, O3. <role>`. Modes are roleplay, pitch, tutor and questionnaire. Use roleplay or pitch for handle objectives. List existing scenarios when supplied; omit the section if scenarios were skipped.

Under Open gaps name every unresolved question affecting instruction, unsupported key point ID and resulting omission.

## Gate 3

Save with `training.py save blueprint --built`. Run `training.py check`. After approval use `training.py approve blueprint` per level.
