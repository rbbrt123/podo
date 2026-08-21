import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import shutil

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
                target_minutes INTEGER NOT NULL,
                intros INTEGER NOT NULL DEFAULT 1,
                host_agent_id INTEGER REFERENCES agents(id),
                instructions TEXT NOT NULL DEFAULT '',
                elapsed_seconds REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                audio_path TEXT,
                created_at TEXT NOT NULL
            )
        """)
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
        if "intros" not in existing_columns:
            conn.execute("ALTER TABLE episodes ADD COLUMN intros INTEGER NOT NULL DEFAULT 1")
        if "host_agent_id" not in existing_columns:
            conn.execute("ALTER TABLE episodes ADD COLUMN host_agent_id INTEGER REFERENCES agents(id)")
        if "instructions" not in existing_columns:
            conn.execute("ALTER TABLE episodes ADD COLUMN instructions TEXT NOT NULL DEFAULT ''")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER NOT NULL REFERENCES episodes(id),
                turn_index INTEGER NOT NULL,
                speaker TEXT NOT NULL,
                text TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                prompt TEXT NOT NULL,
                voice_id TEXT NOT NULL,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                is_host INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        existing_agent_columns = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
        if "is_host" not in existing_agent_columns:
            conn.execute("ALTER TABLE agents ADD COLUMN is_host INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE agents SET is_host = 1 WHERE is_builtin = 1 AND name = 'Nova'")


def create_episode(title: str, topic: str, target_minutes: int, intros: bool, host_agent_id: int, instructions: str = "") -> int:
    resolved_title = title.strip() or topic
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO episodes (title, topic, target_minutes, intros, host_agent_id, instructions, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (resolved_title, topic, target_minutes, int(intros), host_agent_id, instructions, datetime.now(timezone.utc).isoformat()),
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


def update_episode_elapsed(episode_id: int, elapsed_seconds: float) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE episodes SET elapsed_seconds = ? WHERE id = ?",
            (elapsed_seconds, episode_id),
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
            "SELECT id, title, topic, target_minutes, status, created_at FROM episodes ORDER BY created_at DESC"
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


def create_agent(name: str, prompt: str, voice_id: str, is_builtin: bool = False, is_host: bool = False) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO agents (name, prompt, voice_id, is_builtin, is_host, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, prompt, voice_id, int(is_builtin), int(is_host), datetime.now(timezone.utc).isoformat()),
        )
        return cursor.lastrowid


def list_agents() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM agents ORDER BY is_builtin DESC, name").fetchall()
        return [dict(row) for row in rows]


def get_agent(agent_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None


def update_agent(agent_id: int, name: str, prompt: str, voice_id: str, is_host: bool = False) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE agents SET name = ?, prompt = ?, voice_id = ?, is_host = ? WHERE id = ?",
            (name, prompt, voice_id, int(is_host), agent_id),
        )


def delete_agent(agent_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))


def delete_episode(episode_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM turns WHERE episode_id = ?", (episode_id,))
        conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
    episode_dir = EPISODES_DIR / str(episode_id)
    if episode_dir.exists():
        shutil.rmtree(episode_dir)


def seed_builtin_agents() -> None:
    defaults = [
        ("Nova", "You are Nova, a podcast host who thinks in tangents and vivid analogies. You're relentlessly curious but impatient with vague answers — when a guest gives you an abstract claim, you immediately demand a concrete example or a 'so what does that mean for a normal person' follow-up. You interrupt (politely) when you sense someone is about to ramble into jargon, and you have a habit of restating complex points as slightly absurd analogies to test whether you actually understood them. You're not afraid to say 'wait, that sounds wrong' out loud.", "aMSt68OGf4xUZAnLpTU8", True),

        ("Professor Okafor", "You are Professor Okafor, a domain expert with a reputation for overturning conventional wisdom using counterintuitive research and real data. You speak with quiet authority and mild academic stubbornness — you don't back down from a claim just because it's challenged, you defend it with evidence, though you'll happily admit uncertainty on things outside your specialty. You have a dry wit and occasionally can't resist a pointed jab at popular misconceptions. You dislike vague hand-waving and will gently call it out.", "vBKc2FfBKJfcZNyEt1n6", False),

        ("Sam", "You are Sam, a sharp skeptical outsider who wasn't briefed on the topic beforehand — you're hearing the claims for the first time, like the audience is. You ask the 'dumb' questions that are actually the important ones ('wait, but doesn't that contradict what you just said?'), push everyone to explain jargon in plain language, and are openly unconvinced until someone gives you a real-world stake or consequence. You're not hostile, just stubbornly literal-minded, and you enjoy poking holes in things that sound too neat.", "UgBBYS2sOqTuMpoF3BR0", False),
    ]
    with sqlite3.connect(DB_PATH) as conn:
        already_seeded = conn.execute("SELECT COUNT(*) FROM agents WHERE is_builtin = 1").fetchone()[0]
        if already_seeded:
            return
        for name, prompt, voice_id, is_host in defaults:
            conn.execute(
                "INSERT INTO agents (name, prompt, voice_id, is_builtin, is_host, created_at) VALUES (?, ?, ?, 1, ?, ?)",
                (name, prompt, voice_id, int(is_host), datetime.now(timezone.utc).isoformat()),
            )