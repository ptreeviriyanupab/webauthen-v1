"""Clear only the 'successful_students' table.

The four synthetic lab accounts in 'users' are never touched by this script.
Run from the project root:

    python reset_results.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "lab.db"


def main() -> None:
    if not DB_PATH.exists():
        print(f"No database found at {DB_PATH}. Nothing to reset.")
        return

    answer = input(
        "This will permanently delete all rows in 'successful_students' "
        "(lab accounts in 'users' are NOT affected). Continue? [y/N]: "
    ).strip().lower()
    if answer != "y":
        print("Aborted. No changes made.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("DELETE FROM successful_students")
        conn.commit()
        print(f"Cleared {cursor.rowcount} submission(s) from 'successful_students'.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
