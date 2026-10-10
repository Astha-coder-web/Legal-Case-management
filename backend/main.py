from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import DuplicateKeyError
from pwdlib import PasswordHash

load_dotenv(Path(__file__).with_name(".env"))

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "legalsmart")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30
COOKIE_NAME = "legalsmart_session"
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

password_hash = PasswordHash.recommended()
dummy_password_hash = password_hash.hash(secrets.token_urlsafe(32))
class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Name must not be blank")
        return name


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    email: EmailStr


def normalized_email(email: str) -> str:
    return email.strip().casefold()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def user_response(user: dict[str, Any]) -> UserResponse:
    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
    )


def get_database(request: Request) -> Any:
    return request.app.state.database


def create_access_token(user_id: str, jti: str, expires_at: datetime) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "jti": jti,
            "iat": datetime.now(timezone.utc),
            "exp": expires_at,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


async def current_user(
    request: Request,
    database: Annotated[Any, Depends(get_database)],
) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not isinstance(user_id, str) or not isinstance(jti, str):
            raise jwt.InvalidTokenError("Missing token claims")
        object_id = ObjectId(user_id)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from None

    now = datetime.now(timezone.utc)
    session = await database.sessions.find_one(
        {
            "jti": jti,
            "token_hash": token_digest(token),
            "revoked_at": None,
            "expires_at": {"$gt": now},
        }
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user = await database.users.find_one({"_id": object_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI must be configured")

    client = AsyncMongoClient(MONGODB_URI, tz_aware=True)
    try:
        await client.admin.command("ping")
        database = client[MONGODB_DATABASE]
        await database.users.create_index(
            [("email", ASCENDING)],
            unique=True,
            name="unique_user_email",
        )
        await database.sessions.create_index(
            [("jti", ASCENDING)],
            unique=True,
            name="unique_session_jti",
        )
        await database.sessions.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,
            name="expire_sessions",
        )
        app.state.mongo_client = client
        app.state.database = database
        yield
    finally:
        await client.close()


app = FastAPI(title="LegalSmart API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/auth/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    body: SignupRequest,
    database: Annotated[Any, Depends(get_database)],
) -> UserResponse:
    user = {
        "name": body.name.strip(),
        "email": normalized_email(str(body.email)),
        "password_hash": password_hash.hash(body.password),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await database.users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    user["_id"] = result.inserted_id
    return user_response(user)


@app.post("/api/auth/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    database: Annotated[Any, Depends(get_database)],
) -> UserResponse:
    email = normalized_email(str(body.email))
    user = await database.users.find_one({"email": email})
    stored_password_hash = (
        user["password_hash"] if user else dummy_password_hash
    )
    password_matches = password_hash.verify(body.password, stored_password_hash)
    if not user or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    jti = secrets.token_urlsafe(24)
    token = create_access_token(str(user["_id"]), jti, expires_at)
    await database.sessions.insert_one(
        {
            "jti": jti,
            "user_id": user["_id"],
            "token_hash": token_digest(token),
            "created_at": now,
            "expires_at": expires_at,
            "revoked_at": None,
        }
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )
    return user_response(user)


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user(
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> UserResponse:
    return user_response(user)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    database: Annotated[Any, Depends(get_database)],
) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            jti = payload.get("jti")
            if isinstance(jti, str):
                await database.sessions.update_one(
                    {
                        "jti": jti,
                        "token_hash": token_digest(token),
                        "revoked_at": None,
                    },
                    {"$set": {"revoked_at": datetime.now(timezone.utc)}},
                )
        except jwt.InvalidTokenError:
            pass
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
