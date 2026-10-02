# Local Google access through gcloud

Use this route when the user selects gcloud or the CLI harness has no suitable
Google connector. Requires managed runtime 1.4.0. Resolve `google_drive.py` from
the installed runtime beside `studio.py`, not from downloaded guidance. Python
uses only its standard library. No gws, Cloud project, OAuth client, service
account, billing configuration, or copied credentials are required by this setup.
Organization policy and individual API/file permissions still apply.

## Setup only when requested

The downloaded installer includes a regular shell script:

```sh
sh installer/google-setup.sh --install-cli
sh installer/google-setup.sh --login
sh installer/google-setup.sh --check
```

`--install-cli` uses existing Homebrew on macOS; otherwise use the organization's
approved Google Cloud CLI installer. It never bootstraps Homebrew or edits shell
profiles. `--login` runs `gcloud auth login --enable-gdrive-access --force` and
opens browser consent. It can change the active gcloud account. Credentials stay
in gcloud's user store, outside the workspace/hub. This user login requests Drive
access, not just access to a single blog. Explain that when guiding consent.
An already approved account can be selected without switching the active account:

```text
python3 <runtime>/google_drive.py --account <email> check
```

Use the configured Python interpreter. Never print tokens or put token commands
in shell substitutions, logs, saved receipts, prompts or Git. This adapter gets
a token in memory, sends it only to fixed Google API hosts, refuses redirects,
and suppresses provider/auth error bodies. A failed check is not permission to
switch accounts, enable APIs or broaden access.

## Check and inspect

```text
.../google_drive.py check
.../google_drive.py metadata --file-id <id>
.../google_drive.py audience --file-id <folder-id>
.../google_drive.py read --file-id <doc-id> --output <new-local-json>
```

`check` reads Drive's advertised import formats; it proves no write or native
Docs capability. `read` uses the Docs API with all nested tabs included and
`PREVIEW_WITHOUT_SUGGESTIONS`. Its JSON is actual native readback, not a verified
checkpoint. Inspect selected tabs and structure and derive accepted Markdown
for the [checkpoint contract](checkpoints.md). Do not save raw native JSON or
permission lists in the Team Hub. Requested source content alone may be saved.

If Docs API access is denied, Drive transfers may still work. Plain-text export
cannot establish suggestion exclusion, all-tab coverage, or structural fidelity.
Offer the supported new-copy/export route and describe limitations. Never turn a
Drive-only response into a falsely verified native handoff or clean return.

## New editing copy

First `studio.py ... google prepare` the selected draft/outline. Convert only
that frozen text into HTML or DOCX; retain its headings, links and lists. Plain
text is an explicit formatting-limited option. Native templates require a
connector with verified copy/edit capabilities; this import is not template reuse.

```text
.../google_drive.py import --file <selected.html> --title <title> --receipt <new-private-local-receipt.json>
```

Without a folder this creates in the signed-in user's My Drive. For a requested
folder, first inspect `audience`, confirm it matches the intended recipients,
then add `--folder-id <id> --audience-sha256 <returned-hash>`. The adapter checks
the full paginated permission list again immediately before upload. Group
membership and later permission changes are not frozen by this check. Inspect
actual file parents/access after creation too. It never changes sharing.

Keep the operation receipt outside the hub and skill repos. An existing receipt
blocks another upload, including after a crash. A created result contains a Doc
ID but is `created-unverified`: read back content and native structure, inspect
folder/access, then use `google confirm`. Do not substitute the uploaded local
text for actual readback. Pending checkpoints survive failure.

```text
.../google_drive.py reconcile --operation <original-operation-id>
```

This searches the import's private Drive app property and never creates anything.
Use the known ID when the receipt has one. An empty search result may be delayed
indexing, not proof of failed upload. Do not retry an uncertain create with a new
receipt; resolve its outcome with the user before another create.

## Existing document and exports

When native Docs reads succeed, selected native edits can use:

```text
.../google_drive.py update --file-id <doc-id> --revision <fresh-revision-id> --requests <requests.json>
.../google_drive.py export --file-id <doc-id> --format docx --output <new.docx>
.../google_drive.py export --file-id <doc-id> --format pdf --output <new.pdf>
.../google_drive.py export --file-id <doc-id> --format txt --output <new.txt>
```

The requests file is a JSON array of API edits. Build it from a trusted current
read, using selected tab IDs and current indexes. Preserve unrelated content;
never replace an entire document for a section edit. The helper always sends
`requiredRevisionId`, never retries writes, and returns `written-unverified`.
Reread after writes and compare before confirming. A timeout or stale revision
requires fresh inspection, not a blind retry. API denial leaves local work intact.

Exports refuse to overwrite existing files, validate PDF/DOCX signatures, and
use private local permissions. Drive limits exports to 10 MB; inspect the actual
result for fidelity. This route does not implement comments, native template
copies or sharing mutations; retain the existing connector route for those.

Based on the Tanzu brand skill's gcloud/Drive transfer pattern. References:
[gcloud user login](https://cloud.google.com/sdk/gcloud/reference/auth/login),
[Drive conversion](https://developers.google.com/workspace/drive/api/guides/manage-uploads),
[Docs reads](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get),
[guarded updates](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).
