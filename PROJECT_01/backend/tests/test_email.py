import imaplib

import pytest
from sqlalchemy import select

from app.models import EmailAccount
from app.services import imap

HEADERS_101 = (
    b'From: "Priya Shah" <priya@example.com>\r\n'
    b"Subject: =?utf-8?q?Invoice_=E2=82=AC20?=\r\n"
    b"Date: Mon, 02 Nov 2026 09:15:00 +0530\r\n"
    b"Message-ID: <a1@example.com>\r\n\r\n"
)
HEADERS_102 = b"From: bob@example.com\r\nSubject: Lunch?\r\nDate: Tue, 03 Nov 2026 12:00:00 +0000\r\n\r\n"

FETCH_RESPONSE = [
    (b"1 (UID 101 FLAGS (\\Seen) BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] {150}", HEADERS_101),
    b")",
    # This server sends FLAGS after the literal.
    (b"2 (UID 102 BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] {90}", HEADERS_102),
    b" FLAGS (\\Flagged))",
]


class FakeIMAP:
    """Minimal stand-in for imaplib.IMAP4_SSL that records how it is used."""

    password = "app-password"
    uids = [b"101", b"102"]
    calls: list = []

    def __init__(self, host, port):
        self.host, self.port = host, port

    def login(self, user, password):
        FakeIMAP.calls.append(("login", user))
        if password != self.password:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=False):
        FakeIMAP.calls.append(("select", mailbox, readonly))
        return ("OK", [b"2"]) if mailbox == '"INBOX"' else ("NO", [b"no such mailbox"])

    def uid(self, command, *args):
        FakeIMAP.calls.append(("uid", command, args))
        if command == "SEARCH":
            return "OK", [b" ".join(FakeIMAP.uids)]
        wanted = set(args[0].split(","))
        return "OK", [item for pair in zip(FETCH_RESPONSE[::2], FETCH_RESPONSE[1::2])
                      if pair[0][0].split()[2].decode() in wanted for item in pair]

    def logout(self):
        FakeIMAP.calls.append(("logout",))


@pytest.fixture(autouse=True)
def fake_server(monkeypatch):
    FakeIMAP.calls = []
    FakeIMAP.uids = [b"101", b"102"]
    monkeypatch.setattr(imap, "open_connection", lambda host, port, timeout=20.0: FakeIMAP(host, port))


ACCOUNT = {"host": "imap.example.com", "username": "ana@example.com", "password": "app-password"}


def test_parse_fetch_decodes_headers_and_flags():
    first, second = imap._parse_fetch(FETCH_RESPONSE)
    assert (first.uid, first.from_name, first.from_addr) == ("101", "Priya Shah", "priya@example.com")
    assert first.subject == "Invoice €20"
    assert first.is_unread is False and first.is_flagged is False
    assert first.received_at.isoformat() == "2026-11-02T03:45:00+00:00"
    assert (second.uid, second.from_name, second.is_unread, second.is_flagged) == ("102", "bob@example.com", True, True)


def test_sync_is_read_only():
    headers = imap.fetch_recent_headers("imap.example.com", 993, "ana", "app-password", "INBOX")
    assert len(headers) == 2
    assert ("select", '"INBOX"', True) in FakeIMAP.calls
    fetch = next(c for c in FakeIMAP.calls if c[:2] == ("uid", "FETCH"))
    assert "BODY.PEEK" in fetch[2][1]
    assert FakeIMAP.calls[-1] == ("logout",)


def test_connect_validates_and_encrypts(client, app):
    r = client.put("/api/email/account", json=ACCOUNT)
    assert r.status_code == 200, r.text
    assert "password" not in r.json() and r.json()["port"] == 993
    with app.state.sessionmaker() as db:
        stored = db.scalar(select(EmailAccount.password_encrypted))
    assert "app-password" not in stored
    assert app.state.secret_box.decrypt(stored) == "app-password"


def test_connect_with_wrong_password_is_rejected(client):
    r = client.put("/api/email/account", json={**ACCOUNT, "password": "wrong"})
    assert r.status_code == 400 and "app password" in r.json()["detail"]
    assert client.get("/api/email/account").json() is None


def test_unknown_mailbox_is_rejected(client):
    r = client.put("/api/email/account", json={**ACCOUNT, "mailbox": "Archive"})
    assert r.status_code == 400 and "Archive" in r.json()["detail"]


def test_sync_list_and_make_task(client):
    assert client.post("/api/email/sync").status_code == 409  # nothing connected yet
    client.put("/api/email/account", json=ACCOUNT)
    assert client.post("/api/email/sync").json() == {"fetched": 2, "attention": 1}

    assert len(client.get("/api/email/messages?filter=all").json()) == 2
    [attention] = client.get("/api/email/messages").json()
    assert attention["subject"] == "Lunch?" and attention["is_flagged"]

    task = client.post(f"/api/email/messages/{attention['id']}/task")
    assert task.status_code == 201
    assert task.json()["title"] == "Reply: Lunch?" and task.json()["priority"] == "high"
    assert client.post(f"/api/email/messages/{attention['id']}/task").status_code == 409
    assert client.get("/api/email/messages").json()[0]["task_id"] == task.json()["id"]


def test_resync_drops_messages_gone_from_server(client):
    client.put("/api/email/account", json=ACCOUNT)
    client.post("/api/email/sync")
    FakeIMAP.uids = [b"102"]
    client.post("/api/email/sync")
    assert [m["subject"] for m in client.get("/api/email/messages?filter=all").json()] == ["Lunch?"]


def test_sync_failure_is_recorded(client, monkeypatch):
    client.put("/api/email/account", json=ACCOUNT)

    def offline(host, port, timeout=20.0):
        raise OSError("network down")

    monkeypatch.setattr(imap, "open_connection", offline)
    r = client.post("/api/email/sync")
    assert r.status_code == 502
    assert "Could not connect" in client.get("/api/email/account").json()["last_error"]


def test_disconnect_removes_messages(client, make_client):
    client.put("/api/email/account", json=ACCOUNT)
    client.post("/api/email/sync")
    bob = make_client("bob@example.com", name="Bob")
    assert bob.get("/api/email/messages?filter=all").json() == []
    msg_id = client.get("/api/email/messages").json()[0]["id"]
    assert bob.post(f"/api/email/messages/{msg_id}/task").status_code == 404

    assert client.delete("/api/email/account").status_code == 204
    assert client.get("/api/email/messages?filter=all").json() == []
    assert client.delete("/api/email/account").status_code == 404
