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


def load_episode(episode_id):
    """This runs when the user picks something from that dropdown, to actually load and display an existing episode"""
    if episode_id is None:
        return None, ""
    episode = httpx.get(f"{BACKEND_URL}/episodes/{episode_id}").json()
    if episode["status"] != "complete":
        return None, f"Episode is {episode['status']}, no audio yet."
    transcript = "\n\n".join(f"{t['speaker']}: {t['text']}" for t in episode["turns"])
    return _download_audio(episode_id), transcript


def build_app():
    """assembling the actual UI"""
    with gr.Blocks(title="podo") as demo:
        gr.Markdown("# podo")

        with gr.Tab("Generate"):
            topic_input = gr.Textbox(label="Topic")
            num_turns_input = gr.Slider(minimum=2, maximum=20, value=6, step=1, label="Number of turns")
            generate_button = gr.Button("Generate episode")
            status_output = gr.Markdown()
            audio_output = gr.Audio(label="Episode audio")
            transcript_output = gr.Textbox(label="Transcript", lines=15, interactive=False)

        generate_button.click(
                fn=generate_episode,
                inputs=[topic_input, num_turns_input],
                outputs=[status_output, audio_output, transcript_output],
            )

        with gr.Tab("Library"):
            refresh_button = gr.Button("Refresh")
            episode_dropdown = gr.Dropdown(label="Saved episodes", choices=[])
            library_audio_output = gr.Audio(label="Episode audio")
            library_transcript_output = gr.Textbox(label="Transcript", lines=15, interactive=False)

            refresh_button.click(fn=list_episode_choices, outputs=episode_dropdown)
            episode_dropdown.change(
                fn=load_episode,
                inputs=episode_dropdown,
                outputs=[library_audio_output, library_transcript_output],
            )
            demo.load(fn=list_episode_choices, outputs=episode_dropdown)

    return demo


if __name__ == "__main__":
    build_app().launch()