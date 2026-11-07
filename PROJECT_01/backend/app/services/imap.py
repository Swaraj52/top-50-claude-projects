"""Read-only IMAP header sync. Never modifies the mailbox (SELECT readonly + BODY.PEEK)."""

from __future__ import annotations

import imaplib
import logging
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.parser import BytesHeaderParser
from email.policy import default as default_policy
from email.utils import getaddresses, parsedate_to_datetime

log = logging.getLogger(__name__)

SINCE_DAYS = 14
MAX_MESSAGES = 200
FETCH_BATCH = 50
_UID_RE = re.compile(rb"UID (\d+)")
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)")


class ImapError(Exception):
    """A user-facing IMAP problem."""


@dataclass
class MessageHeader:
    uid: str
    message_id: str
    from_name: str
    from_addr: str
    subject: str
    received_at: datetime
    is_unread: bool
    is_flagged: bool


def open_connection(host: str, port: int, timeout: float = 20.0) -> imaplib.IMAP4:
    """Separated so tests can substitute a fake server."""
    if port == 143:
        conn = imaplib.IMAP4(host, port, timeout=timeout)
        conn.starttls(ssl_context=ssl.create_default_context())
        return conn
    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=timeout)


def _login(host: str, port: int, username: str, password: str, mailbox: str) -> imaplib.IMAP4:
    try:
        conn = open_connection(host, port)
    except (socket.gaierror, OSError) as exc:
        raise ImapError(f"Could not connect to {host}:{port} ({exc.__class__.__name__})") from exc
    try:
        conn.login(username, password)
    except imaplib.IMAP4.error as exc:
        _safe_logout(conn)
        raise ImapError(
            "The mail server rejected the username or password. Many providers need an "
            "app password for IMAP."
        ) from exc
    typ, _ = conn.select(_quote(mailbox), readonly=True)
    if typ != "OK":
        _safe_logout(conn)
        raise ImapError(f"Mailbox '{mailbox}' was not found")
    return conn


def _quote(mailbox: str) -> str:
    return '"' + mailbox.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _safe_logout(conn: imaplib.IMAP4) -> None:
    try:
        conn.logout()
    except Exception:  # noqa: BLE001 - best effort on an already-broken connection
        pass


def verify_login(host: str, port: int, username: str, password: str, mailbox: str) -> None:
    _safe_logout(_login(host, port, username, password, mailbox))


def _parse_fetch(resp: list) -> list[MessageHeader]:
    parser = BytesHeaderParser(policy=default_policy)
    out: list[MessageHeader] = []
    for i, item in enumerate(resp):
        if not isinstance(item, tuple):
            continue
        meta = item[0]
        # Some servers send FLAGS after the header literal, in the next element.
        if i + 1 < len(resp) and isinstance(resp[i + 1], bytes):
            meta += resp[i + 1]
        uid_m = _UID_RE.search(meta)
        if not uid_m:
            continue
        flags_m = _FLAGS_RE.search(meta)
        flags = flags_m.group(1).decode(errors="replace").split() if flags_m else []
        msg = parser.parsebytes(item[1])
        addresses = getaddresses([str(msg.get("From", ""))])
        name, addr = addresses[0] if addresses else ("", "")
        try:
            received = parsedate_to_datetime(str(msg.get("Date", "")))
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, IndexError):
            received = datetime.now(timezone.utc)
        out.append(
            MessageHeader(
                uid=uid_m.group(1).decode(),
                message_id=str(msg.get("Message-ID", "")).strip()[:255],
                from_name=(name or addr)[:200],
                from_addr=addr[:254],
                subject=(str(msg.get("Subject", "")).strip() or "(no subject)")[:500],
                received_at=received.astimezone(timezone.utc),
                is_unread="\\Seen" not in flags,
                is_flagged="\\Flagged" in flags,
            )
        )
    return out


def fetch_recent_headers(
    host: str, port: int, username: str, password: str, mailbox: str
) -> list[MessageHeader]:
    conn = _login(host, port, username, password, mailbox)
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=SINCE_DAYS)).strftime("%d-%b-%Y")
        typ, data = conn.uid("SEARCH", None, f"SINCE {since}")
        if typ != "OK":
            raise ImapError("The mail server refused the search request")
        uids = (data[0] or b"").split()[-MAX_MESSAGES:]
        headers: list[MessageHeader] = []
        for start in range(0, len(uids), FETCH_BATCH):
            batch = b",".join(uids[start : start + FETCH_BATCH]).decode()
            typ, resp = conn.uid(
                "FETCH",
                batch,
                "(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
            )
            if typ != "OK":
                raise ImapError("The mail server refused to return message headers")
            headers.extend(_parse_fetch(resp))
        return headers
    except (imaplib.IMAP4.abort, OSError) as exc:
        raise ImapError(f"Connection to the mail server was lost ({exc})") from exc
    finally:
        _safe_logout(conn)
