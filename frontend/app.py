import os
import tempfile

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


def start_generation(title, topic, num_turns):
    """Kicks off generation and starts the polling timer."""
    if not topic.strip():
        return None, "Please enter a topic.", gr.skip(), gr.skip(), gr.Timer(active=False)

    total_turns = int(num_turns)
    response = httpx.post(
        f"{BACKEND_URL}/episodes",
        json={"title": title, "topic": topic, "num_turns": total_turns},
    )
    response.raise_for_status()
    episode_id = response.json()["id"]

    return episode_id, f"Episode #{episode_id}: pending...", None, "", gr.Timer(active=True)


def poll_episode(episode_id):
    """Runs on every Timer tick while a generation is in progress."""
    if episode_id is None:
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()

    episode = httpx.get(f"{BACKEND_URL}/episodes/{episode_id}").json()
    status = episode["status"]

    if status == "complete":
        transcript = "\n\n".join(f"{t['speaker']}: {t['text']}" for t in episode["turns"])
        return f"Episode #{episode_id}: done!", _download_audio(episode_id), transcript, gr.Timer(active=False)
    elif status == "failed":
        return f"Episode #{episode_id} failed: {episode['error_message']}", gr.skip(), gr.skip(), gr.Timer(active=False)
    else:
        status_text = f"Episode #{episode_id}: {status}... ({episode['current_turn']}/{episode['num_turns']} turns)"
        return status_text, gr.skip(), gr.skip(), gr.skip()


def list_episode_choices():
    episodes = httpx.get(f"{BACKEND_URL}/episodes").json()
    choices = [(f"#{ep['id']} — {ep['title']} ({ep['status']})", ep["id"]) for ep in episodes]
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
            title_input = gr.Textbox(label="Episode title (optional - defaults to the topic)")
            topic_input = gr.Textbox(label="Topic")
            num_turns_input = gr.Slider(minimum=2, maximum=20, value=6, step=1, label="Number of turns")
            generate_button = gr.Button("Generate episode")
            status_output = gr.Markdown()
            audio_output = gr.Audio(label="Episode audio")
            transcript_output = gr.Textbox(label="Transcript", lines=15, interactive=False)

            episode_id_state = gr.State(value=None)
            poll_timer = gr.Timer(2, active=False)

        generate_button.click(
                fn=start_generation,
                inputs=[title_input, topic_input, num_turns_input],
                outputs=[episode_id_state, status_output, audio_output, transcript_output, poll_timer],
                show_progress="hidden",
            )

        poll_timer.tick(
            fn=poll_episode,
            inputs=[episode_id_state],
            outputs=[status_output, audio_output, transcript_output, poll_timer],
            show_progress="hidden",
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