"""Local account authentication and private state. No third-party identity keys."""
import base64
import hashlib
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr
from starlette.concurrency import run_in_threadpool

from core import db
from hives.careers.matching import Profile
from hives.careers.taxonomy import FIELDS

router = APIRouter(prefix="/api/account")
COOKIE = "hivework_session"
PRIVATE = {"Cache-Control": "no-store"}
STAGES = Literal["", "saved", "preparing", "applied", "interview", "offer", "rejected", "dismissed"]


async def initialize(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS career_accounts (
            id BIGSERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            profile JSONB NOT NULL DEFAULT '{}'::jsonb, preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
            applications JSONB NOT NULL DEFAULT '{}'::jsonb, revision INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS career_sessions (
            token_hash TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES career_accounts(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 days'
        );
        CREATE TABLE IF NOT EXISTS career_auth_attempts (
            key TEXT PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL DEFAULT now(), attempts INTEGER NOT NULL DEFAULT 1
        );
    """)


@asynccontextmanager
async def connection():
    conn = None
    try:
        conn = await db.connect()
        await initialize(conn)
        yield conn
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Account storage is unavailable. Please retry shortly.", headers=PRIVATE) from exc
    finally:
        if conn:
            await conn.close()


def same_origin(request):
    origin = request.headers.get("origin")
    expected = str(request.base_url).rstrip("/")
    if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Account changes must come from this site.", headers=PRIVATE)


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password, encoded):
    try:
        algorithm, salt, _ = encoded.split("$")
        if algorithm != "scrypt":
            return False
        return secrets.compare_digest(hash_password(password, base64.b64decode(salt, validate=True)), encoded)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password("a-dummy-password-never-used", b"0" * 16)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def json_value(value):
    return json.loads(value) if isinstance(value, str) else value


def state(row):
    return {"user": {"username": row["username"]}, "profile": json_value(row["profile"]),
            "preferences": json_value(row["preferences"]), "applications": json_value(row["applications"]), "revision": row["revision"]}


async def user(conn, request, required=True):
    token = request.cookies.get(COOKIE, "")
    row = None
    if re.fullmatch(r"[A-Za-z0-9_-]{40,100}", token):
        row = await conn.fetchrow("""SELECT a.* FROM career_accounts a JOIN career_sessions s ON s.user_id=a.id
            WHERE s.token_hash=$1 AND s.expires_at > now()""", token_hash(token))
    if required and row is None:
        raise HTTPException(401, "Sign in to save account changes.", headers=PRIVATE)
    return row


async def throttle(conn, request, action, username=""):
    host = request.client.host if request.client else "unknown"
    # Hashed rate-limit identifiers; no raw IP addresses or usernames in this table.
    key = token_hash(action + ":" + host + ":" + username)
    attempts = await conn.fetchval("""INSERT INTO career_auth_attempts(key) VALUES ($1)
        ON CONFLICT(key) DO UPDATE SET
          attempts=CASE WHEN career_auth_attempts.started_at < now()-interval '15 minutes' THEN 1 ELSE career_auth_attempts.attempts+1 END,
          started_at=CASE WHEN career_auth_attempts.started_at < now()-interval '15 minutes' THEN now() ELSE career_auth_attempts.started_at END
        RETURNING attempts""", key)
    if attempts > (10 if action == "login" else 5):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.", headers={**PRIVATE, "Retry-After": "900"})
    return key


async def create_session(conn, request, response, user_id):
    old = request.cookies.get(COOKIE)
    if old:
        await conn.execute("DELETE FROM career_sessions WHERE token_hash=$1", token_hash(old))
    token = secrets.token_urlsafe(32)
    await conn.execute("DELETE FROM career_sessions WHERE expires_at < now()")
    await conn.execute("DELETE FROM career_auth_attempts WHERE started_at < now()-interval '1 day'")
    await conn.execute("INSERT INTO career_sessions(token_hash,user_id) VALUES ($1,$2)", token_hash(token), user_id)
    secure = request.url.scheme == "https" or os.getenv("CAREERS_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(COOKIE, token, max_age=30 * 86400, httponly=True, secure=secure, samesite="lax", path="/")
    response.headers.update(PRIVATE)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: SecretStr


class Preferences(BaseModel):
    query: str = Field(default="", max_length=200)
    role_type: str = Field(default="early_career", pattern="^(early_career|internship|new_grad|entry_level|apprenticeship|other|all)$")
    career_field: str = Field(default="all", pattern="^(all|" + "|".join(FIELDS) + ")$")
    location: str = Field(default="", max_length=150)
    workplace: str = Field(default="all", pattern="^(all|remote|hybrid|onsite|unspecified)$")
    company: str = Field(default="", max_length=100)
    sort: str = Field(default="fit", pattern="^(fit|newest)$")
    comparable_only: bool = False


class SavedState(BaseModel):
    profile: Profile
    preferences: Preferences
    revision: int = Field(ge=0)


class Application(BaseModel):
    status: STAGES


@router.post("/register")
async def register(data: Credentials, request: Request, response: Response):
    same_origin(request)
    password = data.password.get_secret_value()
    if not 12 <= len(password) <= 128:
        raise HTTPException(400, "Use a password between 12 and 128 characters.", headers=PRIVATE)
    async with connection() as conn:
        await throttle(conn, request, "register")
        encoded = await run_in_threadpool(hash_password, password)
        row = await conn.fetchrow("""INSERT INTO career_accounts(username,password_hash) VALUES ($1,$2)
            ON CONFLICT(username) DO NOTHING RETURNING *""", data.username.lower(), encoded)
        if row is None:
            raise HTTPException(409, "That username is already taken.", headers=PRIVATE)
        await create_session(conn, request, response, row["id"])
        return state(row)


@router.post("/login")
async def login(data: Credentials, request: Request, response: Response):
    same_origin(request)
    password = data.password.get_secret_value()
    if len(password) > 128:
        raise HTTPException(401, "Incorrect username or password.", headers=PRIVATE)
    async with connection() as conn:
        key = await throttle(conn, request, "login", data.username.lower())
        row = await conn.fetchrow("SELECT * FROM career_accounts WHERE username=$1", data.username.lower())
        valid = await run_in_threadpool(verify_password, password, row["password_hash"] if row else DUMMY_HASH)
        if not row or not valid:
            raise HTTPException(401, "Incorrect username or password.", headers=PRIVATE)
        await conn.execute("DELETE FROM career_auth_attempts WHERE key=$1", key)
        await create_session(conn, request, response, row["id"])
        return state(row)


@router.get("/session")
async def session(request: Request, response: Response):
    response.headers.update(PRIVATE)
    async with connection() as conn:
        row = await user(conn, request, required=False)
        return state(row) if row else {"user": None}


@router.post("/logout")
async def logout(request: Request, response: Response):
    same_origin(request)
    async with connection() as conn:
        await conn.execute("DELETE FROM career_sessions WHERE token_hash=$1", token_hash(request.cookies.get(COOKIE, "")))
    response.delete_cookie(COOKIE, path="/")
    response.headers.update(PRIVATE)
    return {"user": None}


@router.put("/state")
async def save_state(data: SavedState, request: Request, response: Response):
    same_origin(request)
    response.headers.update(PRIVATE)
    async with connection() as conn:
        account = await user(conn, request)
        row = await conn.fetchrow("""UPDATE career_accounts SET profile=$2::jsonb, preferences=$3::jsonb, revision=revision+1
            WHERE id=$1 AND revision=$4 RETURNING *""", account["id"], data.profile.model_dump_json(), data.preferences.model_dump_json(), data.revision)
        if row is None:
            raise HTTPException(409, "Your account changed in another tab or device. Reload account data before saving.", headers=PRIVATE)
        return state(row)


@router.put("/applications/{job_id:path}")
async def save_application(job_id: str, data: Application, request: Request, response: Response):
    same_origin(request)
    if not re.fullmatch(r"[A-Za-z0-9_:.-]{1,200}", job_id):
        raise HTTPException(400, "Invalid job identifier.", headers=PRIVATE)
    response.headers.update(PRIVATE)
    async with connection() as conn:
        account = await user(conn, request)
        applications = json_value(account["applications"])
        if data.status and job_id not in applications and len(applications) >= 2000:
            raise HTTPException(400, "You can save up to 2,000 application statuses.", headers=PRIVATE)
        if data.status:
            await conn.execute("UPDATE career_accounts SET applications=applications || jsonb_build_object($2::text,$3::text) WHERE id=$1", account["id"], job_id, data.status)
        else:
            await conn.execute("UPDATE career_accounts SET applications=applications-$2::text WHERE id=$1", account["id"], job_id)
        return {"job_id": job_id, "status": data.status}
