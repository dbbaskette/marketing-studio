# Yoodli scenarios (optional)

This stage runs only when the user asked for it, which shows as `yoodli` in `settings.stages`.

- Turn it on or off at the person's request with `studio desk scope` and `"yoodli": true` or `false`, as the requests reference describes. It needs the brief and the scenarios. Files already written stay where they are.

For each approved scenario it writes `yoodli/<id>.md` (`yoodli:<id>`): the scenario laid out in the fields of Yoodli's roleplay Builder, with the brief as the AI's knowledge.

## Build

Read the Yoodli profile reference for the fields, limits and counts, and the mode reference for how that mode maps. Follow the example Yoodli scenario.

The file need not share wording with the brief, but every product fact in it must be one the brief supports.

Under each goal, outside the pasteable blocks:

- `<!-- criterion: 2 -->` names the success criterion the goal carries. Every criterion in the scenario file needs a goal; one goal may carry several.
- `<!-- assesses: O3 -->` names the objective it assesses, where one applies.

Read `studio desk context --folder PATH --target yoodli:<id>` and submit kind `text`, as the conversation reference describes; then `training.py check --all`. With this stage on, the `practice` report is taken from the goals' `assesses` comments.

## Present

For each, present the scenario and its Yoodli file together:

- which goal carries each success criterion,
- the counts against Yoodli's limits, and that the limits are provisional while `check` says so,
- whether the brief's Google Doc or export is `current`, since it is the file the user uploads,
- your judgment of whether the context and goals agree with the brief.

Each is Ready only when the person marks it so, as the completion reference describes. Marking it ready makes no copies, and no checked operation in a conversation makes them; the workspace reference says how a training the runner runs keeps them.

A saved record is not continued here: if `training.py status` or the page says the training is one, use Bring it in, Open on the desk or Start new work from this, as its page offers.

## Afterwards

If the user edits a scenario file, its Yoodli scenario becomes stale and nothing else does. Rebuild that one.

Training Studio prepares files. Creating the roleplay in Yoodli, and uploading anything to it, are the user's actions.
