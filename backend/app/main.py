from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import generation, storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    yield

app = FastAPI(lifespan=lifespan)


class CreateEpisodeRequest(BaseModel):
    topic: str
    num_turns: int = Field(default=6, ge=2, le=20)


@app.post("/episodes")
def create_episode(request: CreateEpisodeRequest, background_tasks: BackgroundTasks):
    episode_id = storage.create_episode(request.topic, request.num_turns)
    background_tasks.add_task(generation.generate_episode, episode_id, request.topic, request.num_turns)
    return {"id": episode_id, "status": "pending"}


@app.get("/episodes")
def list_episodes():
    return storage.list_episodes()


@app.get("/episodes/{episode_id}")
def get_episode(episode_id: int):
    episode = storage.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@app.get("/episodes/{episode_id}/audio")
def get_episode_audio(episode_id: int):
    episode = storage.get_episode(episode_id)
    if episode is None or episode["audio_path"] is None:
        raise HTTPException(status_code=404, detail="Audio not available")
    return FileResponse(storage.DATA_DIR / episode["audio_path"], media_type="audio/mpeg")