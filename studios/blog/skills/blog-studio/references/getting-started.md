# Setup and help inside the harness

Use the installed runtime returned by the bootstrap; offline packages use their
`scripts/`. This flow creates no article and makes no model requests.

```text
python3 <runtime>/studio.py --root <absolute-workspace> readiness --harness codex
python3 <runtime>/studio.py --root <absolute-workspace> readiness --harness claude --online
```

Run for first-use help, “check my setup,” or setup failures, not every turn.
`--online` checks private approved main with existing Git credentials, without
fetching executable code or moving article pins. Show a short ready/action-needed
summary and the specific next action; keep raw diagnostics and identities out of
chat. CLI sign-in and file integrity do not prove live skill discovery. The current
successful invocation is discovery evidence for this session only. Never start a
login, install, repair, or account change just to check readiness.

A new workspace is normal. Use the author's current writing project `.blog-studio`
or their chosen location. Name it and initialize only when saving work. Offer
[continue saved work](workspace/resume.md) or the [writing choices](entry-flows.md).
Accept uploads, pasted notes, and links in chat; no external form is required.

Google is optional. When requested, inspect this harness's actual connected tool
capabilities via the [Google router](google/workflow.md), then make an authorized
read of the selected test document. A Google Workspace skill, installed CLI, or
past receipt is not proof of a usable current connection. State unsupported actions
individually and preserve local writing. Never report “Google ready” from filenames.

Help examples: “Show my blogs,” “Continue <title>,” “Outline this; stop before the
draft,” “What do you know about this article?”, “Remember this for this article,”
“Remember this for our team,” and “Stop using that rule in this article.”
