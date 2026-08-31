# database.py
"""
SQLite database layer with WAL mode for concurrent access.
Manages sessions, messages, and usage tracking.
Auth tables removed — uses a single default user.
"""
import sqlite3
import json
import logging
from datetime import datetime, date
from contextlib import contextmanager
import config

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """Context manager for database connections with WAL mode."""
    conn = sqlite3.connect(config.DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize all database tables and seed default user."""
    with get_connection() as conn:
        c = conn.cursor()

        # Users table (minimal — just for FK compatibility)
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL DEFAULT '',
                role TEXT DEFAULT 'admin',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed default user if not exists
        existing = c.execute("SELECT id FROM users WHERE id = 1").fetchone()
        if not existing:
            c.execute(
                "INSERT INTO users (id, username, password_hash, role) VALUES (1, 'default', '', 'admin')"
            )

        # Sessions table
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT 'New Chat',
                pinned INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Messages table
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                source_type TEXT,
                score REAL,
                model_used TEXT,
                token_usage TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Session documents (tracks which docs are attached to which session)
        c.execute("""
            CREATE TABLE IF NOT EXISTS session_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                document_name TEXT NOT NULL,
                file_type TEXT,
                ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        # Usage tracking
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Migrations for messages table — add columns that may be missing from older databases
        for col in ["user_id INTEGER", "model_used TEXT", "token_usage TEXT", "source_type TEXT", "score REAL", "sources TEXT"]:
            col_name = col.split()[0]
            try:
                c.execute(f"ALTER TABLE messages ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass  # Column already exists

    logger.info("Database initialized successfully")


# ─── Session Operations ─────────────────────────────────────

def create_session(session_id: str, user_id: int, title: str = "New Chat") -> dict:
    """Create a new chat session."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, title) VALUES (?, ?, ?)",
            (session_id, user_id, title),
        )
    return {"id": session_id, "user_id": user_id, "title": title}


def get_user_sessions(user_id: int) -> list[dict]:
    """Get all sessions for a user, ordered by pinned first then most recent."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT s.id, s.title, s.pinned, s.created_at, s.updated_at,
                      COUNT(m.id) as message_count
               FROM sessions s
               LEFT JOIN messages m ON m.session_id = s.id
               WHERE s.user_id = ?
               GROUP BY s.id
               ORDER BY s.pinned DESC, s.updated_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_session_messages(session_id: str, user_id: int) -> list[dict]:
    """Get all messages for a session."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, content, sources, source_type, score, model_used,
                      token_usage, timestamp
               FROM messages
               WHERE session_id = ? AND user_id = ?
               ORDER BY id ASC""",
            (session_id, user_id),
        ).fetchall()

    messages = []
    for row in rows:
        msg = dict(row)
        if msg.get("sources"):
            try:
                msg["sources"] = json.loads(msg["sources"])
            except Exception:
                msg["sources"] = []
        if msg.get("token_usage"):
            try:
                msg["token_usage"] = json.loads(msg["token_usage"])
            except Exception:
                msg["token_usage"] = None
        messages.append(msg)
    return messages


def save_message(
    session_id: str,
    user_id: int,
    role: str,
    content: str,
    sources: list[dict] = None,
    source_type: str = None,
    score: float = None,
    model_used: str = None,
    token_usage: dict = None,
):
    """Save a message to the database."""
    with get_connection() as conn:
        # Ensure session exists
        existing = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not existing:
            create_session(session_id, user_id)

        # Auto-title: use first user message as session title
        if role == "user":
            conn.execute(
                """UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND title = 'New Chat'""",
                (content[:50], session_id),
            )
            # Always update timestamp
            conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )

        conn.execute(
            """INSERT INTO messages
               (session_id, user_id, role, content, sources, source_type, score, model_used, token_usage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                user_id,
                role,
                content,
                json.dumps(sources) if sources else None,
                source_type,
                score,
                model_used,
                json.dumps(token_usage) if token_usage else None,
            ),
        )


def delete_session(session_id: str, user_id: int):
    """Delete a session and all its messages."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )


def rename_session(session_id: str, user_id: int, new_title: str):
    """Rename a session."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ? AND user_id = ?",
            (new_title, session_id, user_id),
        )


def toggle_pin_session(session_id: str, user_id: int):
    """Toggle pin status of a session."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE sessions SET pinned = CASE WHEN pinned = 1 THEN 0 ELSE 1 END
               WHERE id = ? AND user_id = ?""",
            (session_id, user_id),
        )


def clear_user_sessions(user_id: int):
    """Delete all sessions for a user."""
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def search_sessions(user_id: int, query: str) -> list[dict]:
    """Search across all sessions by message content."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT s.id, s.title, s.pinned, s.created_at, s.updated_at
               FROM sessions s
               JOIN messages m ON m.session_id = s.id
               WHERE s.user_id = ? AND m.content LIKE ?
               ORDER BY s.updated_at DESC""",
            (user_id, f"%{query}%"),
        ).fetchall()
    return [dict(row) for row in rows]


# ─── Session Documents ──────────────────────────────────────

def add_session_document(session_id: str, document_name: str, file_type: str):
    """Track a document uploaded to a specific session."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO session_documents (session_id, document_name, file_type) VALUES (?, ?, ?)",
            (session_id, document_name, file_type),
        )


def get_session_documents(session_id: str) -> list[dict]:
    """Get all documents attached to a session."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT document_name, file_type, ingested_at FROM session_documents WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# ─── Usage Tracking ─────────────────────────────────────────

def log_usage(user_id: int, action: str):
    """Log a usage event (query, ingest, etc.)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO usage_log (user_id, action) VALUES (?, ?)",
            (user_id, action),
        )


def get_daily_usage(user_id: int, action: str) -> int:
    """Get today's usage count for a specific action."""
    today = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM usage_log
               WHERE user_id = ? AND action = ? AND DATE(timestamp) = ?""",
            (user_id, action, today),
        ).fetchone()
    return row["cnt"] if row else 0


def get_global_stats() -> dict:
    """Get global usage statistics for admin panel."""
    with get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        total_sessions = conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()["cnt"]
        total_messages = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()["cnt"]
        today = date.today().isoformat()
        today_queries = conn.execute(
            "SELECT COUNT(*) as cnt FROM usage_log WHERE action = 'query' AND DATE(timestamp) = ?",
            (today,),
        ).fetchone()["cnt"]
    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "today_queries": today_queries,
    }
