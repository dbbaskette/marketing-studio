# Google gcloud adapter validation — 2026-10-02

Implemented the gcloud user-login/Drive API pattern from the installed Tanzu brand
skill. Runtime 1.4.0 adds a standard-library Python transport and a regular shell
setup script. No custom OAuth client, Cloud project, billing or service-account
setup is performed. Existing writing pins and prior runtime versions are retained.

## Evidence

- Full relevant suite: 139 tests passed in Tart with Python 3.13.16 (88.266s).
- Subsequent offline/noninteractive installer guards, response-object validation,
  and packaged Google guidance were verified with affected suites: 10 transport,
  21 installer, and 1 extracted-bundle tests passed. This includes two new installer
  tests added after the full run; unchanged hub/writing checks were not repeated.
- Both skill frontmatter validators, package integrity/link/provenance validation,
  guidance token inventory, shell syntax and `git diff --check` passed.
- Tart test VM: Google Cloud CLI installed through Homebrew. Candidate runtime
  `1.4.0-08f048f1ab1a` installed for both harnesses; installer integrity check passed.
- User-facing setup bundle is in guest `~/Downloads/Blog-Studio-Google-1.4.0`.
  Sign-in is user-driven through `installer/google-setup.sh --login`.

## Covered behavior

Token/auth/provider-error redaction; fixed HTTPS API hosts and refused redirects;
all-page folder audience checks; native multipart imports; private local receipts;
no duplicate upload from a reused receipt; read-only uncertain-upload reconciliation;
all-tab native reads excluding suggestions; required revision guards; no write
retries; PDF/DOCX export format checks and refused local overwrites; offline and
JSON/noninteractive installer paths never initiating sign-in.

## Remaining live acceptance

User Google sign-in, real Drive access and import/export, native Docs availability,
selected-tab fidelity, revision rejection, readback/checkpoint integration, and
Codex/Claude session discovery must still be verified with a selected disposable
Doc. No real Google document was created or changed by these tests. Drive login
alone is not evidence of native Docs read or write access. Comments, native
copies and sharing remain connector operations. See the existing G4 pilot.
