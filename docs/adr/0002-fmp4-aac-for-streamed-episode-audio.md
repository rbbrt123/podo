# Use fragmented MP4/AAC with MSE "sequence" mode for streamed episode audio

**Status:** accepted

## Context

Episode generation already produces audio in independent per-chunk pieces
(`synthesize_chunk` in `backend/app/generation.py`), but today only the fully
stitched final `episode.mp3` is ever exposed to listeners — nothing is
playable until generation finishes entirely, even though most of the audio
exists much earlier.

The goal is to stream episode audio to listeners as chunks become ready,
using the browser's Media Source Extensions (MSE) API — the actual mechanism
real streaming platforms (YouTube, Twitch) use, as opposed to a "play file
after file" approximation. This also requires replacing the Gradio frontend,
since Gradio has no hook into raw MSE.

Before committing to that rewrite, we ran a standalone format spike
(`spikes/mse-format/`, now removed — see git history on branch
`feature/mse-streaming` if it needs revisiting) to answer one question: what
audio container/codec can MSE actually play back gaplessly, given that
chunks are produced as independent files, not as one continuous encoder
session?

## What we tested

All tests used real generated audio — two leftover chunk files from an
interrupted episode run (episode 7) — driven live in headless Chromium via
Playwright, not simulated or assumed from documentation.

1. Raw MP3 (`audio/mpeg`) via `SourceBuffer.appendBuffer`, matching the exact
   bytes `synthesize_chunk` produces today (ElevenLabs audio, decoded and
   re-encoded once via pydub/ffmpeg's own MP3 encoder).
2. Each MP3 chunk transcoded **independently** to fragmented MP4/AAC
   (`ffmpeg -c:a aac -movflags frag_keyframe+empty_moov+default_base_moof`),
   appended via `SourceBuffer` under both of MSE's append modes: `segments`
   (default) and `sequence`.

## Findings

- **Raw MP3 chunks are not gapless over MSE.** Both source files carry
  standard LAME-style gapless metadata (576-sample encoder delay, up to
  1152-sample padding per chunk) that a normal `<audio src=...>` player, VLC,
  or ffprobe would trim. Chrome's MSE MP3 path does not trim it: the
  browser-reported total duration after appending two chunks (106.553466s)
  exactly matched the *untrimmed* raw frame count of both files, proving MSE
  decoded the encoder delay/padding as real audio instead of discarding it.
  Net effect: a real, audible ~39ms artifact at every chunk boundary.
- **Fragmented MP4/AAC under the default `segments` mode breaks outright**,
  not just imprecisely: because each independently-encoded chunk's internal
  timestamps start at 0, appending the second chunk overwrote the first
  instead of extending the timeline. Reported duration after appending both
  chunks was 85.14s — exactly chunk 0's own length; chunk 1 was unreachable.
- **Fragmented MP4/AAC under `SourceBuffer.mode = 'sequence'` is correct and
  precise.** Sequence mode ignores each segment's own embedded timestamps and
  places appended data immediately after whatever is already buffered.
  Reported duration after appending two independently-encoded chunks:
  106.526438s, against a ground-truth sum (ffprobe) of 106.526440s — a
  difference of 2 microseconds. Real playback (sampled after 1s) advanced
  normally with no stalls or errors.
- Structural inspection of the transcoded files (raw box parsing) confirmed
  each carries its own `ftyp`+`moov` (an independent initialization segment)
  rather than sharing one — which is exactly why `segments` mode fails, and
  why `sequence` mode (which doesn't depend on a shared init/timeline) is the
  correct fit rather than a lucky workaround.

## Decision

Streamed episode audio will be delivered as **AAC audio in fragmented MP4
containers, transcoded per chunk**. No architectural change is needed to
produce one continuous encoder session per episode — each already-independent
chunk can keep being transcoded on its own, matching the current
one-chunk-at-a-time backend design. The frontend's `SourceBuffer` must be
created with `mode = 'sequence'` before any data is appended.

Plain MP3 delivery over MSE is rejected for this purpose.

## Considered options

- **Raw MP3 over MSE** — rejected: proven (not assumed) to introduce a
  ~39ms audible artifact at every chunk boundary from unhandled encoder
  delay/padding.
- **fMP4/AAC with `segments` mode** — rejected: breaks outright for
  independently-encoded chunks (second chunk overwrites the first); would
  require every chunk to carry accurate, hand-managed timestamp offsets to
  work around it — needless complexity when `sequence` mode solves it for
  free.
- **A single persistent encoder process spanning the whole episode**,
  emitting one shared init segment and continuous fragments as audio is
  produced — considered but not needed: `sequence` mode gets the same
  gapless result from independently-encoded per-chunk files, at far lower
  implementation cost (no long-lived subprocess/pipe management per
  episode).

## Consequences

- The backend needs a transcode step (MP3 → fragmented MP4/AAC) added after
  each chunk is synthesized, in addition to — not instead of — today's final
  stitched `episode.mp3` used for storage/playback in the Library.
- The frontend must be hand-built (plain HTML/JS to start) around
  `MediaSource`/`SourceBuffer`, since Gradio has no hook into these browser
  APIs. This ADR covers only the audio format/delivery decision the rewrite
  depends on, not the rewrite's scope.
- This spike only tested Chromium (the only engine available in the test
  environment) — Firefox/Safari MSE behavior for fragmented MP4/AAC is
  expected to be far more consistent than for raw MP3 (fMP4 is the
  standard MSE format across browsers), but hasn't been directly verified
  here and is still open before relying on this in production.
