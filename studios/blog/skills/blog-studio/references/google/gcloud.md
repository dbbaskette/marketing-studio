# Local Google access through gcloud

Use this route when the user selects gcloud or the CLI harness has no suitable
Google connector. Resolve `google_drive.py` from the installed runtime beside
`studio.py`, not from downloaded guidance. Python uses only its standard library.
No gws, Cloud project, OAuth client, service account, billing configuration, or
copied credentials are required by this setup. Organization policy and individual
API/file permissions still apply.

## Setup only when requested

The downloaded installer includes a regular shell script:

```sh
sh installer/google-setup.sh --install-cli
sh installer/google-setup.sh --login you@example.com
sh installer/google-setup.sh --check you@example.com
```

`--install-cli` uses existing Homebrew on macOS; otherwise use the organization's
approved Google Cloud CLI installer. It never bootstraps Homebrew or edits shell
profiles. `--login <email>` runs `gcloud auth login <email> --enable-gdrive-access
--force --no-activate` and opens browser consent: the named account is added and
the account gcloud already uses stays active. Add `--activate` only when the user
asks to switch gcloud's active account. Without an email, login proceeds only when
gcloud has no account yet; otherwise it stops and asks for the email, so an
existing sign-in is never replaced silently. Credentials stay in gcloud's user
store, outside the workspace/hub.

