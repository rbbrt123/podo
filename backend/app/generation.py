import json
import logging
import os
import re

from anthropic import Anthropic
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from pydub import AudioSegment
from dotenv import load_dotenv

from app import storage

load_dotenv()

logger = logging.getLogger(__name__)

anthropic_client = Anthropic()
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

HOST_GUEST_CAP  = 2  # ADR-0001: host must reclaim control within this many consecutive guest turns


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


def _normalize_name(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve_next_speaker(raw_next_speaker, current_speaker, speakers):
    if not raw_next_speaker:
        return None

    candidates = [name for name in speakers if name != current_speaker]
    normalized_raw = _normalize_name(raw_next_speaker)
    if not normalized_raw:
        return None

    exact_matches = [name for name in candidates if _normalize_name(name) == normalized_raw]
    if len(exact_matches) == 1:
        return exact_matches[0]

    fuzzy_matches = [
        name for name in candidates
        if _normalize_name(name) in normalized_raw or normalized_raw in _normalize_name(name)
    ]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]

    return None


def _next_in_rotation(current_speaker, speakers):
    current_index = speakers.index(current_speaker)
    return speakers[(current_index + 1) % len(speakers)]


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

    raw_text = "".join(block.text for block in response.content if block.type == "text")

    if response.stop_reason == "max_tokens":
        return "", None, raw_text

    line, next_speaker = parse_response(raw_text)
    return line, next_speaker, raw_text


def _build_chunk_system_prompt(
        topic: str,
        agents: dict,
        host_name: str,
        guest_cap: int,
        include_intros: bool = False,
        is_final_chunk: bool = False,
) -> str:
    persona_blocks = "\n\n".join(
        f"### {name}\n{agent['prompt']}" for name, agent in agents.items()
    )
    other_names = [name for name in agents if name != host_name]
    prompt = (
        "You are writing a segment of a multi-person podcast conversation. "
        "There are multiple speakers, each with their own persona, described "
        "below.\n\n"
        + persona_blocks
        + f"\n\nThe topic is: {topic}\n\n"
        + f"{host_name} is the HOST of this episode: driving the conversation, keeping it "
        + "on topic, and making sure every guest gets a turn. "
        + f"{', '.join(other_names)} {'is' if len(other_names) == 1 else 'are'} guest(s) — "
        + "guests can riff and respond to each other directly, but "
        + f"{host_name} must speak again at least once within every {guest_cap} consecutive "
        + "turns from other speakers, to steer the conversation and ask follow-up questions.\n\n"
        + "This is a real conversation, not a lecture. Vary turn length naturally - "
        + "sometimes a short reaction ('wait, really?', 'Right, exactly.'), sometimes a "
        + "longer explanation. It's fine to just react without adding new information. "
        + "Let speakers genuinely disagree with each other, interrupt, and react to "
        + "what was just said. Sound like real people, not a scripted panel.\n\n"
        + "Each speaker can direct their own vocal delivery using ElevenLabs audio tags "
        + "in square brackets, placed right before the words they affect — e.g. "
        + "[laughs], [sighs], [curious], [excited], [interrupting]. Use them only where "
        + "they'd genuinely happen, not on every line."
    )
    if include_intros:
        prompt += (
            f"\n\nThis is the very start of the episode. Before the real discussion begins, "
            f"have {host_name} briefly welcome listeners and introduce the topic, then have "
            f"each guest give a short, one-sentence self-introduction — just their name and "
            f"a brief sense of their angle — before the real discussion starts."
        )
    if is_final_chunk:
        prompt += (
            f"\n\nThis is the FINAL segment of the episode. Time is running out — wrap the "
            f"discussion up naturally within these turns, and end with {host_name} signing "
            f"off: briefly reference what was discussed and thank the guest(s) by name "
            f"({', '.join(other_names)}). The very last turn must be {host_name}'s sign-off "
            "— don't open a new thread or ask a new question after it."
        )
    return prompt


def _format_transcript_for_chunk(transcript: list[dict]) -> str:
    if not transcript:
        return "(the conversation hasn't started yet)"
    return "\n".join(f"{turn['speaker']}: {turn['text']}" for turn in transcript)


def generate_chunk(
        topic: str,
        agents: dict,
        transcript: list[dict],
        host_name: str,
        guest_cap: int = HOST_GUEST_CAP,
        chunk_size: int = 6,
        include_intros: bool = False,
        is_final_chunk: bool = False,
        extra_instruction: str | None = None,
) -> list[dict]:
    """Generate the next `chunk_size` turns of dialogue in a single call.

    `agents` is {name: {"prompt": ..., "voice_id": ...}} for every speaker in
    the episode. `transcript` is the accumulated turns so far, as
    {"speaker": ..., "text": ...} dicts. Returns the newly generated turns in
    the same shape.
    """
    system_prompt = _build_chunk_system_prompt(
        topic, agents, host_name, guest_cap, include_intros, is_final_chunk=is_final_chunk
    )
    conversation_so_far = _format_transcript_for_chunk(transcript)

    user_content = (
        f"Conversation so far:\n{conversation_so_far}\n\n"
        f"Write the next {chunk_size} turns now."
    )
    if extra_instruction:
        user_content += f"\n\n{extra_instruction}"

    speaker_names = list(agents)
    output_schema = {
        "type": "object",
        "properties": {
            "turns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string", "enum": speaker_names},
                        "text": {"type": "string"},
                    },
                    "required": ["speaker", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["turns"],
        "additionalProperties": False,
    }

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": output_schema}},
        messages=[{"role": "user", "content": user_content}],
    )

    if response.stop_reason == "max_tokens":
        raise ValueError("chunk generation truncated before completing — max_tokens too low for chunk_size")

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    parsed = json.loads(raw_text)
    return parsed["turns"]


