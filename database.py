import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("bot_data.sqlite3")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS groups(chat_id INTEGER PRIMARY KEY, title TEXT)")
        conn.execute("""CREATE TABLE IF NOT EXISTS global_replies(
            keyword TEXT PRIMARY KEY COLLATE NOCASE,
            response TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            media_type TEXT NOT NULL DEFAULT 'text',
            file_id TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS saved_permissions(
            chat_id INTEGER PRIMARY KEY, permissions_json TEXT NOT NULL)""")
        # Migrate the v2 table without losing existing text replies.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(global_replies)")}
        if "media_type" not in columns:
            conn.execute("ALTER TABLE global_replies ADD COLUMN media_type TEXT NOT NULL DEFAULT 'text'")
        if "file_id" not in columns:
            conn.execute("ALTER TABLE global_replies ADD COLUMN file_id TEXT")


def register_group(chat_id, title):
    with connect() as conn:
        conn.execute(
            "INSERT INTO groups VALUES(?, ?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title",
            (chat_id, title)
        )


def get_groups():
    with connect() as conn:
        return [row[0] for row in conn.execute("SELECT chat_id FROM groups")]


def add_global_reply(keyword, media_type, file_id, response):
    with connect() as conn:
        conn.execute("""
            INSERT INTO global_replies(keyword,response,enabled,media_type,file_id)
            VALUES(?,?,1,?,?)
            ON CONFLICT(keyword) DO UPDATE SET
                response=excluded.response, enabled=1,
                media_type=excluded.media_type, file_id=excluded.file_id
        """, (keyword, response, media_type, file_id))


def delete_global_reply(keyword):
    with connect() as conn:
        cur = conn.execute("DELETE FROM global_replies WHERE keyword=? COLLATE NOCASE", (keyword,))
        return cur.rowcount > 0


def edit_global_reply(old_keyword, new_keyword, media_type, file_id, response):
    with connect() as conn:
        cur = conn.execute("""
            UPDATE global_replies SET keyword=?, response=?, media_type=?, file_id=?
            WHERE keyword=? COLLATE NOCASE
        """, (new_keyword, response, media_type, file_id, old_keyword))
        return cur.rowcount > 0


def list_global_replies():
    with connect() as conn:
        return conn.execute("""
            SELECT keyword,media_type,file_id,response,enabled
            FROM global_replies ORDER BY keyword
        """).fetchall()


def set_reply_enabled(keyword, enabled):
    with connect() as conn:
        cur = conn.execute(
            "UPDATE global_replies SET enabled=? WHERE keyword=? COLLATE NOCASE",
            (int(enabled), keyword)
        )
        return cur.rowcount > 0


def save_permissions(chat_id, permissions):
    with connect() as conn:
        conn.execute("""
            INSERT INTO saved_permissions VALUES(?,?)
            ON CONFLICT(chat_id) DO UPDATE SET permissions_json=excluded.permissions_json
        """, (chat_id, json.dumps(permissions)))


def get_saved_permissions(chat_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT permissions_json FROM saved_permissions WHERE chat_id=?", (chat_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def clear_saved_permissions(chat_id):
    with connect() as conn:
        conn.execute("DELETE FROM saved_permissions WHERE chat_id=?", (chat_id,))
