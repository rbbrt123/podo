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


def start_generation(title, topic, num_turns, agent_ids):
    """Kicks off generation and starts the polling timer."""
    if not topic.strip():
        return None, "Please enter a topic.", gr.skip(), gr.skip(), gr.Timer(active=False)
    if not agent_ids or len(agent_ids) < 2:
        return None, "Pick at least two agents.", gr.skip(), gr.skip(), gr.Timer(active=False)

    total_turns = int(num_turns)
    response = httpx.post(
        f"{BACKEND_URL}/episodes",
        json={"title": title, "topic": topic, "num_turns": total_turns, "agent_ids": agent_ids},
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
    episodes.sort(key=lambda ep: ep["title"].lower())
    choices = [(f"{ep['title']} ({ep['status']})", ep["id"]) for ep in episodes]
    return gr.Dropdown(choices=choices)


def load_episode(episode_id):
    """This runs when the user picks something from that dropdown, to actually load and display an existing episode"""
    if episode_id is None:
        return None, "", gr.Button(interactive=False)
    episode = httpx.get(f"{BACKEND_URL}/episodes/{episode_id}").json()
    can_delete = episode["status"] not in ("pending", "generating")
    if episode["status"] != "complete":
        return None, f"Episode is {episode['status']}, no audio yet.", gr.Button(interactive=can_delete)
    transcript = "\n\n".join(f"{t['speaker']}: {t['text']}" for t in episode["turns"])
    return _download_audio(episode_id), transcript, gr.Button(interactive=can_delete)


def delete_episode(episode_id):
    if episode_id is None:
        return gr.skip(), "No episode selected."
    httpx.delete(f"{BACKEND_URL}/episodes/{episode_id}").raise_for_status()
    return list_episode_choices(), "Episode deleted."


def _form_state(agent_id, name, prompt, voice_id, is_builtin):
    return (
        gr.Textbox(value=name, interactive=not is_builtin),
        gr.Textbox(value=prompt, interactive=not is_builtin),
        gr.Dropdown(value=voice_id, interactive=not is_builtin),
        agent_id,
        gr.Button(visible=not is_builtin),                        
        gr.Button(visible=agent_id is not None and not is_builtin), 
        gr.Button(visible=is_builtin),
    )


def _fetch_agent_choices():
    agents = httpx.get(f"{BACKEND_URL}/agents").json()
    return [(a["name"] + (" (built-in)" if a["is_builtin"] else ""), a["id"]) for a in agents]


def list_agent_choices():
    return gr.Dropdown(choices=_fetch_agent_choices())


def list_agent_checkboxes():
    return gr.CheckboxGroup(choices=_fetch_agent_choices())


def list_voice_choices():
    voices = httpx.get(f"{BACKEND_URL}/voices").json()
    choices = [(v["name"], v["voice_id"]) for v in voices]
    previews = {v["voice_id"]: v["preview_url"] for v in voices}
    return gr.Dropdown(choices=choices), previews


def preview_voice(voice_id, previews):
    return previews.get(voice_id)


def load_agent(agent_id):
    """Runs when an agent is picked from the dropdown, to populate the form."""
    if agent_id is None:
        return _form_state(None, "", "", None, is_builtin=False)
    agent = httpx.get(f"{BACKEND_URL}/agents/{agent_id}").json()
    return _form_state(agent["id"], agent["name"], agent["prompt"], agent["voice_id"], agent["is_builtin"])


def new_agent_form():
    return _form_state(None, "", "", None, is_builtin=False)


def save_agent(agent_id, name, prompt, voice_id):
    if not name.strip() or not prompt.strip() or not voice_id:
        return gr.skip(), "Name, prompt, and voice ID are all required."

    payload = {"name": name, "prompt": prompt, "voice_id": voice_id}
    if agent_id is None:
        httpx.post(f"{BACKEND_URL}/agents", json=payload).raise_for_status()
        message = f"Created agent '{name}'."
    else:
        httpx.put(f"{BACKEND_URL}/agents/{agent_id}", json=payload).raise_for_status()
        message = f"Saved agent '{name}'."

    return list_agent_choices(), message


def duplicate_agent(name, prompt, voice_id):
    return _form_state(None, f"{name} (copy)", prompt, voice_id, is_builtin=False)


def delete_agent(agent_id):
    if agent_id is None:
        return gr.skip(), "No agent selected."
    httpx.delete(f"{BACKEND_URL}/agents/{agent_id}").raise_for_status()
    return list_agent_choices(), "Agent deleted."


def build_app():
    """assembling the actual UI"""
    with gr.Blocks(title="podo") as demo:
        gr.Markdown("# podo")

        with gr.Tab("Generate"):
            title_input = gr.Textbox(label="Episode title (optional - defaults to the topic)")
            topic_input = gr.Textbox(label="Topic")
            with gr.Row():
                agent_checkboxes = gr.CheckboxGroup(label="Agents (pick at least two)", choices=[])
                refresh_generate_agents_button = gr.Button("Refresh agents")
            num_turns_input = gr.Slider(minimum=2, maximum=20, value=6, step=1, label="Number of turns")
            generate_button = gr.Button("Generate episode")
            status_output = gr.Markdown()
            audio_output = gr.Audio(label="Episode audio")
            transcript_output = gr.Textbox(label="Transcript", lines=15, interactive=False)

            episode_id_state = gr.State(value=None)
            poll_timer = gr.Timer(2, active=False)

        generate_button.click(
                fn=start_generation,
                inputs=[title_input, topic_input, num_turns_input, agent_checkboxes],
                outputs=[episode_id_state, status_output, audio_output, transcript_output, poll_timer],
                show_progress="hidden",
            )

        poll_timer.tick(
            fn=poll_episode,
            inputs=[episode_id_state],
            outputs=[status_output, audio_output, transcript_output, poll_timer],
            show_progress="hidden",
        )

        refresh_generate_agents_button.click(fn=list_agent_checkboxes, outputs=agent_checkboxes)
        demo.load(fn=list_agent_checkboxes, outputs=agent_checkboxes)

        with gr.Tab("Library"):
            refresh_button = gr.Button("Refresh")
            episode_dropdown = gr.Dropdown(label="Saved episodes", choices=[])
            library_audio_output = gr.Audio(label="Episode audio")
            library_transcript_output = gr.Textbox(label="Transcript", lines=15, interactive=False)
            delete_episode_button = gr.Button("Delete", variant="stop")
            library_status_output = gr.Markdown()

            refresh_button.click(fn=list_episode_choices, outputs=episode_dropdown)
            episode_dropdown.change(
                fn=load_episode,
                inputs=episode_dropdown,
                outputs=[library_audio_output, library_transcript_output, delete_episode_button],
            )
            delete_episode_button.click(
                fn=delete_episode,
                inputs=episode_dropdown,
                outputs=[episode_dropdown, library_status_output],
            )
            demo.load(fn=list_episode_choices, outputs=episode_dropdown)

        with gr.Tab("Agent Lab"):
            agent_dropdown = gr.Dropdown(label="Agents", choices=[])
            refresh_agents_button = gr.Button("Refresh")

            name_input = gr.Textbox(label="Name")
            prompt_input = gr.Textbox(label="Prompt", lines=6)
            voice_id_input = gr.Dropdown(label="Voice", choices=[])
            voice_preview_output = gr.Audio(label="Voice preview", autoplay=True)
            voice_previews_state = gr.State(value={})

            with gr.Row():
                new_agent_button = gr.Button("New agent")
                save_agent_button = gr.Button("Save")
                delete_agent_button = gr.Button("Delete", variant="stop")
                duplicate_agent_button = gr.Button("Duplicate into editable copy")

            agent_status_output = gr.Markdown()
            agent_id_state = gr.State(value=None)

            agent_dropdown.change(
                fn=load_agent,
                inputs=agent_dropdown,
                outputs=[name_input, prompt_input, voice_id_input, agent_id_state,
                         save_agent_button, delete_agent_button, duplicate_agent_button],
            )

            new_agent_button.click(
                fn=new_agent_form,
                outputs=[name_input, prompt_input, voice_id_input, agent_id_state,
                         save_agent_button, delete_agent_button, duplicate_agent_button],
            )

            duplicate_agent_button.click(
                fn=duplicate_agent,
                inputs=[name_input, prompt_input, voice_id_input],
                outputs=[name_input, prompt_input, voice_id_input, agent_id_state,
                         save_agent_button, delete_agent_button, duplicate_agent_button],
            )

            save_agent_button.click(
                fn=save_agent,
                inputs=[agent_id_state, name_input, prompt_input, voice_id_input],
                outputs=[agent_dropdown, agent_status_output],
            )

            delete_agent_button.click(
                fn=delete_agent,
                inputs=agent_id_state,
                outputs=[agent_dropdown, agent_status_output],
            )

            refresh_agents_button.click(fn=list_agent_choices, outputs=agent_dropdown)
            demo.load(fn=list_agent_choices, outputs=agent_dropdown)
            demo.load(fn=list_voice_choices, outputs=[voice_id_input, voice_previews_state])

            voice_id_input.change(
                fn=preview_voice,
                inputs=[voice_id_input, voice_previews_state],
                outputs=voice_preview_output,
            )

    return demo


if __name__ == "__main__":
    build_app().launch()