"""
db.py — the bot's memory.

Everything the chef remembers about a user lives in one SQLite file on disk.
SQLite = a whole database in a single file, no server to run. Perfect for a
small bot. Each Telegram user is identified by their chat_id (a number).

You can open the file anytime with:  sqlite3 chef.db  (then .tables, .schema)
"""

import os
import sqlite3

# The database file. On the VPS this sits on a persistent volume so it
# survives redeploys (same idea as your n8n volume).
DB_PATH = os.environ.get("DB_PATH", "chef.db")


def _conn() -> sqlite3.Connection:
    """Open a connection. row_factory lets us read columns by name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    """Create the tables if they don't exist yet. Safe to run every startup."""
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        schema = f.read()
    with _conn() as conn:
        conn.executescript(schema)


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
def ensure_user(chat_id: int) -> None:
    """First time we see a chat_id, create its row. INSERT OR IGNORE = no dupes."""
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))


# ---------------------------------------------------------------------------
# profile — goals, allergies, region. One block of text per user for now.
# ---------------------------------------------------------------------------
def set_profile(chat_id: int, text: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET profile = ? WHERE chat_id = ?", (text, chat_id))


def get_profile(chat_id: int) -> str | None:
    with _conn() as conn:
        row = conn.execute("SELECT profile FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        return row["profile"] if row else None


# ---------------------------------------------------------------------------
# pantry — what's in the kitchen right now. Replaced wholesale on each update.
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
# taste_events — the gold. Append-only log of every reaction. Never deleted.
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
# recipes_served — so the chef doesn't repeat itself and can reference past dishes
# ---------------------------------------------------------------------------
def log_recipe(chat_id: int, full_text: str) -> None:
    # store just the first line as the "title" for cheap lookups
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
