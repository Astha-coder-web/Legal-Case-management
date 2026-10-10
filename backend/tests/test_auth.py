import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-characters-long")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost/test")

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from backend.main import app


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

    @staticmethod
    def _matches(document, key, expected):
        actual = document.get(key)
        if isinstance(expected, dict) and "$gt" in expected:
            return actual is not None and actual > expected["$gt"]
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


class FakeDatabase:
    def __init__(self):
        self.users = FakeCollection(unique_field="email")
        self.sessions = FakeCollection(unique_field="jti")


@pytest.fixture
def api():
    database = FakeDatabase()
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def test_lifespan(application):
        application.state.database = database
        yield

    app.router.lifespan_context = test_lifespan
    try:
        with TestClient(app) as client:
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
