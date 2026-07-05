-- schema.sql — the shape of the bot's memory.
-- Four tables. Each row keyed by chat_id (the Telegram user).

-- One row per user: their profile text (goals, allergies, region).
CREATE TABLE IF NOT EXISTS users (
    chat_id  INTEGER PRIMARY KEY,
    profile  TEXT
);

-- What's in the kitchen right now. Wiped and refilled on each /despensa update.
CREATE TABLE IF NOT EXISTS pantry (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id  INTEGER NOT NULL,
    item     TEXT NOT NULL
);

-- The crown jewel: every taste reaction, append-only, timestamped.
-- This is what compounds into a palate over time.
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
