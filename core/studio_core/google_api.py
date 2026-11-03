"""Small fixed-destination Google Drive/Docs transport using explicit existing gcloud login.

Google Slides decks are read as a Drive PowerPoint export, never through the Slides
API, which a gcloud sign-in cannot call without a quota project.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

DOC_MIME = "application/vnd.google-apps.document"
SLIDES_MIME = "application/vnd.google-apps.presentation"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
LIMIT = 40_000_000
ERROR_LIMIT = 65_536
SERVICES = {
    "slides.googleapis.com": "the Google Slides API",
    "docs.googleapis.com": "the Google Docs API",
    "drive.googleapis.com": "the Google Drive API",
}
SCOPE_REASONS = {"ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficientPermissions"}
DISABLED_REASONS = {"SERVICE_DISABLED", "accessNotConfigured"}
NO_PERMISSION_REASONS = {
    "forbidden",
    "cannotExportFile",
    "insufficientFilePermissions",
    "appNotAuthorizedToFile",
}
RATE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "RATE_LIMIT_EXCEEDED"}
EMAIL = re.compile(r"[^@\s/]{1,64}@[^@\s/]{1,180}\.[^@\s/]{1,60}\Z")


class GoogleError(ValueError):
    def __init__(self, message, *, status=None, uncertain=False):
        super().__init__(message)
        self.status, self.uncertain = status, uncertain


def account(value):
    if not isinstance(value, str) or len(value)>254 or any(ord(c)<32 or ord(c)==127 for c in value) or not EMAIL.fullmatch(value):
        raise GoogleError(
            "Choose the email of your existing Google account before this action."
        )
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value):
        raise GoogleError("Use a valid Google file identity.")
    return value


def executable(which=shutil.which):
    found = which("gcloud")
    if found:
        return found
    from pathlib import Path

    for path in (
        Path("/opt/homebrew/share/google-cloud-sdk/bin/gcloud"),
        Path("/usr/local/share/google-cloud-sdk/bin/gcloud"),
        Path.home() / "google-cloud-sdk/bin/gcloud",
    ):
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise GoogleError(
        "Google access needs an explicitly installed gcloud CLI. Local PDF delivery remains available."
    )


def active_account(*, run=subprocess.run, which=shutil.which):
    """Read only the locally selected gcloud account, on an explicit Google action."""
    binary = executable(which)
    try:
        done = run(
            [binary, "config", "get-value", "account", "--quiet"],
            capture_output=True,
            text=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
        )
        if done.returncode:
            raise ValueError()
        return account(done.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        raise GoogleError(
            "Google is not signed in with a usable default account. Use the same existing Google sign-in as Blog Studio; no email is needed in this form."
        ) from None


def access_token(selected=None, *, run=subprocess.run, which=shutil.which):
    if selected:
        account(selected)
    selected_executable = executable(which)
    if not selected_executable:
        raise GoogleError(
            "Google access needs an explicitly installed gcloud CLI. Local PDF delivery remains available."
        )
    try:
        done = run(
            [
                selected_executable,
                "auth",
                "print-access-token",
                "--quiet",
                *(["--account", selected] if selected else []),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        raise GoogleError(
            "The local Google sign-in could not be read. Check gcloud access for the selected account."
        ) from None
    value = done.stdout.strip()
    if (
        done.returncode
        or not value
        or len(value) > 8192
        or any(c.isspace() for c in value)
    ):
        raise GoogleError(
            "Google authentication is unavailable for the selected account. Sign in explicitly with Drive access; no write was sent."
        )
    return value


def refusal(body, selected=None):
    """A precise sentence for Google's 403 error body, or None for an unknown reason.

    Only Google's fixed reason codes and a validated service host are read; no
    token, message text or raw response goes into the sentence.
    """
    try:
        error = json.loads(bytes(body[:ERROR_LIMIT]).decode("utf-8")).get("error")
    except (TypeError, ValueError, UnicodeError, AttributeError):
        return None
    if not isinstance(error, dict):
        return None
    status = error.get("status") if isinstance(error.get("status"), str) else ""
    items = [
        item
        for key in ("errors", "details")
        if isinstance(error.get(key), list)
        for item in error[key][:50]
        if isinstance(item, dict)
    ]
    reasons = {item.get("reason") for item in items if isinstance(item.get("reason"), str)}
    said = error.get("message") if isinstance(error.get("message"), str) else ""
    if reasons & SCOPE_REASONS:
        email = selected if isinstance(selected, str) and EMAIL.fullmatch(selected) else "you@example.com"
        return (
            "This Google sign-in was not given the access this needs. Sign in again with "
            "Drive access by running `gcloud auth login " + email
            + " --enable-gdrive-access --force --no-activate` in a terminal, then try again."
        )
    if reasons & DISABLED_REASONS or "quota project" in said.lower():
        hosts = [
            item["metadata"].get("service")
            for item in items
            if isinstance(item.get("metadata"), dict)
        ]
        host = next(
            (
                value
                for value in hosts
                if isinstance(value, str)
                and re.fullmatch(r"[a-z0-9-]{1,60}\.googleapis\.com", value)
            ),
            None,
        )
        service = SERVICES.get(host, host or "this Google service")
        return (
            "Google has not enabled " + service + " for the sign-in's project, so it refused this request."
            + ("" if host == "drive.googleapis.com"
               else " Reads through Google Drive are unaffected. Upload a copy instead.")
        )
    if "exportSizeLimitExceeded" in reasons:
        return (
            "This file is larger than Google Drive can export (10 MB). Download it as a "
            "PDF and upload that copy instead."
        )
    if reasons & RATE_REASONS:
        return "Google is limiting requests. Keep the saved intent and retry an explicit read later."
    if reasons & NO_PERMISSION_REASONS or (status == "PERMISSION_DENIED" and not reasons):
        return (
            "This Google account cannot open this file. Ask its owner to share it with "
            "this account, or upload a copy instead."
        )
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict
    data: bytes


def fixed_url(value):
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise GoogleError("Use a bounded fixed Google API destination.")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        raise GoogleError("Use a fixed Google API destination.") from None
    allowed = (
        (
            parsed.netloc == "www.googleapis.com"
            and (
                parsed.path.startswith("/drive/v3/")
                or parsed.path == "/upload/drive/v3/files"
            )
        )
        or (
            parsed.netloc == "docs.googleapis.com"
            and parsed.path.startswith("/v1/documents/")
        )
    )
    decoded = urllib.parse.unquote(parsed.path)
    if (
        any(part.split(";")[0] in (".", "..") for part in decoded.split("/"))
        or "\\" in decoded
    ):
        raise GoogleError("Use a fixed Google API path.")
    if (
        parsed.scheme != "https"
        or not allowed
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise GoogleError(
            "Google credentials may go only to the fixed Drive and Docs APIs."
        )
    return value


class Client:
    def __init__(
        self,
        selected_account=None,
        *,
        token_provider=access_token,
        transport=None,
        account_provider=active_account,
    ):
        self.account = (
            account(selected_account) if selected_account not in (None, "") else None
        )
        self.account_provider = account_provider
        self.token_provider, self.transport, self._token = (
            token_provider,
            transport,
            None,
        )
        self.opener = urllib.request.build_opener(NoRedirect())

    def selected_account(self):
        if self.account is None:
            self.account = account(self.account_provider())
        return self.account

    def request(self, url, *, method="GET", body=None, headers=None, json_result=True):
        fixed_url(url)  # Before even looking up credentials.
        if method not in ("GET", "POST", "PUT"):
            raise GoogleError(
                "This adapter supports selected reads and new-document creation only."
            )
        payload = (
            json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
            if isinstance(body, dict)
            else body
        )
        if payload is not None and (
            not isinstance(payload, bytes) or len(payload) > LIMIT
        ):
            raise GoogleError("Google transfer exceeds its bounded size.")
        if self._token is None:
            self._token = self.token_provider(self.selected_account())
        sent = {
            "Content-Type": "application/json",
            **(headers or {}),
            "Authorization": "Bearer " + self._token,
        }
        try:
            if self.transport:
                response = self.transport(method, url, sent, payload)
            else:
                request = urllib.request.Request(
                    url, data=payload, method=method, headers=sent
                )
                with self.opener.open(request, timeout=45) as handle:
                    response = Response(
                        handle.status,
                        {k.lower(): v for k, v in handle.headers.items()},
                        handle.read(LIMIT + 1),
                    )
            if len(response.data) > LIMIT:
                raise GoogleError(
                    "Google response exceeded its transfer limit.",
                    uncertain=method != "GET",
                )
            if not 200 <= response.status < 300:
                self.refuse(response.status, method, response.data, account=self.account)
            if not json_result:
                return response
            value = json.loads(response.data)
            if not isinstance(value, dict):
                raise ValueError("shape")
            return value
        except urllib.error.HTTPError as failure:
            try:
                body = failure.read(ERROR_LIMIT)
            except (OSError, ValueError):
                body = b""
            finally:
                failure.close()
            self.refuse(failure.code, method, body, account=self.account)
        except GoogleError:
            raise
        except (OSError, ValueError, UnicodeError):
            raise GoogleError(
                "Google response was unavailable or invalid. Reconcile this request before repeating any write.",
                uncertain=method != "GET",
            ) from None

    @staticmethod
    def refuse(status, method, body=b"", *, account=None):
        message = {
            401: "Google sign-in expired for the selected account.",
            403: "The selected Google account lacks access, download permission or the required API scope.",
            404: "This Google document or destination is unavailable to the selected account.",
            429: "Google is limiting requests. Keep the saved intent and retry an explicit read later.",
        }.get(
            status,
            "Google refused this transfer. Existing local work and deliveries are kept.",
        )
        if status == 403:
            message = refusal(body, account) or message
        raise GoogleError(
            message,
            status=status,
            uncertain=method != "GET"
            and (status >= 500 or status in (301, 302, 303, 307, 308, 408)),
        )

    def file(self, file_id):
        fields = "id,name,mimeType,version,modifiedTime,trashed,capabilities(canDownload,canAddChildren)"
        return self.request(
            "https://www.googleapis.com/drive/v3/files/"
            + identifier(file_id)
            + "?"
            + urllib.parse.urlencode({"supportsAllDrives": "true", "fields": fields})
        )

    def document(self, file_id):
        return self.request(
            "https://docs.googleapis.com/v1/documents/"
            + identifier(file_id)
            + "?includeTabsContent=true"
        )

    def export_presentation(self, file_id):
        """The deck as PowerPoint bytes through Drive; the Slides API is never called."""
        return self.request(
            "https://www.googleapis.com/drive/v3/files/"
            + identifier(file_id)
            + "/export?"
            + urllib.parse.urlencode({"mimeType": PPTX_MIME}),
            json_result=False,
        ).data

    def find_delivery(self, request_key):
        identifier(request_key)
        query = (
            "trashed = false and appProperties has { key='infographic_request' and value='"
            + request_key
            + "' }"
        )
        found = self.request(
            "https://www.googleapis.com/drive/v3/files?"
            + urllib.parse.urlencode(
                {
                    "q": query,
                    "fields": "files(id,name,mimeType,appProperties),nextPageToken",
                    "pageSize": "100",
                }
            )
        )
        if found.get("nextPageToken") or not isinstance(found.get("files"), list):
            raise GoogleError(
                "Google delivery lookup was incomplete. Reconcile explicitly before any new write."
            )
        return found["files"]

    def create_document(
        self, payload, *, title, request_key, payload_hash, folder=None
    ):
        identifier(request_key)
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise GoogleError("Choose a bounded Google document title.")
        metadata = {
            "name": title,
            "mimeType": DOC_MIME,
            "appProperties": {
                "infographic_request": request_key,
                "infographic_payload": payload_hash,
            },
        }
        if folder:
            selected = self.file(identifier(folder))
            if (
                selected.get("trashed")
                or selected.get("mimeType") != "application/vnd.google-apps.folder"
                or selected.get("capabilities", {}).get("canAddChildren") is not True
            ):
                raise GoogleError("Choose a writable Google Drive destination folder.")
            metadata["parents"] = [folder]
        # One initiation and one upload, never automatic write replay. The session URL
        # exists only in memory. A lost response is reconciled by application identity.
        start = self.request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true&fields=id,mimeType,name,appProperties",
            method="POST",
            body=metadata,
            headers={
                "X-Upload-Content-Type": DOCX_MIME,
                "X-Upload-Content-Length": str(len(payload)),
            },
            json_result=False,
        )
        location = {k.lower(): v for k, v in start.headers.items()}.get("location")
        try:
            fixed_url(location)
        except (GoogleError, TypeError):
            raise GoogleError(
                "Google did not return a usable private upload session. Reconcile the saved delivery intent.",
                uncertain=True,
            ) from None
        parts = urllib.parse.urlsplit(location)
        query = urllib.parse.parse_qs(parts.query)
        if (
            parts.netloc != "www.googleapis.com"
            or parts.path != "/upload/drive/v3/files"
            or len(query.get("upload_id", [])) != 1
            or query.get("uploadType") != ["resumable"]
        ):
            raise GoogleError(
                "Google returned an unexpected upload session. No content was sent to it.",
                uncertain=True,
            )
        return self.request(
            location,
            method="PUT",
            body=payload,
            headers={"Content-Type": DOCX_MIME, "Content-Length": str(len(payload))},
        )
