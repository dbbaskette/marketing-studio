# The page

New work uses [checked desk commands](conversation.md) for scoped plans and edits. [Design answers](answers.md) must come from the person. Below is the saved-work path; `training.py desk` still serves it.

A page in the user's browser: where every training on this computer stands. A saved record is not continued here: if `training.py status` or the page says the training is one, use Bring it in, Open on the desk or Start new work from this, as its page offers.

## Open it

Run `training.py desk` as a long-running background command; it serves until stopped. It opens the page in the user's browser itself and prints one line of JSON. If `opened` is false, give the user the command instead. Stop it when they are done, and before the session ends.

## What the user tells you

What the page showed is not evidence: run `training.py status` or `check` and act on that. The page gives the user a sentence naming a training's folder. If that is not the current directory, ask them to start you there.
