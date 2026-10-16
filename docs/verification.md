# Initial implementation verification

Application commit: `047e8c3f89781317d09bf4472f55f2265ce03670`.
The subsequent verification commit adds this record and a reusable acceptance
script; it does not change the application.

- Full `scripts/ci/check.sh`: 27 tests passed on the development Mac.
- Full disposable Tart run: 27 tests passed on macOS 27.0 (26A428), Python
  3.13.15, Node.js 22.23.2, and Apple Git 2.54.0. The test VM was stopped and
  deleted; results and environment logs were retained by the shared runner.
- Native setup acceptance: passed against sibling source checkouts and installed
  3.0.0 runtimes, with isolated HOME, shared config, Git identity, and data folders.
  Each studio read its saved workspace and assistant independently. A changed
  default work folder did not move existing workspaces.
- Native page acceptance: all three studio pages served successfully, repeated
  Open reused the process, and launcher cleanup stopped all three children.
  Background updates and research were disabled by test-only replacements.
- Browser review: the three-step first run reached the launch page; reloading
  retained completion; shared settings and the offline computer check worked.
  At a 390-pixel viewport, the launch and settings views had no horizontal overflow.
- Public-source credential-pattern scan and Git whitespace checks passed.

Studio source checkouts used for native acceptance:

| Studio | Revision |
| --- | --- |
| Blog Studio | `44f59e52d369d6f2cb6b90a2750b5aa98af222f8` plus pre-existing research changes |
| Presentation Studio | `edf565acd3ebc87a7c024d5c59ab17887691017a` |
| Training Studio | `de20a082f361c0505f8c0be5c389b35b76de4828` |

The Blog Studio checkout was already modified before this work. Marketing Studio
did not modify any studio source checkout. Acceptance against installed releases
also passed, independently of those working changes.

No signed-in assistant job, Google delivery, or real team repository was used in
these checks. Provider and collaboration behavior remains covered by the studios'
own verification, rather than by the launcher smoke tests.
