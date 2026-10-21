"""Accounts, saved reports, and seen-question history in SQLite."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

DB_PATH = Path(os.getenv("APP_DB_PATH", "data/app.db"))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128
MAX_FAILURES = 5
LOCK_SECONDS = 60
MAX_REPORT_CHARS = 50_000
SCRYPT_N, SCRYPT_R, SCRYPT_P = 16384, 8, 1

_failures: dict = {}


class AuthError(ValueError):
    pass


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(_connect()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                overall_score REAL NOT NULL,
                markdown TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS seen_questions (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                question_id TEXT NOT NULL,
                PRIMARY KEY (user_id, question_id)
            );
            """
        )


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


_DUMMY_HASH = _hash("dummy-password-for-timing")


def _normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    return email


def _check_password(password: str, confirm: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"Password must be at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise AuthError(f"Password must be at most {MAX_PASSWORD} characters.")
    if password != confirm:
        raise AuthError("Passwords do not match.")


def _check_lock(email: str) -> None:
    count, until = _failures.get(email, (0, 0.0))
    if count >= MAX_FAILURES:
        if time.time() < until:
            raise AuthError("Too many attempts. Try again in a minute.")
        _failures.pop(email, None)


def _register_failure(email: str) -> None:
    count, _ = _failures.get(email, (0, 0.0))
    _failures[email] = (count + 1, time.time() + LOCK_SECONDS)


def sign_up(email: str, password: str, confirm: str) -> dict:
    email = _normalize_email(email)
    _check_password(password, confirm)
    try:
        with closing(_connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, _hash(password))
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise AuthError("An account with this email already exists.")
    return {"id": user_id, "email": email}


def sign_in(email: str, password: str) -> dict:
    try:
        email = _normalize_email(email)
    except AuthError:
        raise AuthError("Invalid email or password.")
    _check_lock(email)
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    # Always verify against a hash so unknown emails take the same time as wrong passwords.
    verified = _verify(password or "", row["password_hash"] if row else _DUMMY_HASH)
    if not row or not verified:
        _register_failure(email)
        raise AuthError("Invalid email or password.")
    _failures.pop(email, None)
    return {"id": row["id"], "email": row["email"]}


def save_report(user_id: int, score: float, markdown: str) -> int:
    with closing(_connect()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO reports (user_id, overall_score, markdown) VALUES (?, ?, ?)",
            (user_id, score, markdown[:MAX_REPORT_CHARS]),
        )
        return cursor.lastrowid


def list_reports(user_id: int, limit: int = 20) -> list:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, overall_score, created_at FROM reports WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_report(user_id: int, report_id: int) -> str | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT markdown FROM reports WHERE id = ? AND user_id = ?", (report_id, user_id)
        ).fetchone()
    return row["markdown"] if row else None


def seen_question_ids(user_id: int) -> list:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT question_id FROM seen_questions WHERE user_id = ?", (user_id,)).fetchall()
    return [row["question_id"] for row in rows]


def mark_seen(user_id: int, question_ids: list) -> None:
    with closing(_connect()) as conn, conn:
        conn.executemany(
            "INSERT OR IGNORE INTO seen_questions (user_id, question_id) VALUES (?, ?)",
            [(user_id, qid) for qid in question_ids],
        )