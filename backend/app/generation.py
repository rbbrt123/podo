import os
import random

from anthropic import Anthropic
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from pydub import AudioSegment
from dotenv import load_dotenv

from app import storage

load_dotenv()

anthropic_client = Anthropic()
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))


def list_voices():
    response = elevenlabs_client.voices.get_all()
    return [
        {"voice_id": voice.voice_id, "name": voice.name, "preview_url": voice.preview_url} 
        for voice in response.voices
        ]


def format_transcript(transcript):
    if not transcript:
        return "(the conversation hasn't started yet)"
    blocks = [
        f"{turn['speaker']}\nLINE: {turn['text']}\nNEXT: {turn['next_speaker']}"
        for turn in transcript
    ]
    return "\n\n".join(blocks)


def parse_response(raw_text):
    line = ""
    next_speaker = None
    for text_line in raw_text.split("\n"):
        text_line = text_line.strip()
        if text_line.startswith("LINE:"):
            line = text_line[len("LINE:"):].strip()
        elif text_line.startswith("NEXT:"):
            next_speaker = text_line[len("NEXT:"):].strip()
    return line, next_speaker


def generate_turn(speaker, topic, transcript, agents):
    other_speakers = [name for name in agents if name != speaker]
    system_prompt = (
        agents[speaker]["prompt"]
        + f"\n\nYou are having a real, casual spoken conversation about: {topic}\n"
        + f"The other speaker(s) is/(are): {', '.join(other_speakers)}\n"
        + "This is a real conversation, not a lecture. Vary your turn length naturally — "
        + "sometimes a short reaction ('Wait, really?', 'Right, exactly.'), sometimes a longer "
        + "explanation. It's fine to just react without adding new information. Disagree when "
        + "you'd genuinely disagree. Sound like a person, not a textbook.\n\n"
        + "You can direct your own vocal delivery using ElevenLabs audio tags in square brackets, "
        + "placed right before the words they affect — e.g. [laughs], [sighs], [curious], "
        + "[excited], [interrupting]. Use them only where they'd genuinely happen, not on every line.\n\n"
        + "Respond in EXACTLY this format, and nothing else:\n"
        + "LINE: <your conversational turn, audio tags inline where relevant, no name label>\n"
        + f"NEXT: <who should speak next — one of: {', '.join(other_speakers)}>"
    )

    conversation_so_far = format_transcript(transcript)

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Conversation so far:\n{conversation_so_far}\n\nGive your next line."}
        ],
    )

    if response.stop_reason == "max_tokens":
        return "", None

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return parse_response(raw_text)


def generate_intro(speaker, agents):
    system_prompt = (
        agents[speaker]["prompt"]
        + "\n\nYou are about to co-host a podcast episode with other speakers. Before the real "
        + "discussion starts, give a short, one-sentence self-introduction — just your name and a "
        + "brief sense of your role or angle. Don't mention the episode's topic yet, and don't ask "
        + "a question — the real discussion starts right after everyone has introduced themselves.\n\n"
        + "Respond with EXACTLY one sentence, and nothing else — no labels, no extra commentary."
    )

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=100,
        system=system_prompt,
        messages=[{"role": "user", "content": "Give your one-sentence self-introduction."}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def generate_outro(speaker, topic, transcript, agents):
    participant_names = ", ".join(agents)
    system_prompt = (
        agents[speaker]["prompt"]
        + f"\n\nYou are having a real, casual spoken conversation about: {topic}\n"
        + "The conversation is about to end, and as the host, it's on you to close the show. "
        + "This is the FINAL line of the episode. Note that time is running out, wrap up the "
        + f"discussion naturally, and sign off — briefly reference what you talked about, and "
        + f"thank your co-host(s) by name ({participant_names}). Don't ask a new question, "
        + "don't open a new thread.\n\n"
        + "You can direct your own vocal delivery using ElevenLabs audio tags in square brackets, "
        + "placed right before the words they affect — e.g. [laughs], [sighs], [warmly]. Use "
        + "them only where they'd genuinely happen.\n\n"
        + "Respond in EXACTLY this format, and nothing else:\n"
        + "LINE: <your closing line, audio tags inline where relevant, no name label>"
    )

    conversation_so_far = format_transcript(transcript)

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Conversation so far:\n{conversation_so_far}\n\nGive your closing line."}
        ],
    )

    if response.stop_reason == "max_tokens":
        return ""

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    for text_line in raw_text.split("\n"):
        text_line = text_line.strip()
        if text_line.startswith("LINE:"):
            return text_line[len("LINE:"):].strip()
    return ""


