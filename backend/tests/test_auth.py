import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-characters-long")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost/test")

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from backend.main import (
    MONGODB_REMINDERS_DATABASE,
    app,
    fire_due_reminders,
    local_hearing_details,
)


class FakeCollection:
    def __init__(self, unique_field=None):
        self.documents = []
        self.unique_field = unique_field

    async def find_one(self, query):
        for document in self.documents:
            if all(
                self._matches(document, key, value)
                for key, value in query.items()
            ):
                return document
        return None

    def find(self, query):
        documents = [
            document
            for document in self.documents
            if all(
                self._matches(document, key, value)
                for key, value in query.items()
            )
        ]
        return FakeCursor(documents)

    @staticmethod
    def _matches(document, key, expected):
        actual = document.get(key)
        if isinstance(expected, dict) and "$gt" in expected:
            return actual is not None and actual > expected["$gt"]
        if isinstance(expected, dict) and "$lte" in expected:
            return actual is not None and actual <= expected["$lte"]
        return actual == expected

    async def insert_one(self, document):
        if self.unique_field and any(
            stored.get(self.unique_field) == document.get(self.unique_field)
            for stored in self.documents
        ):
            raise DuplicateKeyError("duplicate key")
        document["_id"] = ObjectId()
        self.documents.append(document)
        return SimpleNamespace(inserted_id=document["_id"])

    async def update_one(self, query, update):
        document = await self.find_one(query)
        if document:
            document.update(update["$set"])
            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    async def update_many(self, query, update):
        matched = 0
        for document in self.documents:
            if all(
                self._matches(document, key, value)
                for key, value in query.items()
            ):
                document.update(update["$set"])
                matched += 1
        return SimpleNamespace(modified_count=matched)

    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if all(
                self._matches(document, key, value)
                for key, value in query.items()
            ):
                self.documents.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query):
        original_count = len(self.documents)
        self.documents[:] = [
            document
            for document in self.documents
            if not all(
                self._matches(document, key, value)
                for key, value in query.items()
            )
        ]
        return SimpleNamespace(
            deleted_count=original_count - len(self.documents)
        )


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction=1):
        self.documents.sort(
            key=lambda document: document.get(field),
            reverse=direction < 0,
        )
        return self

    async def to_list(self, length=None):
        return self.documents[:length]


class FakeGridFile:
    def __init__(self, file_id, filename, metadata, content):
        self._id = file_id
        self.filename = filename
        self.metadata = metadata
        self.length = len(content)
        self.content = content
        self.position = 0

    async def readchunk(self):
        chunk = self.content[self.position:self.position + 255 * 1024]
        self.position += len(chunk)
        return chunk


class FakeGridUpload:
    def __init__(self, bucket, filename, metadata):
        self.bucket = bucket
        self.filename = filename
        self.metadata = metadata
        self._id = ObjectId()
        self.content = bytearray()

    async def write(self, data):
        self.content.extend(data)

    async def close(self):
        self.bucket.files.append(
            FakeGridFile(
                self._id,
                self.filename,
                self.metadata,
                bytes(self.content),
            )
        )

    async def abort(self):
        self.content.clear()


class FakeGridFSBucket:
    def __init__(self):
        self.files = []

    def open_upload_stream(self, filename, metadata):
        return FakeGridUpload(self, filename, metadata)

    def find(self, query):
        def matches(item):
            for key, expected in query.items():
                value = item
                for part in key.split("."):
                    value = value.get(part) if isinstance(value, dict) else None
                if value != expected:
                    return False
            return True

        return FakeCursor([item for item in self.files if matches({
            "metadata": item.metadata,
        })])

    async def delete(self, file_id):
        self.files[:] = [
            item for item in self.files if item._id != file_id
        ]

    async def open_download_stream(self, file_id):
        for item in self.files:
            if item._id == file_id:
                item.position = 0
                return item
        from gridfs.errors import NoFile

        raise NoFile("file not found")


class FakeDatabase:
    def __init__(self):
        self.users = FakeCollection(unique_field="email")
        self.sessions = FakeCollection(unique_field="jti")
        self.cases = FakeCollection()
        self.clients = FakeCollection()
        self.payments = FakeCollection()


