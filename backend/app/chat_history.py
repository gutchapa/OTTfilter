import sqlite3
import threading
from datetime import datetime

_lock = threading.Lock()
_conn = None

from pathlib import Path

# Ensure DB stored at project root for consistent persistence
def _get_conn():
    global _conn
    if _conn is None:
        # Open or create the SQLite database file
        BASE_DIR = Path(__file__).resolve().parents[2]
        db_file = BASE_DIR / "chat_history.db"
        _conn = sqlite3.connect(str(db_file), check_same_thread=False)
        c = _conn.cursor()
        # Create messages table if not exists
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id  TEXT    NOT NULL,
          role        TEXT    NOT NULL,
          content     TEXT    NOT NULL,
          created_at  TEXT    NOT NULL
        )""")
        _conn.commit()
    return _conn

def save_message(session_id: str, role: str, content: str):
    """Append one turn to the history."""
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, datetime.utcnow().isoformat())
        )
        conn.commit()

def load_history(session_id: str, limit: int = None):
    """Fetch the last `limit` turns for a given session."""
    conn = _get_conn()
    q = "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id DESC"
    params = (session_id,)
    if limit:
        q += f" LIMIT {limit}"
    cur = conn.execute(q, params)
    rows = cur.fetchall()
    # return in chronological order
    return [{"role": r, "content": c, "ts": ts} for r, c, ts in reversed(rows)]
