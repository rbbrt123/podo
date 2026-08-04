import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("PODO_DATA_DIR", PROJECT_ROOT / "data"))
DB_PATH = DATA_DIR / "podo.db"
EPISODES_DIR = DATA_DIR / "episodes"


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                num_turns INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                audio_path TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER NOT NULL REFERENCES episodes(id),
                turn_index INTEGER NOT NULL,
                speaker TEXT NOT NULL,
                text TEXT NOT NULL
            )
        """)


def create_episode(title: str, topic: str, num_turns: int) -> int:
    resolved_title = title.strip() or topic
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO episodes (title, topic, num_turns, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (resolved_title, topic, num_turns, datetime.now(timezone.utc).isoformat()),
        )
        return cursor.lastrowid


def update_episode_status(
    episode_id: int,
    status: str,
    error_message: str | None = None,
    audio_path: str | None = None,
):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE episodes SET status = ?, error_message = ?, audio_path = ? WHERE id = ?",
            (status, error_message, audio_path, episode_id),
        )


def save_turn(episode_id: int, turn_index: int, speaker: str, text: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO turns (episode_id, turn_index, speaker, text) VALUES (?, ?, ?, ?)",
            (episode_id, turn_index, speaker, text),
        )


def list_episodes() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, title, topic, num_turns, status, created_at FROM episodes ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_episode(episode_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        episode_row = conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        if episode_row is None:
            return None
        turn_rows = conn.execute(
            "SELECT speaker, text FROM turns WHERE episode_id = ? ORDER BY turn_index",
            (episode_id,),
        ).fetchall()
        episode = dict(episode_row)
        episode["turns"] = [dict(row) for row in turn_rows]
        return episode


def episode_audio_path(episode_id: int) -> Path:
    episode_dir = EPISODES_DIR / str(episode_id)
    episode_dir.mkdir(parents=True, exist_ok=True)
    return episode_dir / "episode.mp3"