@pytest.fixture
def api():
    database = FakeDatabase()
    reminders_database = SimpleNamespace(reminders=FakeCollection())
    attachments_bucket = FakeGridFSBucket()
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def test_lifespan(application):
        application.state.database = database
        application.state.reminders_database = reminders_database
        application.state.attachments_bucket = attachments_bucket
        yield

    app.router.lifespan_context = test_lifespan
    try:
        with TestClient(app) as client:
            database.reminders_database = reminders_database
            database.attachments_bucket = attachments_bucket
            yield client, database
    finally:
        app.router.lifespan_context = original_lifespan


def test_signup_persists_only_a_password_hash_and_rejects_duplicate_email(api):
    client, database = api
    response = client.post(
        "/api/auth/signup",
        json={
            "name": " Avery Patel ",
            "email": "AVERY@example.com",
            "password": "correct-horse-battery",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "avery@example.com"
    assert response.json()["name"] == "Avery Patel"
    saved_user = database.users.documents[0]
    assert saved_user["password_hash"] != "correct-horse-battery"
    assert "password" not in saved_user

    duplicate_response = client.post(
        "/api/auth/signup",
        json={
            "name": "Another user",
            "email": "avery@example.com",
            "password": "another-secure-password",
        },
    )
    assert duplicate_response.status_code == 409


def test_login_requires_correct_password_and_mongodb_session(api):
    client, database = api
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )

    bad_login = client.post(
        "/api/auth/login",
        json={"email": "avery@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    login = client.post(
        "/api/auth/login",
        json={
            "email": "AVERY@example.com",
            "password": "correct-horse-battery",
        },
    )
    assert login.status_code == 200
    assert login.json()["email"] == "avery@example.com"
    assert login.headers["set-cookie"].lower().find("httponly") >= 0
    assert len(database.sessions.documents) == 1
    assert database.sessions.documents[0]["token_hash"]

    assert client.get("/api/auth/me").status_code == 200

    valid_token = client.cookies.get("legalsmart_session")
    client.cookies.set("legalsmart_session", f"x{valid_token[1:]}")
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("legalsmart_session", valid_token)

    database.sessions.documents[0]["revoked_at"] = datetime.now(timezone.utc)
    assert client.get("/api/auth/me").status_code == 401


def test_logout_revokes_the_session_and_clears_the_cookie(api):
    client, database = api
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 204
    assert database.sessions.documents[0]["revoked_at"] is not None
    assert client.get("/api/auth/me").status_code == 401


def test_cases_are_user_scoped_and_create_scheduled_reminders(api):
    client, database = api
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    hearing_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
    response = client.post(
        "/api/cases",
        json={
            "case_name": "Patel v. Northwind",
            "client_name": "Avery Patel",
            "case_number": "2026-CV-00123",
            "case_type": "civil",
            "court_name": "Central District Court",
            "status": "active",
            "hearing_at": hearing_at.isoformat(),
            "hearing_timezone": "Asia/Kolkata",
            "notes": "Bring the signed documents.",
        },
    )

    assert response.status_code == 201
    assert response.json()["case_name"] == "Patel v. Northwind"
    assert response.json()["case_number"] == "2026-CV-00123"
    assert response.json()["case_type"] == "civil"
    assert response.json()["court_name"] == "Central District Court"
    assert response.json()["status"] == "active"
    assert len(database.cases.documents) == 1
    assert len(database.reminders_database.reminders.documents) == 1
    reminder = database.reminders_database.reminders.documents[0]
    assert reminder["status"] == "scheduled"
    assert reminder["user_id"] == database.users.documents[0]["_id"]
    assert reminder["user_name"] == "Avery Patel"
    assert reminder["user_email"] == "avery@example.com"
    assert reminder["case_name"] == "Patel v. Northwind"
    assert reminder["client_name"] == "Avery Patel"
    assert reminder["case_number"] == "2026-CV-00123"
    assert reminder["case_type"] == "civil"
    assert reminder["court_name"] == "Central District Court"
    assert reminder["case_status"] == "active"
    assert reminder["notes"] == "Bring the signed documents."
    assert reminder["hearing_timezone"] == "Asia/Kolkata"
    assert reminder["hearing_date"] == hearing_at.astimezone(
        timezone(timedelta(hours=5, minutes=30))
    ).date().isoformat()
    assert reminder["hearing_day"] == hearing_at.astimezone(
        timezone(timedelta(hours=5, minutes=30))
    ).strftime("%A")
    assert reminder["hearing_time"] == hearing_at.astimezone(
        timezone(timedelta(hours=5, minutes=30))
    ).strftime("%H:%M")
    saved_case = database.cases.documents[0]
    assert saved_case["hearing_day"] == reminder["hearing_day"]
    assert saved_case["hearing_date"] == reminder["hearing_date"]
    assert saved_case["hearing_time"] == reminder["hearing_time"]
    assert [item["id"] for item in client.get("/api/cases").json()] == [
        response.json()["id"]
    ]

    reminder["hearing_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    asyncio.run(fire_due_reminders(database.reminders_database))
    pending = client.get("/api/reminders/pending")
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    delivered = client.post(
        f"/api/reminders/{pending.json()[0]['id']}/delivered"
    )
    assert delivered.status_code == 204
    assert reminder["status"] == "delivered"
    assert client.get("/api/reminders/pending").json() == []

    client.post(
        "/api/auth/signup",
        json={
            "name": "Morgan Lee",
            "email": "morgan@example.com",
            "password": "another-secure-password",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "morgan@example.com",
            "password": "another-secure-password",
        },
    )
    assert client.get("/api/cases").json() == []


def test_clients_and_payment_ledger_are_saved_per_user(api):
    client, database = api
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )

    new_client = client.post(
        "/api/clients",
        json={
            "name": "Jordan Client",
            "email": "jordan@example.com",
            "phone": "555-0100",
        },
    )
    payment = client.post(
        "/api/payments",
        json={
            "description": "Consultation",
            "amount_cents": 12500,
            "currency": "USD",
            "status": "pending",
        },
    )

    assert new_client.status_code == 201
    assert new_client.json()["name"] == "Jordan Client"
    assert payment.status_code == 201
    assert payment.json()["amount_cents"] == 12500
    assert len(database.clients.documents) == 1
    assert len(database.payments.documents) == 1


def test_scheduler_fires_due_reminders_once_for_database_records():
    reminders_database = SimpleNamespace(reminders=FakeCollection())
    reminders_database.reminders.documents.extend(
        [
            {
                "_id": ObjectId(),
                "user_id": ObjectId(),
                "status": "scheduled",
                "hearing_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
            },
            {
                "_id": ObjectId(),
                "user_id": ObjectId(),
                "status": "scheduled",
                "hearing_at": datetime(2999, 1, 1, tzinfo=timezone.utc),
            },
        ]
    )

    asyncio.run(fire_due_reminders(reminders_database))
    statuses = [
        reminder["status"]
        for reminder in reminders_database.reminders.documents
    ]

    assert statuses == ["fired", "scheduled"]


def test_reminder_database_and_local_hearing_fields():
    assert MONGODB_REMINDERS_DATABASE == "AllRemainders"
    hearing_at = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)

    assert local_hearing_details(hearing_at, "Asia/Kolkata") == {
        "hearing_date": "2030-01-01",
        "hearing_time": "15:30",
        "hearing_day": "Tuesday",
        "hearing_timezone": "Asia/Kolkata",
    }


def test_case_images_editing_and_deletion_are_user_scoped(api):
    client, database = api
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    hearing_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
    created = client.post(
        "/api/cases",
        json={
            "case_name": "Patel v. Northwind",
            "client_name": "Avery Patel",
            "hearing_at": hearing_at.isoformat(),
            "hearing_timezone": "Asia/Kolkata",
            "notes": "Initial notes",
        },
    )
    assert created.status_code == 201
    case_id = created.json()["id"]

    uploaded = client.post(
        f"/api/cases/{case_id}/attachments",
        files=[
            (
                "files",
                ("evidence.png", b"\x89PNG\r\n\x1a\nexample-image", "image/png"),
            )
        ],
    )
    assert uploaded.status_code == 201
    attachment = uploaded.json()[0]
    listed_case = client.get("/api/cases").json()[0]
    assert listed_case["attachments"][0]["filename"] == "evidence.png"
    assert listed_case["attachments"][0]["length"] > 0
    download = client.get(
        f"/api/cases/{case_id}/attachments/{attachment['id']}"
    )
    assert download.status_code == 200
    assert download.content.startswith(b"\x89PNG")
    assert download.headers["content-type"] == "image/png"

    updated_hearing = hearing_at + timedelta(days=3)
    edited = client.put(
        f"/api/cases/{case_id}",
        json={
            "case_name": "Patel v. Northwind (amended)",
            "client_name": "Avery Patel",
            "case_number": "2026-CV-00123-A",
            "case_type": "civil",
            "court_name": "Central District Court",
            "status": "active",
            "hearing_at": updated_hearing.isoformat(),
            "hearing_timezone": "Asia/Kolkata",
            "notes": "Updated notes",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["case_name"] == "Patel v. Northwind (amended)"
    assert edited.json()["case_number"] == "2026-CV-00123-A"
    assert edited.json()["attachments"][0]["id"] == attachment["id"]
    reminder = database.reminders_database.reminders.documents[0]
    assert reminder["case_name"] == "Patel v. Northwind (amended)"
    assert reminder["notes"] == "Updated notes"
    assert reminder["case_number"] == "2026-CV-00123-A"
    assert reminder["status"] == "scheduled"

    closed = client.put(
        f"/api/cases/{case_id}",
        json={
            "case_name": "Patel v. Northwind (amended)",
            "client_name": "Avery Patel",
            "case_number": "2026-CV-00123-A",
            "case_type": "civil",
            "court_name": "Central District Court",
            "status": "closed",
            "hearing_at": updated_hearing.isoformat(),
            "hearing_timezone": "Asia/Kolkata",
            "notes": "Updated notes",
        },
    )
    assert closed.status_code == 200
    assert database.reminders_database.reminders.documents[0]["status"] == "cancelled"

    deleted = client.delete(f"/api/cases/{case_id}")
    assert deleted.status_code == 204
    assert client.get("/api/cases").json() == []
    assert database.reminders_database.reminders.documents == []
    assert database.attachments_bucket.files == []
    assert client.get(
        f"/api/cases/{case_id}/attachments/{attachment['id']}"
    ).status_code == 404


def test_previous_closed_cases_are_saved_without_scheduling_reminders(api):
    client, database = api
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    previous_hearing = datetime.now(timezone.utc) - timedelta(days=30)

    response = client.post(
        "/api/cases",
        json={
            "case_name": "Patel v. Northwind",
            "client_name": "Avery Patel",
            "case_number": "2025-CV-007",
            "case_type": "civil",
            "court_name": "Central District Court",
            "status": "closed",
            "hearing_at": previous_hearing.isoformat(),
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "closed"
    assert datetime.fromisoformat(
        response.json()["hearing_at"].replace("Z", "+00:00")
    ) == previous_hearing
    assert database.reminders_database.reminders.documents == []


def test_case_image_upload_rejects_non_image_files(api):
    client = api[0]
    client.post(
        "/api/auth/signup",
        json={
            "name": "Avery Patel",
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    client.post(
        "/api/auth/login",
        json={
            "email": "avery@example.com",
            "password": "correct-horse-battery",
        },
    )
    hearing_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
    created = client.post(
        "/api/cases",
        json={
            "case_name": "Patel v. Northwind",
            "client_name": "Avery Patel",
            "hearing_at": hearing_at.isoformat(),
            "hearing_timezone": "UTC",
        },
    )

    response = client.post(
        f"/api/cases/{created.json()['id']}/attachments",
        files=[("files", ("not-image.txt", b"nope", "text/plain"))],
    )

    assert response.status_code == 415
