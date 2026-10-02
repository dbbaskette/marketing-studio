# Blog Studio setup help

| What you see | Next step |
| --- | --- |
| macOS blocks the downloaded launcher | Follow your organization's normal process for approving trusted unsigned downloads. This release is a terminal launcher, not a signed native app. |
| Python or Git is missing | Follow the vendor link in setup, then reopen it. Python must be 3.11 or later. |
| GitHub sign-in succeeded but access fails | Confirm your account can open the private repository. Membership, organization approval, and credentials are separate checks. |
| Repository check times out | Check connectivity and your Git credentials. Retry; existing article pins are preserved. |
| Skill is missing in chat | Open a new local session and use the harness's skill picker/invocation. Run installer `check` to inspect links. File placement alone does not verify discovery. |
| Duplicate Blog Studio entries | Back up legacy/manual copies outside the harness discovery roots before using the managed installer. |
| Existing skill needs a backup | Review the folder, then explicitly choose `install --replace`; setup keeps a sibling backup. |
| Runtime/configuration verification failed | Download an intact trusted bundle and run `repair`. The damaged version is retained. |
| Guidance needs a newer runtime | Rerun setup from a newer trusted bundle. A writing task cannot execute a runtime update fetched from Git. |
| Saved guidance changed | Restore an intact saved snapshot or deliberately start/adopt a new guidance task. Do not edit pinned files to bypass the check. |
| Another installer or sync is running | Wait for that operation to finish. If a process crashed, verify it has stopped before removing only its stale `.install.lock` or `.sync.lock`. |
| A discovery link was changed outside setup | Inspect and preserve that folder/link. Setup refuses to remove an unowned target. |
| Rollback rejects a damaged old version | Use `repair` with an intact bundle instead. |

For diagnostics, run `python3 installer/install.py check --json` from the installer download. Add `--offline` to inspect only local state. Diagnostics deliberately omit Git stderr and credentials. If asking for help, provide the reported status; do not paste access tokens or a credential-bearing URL.

Guidance cache lives under the selected author workspace's `task-context/`. Articles, profiles, drafts, and sources live alongside it. Uninstalling discovery links preserves those files. No real writing data needs to be deleted to fix an installation.

## Team Hub work

- **Missing helper/incompatible instructions:** update with the trusted 1.1.0 installer; downloading guidance does not upgrade executable code.
- **Private hub unavailable:** confirm access and GitHub CLI sign-in to your own account; team membership is administered outside the skill.
- **Queued or pending review:** saved work is retained locally. Retry sync after access returns, or review the returned contribution PR. Pending work reaches teammates after merge to main.
- **Competing article/rule revisions:** read each selected revision and make an explicit resolution; do not overwrite either history.
- **Unshared local edits block resume:** save/share those selected edits first, or use a separate writing workspace. Clean imported copies can advance to the latest shared head.
- **Imported guidance not restored:** restore the saved approved commit with `sync_guidance.py pin`, then bind its returned task. Missing historical guidance remains an explicit limitation.

See [Team Hub](team-hub.md) for the short setup flow.
