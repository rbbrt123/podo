import os
import tempfile
import time

import gradio as gr
import httpx


BACKEND_URL = os.getenv("PODO_BACKEND_URL", "http://localhost:8000")


def _download_audio(episode_id):
    """download the finished episode's MP3 from the bacckend and save it locally so the UI can play it"""
    response = httpx.get(f"{BACKEND_URL}/episodes/{episode_id}/audio")
    response.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.write(response.content)
    tmp.close()
    return tmp.name


def generate_episode(topic, num_turns):
    """frontend's whole workflow for kicking off an episode and watching it complete"""
    if not topic.strip():
        yield "Please enter a topic.", None, ""
        return

    response = httpx.post(
        f"{BACKEND_URL}/episodes",
        json={"topic": topic, "num_turns": int(num_turns)},
    )
    response.raise_for_status()
    episode_id = response.json()["id"]

    while True:
        episode = httpx.get(f"{BACKEND_URL}/episodes/{episode_id}").json()
        status = episode["status"]

        if status == "complete":
            transcript = "\n\n".join(f"{t['speaker']}: {t['text']}" for t in episode["turns"])
            yield f"Episode #{episode_id}: done!", _download_audio(episode_id), transcript
            return
        elif status == "failed":
            yield f"Episode #{episode_id} failed: {episode['error_message']}", None, ""
            return
        else:
            yield f"Episode #{episode_id}: {status}...", None, ""
            time.sleep(2)


def list_episode_choices():
    episodes = httpx.get(f"{BACKEND_URL}/episodes").json()
    choices = [(f"#{ep['id']} — {ep['topic']} ({ep['status']})", ep["id"]) for ep in episodes]
    return gr.Dropdown(choices=choices)