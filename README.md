 AI Podcast Generator

A personal project exploring multi-agent AI: two LLM-driven personas hold
a spoken conversation about a topic you choose, generated end-to-end with
Claude (dialogue) and ElevenLabs (voice).

**Status: early / actively in development.** Currently working:
- Two personas generate a back-and-forth conversation, with the model
  itself deciding who speaks next each turn
- Each persona gets a distinct AI voice
- Turns are stitched into one playable episode

**Planned next:** a listener knowledge-level parameter, so the
conversation's depth and vocabulary calibrate to what you already know.

## Setup

1. `uv sync`
2. Create a `.env` file with:
ANTHROPIC_API_KEY=your-key-here
ELEVENLABS_API_KEY=your-key-here
3. `uv run main.py`

## Why this project

I wanted personalized, multi-expert podcasts on niche topics, calibrated
to what I already know — existing podcasts are usually either too
beginner-level or assume expert background. Building this to learn
multi-agent orchestration and TTS pipelines along the way.