from anthropic import Anthropic
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment
from dotenv import load_dotenv
import os

load_dotenv()


anthropic_client = Anthropic()
elevenlabs_client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

TOPIC = "Will programmers get replaced by AI?"

PERSONAS = {
    "Mira" : "You are Mira, the curious host of a podcast. You ask clarifying questions and keep the conversation moving.",
    "Dr. Chen": "You are Dr. Chen, an important voice in the AI community who explains concepts clearly and has novel insights.",
}

VOICE_IDS = {
    "Mira": "aMSt68OGf4xUZAnLpTU8",
    "Dr. Chen": "vBKc2FfBKJfcZNyEt1n6",
}

transcript = []
audio_filenames = []

def format_transcript():
    if not transcript:
        return "(the conversation hasn't started yet)"
    lines = [f"{turn['speaker']}: {turn['text']}" for turn in transcript]
    return "\n".join(lines)


def generate_turn(speaker):
    system_prompt = (
        PERSONAS[speaker] #system prompt of speaker
        + f"\n\nYou are discussing this topic: {TOPIC}\n"
        + "Respond with ONE short conversational turn (2-3 sentences). "
        + "Do not include your name or a label before your line — just the words you'd say."
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

    text = "".join(block.text for block in response.content if block.type == "text")
    return text.strip()


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


speakers = list(PERSONAS.keys()) #just gives: ["Mira","Dr. Chen"]

for i in range(6):
    current_speaker = speakers[i % len(speakers)]
    line = generate_turn(current_speaker) #response of the current speaker
    transcript.append({"speaker": current_speaker, "text": line}) #appended to the transcript
    print(f"{current_speaker}: {line}\n")

    safe_name = current_speaker.replace(" ", "_") #just replacing spaces with _ for the formatting of the file name
    filename = f"turn_{i}_{safe_name}.mp3"
    text_to_speech(line, VOICE_IDS[current_speaker], filename)
    audio_filenames.append(filename)
    print(f"Saved audio to {filename}\n")

pause = AudioSegment.silent(duration=500)
episode = AudioSegment.empty()

for filename in audio_filenames:
    clip = AudioSegment.from_mp3(filename)
    episode = episode + clip + pause

episode.export("episode.mp3", format="mp3")
print("Saved full episode to episode.mp3")