State the real scope when guiding consent. This sign-in grants the Google Cloud
CLI on this computer what every `gcloud auth login` requests (access to the
account's Google Cloud resources) plus full Google Drive access: it can see,
edit, create and delete every Drive file the account can reach, not just one
blog. Google's consent screen is the authority on the exact list. Blog Studio's
helpers call only the Drive and Docs APIs with that access, read only the files
named to them, and write only to Docs linked to a blog in the workspace.

Remember the account for a workspace once; every helper started with `--root
<workspace>` then uses it without `--account` and without switching gcloud:

```text
python3 <runtime>/google_drive.py --root <workspace> account --set <email>
python3 <runtime>/google_drive.py --root <workspace> check
```

The helper's own `login --account <email>` (run with `--root`) signs in the same
way and remembers the account. The setup script cannot know the workspace, so
after a login through it, or when the user says “Use <email> for Google Docs,”
set the account as above. If `check` reports `gcloud active account` for a user
who signed in a named account, ask which account to use and set it. Only the email address is stored, in a local
dot-file that is never sent to a Hub. An explicit `--account` overrides it for
one command.

Use the configured Python interpreter. Never print tokens or put token commands
in shell substitutions, logs, saved receipts, prompts or Git. This adapter gets
a token in memory once per command, sends it only to fixed Google API hosts,
refuses redirects, and suppresses provider/auth error bodies. A failed check is
not permission to switch accounts, enable APIs or broaden access.

## Check and inspect

```text
.../google_drive.py --root <workspace> check
.../google_drive.py --root <workspace> metadata --file-id <id>
.../google_drive.py --root <workspace> audience --file-id <folder-id>
.../google_drive.py --root <workspace> read --file-id <doc-id>
```

`check` reads Drive's advertised import formats; it proves no write or native
Docs capability. `read` uses the Docs API with all nested tabs included and
`PREVIEW_WITHOUT_SUGGESTIONS`, and saves the JSON in the workspace's staging
folder. Its JSON is actual native readback, not a verified checkpoint. For a
linked blog or a starting manuscript, use the capture in
[round trips](roundtrip.md) instead: it produces the observation, Markdown and
snapshot together. Raw native JSON and permission lists never go to the Team
Hub: the helpers keep native JSON on this computer and share only text, DOCX and
fingerprints. Requested source content alone may be saved.

Captures, plans, findings and receipts default to `<workspace>/.google-staging/`,
a private folder that is never shared. A capture is removed when its checkpoint
is saved and a review plan when its submission is verified; anything left over
is swept after a week. Clear it at any time, and always as part of “Clear local
caches”:

```text
.../google_drive.py --root <workspace> staging --clear
```

If Docs API access is denied, Drive transfers may still work. Plain-text export
cannot establish suggestion exclusion, all-tab coverage, or structural fidelity.
Offer the supported new-copy/export route and describe limitations. Never turn a
Drive-only response into a falsely verified native handoff or clean return.

## Reading errors

Reads are repeated automatically after a rate limit, a server error or a dropped
connection; writes are sent once. “Not found or not shared with <account>” means
the link or the Doc's sharing is wrong for that account, not that anything was
written. An error that says a write may have completed needs the read-only
verify or reconcile step named in it; an error that says nothing was written
needs only its cause fixed.

## New editing copy

First `studio.py ... google prepare` the selected draft/outline. Convert only
that frozen text into HTML or DOCX; retain its headings, links and lists. Plain
text is an explicit formatting-limited option. Native templates require a
connector with verified copy/edit capabilities; this import is not template reuse.

```text
.../google_drive.py --root <workspace> import --file <selected.html> --title <title>
```

Without a folder this creates in the signed-in user's My Drive. For a requested
folder, first inspect `audience`, confirm it matches the intended recipients,
then add `--folder-id <id> --audience-sha256 <returned-hash>`. The adapter checks
the full paginated permission list again immediately before upload. Group
membership and later permission changes are not frozen by this check. Inspect
actual file parents/access after creation too. It never changes sharing.

The operation receipt goes to staging, one per file, title and folder, so
repeating the same import is stopped, including after a crash. A sign-in problem
or an upload Google refuses outright leaves no receipt and reports its own
cause. A created result contains a Doc ID but is `created-unverified`: capture
the new Doc, inspect folder/access, then use `google confirm`. Do not substitute
the uploaded local text for actual readback. Pending checkpoints survive failure.

```text
.../google_drive.py --root <workspace> reconcile --operation <original-operation-id>
```

This searches the import's private Drive app property and never creates anything.
Use the known ID when the receipt has one. An empty search result may be delayed
indexing, not proof of failed upload. Do not retry an uncertain create with a new
receipt; resolve its outcome with the user before another create.

## Existing document and exports

For formatted shared editing, use [round trips](roundtrip.md): DOCX and Markdown
snapshots plus guarded wording patches that preserve paragraph styling.

For a structural edit that wording patches cannot express, a raw native update
exists, and for requested files there are exports:

```text
.../google_drive.py --root <workspace> update --file-id <doc-id> --revision <fresh-revision-id> --requests <requests.json>
.../google_drive.py --root <workspace> export --file-id <doc-id> --format docx --output <new.docx>
.../google_drive.py --root <workspace> export --file-id <doc-id> --format pdf --output <new.pdf>
.../google_drive.py --root <workspace> export --file-id <doc-id> --format txt --output <new.txt>
.../google_drive.py --root <workspace> export --file-id <doc-id> --format md --output <new.md>
```

`update` changes only a Doc that a blog in the workspace is linked to;
`--first-handoff` is the explicit exception for a new editing copy that is not
linked yet. The requests file is a JSON array of API edits. Build it from a
trusted current read, using selected tab IDs and current indexes. Preserve
unrelated content; never replace an entire document for a section edit. The
helper always sends `requiredRevisionId`, never retries writes, and returns
`written-unverified`. Reread after writes and compare before confirming. A
timeout or stale revision requires fresh inspection, not a blind retry. API
denial leaves local work intact.

Exports refuse to overwrite existing files, validate PDF/DOCX signatures, and
use private local permissions. Drive limits exports to 10 MB; inspect the actual
result for fidelity. The base transfer helper does not implement native template
copies or sharing mutations; retain the existing connector route for those.

Based on the Tanzu brand skill's gcloud/Drive transfer pattern. References:
[gcloud user login](https://cloud.google.com/sdk/gcloud/reference/auth/login),
[Drive conversion](https://developers.google.com/workspace/drive/api/guides/manage-uploads),
[Docs reads](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get),
[guarded updates](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).

For “Is this the newest?” and linked-article resume, use [freshness status](status.md).
Review suggestions and comments use the separate [review helper](suggestions.md),
which calls the Docs API with this same account when a connector's schema lacks
`writeMode`.

## Diagnose authorization before changing review modes

Local gcloud credential or sandbox access failures are reported separately from
sign-in failures. Restore authorized filesystem access for local credential
denials; repeating login does not fix those. Google errors expose only bounded,
allowlisted status/reason labels. `ACCESS_TOKEN_SCOPE_INSUFFICIENT` or
`insufficientPermissions` requires consent for the intended account, not comment
fallback. On an explicit setup request, sign that account in again as above;
never broaden consent automatically.
