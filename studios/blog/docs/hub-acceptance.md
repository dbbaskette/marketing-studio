# Test a complete Hub workflow

For substantial workflow or storage changes, use both the automated suite and a
command walkthrough. The walkthrough creates a new private GitHub test repository
and installs the current package into two isolated homes. Only fictional source,
voice, blog and review documents are posted. Existing installations and Hubs are
untouched. It checks readable folders and history, a second clone's resume/edit,
offline saves and retry, status, migration with queued work, and protection for
unsaved checkout edits.

With explicit authorization to create the named test repository, run:

```sh
python3 scripts/acceptance/hub-journey.py --live \
  --repo OWNER/NEW-PRIVATE-TEST-REPO \
  --run-directory /absolute/new/test-run-directory
```

The existing authenticated GitHub CLI account needs private repository creation
and write access. Every command and exit code is recorded in `report.json`.
Both local fixtures and the private remote remain available for inspection;
cleanup is a separate explicit operation. This tests two local clones using one
account, not two identities or live Google Docs. Never replace fictional content
with production drafts or attach credentials to the test repository.

Use `--join-existing` to repeat against the same authorized private test Hub.
Each run uses uniquely titled synthetic blogs. `--resume` is limited to failed
setup before document creation; later failures require inspection of the recorded
commands and preserved fixtures.
