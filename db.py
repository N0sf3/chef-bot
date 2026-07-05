"""
db.py — the bot's memory. One SQLite file on disk, no server.
Open it anytime with:  sqlite3 chef.db  (then .tables, .schema)
"""

import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "chef.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    """Create tables if missing, then migrate old DBs to the new columns."""
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        schema = f.read()
    with _conn() as conn:
        conn.executescript(schema)
        _migrate(conn)


def _migrate(conn) -> None:
    """Add any columns that older databases don't have yet. Safe to re-run."""
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    wanted = {
        "equipment": "TEXT",
        "skill": "TEXT",
        "lang": "TEXT DEFAULT 'es'",
        "xp": "INTEGER DEFAULT 0",
    }
    for name, decl in wanted.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {decl}")


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
def ensure_user(chat_id: int) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))


def get_user(chat_id: int) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()


def _set_field(chat_id: int, field: str, value) -> None:
    with _conn() as conn:
        conn.execute(f"UPDATE users SET {field} = ? WHERE chat_id = ?", (value, chat_id))


def set_profile(chat_id: int, text: str) -> None:
    _set_field(chat_id, "profile", text)


def set_equipment(chat_id: int, text: str) -> None:
    _set_field(chat_id, "equipment", text)


def set_skill(chat_id: int, text: str) -> None:
    _set_field(chat_id, "skill", text)


def set_lang(chat_id: int, lang: str) -> None:
    _set_field(chat_id, "lang", lang)


def get_lang(chat_id: int) -> str:
    row = get_user(chat_id)
    return (row["lang"] if row and row["lang"] else "es")


# ---------------------------------------------------------------------------
# xp — returns (old_xp, new_xp) so the caller can detect a level-up
# ---------------------------------------------------------------------------
def add_xp(chat_id: int, amount: int) -> tuple[int, int]:
    with _conn() as conn:
        row = conn.execute("SELECT xp FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        old = (row["xp"] if row and row["xp"] is not None else 0)
        new = old + amount
        conn.execute("UPDATE users SET xp = ? WHERE chat_id = ?", (new, chat_id))
        return old, new


def get_xp(chat_id: int) -> int:
    row = get_user(chat_id)
    return (row["xp"] if row and row["xp"] is not None else 0)


# ---------------------------------------------------------------------------
# pantry
# ---------------------------------------------------------------------------
def set_pantry(chat_id: int, items: list[str]) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM pantry WHERE chat_id = ?", (chat_id,))
        conn.executemany(
            "INSERT INTO pantry (chat_id, item) VALUES (?, ?)",
            [(chat_id, item) for item in items],
        )


def get_pantry(chat_id: int) -> list[str]:
    with _conn() as conn:
        rows = conn.execute("SELECT item FROM pantry WHERE chat_id = ?", (chat_id,)).fetchall()
        return [r["item"] for r in rows]


# ---------------------------------------------------------------------------
# taste_events
# ---------------------------------------------------------------------------
def log_taste(chat_id: int, note: str) -> None:
    with _conn() as conn:
        conn.execute("INSERT INTO taste_events (chat_id, note) VALUES (?, ?)", (chat_id, note))


def recent_tastes(chat_id: int, limit: int = 15) -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT note FROM taste_events WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [r["note"] for r in rows]


# ---------------------------------------------------------------------------
# recipes_served
# ---------------------------------------------------------------------------
def log_recipe(chat_id: int, full_text: str) -> None:
    title = full_text.strip().splitlines()[0][:200] if full_text.strip() else "(sin título)"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO recipes_served (chat_id, title, full_text) VALUES (?, ?, ?)",
            (chat_id, title, full_text),
        )


def recent_recipe_titles(chat_id: int, limit: int = 5) -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT title FROM recipes_served WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [r["title"] for r in rows]
