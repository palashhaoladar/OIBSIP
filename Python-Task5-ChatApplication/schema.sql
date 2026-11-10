-- schema.sql — kept as documentation/reference for the database structure.
-- db.py init_db() executes these same statements programmatically at startup.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    sender    TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    content   TEXT NOT NULL
);

-- Helpful index: the chat history query filters by room_name,
-- so indexing it keeps lookups fast as the table grows.
CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_name);