def text_to_speech(text, voice_id, filename):
    audio_chunks = elevenlabs_client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_v3",
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(stability=0.3, similarity_boost=0.75),
    )
    with open(filename, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)


def generate_episode(episode_id: int, topic: str, target_minutes: int, agent_ids: list[int], intros: bool) -> None:
    storage.update_episode_status(episode_id, "generating")
    try:
        _run_generation(episode_id, topic, target_minutes, agent_ids, intros)
    except Exception as exc:
        storage.update_episode_status(episode_id, "failed", error_message=str(exc))


def _run_generation(episode_id: int, topic: str, target_minutes: int, agent_ids: list[int], intros: bool) -> None:
    agents = {}
    for agent_id in agent_ids:
        agent = storage.get_agent(agent_id)
        if agent is not None:
            agents[agent["name"]] = agent

    final_path = storage.episode_audio_path(episode_id)
    episode_dir = final_path.parent

    transcript = []
    turn_audio_files = []
    speakers = list(agents)
    current_speaker = speakers[0]

    turn_index = 0

    if intros:
        for i, speaker in enumerate(speakers):
            next_intro_speaker = speakers[i + 1] if i + 1 < len(speakers) else speakers[0]
            line = generate_intro(speaker, agents)

            transcript.append({"speaker": speaker, "text": line, "next_speaker": next_intro_speaker})
            storage.save_turn(episode_id, turn_index, speaker, line)

            turn_file = episode_dir / f"turn_{turn_index}.mp3"
            text_to_speech(line, agents[speaker]["voice_id"], str(turn_file))
            turn_audio_files.append(turn_file)
            turn_index += 1

    target_seconds = target_minutes * 60
    elapsed_seconds = 0.0
    attempts = 0
    max_attempts = (target_seconds // 3) * 3

    while elapsed_seconds < target_seconds and attempts < max_attempts:
        attempts += 1
        line, next_speaker = generate_turn(current_speaker, topic, transcript, agents)
        next_speaker_valid = next_speaker in agents and next_speaker != current_speaker

        if line.strip() and next_speaker_valid:
            transcript.append({"speaker": current_speaker, "text": line, "next_speaker": next_speaker})
            storage.save_turn(episode_id, turn_index, current_speaker, line)

            turn_file = episode_dir / f"turn_{turn_index}.mp3"
            text_to_speech(line, agents[current_speaker]["voice_id"], str(turn_file))
            turn_audio_files.append(turn_file)
            elapsed_seconds += AudioSegment.from_mp3(str(turn_file)).duration_seconds

            turn_index += 1
            current_speaker = next_speaker
            storage.update_episode_elapsed(episode_id, elapsed_seconds)

        else:
            current_speaker = random.choice([name for name in speakers if name != current_speaker])

    outro_line = generate_outro(speakers[0], topic, transcript, agents)
    if outro_line.strip():
        storage.save_turn(episode_id, turn_index, speakers[0], outro_line)
        turn_file = episode_dir / f"turn_{turn_index}.mp3"
        text_to_speech(outro_line, agents[speakers[0]]["voice_id"], str(turn_file))
        turn_audio_files.append(turn_file)
        elapsed_seconds += AudioSegment.from_mp3(str(turn_file)).duration_seconds
        storage.update_episode_elapsed(episode_id, elapsed_seconds)

    pause = AudioSegment.silent(duration=500)
    episode_audio = AudioSegment.empty()
    for turn_file in turn_audio_files:
        episode_audio = episode_audio + AudioSegment.from_mp3(str(turn_file)) + pause

    episode_audio.export(str(final_path), format="mp3")

    for turn_file in turn_audio_files:
        turn_file.unlink()

    relative_audio_path = final_path.relative_to(storage.DATA_DIR)
    storage.update_episode_status(episode_id, "complete", audio_path=str(relative_audio_path))