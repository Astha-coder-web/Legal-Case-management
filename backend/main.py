from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from gridfs import AsyncGridFSBucket
from gridfs.errors import GridFSError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from pwdlib import PasswordHash
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv(Path(__file__).with_name(".env"))

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "LegalCases")
MONGODB_REMINDERS_DATABASE = os.getenv(
    "MONGODB_REMINDERS_DATABASE", "AllRemainders"
)
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30
UPLOAD_CHUNK_SIZE = 1024 * 1024
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


class CaseCreate(BaseModel):
    case_name: str = Field(min_length=1, max_length=160)
    client_name: str = Field(min_length=1, max_length=100)
    case_number: str = Field(default="", max_length=80)
    case_type: str = Field(
        default="other",
        pattern=r"^(criminal|civil|family|corporate|property|labor|consumer|other)$",
    )
    court_name: str = Field(default="", max_length=160)
    status: str = Field(default="active", pattern=r"^(active|pending|closed)$")
    hearing_at: datetime
    hearing_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    notes: str = Field(default="", max_length=4000)

    @field_validator("case_name", "client_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("This field must not be blank")
        return text

    @field_validator("case_number", "court_name")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("hearing_at")
    @classmethod
    def validate_hearing_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Hearing time must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("hearing_timezone")
    @classmethod
    def validate_timezone_name(cls, value: str) -> str:
        name = value.strip()
        try:
            ZoneInfo(name)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("A valid timezone name is required") from None
        return name


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_client_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Name must not be blank")
        return name


class PaymentCreate(BaseModel):
    description: str = Field(min_length=1, max_length=160)
    amount_cents: int = Field(gt=0, le=100_000_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    due_at: datetime | None = None
    status: str = Field(default="pending", pattern=r"^(pending|paid)$")

    @field_validator("description")
    @classmethod
    def validate_payment_description(cls, value: str) -> str:
        description = value.strip()
        if not description:
            raise ValueError("Description must not be blank")
        return description

    @field_validator("due_at")
    @classmethod
    def validate_payment_timezone(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Payment date must include a timezone")
            return value.astimezone(timezone.utc)
        return value


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


def get_reminders_database(request: Request) -> Any:
    return request.app.state.reminders_database


def get_attachments_bucket(request: Request) -> Any:
    return request.app.state.attachments_bucket


def serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key: str(value) if isinstance(value, ObjectId) else value
        for key, value in document.items()
        if key != "user_id"
    } | {"id": str(document["_id"])}


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


async def fire_due_reminders(reminders_database: Any) -> None:
    now = datetime.now(timezone.utc)
    await reminders_database.reminders.update_many(
        {
            "status": "scheduled",
            "hearing_at": {"$lte": now},
        },
        {"$set": {"status": "fired", "fired_at": now}},
    )


async def save_image_upload(
    bucket: Any,
    upload: UploadFile,
    user_id: ObjectId,
    case_id: ObjectId,
) -> dict[str, Any]:
    content_type = (upload.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"{upload.filename or 'Uploaded file'} is not an image",
        )
    filename = Path(upload.filename or "image").name
    grid_file = bucket.open_upload_stream(
        filename,
        metadata={
            "user_id": user_id,
            "case_id": case_id,
            "content_type": content_type,
        },
    )
    try:
        while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
            await grid_file.write(chunk)
        await grid_file.close()
    except (GridFSError, PyMongoError, OSError):
        await grid_file.abort()
        raise
    return {
        "id": str(grid_file._id),
        "filename": filename,
        "content_type": content_type,
    }


async def list_case_attachments(
    bucket: Any, user_id: ObjectId, case_id: ObjectId
) -> list[dict[str, Any]]:
    files = await bucket.find(
        {"metadata.user_id": user_id, "metadata.case_id": case_id}
    ).to_list(length=None)
    return [
        {
            "id": str(item._id),
            "filename": item.filename,
            "content_type": item.metadata["content_type"],
            "length": item.length,
        }
        for item in files
    ]


def local_hearing_details(
    hearing_at: datetime, timezone_name: str
) -> dict[str, str]:
    local_hearing = hearing_at.astimezone(ZoneInfo(timezone_name))
    return {
        "hearing_date": local_hearing.date().isoformat(),
        "hearing_time": local_hearing.strftime("%H:%M"),
        "hearing_day": local_hearing.strftime("%A"),
        "hearing_timezone": timezone_name,
    }


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
        reminders_database = client[MONGODB_REMINDERS_DATABASE]
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
        await database.cases.create_index(
            [("user_id", ASCENDING), ("hearing_at", ASCENDING)],
            name="user_case_hearings",
        )
        attachments_bucket = AsyncGridFSBucket(
            database, bucket_name="case_attachments"
        )
        await database.clients.create_index(
            [("user_id", ASCENDING), ("name", ASCENDING)],
            name="user_clients",
        )
        await database.payments.create_index(
            [("user_id", ASCENDING), ("created_at", ASCENDING)],
            name="user_payments",
        )
        await reminders_database.reminders.create_index(
            [("status", ASCENDING), ("hearing_at", ASCENDING)],
            name="scheduled_reminders",
        )
        await reminders_database.reminders.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)],
            name="user_fired_reminders",
        )
        scheduler = AsyncIOScheduler(timezone=timezone.utc)
        scheduler.add_job(
            fire_due_reminders,
            "interval",
            seconds=5,
            args=[reminders_database],
            id="fire_due_case_reminders",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        app.state.mongo_client = client
        app.state.database = database
        app.state.reminders_database = reminders_database
        app.state.attachments_bucket = attachments_bucket
        app.state.scheduler = scheduler
        yield
    finally:
        if "scheduler" in locals() and scheduler.running:
            scheduler.shutdown(wait=False)
        await client.close()


app = FastAPI(title="LegalSmart API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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


@app.get("/api/cases")
async def list_cases(
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
    attachments_bucket: Annotated[Any, Depends(get_attachments_bucket)],
) -> list[dict[str, Any]]:
    cases = await database.cases.find(
        {"user_id": user["_id"]}
    ).sort("hearing_at", ASCENDING).to_list(length=500)
    result = []
    for case in cases:
        serialized_case = serialize_document(case)
        serialized_case["attachments"] = await list_case_attachments(
            attachments_bucket, user["_id"], case["_id"]
        )
        result.append(serialized_case)
    return result


@app.post("/api/cases", status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
    reminders_database: Annotated[Any, Depends(get_reminders_database)],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    case = {
        "user_id": user["_id"],
        "case_name": body.case_name,
        "client_name": body.client_name,
        "case_number": body.case_number,
        "case_type": body.case_type,
        "court_name": body.court_name,
        "status": body.status,
        "hearing_at": body.hearing_at,
        **local_hearing_details(body.hearing_at, body.hearing_timezone),
        "notes": body.notes.strip(),
        "created_at": now,
    }
    result = await database.cases.insert_one(case)
    case["_id"] = result.inserted_id

    if body.hearing_at > now and body.status != "closed":
        try:
            await reminders_database.reminders.insert_one(
                {
                    "user_id": user["_id"],
                    "user_name": user["name"],
                    "user_email": user["email"],
                    "case_id": result.inserted_id,
                    "case_name": body.case_name,
                    "client_name": body.client_name,
                    "case_number": body.case_number,
                    "case_type": body.case_type,
                    "court_name": body.court_name,
                    "case_status": body.status,
                    "hearing_at": body.hearing_at,
                    **local_hearing_details(
                        body.hearing_at, body.hearing_timezone
                    ),
                    "notes": body.notes.strip(),
                    "status": "scheduled",
                    "created_at": now,
                    "fired_at": None,
                    "delivered_at": None,
                }
            )
        except PyMongoError:
            await database.cases.delete_one(
                {"_id": result.inserted_id, "user_id": user["_id"]}
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not schedule the case reminder; the case was not saved",
            ) from None
    return serialize_document(case)


@app.put("/api/cases/{case_id}")
async def update_case(
    case_id: str,
    body: CaseCreate,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
    reminders_database: Annotated[Any, Depends(get_reminders_database)],
    attachments_bucket: Annotated[Any, Depends(get_attachments_bucket)],
) -> dict[str, Any]:
    try:
        object_id = ObjectId(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found") from None

    case = await database.cases.find_one(
        {"_id": object_id, "user_id": user["_id"]}
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    fields = {
        "case_name": body.case_name,
        "client_name": body.client_name,
        "case_number": body.case_number,
        "case_type": body.case_type,
        "court_name": body.court_name,
        "status": body.status,
        "hearing_at": body.hearing_at,
        **local_hearing_details(body.hearing_at, body.hearing_timezone),
        "notes": body.notes.strip(),
        "updated_at": datetime.now(timezone.utc),
    }
    await database.cases.update_one(
        {"_id": object_id, "user_id": user["_id"]},
        {"$set": fields},
    )
    should_schedule_reminder = (
        body.hearing_at > datetime.now(timezone.utc)
        and body.status != "closed"
    )
    reminder_fields = {
        **fields,
        "case_status": body.status,
        "user_name": user["name"],
        "user_email": user["email"],
        "status": "scheduled" if should_schedule_reminder else "cancelled",
        "fired_at": None,
        "delivered_at": None,
    }
    reminder_result = await reminders_database.reminders.update_many(
        {"user_id": user["_id"], "case_id": object_id},
        {
            "$set": reminder_fields
        },
    )
    if should_schedule_reminder and not reminder_result.modified_count:
        await reminders_database.reminders.insert_one(
            {
                **reminder_fields,
                "user_id": user["_id"],
                "case_id": object_id,
                "created_at": datetime.now(timezone.utc),
            }
        )
    case.update(fields)
    serialized_case = serialize_document(case)
    serialized_case["attachments"] = await list_case_attachments(
        attachments_bucket, user["_id"], object_id
    )
    return serialized_case


@app.delete("/api/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: str,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
    reminders_database: Annotated[Any, Depends(get_reminders_database)],
    attachments_bucket: Annotated[Any, Depends(get_attachments_bucket)],
) -> None:
    try:
        object_id = ObjectId(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found") from None

    case = await database.cases.find_one(
        {"_id": object_id, "user_id": user["_id"]}
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    await database.cases.delete_one(
        {"_id": object_id, "user_id": user["_id"]}
    )
    await reminders_database.reminders.delete_many(
        {"user_id": user["_id"], "case_id": object_id}
    )
    files = await attachments_bucket.find(
        {"metadata.user_id": user["_id"], "metadata.case_id": object_id}
    ).to_list(length=None)
    for grid_file in files:
        await attachments_bucket.delete(grid_file._id)


@app.post(
    "/api/cases/{case_id}/attachments",
    status_code=status.HTTP_201_CREATED,
)
async def upload_case_attachments(
    case_id: str,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
    attachments_bucket: Annotated[Any, Depends(get_attachments_bucket)],
    files: Annotated[list[UploadFile], File()],
) -> list[dict[str, Any]]:
    try:
        object_id = ObjectId(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found") from None
    if not await database.cases.find_one(
        {"_id": object_id, "user_id": user["_id"]}
    ):
        raise HTTPException(status_code=404, detail="Case not found")
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one image",
        )

    stored_files = []
    try:
        for upload in files:
            stored_files.append(
                await save_image_upload(
                    attachments_bucket, upload, user["_id"], object_id
                )
            )
    except HTTPException:
        for stored_file in stored_files:
            await attachments_bucket.delete(ObjectId(stored_file["id"]))
        raise
    except (GridFSError, PyMongoError, OSError):
        for stored_file in stored_files:
            await attachments_bucket.delete(ObjectId(stored_file["id"]))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not store the case images",
        ) from None
    finally:
        for upload in files:
            await upload.close()
    return stored_files


@app.get("/api/cases/{case_id}/attachments/{attachment_id}")
async def download_case_attachment(
    case_id: str,
    attachment_id: str,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
    attachments_bucket: Annotated[Any, Depends(get_attachments_bucket)],
) -> StreamingResponse:
    try:
        case_object_id = ObjectId(case_id)
        file_object_id = ObjectId(attachment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Image not found") from None
    if not await database.cases.find_one(
        {"_id": case_object_id, "user_id": user["_id"]}
    ):
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        grid_file = await attachments_bucket.open_download_stream(file_object_id)
    except GridFSError:
        raise HTTPException(status_code=404, detail="Image not found") from None
    if (
        grid_file.metadata.get("user_id") != user["_id"]
        or grid_file.metadata.get("case_id") != case_object_id
    ):
        raise HTTPException(status_code=404, detail="Image not found")

    async def image_chunks():
        while chunk := await grid_file.readchunk():
            yield chunk

    filename = quote(grid_file.filename)
    return StreamingResponse(
        image_chunks(),
        media_type=grid_file.metadata["content_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/clients")
async def list_clients(
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
) -> list[dict[str, Any]]:
    clients = await database.clients.find(
        {"user_id": user["_id"]}
    ).sort("name", ASCENDING).to_list(length=500)
    return [serialize_document(client) for client in clients]


@app.post("/api/clients", status_code=status.HTTP_201_CREATED)
async def create_client(
    body: ClientCreate,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
) -> dict[str, Any]:
    client = {
        "user_id": user["_id"],
        "name": body.name,
        "email": body.email.strip(),
        "phone": body.phone.strip(),
        "notes": body.notes.strip(),
        "created_at": datetime.now(timezone.utc),
    }
    result = await database.clients.insert_one(client)
    client["_id"] = result.inserted_id
    return serialize_document(client)


@app.get("/api/payments")
async def list_payments(
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
) -> list[dict[str, Any]]:
    payments = await database.payments.find(
        {"user_id": user["_id"]}
    ).sort("created_at", -1).to_list(length=500)
    return [serialize_document(payment) for payment in payments]


@app.post("/api/payments", status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    user: Annotated[dict[str, Any], Depends(current_user)],
    database: Annotated[Any, Depends(get_database)],
) -> dict[str, Any]:
    payment = {
        "user_id": user["_id"],
        "description": body.description,
        "amount_cents": body.amount_cents,
        "currency": body.currency,
        "due_at": body.due_at,
        "status": body.status,
        "created_at": datetime.now(timezone.utc),
    }
    result = await database.payments.insert_one(payment)
    payment["_id"] = result.inserted_id
    return serialize_document(payment)


@app.get("/api/reminders/pending")
async def list_pending_reminders(
    user: Annotated[dict[str, Any], Depends(current_user)],
    reminders_database: Annotated[Any, Depends(get_reminders_database)],
) -> list[dict[str, Any]]:
    reminders = await reminders_database.reminders.find(
        {"user_id": user["_id"], "status": "fired"}
    ).sort("hearing_at", ASCENDING).to_list(length=50)
    return [serialize_document(reminder) for reminder in reminders]


@app.post("/api/reminders/{reminder_id}/delivered", status_code=status.HTTP_204_NO_CONTENT)
async def mark_reminder_delivered(
    reminder_id: str,
    user: Annotated[dict[str, Any], Depends(current_user)],
    reminders_database: Annotated[Any, Depends(get_reminders_database)],
) -> None:
    try:
        object_id = ObjectId(reminder_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        ) from None
    result = await reminders_database.reminders.update_one(
        {
            "_id": object_id,
            "user_id": user["_id"],
            "status": "fired",
        },
        {
            "$set": {
                "status": "delivered",
                "delivered_at": datetime.now(timezone.utc),
            }
        },
    )
    if not result.modified_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        )
