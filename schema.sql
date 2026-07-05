-- schema.sql — the shape of the bot's memory.
-- Fresh installs get all columns here; existing DBs get migrated in db.py.

-- One row per user.
CREATE TABLE IF NOT EXISTS users (
    chat_id    INTEGER PRIMARY KEY,
    profile    TEXT,              -- goals, allergies, region, diet
    equipment  TEXT,              -- tools + available cooking methods
    skill      TEXT,              -- self-reported: principiante/intermedio/avanzado
    lang       TEXT DEFAULT 'es', -- UI language for command replies
    xp         INTEGER DEFAULT 0  -- kitchen XP (the RPG layer)
);

-- What's in the kitchen right now. Wiped and refilled on each /despensa update.
CREATE TABLE IF NOT EXISTS pantry (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id  INTEGER NOT NULL,
    item     TEXT NOT NULL
);

-- The crown jewel: every taste reaction, append-only. This is what compounds.
CREATE TABLE IF NOT EXISTS taste_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id  INTEGER NOT NULL,
    note     TEXT NOT NULL,
    created  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Everything the chef has cooked, so it never repeats and can reference dishes.
CREATE TABLE IF NOT EXISTS recipes_served (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    title      TEXT NOT NULL,
    full_text  TEXT NOT NULL,
    created    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Access control: only these users (plus the owner) get served.
CREATE TABLE IF NOT EXISTS allowed_users (
    chat_id  INTEGER PRIMARY KEY,
    note     TEXT,
    added    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Activation codes you hand out. Redeeming one adds that user to allowed_users.
CREATE TABLE IF NOT EXISTS access_codes (
    code     TEXT PRIMARY KEY,
    note     TEXT,               -- e.g. "Coach Mike batch 1"
    used_by  INTEGER,            -- chat_id that redeemed it (NULL = unused)
    created  TEXT NOT NULL DEFAULT (datetime('now'))
);
