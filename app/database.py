import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Project root is the parent of app/, so this resolves to <project>/data/lab.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "lab.db"

# Synthetic classroom accounts only. Passwords are never stored in plaintext --
# only the pre-computed leaked hash and the algorithm used to produce it.
SEED_USERS = [
    ("student01", "4df3840838b302182d5a2f2c326bb232", "md5"),
    ("student02", "4e7c91ebad8e5c5697f4025fda06fa8bc8d7c346", "sha1"),
    (
        "student03",
        "b5f010c1902d79a20b45b76381f07d1977b29fc6acd37b776e2fcb6d1d75cc8e",
        "sha256",
    ),
    (
        "student04",
        "ce11c772a14d78598a0121935f1b25f819d374bb069665e83873c520a9a04c1"
        "482e01454c23ab237810460eca3b218467d1e85170d8e45439a6eae67c6f8d29d",
        "sha512",
    ),
]


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                hash_algorithm TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS successful_students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL UNIQUE,
                student_name TEXT NOT NULL,
                login_username TEXT NOT NULL,
                submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO users (username, password_hash, hash_algorithm) "
            "VALUES (?, ?, ?)",
            SEED_USERS,
        )
        conn.commit()


def get_user_by_username(username: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT username, password_hash, hash_algorithm FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def create_submission(student_id: str, student_name: str, login_username: str) -> None:
    """Raises sqlite3.IntegrityError if student_id has already submitted."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO successful_students (student_id, student_name, login_username) "
            "VALUES (?, ?, ?)",
            (student_id, student_name, login_username),
        )
        conn.commit()


def get_all_submissions():
    with get_connection() as conn:
        return conn.execute(
            "SELECT student_id, student_name, login_username, submitted_at "
            "FROM successful_students ORDER BY submitted_at DESC, id DESC"
        ).fetchall()
