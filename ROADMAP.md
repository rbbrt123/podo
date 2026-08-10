# Roadmap

_Last reviewed: 2026-08-10_

This is the living plan for podo: what's next, in what order, and why.
It replaces the phone notes app as the source of truth for feature
ideas — the goal is that adding a new idea takes 10 seconds, and
anyone (including future-you) can read this file and understand not
just what's planned but why it's sequenced the way it is.

## How to use this file

- **Got a new idea?** Add one line to [Idea backlog](#idea-backlog)
  at the bottom. Don't stop to write effort estimates or find the
  "right" spot for it — that happens later, in a batch, during
  grooming.
- **Starting work on something?** Update its Status below to `In
  progress`, and open a branch/PR as usual (this project already uses
  feature branches + PRs against `main` — link the PR to the relevant
  section here in the description).
- **Shipped something?** Move its entry to [Shipped](#shipped) with a
  link to the merge commit or PR, and check whether the README's
  "Currently working" / "Planned next" summary needs a one-line
  update.
- **Grooming** (whenever the backlog list below gets long, or
  priorities shift): fold backlog items into the prioritized list,
  re-sequence if dependencies changed, and bump "Last reviewed" above.
  Git history on this file is the changelog of *why* priorities moved
  — write commit messages accordingly (e.g. "Reorder: pull doc
  grounding forward, blocked on nothing and higher value than agent
  personalization").

### Why a roadmap file instead of GitHub Issues / a Project board

Worth recording so this choice doesn't look like an accident:

- **Single-file narrative beats scattered tickets at this size.** The
  main value right now isn't tracking individual tasks, it's
  reasoning about *order* — what unblocks what, what's safe to build
  cheaply now vs. later. That's a narrative, and it reads far better
  as one reviewable document than as ten issues you'd have to
  reconstruct the story from.
- **Zero new surface.** No new account/tab to check, no labels or
  board columns to maintain for an audience of one. Every review
  tool you already use (git log, git diff, PR review) works on this
  file for free.
- **Capture is already low-friction.** Appending a bullet to the
  backlog section is at least as fast as filing an issue, and it can
  be done straight from GitHub's mobile web editor if an idea shows
  up away from a laptop.
- **Revisit this if the project gets collaborators.** Issues +
  a Project board start winning once more than one person is picking
  up work concurrently and needs status visibility without reading
  prose, or once individual items need their own discussion threads.
  At that point, promote items out of this file into issues one at a
  time as they're picked up — no need to migrate everything at once.

## Current priority order

| # | Feature | Effort | Status |
|---|---|---|---|
| 1 | [Delete episodes](#1-delete-episodes) | Small | Not started |
| 2 | [Optional self-introductions toggle](#2-optional-self-introductions-toggle) | Small | Not started |
| 3 | [Duration-based length](#3-duration-based-length) | Small–Medium | Not started |
| 4 | [Faster generation](#4-faster-generation) | Medium | Not started |
| 5 | [Document-grounded episodes](#5-document-grounded-episodes) | Medium–Large | Not started |
| 6 | [AI-assisted prompt generation](#6-ai-assisted-prompt-generation) | Medium | Not started |
| 7 | [Agent personalization](#7-agent-personalization) | Medium (scope assumed — see notes) | Not started |
| 8 | [More natural conversational flow](#8-more-natural-conversational-flow) | Medium–Large | Not started |
| 9 | [React frontend](#9-react-frontend) | Large | Not started |
| 10 | [Interactive interruptions](#10-interactive-interruptions) | Large | Not started |

The order groups into six phases. The logic, in one sentence each:
ship the trivial wins first, then buy speed while the pipeline is
still simple, then add product breadth that's cheap to build in
today's Gradio UI, then rework the conversational engine once the
surrounding feature set has settled, then rebuild the UI once against
that settled engine, then build the flagship interactive feature on
top of everything else.

---

### Phase 1 — Quick wins (no dependencies)

Ship these first: they're cheap, self-contained, and each one is an
immediate, visible improvement. No reason to sit on them while
bigger items are planned.

#### 1. Delete episodes
- **Effort:** Small
- **Depends on:** —
- **Why here:** Trivial and mirrors a pattern that already exists —
  `delete_agent` in `storage.py` / `DELETE /agents/{id}` in
  `main.py` is a direct template for the episode equivalent. Good
  first PR, immediate quality-of-life fix for the Library tab.
- **What it involves:** `DELETE /episodes/{id}` endpoint, row + audio
  file cleanup in `storage.py`, a delete button in the Library tab.

#### 2. Optional self-introductions toggle
- **Effort:** Small
- **Depends on:** —
- **Why here:** One boolean threaded through `CreateEpisodeRequest`
  into the system prompt built in `generate_turn()`. No schema
  change beyond one column, no new UI beyond one checkbox.
- **What it involves:** New `intros` flag on episode creation;
  conditionally include/omit an "introduce yourself first" prompt
  instruction for each agent's first turn.

#### 3. Duration-based length
- **Effort:** Small–Medium
- **Depends on:** —
- **Why here:** Still isolated to the generation loop and the
  `episodes` table (`num_turns` → a target duration), but touches the
  stopping condition in `_run_generation()`, so it's a notch above
  the other two. Worth landing before more features start assuming
  today's turn-count semantics.
- **What it involves:** Replace the turn-count stop condition with
  one based on accumulated audio duration (estimate turns needed
  from a running average turn length, or just check elapsed
  synthesized duration after each turn); swap the turns slider in the
  Generate tab for a minutes input.

---

### Phase 2 — Buy speed while the pipeline is still simple

#### 4. Faster generation
- **Effort:** Medium
- **Depends on:** —
- **Why here:** `_run_generation()` today is strictly sequential —
  generate a line, then synthesize it, then generate the next line —
  with no overlap. That's the easiest version of the pipeline to
  optimize (pipeline TTS for turn *N* while generating dialogue for
  turn *N+1*; cut the `max_attempts = num_turns * 3` retry waste).
  Doing this now matters because every later item that adds more LLM
  round-trips per episode — natural conversational flow (#8, more/
  shorter turns) and especially interactive interruptions (#10, which
  needs low per-turn latency to feel "live") — inherits whatever
  latency floor exists here. Fix the floor before building more on
  top of it, not after.
- **What it involves:** Overlap TTS synthesis with next-turn dialogue
  generation, reduce retry waste, consider streaming synthesis.

---

### Phase 3 — Product breadth (independent, cheap to build in Gradio today)

These three are self-contained, don't depend on each other except
where noted, and are all comfortably buildable in the current Gradio
frontend — a `gr.File` drop zone or an extra textbox is a few lines.
Building them now, before the React rewrite (#9), means they get
built once instead of built in Gradio and then re-ported.

#### 5. Document-grounded episodes
- **Effort:** Medium–Large
- **Depends on:** —
- **Why here:** Biggest standalone product value in the backlog — it
  directly serves the project's stated goal (README: "personalized,
  multi-expert podcasts... calibrated to what I already know").
  Fully independent of the other items, and the upload UI is cheap in
  Gradio (`gr.File`) right now; a custom drop zone is more work to
  build well from scratch in React later, so there's a real cost to
  deferring this past #9.
- **What it involves:** Upload endpoint + storage for the source
  file, PDF text extraction (e.g. `pypdf`), chunking for
  token-limit-sized context, feeding extracted content into the
  system/topic prompt in `generate_turn()`.

#### 6. AI-assisted prompt generation
- **Effort:** Medium
- **Depends on:** —
- **Why here:** Standalone addition to the existing Agent Lab tab;
  reuses the same Anthropic client pattern already in `generation.py`
  for a new "draft a persona prompt from keywords" call. Sequenced
  next to #7 because both touch the agent-creation form — doing them
  in the same pass avoids touching that UI twice.
- **What it involves:** New endpoint (e.g. `POST /agents/generate`)
  that takes keywords/traits and returns a drafted persona prompt;
  Agent Lab flow to review/edit the draft before saving.

#### 7. Agent personalization
- **Effort:** Medium, **but scope is genuinely ambiguous — flagging
  the assumption below rather than guessing silently and building the
  wrong thing.**
- **Depends on:** Loose synergy with #6 (same form), not a hard
  dependency.
- **Assumption made:** The request says "extra personal touches...
  exact form is still open." I'm assuming this means a small set of
  additional *optional structured fields* on an agent — e.g.
  backstory, catchphrases/quirks, an avatar image — surfaced in Agent
  Lab and folded into the system prompt at generation time. That's a
  schema migration on `agents` (a few nullable columns) plus form
  fields — Medium effort.
  **If instead this means something like cross-episode memory or
  continuity** (an agent "remembering" past episodes with you), that
  is a materially larger, architecturally different feature (persistent
  per-agent state, retrieval across episodes) and should be re-scoped
  and re-estimated on its own before starting. **Confirm which one
  this is before picking this item up.**
- **What it involves (under the assumed scope):** New nullable
  columns on `agents`, Agent Lab form additions, prompt assembly
  changes to weave the extra fields into `generate_turn()`'s system
  prompt.

---

### Phase 4 — Rework the conversational engine

#### 8. More natural conversational flow
- **Effort:** Medium–Large
- **Depends on:** Sequenced after #4 (speed) and Phase 3, before #9
  and #10.
- **Why here:** Today's "turn" is a whole utterance, generated in
  full, then synthesized in full, then handed to the next speaker —
  the model already picks who speaks next (see `NEXT:` in
  `parse_response()`), but there's no mechanism for an agent to break
  in mid-turn. Letting agents genuinely interrupt each other means
  a real rework of the transcript/turn data model (from
  one-turn-per-utterance to something more granular) and the
  prompting strategy (agents need to be able to decide *mid-context*
  whether to jump in). That's exactly the plumbing that listener
  interruptions (#10) needs too — #10 is really "let the *listener*
  be one of the interrupters" — so building the general mechanism
  here first, once, means #10 doesn't have to invent it under
  pressure later. Sequenced after Phase 3 so those features don't
  have to be rebuilt against a moving transcript model; sequenced
  after speed work (#4) because finer-grained turns mean more, not
  fewer, LLM round-trips per episode.
- **What it involves:** Rework the turn/transcript data model to
  support sub-turn interjections, rework prompting so agents can
  decide to interrupt given partial context, rework audio stitching
  to handle interjected segments.

---

### Phase 5 — Rebuild the UI platform

#### 9. React frontend
- **Effort:** Large
- **Depends on:** Best done after Phase 1–4 so the UI is built once
  against a settled feature set and the final transcript/turn data
  model from #8, not rebuilt mid-flight as those land.
- **Why here:** This is a full rewrite of `frontend/app.py`, so
  timing matters more than effort. Doing it too early means every
  Gradio-cheap feature in Phase 3 gets built twice. Doing it here
  means: the product surface (uploads, duration, toggles, agent
  fields, AI-assisted prompts) has stabilized, the turn/transcript
  data model from #8 is final, and the rewrite directly sets up
  #10 — real-time interruptions need custom audio/mic UI primitives
  (streaming playback, push-to-talk) that are a much better fit for a
  custom React app than for Gradio's component set.
- **What it involves:** New React frontend consuming the existing
  FastAPI JSON API (`/episodes`, `/agents`, `/voices`, ...); check
  CORS and audio file serving work cleanly from a separate origin/dev
  server.

---

### Phase 6 — The flagship feature

#### 10. Interactive interruptions
- **Effort:** Large
- **Depends on:** #8 (interrupt-aware conversational engine), #9
  (custom real-time UI for mic/audio input mid-playback); benefits
  from #4 (per-turn latency needs to be low for an interruption-and-
  resume to feel natural rather than laggy).
- **Why here:** The most ambitious and most architecturally
  open-ended item in the list — it turns podo from "generates an
  episode you play back" into "a live session you can talk to," which
  is a different interaction model, not just a new parameter. It's
  also the item with the most reuse from everything before it: the
  interrupt/interject mechanism from #8 extends naturally to a human
  interrupter once it exists, and it needs #9's UI primitives to
  capture and inject listener input mid-playback. Building it first,
  without those, means solving all of that from scratch under one
  feature instead of inheriting it. Natural culmination of the plan.
- **What it involves:** Live/streaming generation instead of
  generate-then-play, a listener input channel (text or voice) during
  playback, injecting listener input into the transcript context, and
  resuming generation naturally afterward.

---

## Idea backlog

_New ideas land here as a single line, no formatting required. Groom
into the prioritized list above periodically._

_(empty — all current ideas are prioritized above)_

## Shipped

_Move items here once merged, with a link to the PR._

_(nothing shipped from this roadmap yet)_
