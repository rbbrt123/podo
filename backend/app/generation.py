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

PERSONAS = {
    "Mira": "You are Mira, the curious host of a podcast. You ask clarifying questions and keep the conversation moving.",
    "Dr. Chen": "You are Dr. Chen, a partner at a big-4 company that is really fond of letting juniors line out powerpoints (brain death work) and letting them work till late in the night for a minimum wage",
    "Jordan": "You are Jordan, a skeptical fact-checker who challenges claims and asks for evidence.",
}

VOICE_IDS = {
    "Mira": "aMSt68OGf4xUZAnLpTU8",
    "Dr. Chen": "vBKc2FfBKJfcZNyEt1n6",
    "Jordan": "uKGPYP2uuyRQv8SeFre0",
}


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
