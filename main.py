from anthropic import Anthropic
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment
from dotenv import load_dotenv
import os
import random

load_dotenv()


anthropic_client = Anthropic()
elevenlabs_client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

TOPIC = "Is selling your voice to an AI company ethical?"
NUM_TURNS = 6

PERSONAS = {
    "Mira" : "You are Mira, the curious host of a podcast. You ask clarifying questions and keep the conversation moving.",
    "Dr. Chen": "You are Dr. Chen, an important voice in the AI community who explains concepts clearly and has novel insights.",
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
    return line, next_speaker


def generate_turn(speaker):
    other_speakers = [name for name in PERSONAS if name != speaker]
    system_prompt = (
        PERSONAS[speaker] #system prompt of speaker
        + f"\n\nYou are discussing this topic: {TOPIC}\n"
        + f"The other speaker(s) is/(are): {', '.join(other_speakers)}\n"
        + "Respond in EXACTLY this format, and nothing else:\n"
        + "LINE: <your conversational turn, 2-3 sentences, no name label>\n"
        + f"NEXT: <who should speak next — one of: {', '.join(other_speakers)}>"
    )

    conversation_so_far = format_transcript() #all the outputs so far formatted in a nice way

    response = anthropic_client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Conversation so far:\n{conversation_so_far}\n\nGive your next line."}
        ]
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return parse_response(raw_text)


def text_to_speech(text, voice_id, filename):
    audio_chunks = elevenlabs_client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    with open(filename, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)


speakers = list(PERSONAS)
current_speaker = speakers[0]

for i in range(NUM_TURNS):
    line, next_speaker = generate_turn(current_speaker)
    transcript.append({"speaker": current_speaker, "text": line})
    print(f"{current_speaker}: {line}\n")

    safe_name = current_speaker.replace(" ", "_")
    filename = f"turn_{i}_{safe_name}.mp3"
    text_to_speech(line, VOICE_IDS[current_speaker], filename)
    audio_filenames.append(filename)
    print(f"Saved audio to {filename}\n")

    if next_speaker in PERSONAS and next_speaker != current_speaker:
        current_speaker = next_speaker
    else:
        current_speaker = random.choice([name for name in speakers if name != current_speaker])

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