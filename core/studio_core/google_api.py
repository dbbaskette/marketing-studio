"""Small fixed-destination Google Drive/Docs transport using explicit existing gcloud login.

Google Slides decks are read as a Drive PowerPoint export, never through the Slides
API, which a gcloud sign-in cannot call without a quota project.

Every studio's Google requests are sent from here, so the safety rules live in one
place: a studio names the routes its token may go to (`Route`, `allowed`), the token
comes from gcloud (`print_access_token`), a request is sent once and never follows a
redirect (`send`, `exchange`, `opener`), an HTTP error answer arrives as `Refused` for
the studio to word, and only a read is ever repeated (`read_retried`). Each studio
keeps its own sentences and error type.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

DOC_MIME = "application/vnd.google-apps.document"
SLIDES_MIME = "application/vnd.google-apps.presentation"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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


def print_access_token(gcloud, *, run, account=None, quiet=True, timeout=30, **options):
    """Ask gcloud for the signed-in account's access token, once, on an explicit action.

    Returns (the token, or None when gcloud gave no usable one, the finished process).
    A failure to run gcloud at all (OSError, subprocess errors) is raised for the caller
    to word. Nothing gcloud printed is ever repeated: its output is where the token is.
    """
    done = run(
        [
            gcloud,
            "auth",
            "print-access-token",
            *(["--quiet"] if quiet else []),
            *(["--account", account] if account else []),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        **options,
    )
    value = (done.stdout or "").strip() if done.returncode == 0 else ""
    usable = bool(value) and not any(c.isspace() for c in value)
    return (value if usable else None), done


def access_token(selected=None, *, run=subprocess.run, which=shutil.which):
    if selected:
        account(selected)
    selected_executable = executable(which)
    if not selected_executable:
        raise GoogleError(
            "Google access needs an explicitly installed gcloud CLI. Local PDF delivery remains available."
        )
    try:
        value, _ = print_access_token(
            selected_executable,
            run=run,
            account=selected,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        raise GoogleError(
            "The local Google sign-in could not be read. Check gcloud access for the selected account."
        ) from None
    if value is None or len(value) > 8192:
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


# --- sending, for every studio ---------------------------------------------------------


@dataclass(frozen=True)
class Route:
    """One destination a studio sends to: a host, matched exactly ('*.example.com' is
    example.com or any name under it), a path pattern matched whole against the path as
    sent (before any decoding), and the methods it uses there."""

    host: str
    path: str
    methods: tuple


class Disallowed(GoogleError):
    """A destination outside the routes a studio named. Nothing was sent, no token read."""


class Refused(Exception):
    """Google answered with an HTTP error. `body` is the bounded part of its answer read,
    `reason` the HTTP reason phrase. The studio words what it means."""

    def __init__(self, status, reason, body):
        super().__init__("Google answered HTTP " + str(status) + ".")
        self.status, self.reason, self.body = status, reason, body


def allowed(url, method, routes):
    """True when `url` is plain https to one of `routes` with a method used there.

    No user information, port, fragment, whitespace, control character, backslash or
    dot segment is ever allowed, whatever a route's pattern says.
    """
    if (
        not isinstance(url, str)
        or len(url) > 4096
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)
    ):
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
        or "\\" in parsed.path
        or any(part in (".", "..") for part in parsed.path.split("/"))
    ):
        return False
    return any(
        method in route.methods
        and _host(route.host, parsed.netloc)
        and re.fullmatch(route.path, parsed.path)
        for route in routes
    )


def _host(wanted, netloc):
    if wanted.startswith("*."):
        return netloc == wanted[2:] or (
            netloc.endswith(wanted[1:])
            and re.fullmatch(r"(?:[A-Za-z0-9-]+\.)+", netloc[: -len(wanted[2:])]) is not None
        )
    return netloc == wanted


def opener():
    """An opener that never follows a redirect: a request goes only where it was sent."""
    return urllib.request.build_opener(NoRedirect())


def urlopen(request, timeout):
    """Open one request with `opener()`. The default for a studio without its own."""
    return opener().open(request, timeout=timeout)


def exchange(opening, method, url, headers, payload=None, *, timeout, limit=None,
             error_limit=ERROR_LIMIT):
    """Send one request through `opening(request, timeout=...)` and read the answer.

    Returns a Response holding at most `limit` + 1 bytes (all of it when `limit` is
    None); the caller says what more than `limit` means. An HTTP error answer is raised
    as Refused with at most `error_limit` bytes of its body. Other failures (OSError,
    http.client errors) are raised as they are, for the caller to word.
    """
    request = urllib.request.Request(url, data=payload, method=method, headers=headers or {})
    try:
        with opening(request, timeout=timeout) as handle:
            data = handle.read() if limit is None else handle.read(limit + 1)
            answered = getattr(handle, "headers", None)
            return Response(
                getattr(handle, "status", 200),
                {k.lower(): v for k, v in answered.items()} if answered is not None else {},
                data,
            )
    except urllib.error.HTTPError as failure:
        try:
            body = failure.read() if error_limit is None else failure.read(error_limit)
        except (OSError, ValueError):
            body = b""
        finally:
            failure.close()
        raise Refused(failure.code, failure.reason, body if isinstance(body, bytes) else b"") from None


def send(method, url, *, routes, token=None, headers=None, payload=None, opening=None,
         timeout, limit=None, error_limit=ERROR_LIMIT):
    """Send one request to a route a studio named, with its token, never following a
    redirect, and never more than once.

    The destination is checked before `token()` is called, so a token never goes
    anywhere else. `opening` defaults to `urlopen`. See `exchange` for the answer.
    """
    if not allowed(url, method, routes):
        raise Disallowed("Google credentials may go only to the fixed Google APIs this studio uses.")
    sent = dict(headers or {})
    if token is not None:
        sent["Authorization"] = "Bearer " + token()
    return exchange(opening or urlopen, method, url, sent, payload, timeout=timeout,
                    limit=limit, error_limit=error_limit)


def read_retried(attempt, *, method, delays, transient, sleep=time.sleep):
    """`attempt()`, repeated after each of `delays` while it fails in a way `transient`
    says is worth repeating, but only for a read: any other method is sent exactly once."""
    for delay in (*(delays if method == "GET" else ()), None):
        try:
            return attempt()
        except Exception as failure:
            if delay is None or not transient(failure):
                raise
            sleep(delay)


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
        self.opener = opener()
        self._signing = threading.Lock()

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
            # Asked for once, however many threads share this client (a folder's documents
            # are read several at a time).
            with self._signing:
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
                response = exchange(self.opener.open, method, url, sent, payload,
                                    timeout=45, limit=LIMIT)
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
        except Refused as failure:
            self.refuse(failure.status, method, failure.body, account=self.account)
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

    def children(self, folder_id, page_token=None):
        """One page of what a Google Drive folder holds directly, shared drives included.

        Read-only listing for a folder a person named. A shortcut carries its target in
        `shortcutDetails`; `nextPageToken` is present while more pages remain.
        """
        if page_token is not None and (
            not isinstance(page_token, str) or not 0 < len(page_token) <= 2000
        ):
            raise GoogleError("Google returned an unusable folder page.")
        asked = {
            "q": "'" + identifier(folder_id) + "' in parents and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType,size,"
            "shortcutDetails(targetId,targetMimeType))",
            "pageSize": "200",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            asked["pageToken"] = page_token
        found = self.request(
            "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(asked)
        )
        if not isinstance(found.get("files"), list):
            raise GoogleError("Google returned an unusable folder listing.")
        return found

    def entry(self, file_id):
        """A Drive file's name, type and size, and what it points to when it is a shortcut."""
        return self.request(
            "https://www.googleapis.com/drive/v3/files/"
            + identifier(file_id)
            + "?"
            + urllib.parse.urlencode(
                {"supportsAllDrives": "true", "fields": "id,name,mimeType,size,trashed,"
                 "shortcutDetails(targetId,targetMimeType)"}
            )
        )

    def download(self, file_id):
        """An uploaded Drive file's own bytes. Google files are exported instead."""
        return self.request(
            "https://www.googleapis.com/drive/v3/files/"
            + identifier(file_id)
            + "?"
            + urllib.parse.urlencode({"alt": "media", "supportsAllDrives": "true"}),
            json_result=False,
        ).data

    def export_workbook(self, file_id):
        """A Google Sheets file as an .xlsx workbook through Drive, with every sheet in it."""
        return self.request(
            "https://www.googleapis.com/drive/v3/files/"
            + identifier(file_id)
            + "/export?"
            + urllib.parse.urlencode({"mimeType": XLSX_MIME}),
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