def _validate_host_cap(turns: list[dict], host_name: str, guest_cap: int) -> str | None:
    """Returns a description of the violation if the host didn't reappear
    within `guest_cap` consecutive turns from other speakers, or None if valid."""
    consecutive_non_host = 0
    for turn in turns:
        if turn["speaker"] == host_name:
            consecutive_non_host = 0
        else:
            consecutive_non_host += 1
            if consecutive_non_host > guest_cap:
                return (
                    f"{host_name} (the host) did not reappear within {guest_cap} "
                    f"consecutive turns from other speakers."
                )
    return None


def generate_validated_chunk(
    episode_id: int,
    topic: str,
    agents: dict,
    transcript: list[dict],
    host_name: str,
    guest_cap: int = HOST_GUEST_CAP,
    chunk_size: int = 6,
    include_intros: bool = False,
    is_final_chunk: bool = False,
    max_attempts: int = 3,
) -> list[dict]:
    """Generate a chunk, regenerating the whole thing (with the failure reason
    fed back into the prompt) if it comes back malformed, empty, or violates
    the host cap. Raises if `max_attempts` is exhausted — never returns a
    silently-broken chunk."""
    failure_reason = None
    for attempt in range(1, max_attempts + 1):
        extra_instruction = None
        if failure_reason:
            extra_instruction = (
                f"Your previous attempt was rejected: {failure_reason} "
                "Write a corrected version of the next turns that fixes this."
            )
        try:
            turns = generate_chunk(
                topic, agents, transcript, host_name, guest_cap,
                chunk_size=chunk_size, include_intros=include_intros,
                is_final_chunk=is_final_chunk, extra_instruction=extra_instruction,
            )
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            failure_reason = f"response could not be parsed ({exc})"
            logger.warning("episode %s chunk attempt %s: %s", episode_id, attempt, failure_reason)
            continue

        if not turns or any(not turn.get("text", "").strip() for turn in turns):
            failure_reason = "response contained an empty turn"
            logger.warning("episode %s chunk attempt %s: %s", episode_id, attempt, failure_reason)
            continue

        violation = _validate_host_cap(turns, host_name, guest_cap)
        if violation:
            failure_reason = violation
            logger.warning("episode %s chunk attempt %s rejected: %s", episode_id, attempt, violation)
            continue

        return turns

    raise RuntimeError(
        f"episode {episode_id}: exhausted {max_attempts} attempts generating a valid chunk "
        f"(last failure: {failure_reason})"
    )


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


def generate_episode(episode_id: int, topic: str, target_minutes: int, agent_ids: list[int], intros: bool, host_agent_id: int) -> None:
    storage.update_episode_status(episode_id, "generating")
    try:
        _run_generation(episode_id, topic, target_minutes, agent_ids, intros, host_agent_id)
    except Exception as exc:
        storage.update_episode_status(episode_id, "failed", error_message=str(exc))


def _run_generation(episode_id: int, topic: str, target_minutes: int, agent_ids: list[int], intros: bool, host_agent_id: int) -> None:
    # host_agent_id is accepted here so the API is host-aware end-to-end, but
    # this loop still runs the pre-chunking generate_turn() pipeline
    # unchanged. Wired into generate_validated_chunk() once this loop itself
    # is replaced (feature/chunk-duration-control).
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
        line, raw_next_speaker, raw_text = generate_turn(current_speaker, topic, transcript, agents)
        line = line.strip()

        if not line:
            logger.warning(
                "episode %s turn %s attempt %s: unusable line from %s; raw output: %r",
                episode_id, turn_index, attempts, current_speaker, raw_text,
            )
            current_speaker = _next_in_rotation(current_speaker, speakers)
            continue

        next_speaker = resolve_next_speaker(raw_next_speaker, current_speaker, speakers)
        if next_speaker is None:
            next_speaker = _next_in_rotation(current_speaker, speakers)
            logger.warning(
                "episode %s turn %s: could not resolve NEXT speaker (raw=%r) after %s; falling back to %s",
                episode_id, turn_index, raw_next_speaker, current_speaker, next_speaker,
            )

        transcript.append({"speaker": current_speaker, "text": line, "next_speaker": next_speaker})
        storage.save_turn(episode_id, turn_index, current_speaker, line)
        
        turn_file = episode_dir / f"turn_{turn_index}.mp3"
        text_to_speech(line, agents[current_speaker]["voice_id"], str(turn_file))
        turn_audio_files.append(turn_file)
        elapsed_seconds += AudioSegment.from_mp3(str(turn_file)).duration_seconds

        turn_index += 1
        current_speaker = next_speaker
        storage.update_episode_elapsed(episode_id, elapsed_seconds)

    #did we stop because attempts ran out, while still short of the goal?
    attempts_exhausted = attempts >= max_attempts and elapsed_seconds < target_seconds

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

    shortfall_message = None
    if attempts_exhausted:
        shortfall_message = (
            f"Reached {elapsed_seconds / 60:.1f} of {target_minutes} target minutes "
            f"after exhausting {attempts} turn-generation attempts."
        )
        logger.warning("episode %s: %s", episode_id, shortfall_message)

    storage.update_episode_status(
        episode_id, "complete", error_message=shortfall_message, audio_path=str(relative_audio_path)
    )