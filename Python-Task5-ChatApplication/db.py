"""
db.py — SQLite data layer for the chat application.

Design decisions:
- SQLite is serverless and file-based: perfect for an internship-scale project.
- One connection per operation (SQLite connections are cheap and NOT thread-safe
  to share across Flask's threaded request handlers), so we open with a context
  manager and let it close automatically.
- The `check_same_thread=False` flag plus `threaded=True` on the Flask run
  command lets Socket.IO background threads touch the DB safely.
"""

import sqlite3
from datetime import datetime
from contextlib import closing

DATABASE = "chat.db"  # name of the SQLite file on disk


def get_db_connection():
    """
    Open (and return) a connection to the SQLite database.

    - row_factory = sqlite3.Row  -> lets us access columns by NAME
      (e.g. row["username"]) instead of by index (row[1]).
    - check_same_thread=False    -> Flask-SocketIO runs handlers in background
      threads; without this flag SQLite would raise a ProgrammingError.
    """
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create the database file and both tables if they do not already exist.

    Called once from app.py at startup. The `IF NOT EXISTS` clauses make this
    function idempotent — safe to call on every server restart.
    """
    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()

        # --- users table ---------------------------------------------------
        # id            : auto-incrementing primary key
        # username      : unique login name (UNIQUE constraint enforces this)
        # password_hash : NEVER store plain-text passwords — we store the
        #                 salted hash produced by werkzeug's generate_password_hash()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        # --- messages table ------------------------------------------------
        # room_name : which chat room the message belongs to
        # sender    : username of the author
        # timestamp : set SERVER-side (ISO format) so clients can't fake it
        # content   : message body, stored in PLAIN TEXT (see README §Security)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                room_name TEXT NOT NULL,
                sender    TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                content   TEXT NOT NULL
            )
        """)

        conn.commit()  # persist the CREATE TABLE statements to disk


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------

def create_user(username, password_hash):
    """
    Insert a new user. Returns True on success, False if the username is taken
    (the UNIQUE constraint on username raises sqlite3.IntegrityError).
    """
    try:
        with closing(get_db_connection()) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        # UNIQUE(username) violation -> username already exists
        return False


def get_user_by_username(username):
    """Fetch one user row by username, or None if not found."""
    with closing(get_db_connection()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row  # sqlite3.Row or None


# ---------------------------------------------------------------------------
# Message queries
# ---------------------------------------------------------------------------

def insert_message(room_name, sender, timestamp, content):
    """
    Persist a single chat message.

    Parameters mirror the messages table columns exactly. This function is
    called by the Socket.IO 'message' handler on the server, BEFORE the
    message is broadcast — guaranteeing a message is never lost if a client
    disconnects mid-broadcast.
    """
    with closing(get_db_connection()) as conn:
        conn.execute(
            "INSERT INTO messages (room_name, sender, timestamp, content) "
            "VALUES (?, ?, ?, ?)",
            (room_name, sender, timestamp, content),
        )
        conn.commit()


def get_recent_messages(room_name, limit=50):
    """
    Retrieve the last `limit` messages for a room, in chronological order.

    Why the nested ORDER BY:
      - INNER query: ORDER BY id DESC LIMIT 50  -> grabs the NEWEST 50 rows
      - OUTER query: ORDER BY id ASC            -> flips them back into
        oldest-first order so the chat reads naturally when displayed.
    """
    with closing(get_db_connection()) as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT id, room_name, sender, timestamp, content
                FROM messages
                WHERE room_name = ?
                ORDER BY id DESC
                LIMIT ?
            ) ORDER BY id ASC
            """,
            (room_name, limit),
        ).fetchall()
        # Convert sqlite3.Row objects to plain dicts for JSON serialization
        return [dict(row) for row in rows]
