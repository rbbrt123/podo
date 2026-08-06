from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import generation, storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    storage.seed_builtin_agents()
    yield

app = FastAPI(lifespan=lifespan)


class CreateEpisodeRequest(BaseModel):
    title: str = ""
    topic: str
    num_turns: int = Field(default=6, ge=2, le=20)


class AgentRequest(BaseModel):
    name: str
    prompt: str
    voice_id: str


@app.post("/episodes")
def create_episode(request: CreateEpisodeRequest, background_tasks: BackgroundTasks):
    episode_id = storage.create_episode(request.title, request.topic, request.num_turns)
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


@app.post("/agents")
def create_agent(request: AgentRequest):
    agent_id = storage.create_agent(request.name, request.prompt, request.voice_id)
    return {"id": agent_id}


@app.get("/agents")
def list_agents():
    return storage.list_agents()


@app.get("/agents/{agent_id}")
def get_agent(agent_id: int):
    agent = storage.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.put("/agents/{agent_id}")
def update_agent(agent_id: int, request: AgentRequest):
    agent = storage.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["is_builtin"]:
        raise HTTPException(status_code=400, detail="Built-in agents can't be edited directly — duplicate it into a new agent instead")
    storage.update_agent(agent_id, request.name, request.prompt, request.voice_id)
    return {"status": "updated"}


@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: int):
    agent = storage.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["is_builtin"]:
        raise HTTPException(status_code=400, detail="Built-in agents can't be deleted")
    storage.delete_agent(agent_id)
    return {"status": "deleted"}
