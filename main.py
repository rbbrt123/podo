from anthropic import Anthropic
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from pydub import AudioSegment
from dotenv import load_dotenv
import os
import random

load_dotenv()


anthropic_client = Anthropic()
elevenlabs_client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

TOPIC = "Is it a good idea to let juniors line out powerpoints for the first year at a big-4 company which is often refered to as 'brain-dead' work?"
NUM_TURNS = 6

PERSONAS = {
    "Mira" : "You are Mira, the curious host of a podcast. You ask clarifying questions and keep the conversation moving.",
    "Dr. Chen": "You are Dr. Chen, a partner at a big-4 company that is really fond of letting juniors line out powerpoints (brain death work) and letting them work till late in the night for a minimum wage",
    "Jordan": "You are Jordan, a skeptical fact-checker who challenges claims and asks for evidence.",
}

VOICE_IDS = {
    "Mira": "aMSt68OGf4xUZAnLpTU8",
    "Dr. Chen": "vBKc2FfBKJfcZNyEt1n6",
    "Jordan": "uKGPYP2uuyRQv8SeFre0",
}

transcript = []
audio_filenames = []

def format_transcript():
    if not transcript:
        return "(the conversation hasn't started yet)"
    lines = [f"{turn['speaker']}: {turn['text']}" for turn in transcript]
    return "\n".join(lines)


def parse_response(raw_text):
    line = ""
    next_speaker = None
    for text_line in raw_text.split("\n"):
        text_line = text_line.strip()
        if text_line.startswith("LINE:"):
            line = text_line[len("LINE:"):].strip()
        elif text_line.startswith("NEXT:"):
            next_speaker = text_line[len("NEXT:"):].strip()
    if not line:
        print(f"Warning: couldn't find a LINE: in the model's response:\n{raw_text!r}\n")
    return line, next_speaker


def generate_turn(speaker):
    other_speakers = [name for name in PERSONAS if name != speaker]
    system_prompt = (
        PERSONAS[speaker] #system prompt of speaker
        + f"\n\nYou are having a real, casual spoken conversation about: {TOPIC}\n"
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

    conversation_so_far = format_transcript() #all the outputs so far formatted in a nice way

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Conversation so far:\n{conversation_so_far}\n\nGive your next line."}
        ]
    )

    if response.stop_reason == "max_tokens":
        print(f"Warning: {speaker}'s response was cut off (hit max_tokens).\n")
        return "", None

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return parse_response(raw_text)


def text_to_speech(text, voice_id, filename):
    audio_chunks = elevenlabs_client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_v3",
        output_format="mp3_44100_128",
        voice_settings = VoiceSettings(
            stability=0.3,
            similarity_boost=0.75,
        ),
    )
    with open(filename, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)


speakers = list(PERSONAS)
current_speaker = speakers[0]

successful_turns = 0
attempts = 0
max_attempts = NUM_TURNS * 3 # safety valve so persistent failures can't loop forever

while successful_turns < NUM_TURNS and attempts < max_attempts:
    attempts += 1
    line, next_speaker = generate_turn(current_speaker)
    next_speaker_valid = next_speaker in PERSONAS and next_speaker != current_speaker

    if line.strip() and next_speaker_valid:
        transcript.append({"speaker": current_speaker, "text": line})
        print(f"{current_speaker}: {line}\n")

        safe_name = current_speaker.replace(" ", "_")
        filename = f"turn_{successful_turns}_{safe_name}.mp3"
        text_to_speech(line, VOICE_IDS[current_speaker], filename)
        audio_filenames.append(filename)
        print(f"Saved audio to {filename}\n")
        successful_turns += 1
        current_speaker = next_speaker
    else:
        if not line.strip():
            print(f"Skipping {current_speaker}'s turn — model returned no usable line.\n")
        else:
            print(f"Skipping {current_speaker}'s turn — model didn't return a valid NEXT speaker ({next_speaker!r}).\n")
        current_speaker = random.choice([name for name in speakers if name != current_speaker])

if successful_turns < NUM_TURNS:
    print(f"Warning: only got {successful_turns}/{NUM_TURNS} turns after {attempts} attempts.\n")

pause = AudioSegment.silent(duration=500)
episode = AudioSegment.empty()

for filename in audio_filenames:
    clip = AudioSegment.from_mp3(filename)
    episode = episode + clip + pause

episode.export("episode.mp3", format="mp3")
print("Saved full episode to episode.mp3")

for filename in audio_filenames:
    os.remove(filename)
print("Removed individual turn files")