import io
import json
import logging
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic
from elevenlabs import DialogueInput
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment
from dotenv import load_dotenv

from app import storage

load_dotenv()

logger = logging.getLogger(__name__)

anthropic_client = Anthropic()
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

HOST_GUEST_CAP  = 2  # ADR-0001: host must reclaim control within this many consecutive guest turns
DEFAULT_CHUNK_SIZE = 6
MIN_FINAL_CHUNK_SIZE = 2
DEFAULT_SECONDS_PER_TURN_ESTIMATE = 12.0  # rough guess before we have any real data for this episode
MIN_PLAUSIBLE_SECONDS_PER_TURN = 2.0      # backstop only: guards against a runaway loop if a chunk's audio comes back implausibly short


def list_voices():
    response = elevenlabs_client.voices.get_all()
    return [
        {"voice_id": voice.voice_id, "name": voice.name, "preview_url": voice.preview_url} 
        for voice in response.voices
        ]


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


def _validate_chunk_content(turns: list[dict], host_name: str, is_final_chunk: bool) -> str | None:
    """Returns a description of the violation if the chunk contains an
    obviously broken placeholder turn, or if the final chunk doesn't end on
    the host's sign-off, or None if valid."""
    for turn in turns:
        if turn["text"].strip().lower() == "placeholder":
            return (
                f"a turn from {turn['speaker']} contained the literal text "
                "\"placeholder\" instead of real dialogue."
            )
    if is_final_chunk and turns and turns[-1]["speaker"] != host_name:
        return (
            f"this is the final chunk but the last turn was from {turns[-1]['speaker']}, "
            f"not {host_name} -- the host must deliver the sign-off as the very last turn."
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

        content_violation = _validate_chunk_content(turns, host_name, is_final_chunk)
        if content_violation:
            failure_reason = content_violation
            logger.warning("episode %s chunk attempt %s rejected: %s", episode_id, attempt, content_violation)
            continue

        return turns

    raise RuntimeError(
        f"episode {episode_id}: exhausted {max_attempts} attempts generating a valid chunk "
        f"(last failure: {failure_reason})"
    )


def _split_turns_into_batches(turns: list[dict], max_chars: int = 2000) -> list[list[dict]]:
    """Groups turns into batches that each fit ElevenLabs' Text to Dialogue
    per-request character budget (~2000 chars combined across all turns).
    Splitting is a rare fallback -- most chunks fit in a single batch."""
    batches = []
    current_batch = []
    current_chars = 0
    for turn in turns:
        turn_chars = len(turn["text"])
        if current_batch and current_chars + turn_chars > max_chars:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(turn)
        current_chars += turn_chars
    if current_batch:
        batches.append(current_batch)
    return batches


def synthesize_chunk(turns: list[dict], agents: dict, filename: str) -> None:
    """Synthesizes a whole chunk's turns into one combined audio file via
    ElevenLabs' Text to Dialogue endpoint -- one call per chunk (or, rarely,
    per sub-batch if the chunk exceeds the endpoint's character budget)
    instead of one call per line."""
    batches = _split_turns_into_batches(turns)

    combined_audio = AudioSegment.empty()
    for batch in batches:
        dialogue_inputs = [
            DialogueInput(text=turn["text"], voice_id=agents[turn["speaker"]]["voice_id"])
            for turn in batch
        ]
        audio_chunks = elevenlabs_client.text_to_dialogue.convert(
            inputs=dialogue_inputs,
            model_id="eleven_v3",
            output_format="mp3_44100_128",
        )
        batch_bytes = b"".join(audio_chunks)
        combined_audio += AudioSegment.from_mp3(io.BytesIO(batch_bytes))

    combined_audio.export(filename, format="mp3") 


def _plan_next_chunk(
        elapsed_seconds: float,
        target_seconds: float,
        turns_so_far: int,
        in_flight_turns: int = 0,
) -> tuple[int, bool]:
    """Decides how many turns to request next and whether this should be the
    final chunk, based on actual pacing observed so far in this episode.

    `in_flight_turns` lets a chunk whose audio is still synthesizing (its
    real duration isn't known yet) count toward the pacing estimate anyway,
    projected using the average pace observed so far -- needed once
    generation and synthesis run concurrently and chunk N+1 has to be
    planned before chunk N's audio duration is known.

    Returns (chunk_size, is_final_chunk).
    """
    if turns_so_far == 0:
        avg_seconds_per_turn = DEFAULT_SECONDS_PER_TURN_ESTIMATE
    else:
        avg_seconds_per_turn = elapsed_seconds / turns_so_far

    projected_elapsed = elapsed_seconds + avg_seconds_per_turn * in_flight_turns
    remaining_seconds = target_seconds - projected_elapsed
    turns_remaining_estimate = remaining_seconds / avg_seconds_per_turn

    if turns_remaining_estimate <= DEFAULT_CHUNK_SIZE:
        chunk_size = max(MIN_FINAL_CHUNK_SIZE, round(turns_remaining_estimate))
        return chunk_size, True

    return DEFAULT_CHUNK_SIZE, False


def generate_episode(episode_id: int, topic: str, target_minutes: int, agent_ids: list[int], intros: bool, host_agent_id: int) -> None:
    storage.update_episode_status(episode_id, "generating")
    try:
        _run_generation(episode_id, topic, target_minutes, agent_ids, intros, host_agent_id)
    except Exception as exc:
        storage.update_episode_status(episode_id, "failed", error_message=str(exc))


def _run_generation(episode_id: int, topic: str, target_minutes: int, agent_ids: list[int], intros: bool, host_agent_id: int) -> None:
    agents = {}
    for agent_id in agent_ids:
        agent = storage.get_agent(agent_id)
        if agent is not None:
            agents[agent["name"]] = agent
    host_name = next(name for name, agent in agents.items() if agent["id"] == host_agent_id)

    final_path = storage.episode_audio_path(episode_id)
    episode_dir = final_path.parent

    transcript = []
    chunk_audio_files = []
    turn_index = 0
    chunk_index = 0

    target_seconds = target_minutes * 60
    elapsed_seconds = 0.0
    max_chunks = math.ceil(target_seconds / (MIN_PLAUSIBLE_SECONDS_PER_TURN * MIN_FINAL_CHUNK_SIZE))

    chunk_size, is_final_chunk = _plan_next_chunk(elapsed_seconds, target_seconds, len(transcript))
    turns = generate_validated_chunk(
        episode_id, topic, agents, transcript, host_name,
        chunk_size=chunk_size,
        include_intros=intros,
        is_final_chunk=is_final_chunk,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        while True:
            chunk_file = episode_dir / f"chunk_{chunk_index}.mp3"
            synth_future = executor.submit(synthesize_chunk, turns, agents, str(chunk_file))

            # While this chunk's audio synthesizes in the background, generate
            # the *next* chunk's text on the main thread -- it only needs the
            # transcript so far, not this chunk's finished audio, so the two
            # calls don't actually depend on each other.
            will_continue = not is_final_chunk and chunk_index + 1 < max_chunks
            if will_continue:
                next_chunk_size, next_is_final = _plan_next_chunk(
                    elapsed_seconds, target_seconds, len(transcript), in_flight_turns=len(turns)
                )
                next_turns = generate_validated_chunk(
                    episode_id, topic, agents, transcript + turns, host_name,
                    chunk_size=next_chunk_size,
                    include_intros=False,
                    is_final_chunk=next_is_final,
                )
            synth_future.result()
            chunk_duration = AudioSegment.from_mp3(str(chunk_file)).duration_seconds

            for turn in turns:
                storage.save_turn(episode_id, turn_index, turn["speaker"], turn["text"])
                transcript.append(turn)
                turn_index += 1

            chunk_audio_files.append(chunk_file)
            elapsed_seconds += chunk_duration
            storage.update_episode_elapsed(episode_id, elapsed_seconds)
            chunk_index += 1

            if not will_continue:
                break

            turns = next_turns
            is_final_chunk = next_is_final

    # did we stop because the chunk budget ran out, while still short of the goal?
    chunks_exhausted = chunk_index >= max_chunks and elapsed_seconds < target_seconds

    # only a short pause between chunks -- ElevenLabs' Text to Dialogue already
    # paces the turns *within* a chunk naturally; we only need to smooth the seam
    # between separate synthesis calls.
    pause = AudioSegment.silent(duration=300)
    episode_audio = AudioSegment.empty()
    for i, chunk_file in enumerate(chunk_audio_files):
        if i > 0:
            episode_audio += pause
        episode_audio += AudioSegment.from_mp3(str(chunk_file))

    episode_audio.export(str(final_path), format="mp3")

    for chunk_file in chunk_audio_files:
        chunk_file.unlink()

    relative_audio_path = final_path.relative_to(storage.DATA_DIR)

    shortfall_message = None
    if chunks_exhausted:
        shortfall_message = (
            f"Reached {elapsed_seconds / 60:.1f} of {target_minutes} target minutes "
            f"after exhausting {chunk_index} chunk-generation attempts."
        )
        logger.warning("episode %s: %s", episode_id, shortfall_message)

    storage.update_episode_status(
        episode_id, "complete", error_message=shortfall_message, audio_path=str(relative_audio_path)
    )