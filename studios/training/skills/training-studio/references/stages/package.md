# Package

The last stage reports whether the training is ready.

## Check readiness

Run `training.py check --complete --all` and `training.py status`.

- `ready` is true only when every wanted artifact is approved, nothing is stale, no check failed or could not run, no copy is out of date, and no question is waiting on the user.
- `blocking` lists each reason it is not ready.
- `limitations` lists what was skipped at the user's request or could not be produced.

If `ready` is false, resolve what you can, tell the user what remains, and do not describe the training as complete.

## The index

Training Studio writes the index, `README.md`, itself, and only when its runner runs the training and every requested material is Ready. Never write or save it by hand. Desk work in a conversation gets no index: it is handed to the runner (`studio desk handoff`, as the conversation reference describes) only with a runner research contract, which research submitted in the conversation does not give.

Desk work in a conversation does not reach `ready` either: no checked operation records the deck's coverage review or makes the copies, so `blocking` keeps naming them. Say so; do not work around it.

## Report

Tell the user in a few lines: what was produced, whether it is ready, what is blocking, the limitations and the open gaps.

A saved record is not continued here: if `training.py status` or the page says the training is one, use Bring it in, Open on the desk or Start new work from this, as its page offers.

## Afterwards

If Yoodli was used: when the user reports how a paste into Yoodli went, note each field name or limit that differed. A successful paste confirms the fields were accepted. It says nothing about factual grounding or the quality of the goals.

Corrections belong in the skill's `assets/profiles/yoodli.json` and its Yoodli profile reference, which are changed in the skill's repository, not from a training directory. Tell the user what to change there.

Offer the blueprint's one-page job aid for a repeatable task. After personal approval, select it in Infographic Studio under Import selected studio material. Review steps, evidence and exceptions, then choose print or accessible text.
