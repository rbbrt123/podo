# podo — AI Podcast Generator

A personal project exploring multi-agent AI: any number of LLM-driven
personas hold a spoken conversation about a topic you choose, generated
end-to-end with Claude (dialogue) and ElevenLabs (voice).

**Status: early / actively in development.** Currently working:
- Any number of personas can hold a back-and-forth conversation, with
  the model itself deciding who speaks next each turn
- Each persona gets a distinct AI voice
- Turns are stitched into one playable episode
- A FastAPI backend generates episodes in the background and a Gradio
  web UI lets you kick them off and browse a library of past episodes
- Personas ("agents") are user-created and editable in an **Agent
  Lab** tab — a name, a prompt, and a voice picked from your
  ElevenLabs voice library, with instant preview playback of each
  voice. Three locked built-in agents ship by default; anything you
  create yourself is fully editable, and you can duplicate a built-in
  into an editable copy to start from

**Planned next:** a listener knowledge-level parameter, so the
conversation's depth and vocabulary calibrate to what you already know.

## How it's structured

The app is split into two services:

- **`backend/`** — a FastAPI service that owns episode generation and
  agent storage. It exposes a REST API (`POST /episodes`,
  `GET /episodes`, `GET /episodes/{id}`, `GET /episodes/{id}/audio`,
  full CRUD on `/agents`, and `GET /voices` which proxies your
  ElevenLabs voice library so the API key stays server-side), runs the
  conversation loop against Claude, synthesizes each turn with
  ElevenLabs, stitches the turns into a single MP3, and persists
  episodes/turns/agents in a SQLite database.
- **`frontend/`** — a Gradio app with three tabs: **Generate** (pick
  at least two agents, submit a topic and turn count, watch status
  update, play the finished episode), **Library** (browse and replay
  past episodes), and **Agent Lab** (create/edit/delete agents — a
  name, a prompt, and a voice chosen from a dropdown backed by
  `GET /voices`, with click-to-preview audio for each voice). It talks
  to the backend purely over HTTP.

Generated data (the SQLite DB and per-episode MP3s) lives under
`data/`, shared between the backend container and your host via a
volume mount.

There's also a standalone `main.py` at the repo root — the original
single-script prototype this project grew out of. It runs one
hardcoded conversation end-to-end and writes `episode.mp3` to the
current directory; it's kept around for quick experiments but isn't
part of the backend/frontend app.

## Requirements

- An [Anthropic API key](https://console.anthropic.com/) and an
  [ElevenLabs API key](https://elevenlabs.io/)
- Either:
  - **Docker** and **Docker Compose**, or
  - **Python 3.14** and [**uv**](https://docs.astral.sh/uv/) plus
    **ffmpeg** installed locally (needed by `pydub` to stitch turns
    together)

## Setup

1. Clone the repo and create a `.env` file in the project root with
   your API keys:

   ```
   ANTHROPIC_API_KEY=your-key-here
   ELEVENLABS_API_KEY=your-key-here
   ```

2. Run it — pick one of the two options below.

### Option A: Docker Compose (recommended)

```
docker compose up --build
```

This builds and starts both services:
- Backend on [http://localhost:8000](http://localhost:8000)
- Frontend on [http://localhost:7860](http://localhost:7860)

Open the frontend URL in your browser, pick at least two agents,
enter a topic and number of turns on the **Generate** tab, and hit
"Generate episode". Generated episodes and the SQLite database are
written to `./data` on your host (mounted into the backend container)
and persist across restarts.

### Option B: Run locally with uv

Run the backend and frontend in two separate terminals from the
project root.

Backend:
```
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:
```
cd frontend
uv sync
uv run python app.py
```

The frontend defaults to talking to the backend at
`http://localhost:8000`; set `PODO_BACKEND_URL` if you're running the
backend elsewhere. By default, generated data is written to `./data`
at the project root; set `PODO_DATA_DIR` to change that. Then open
[http://localhost:7860](http://localhost:7860).

### Running the standalone prototype instead

If you just want to generate a single episode from the command line
without starting either service:

```
uv sync
uv run main.py
```

This uses the same `.env` file and writes `episode.mp3` to the
current directory.

## Configuration

| Variable | Used by | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | backend / `main.py` | — (required) | Generates each persona's dialogue turn |
| `ELEVENLABS_API_KEY` | backend / `main.py` | — (required) | Synthesizes each turn's audio |
| `PODO_DATA_DIR` | backend | `./data` | Where the SQLite DB and episode audio are stored |
| `PODO_BACKEND_URL` | frontend | `http://localhost:8000` | Where the frontend looks for the backend API |

Agents (a persona prompt plus a voice picked from your ElevenLabs
voice library) are managed through the **Agent Lab** tab, or directly
via the `/agents` API — no code changes needed to add, edit, or remove
one. Pick at least two agents on the **Generate** tab for each
episode.

## Why this project

I wanted personalized, multi-expert podcasts on niche topics, calibrated
to what I already know — existing podcasts are usually either too
beginner-level or assume expert background. Building this to learn
multi-agent orchestration and TTS pipelines along the way.
