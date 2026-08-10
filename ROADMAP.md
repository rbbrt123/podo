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
  as one reviewable document than as a dozen issues you'd have to
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
| 4 | [Deploying podo](#4-deploying-podo) | Small–Medium (scope assumed — see notes) | Not started |
| 5 | [Faster generation](#5-faster-generation) | Medium | Not started |
| 6 | [Document-grounded episodes](#6-document-grounded-episodes) | Medium–Large | Not started |
| 7 | [AI-assisted prompt generation](#7-ai-assisted-prompt-generation) | Medium | Not started |
| 8 | [Agent personalization](#8-agent-personalization) | Medium (scope assumed — see notes) | Not started |
| 9 | [More natural conversational flow](#9-more-natural-conversational-flow) | Medium–Large | Not started |
| 10 | [React frontend](#10-react-frontend) | Large | Not started |
| 11 | [Make an app out of podo](#11-make-an-app-out-of-podo) | Small–Medium (scope assumed — see notes) | Not started |
| 12 | [Interactive interruptions](#12-interactive-interruptions) | Large | Not started |
| 13 | [Sharing platform](#13-sharing-platform) | Large — biggest item here (open questions — see notes) | Not started |

The order groups into eight phases. The logic, in one sentence each:
ship the trivial wins first, get podo reachable outside your laptop,
then buy speed while the pipeline is still simple, then add product
breadth that's cheap to build in today's Gradio UI, then rework the
conversational engine once the surrounding feature set has settled,
then rebuild the UI once against that settled engine (and make it
installable), then build the flagship single-user interactive
feature, and only last — once nearly everything else has derisked
what a shared agent or episode actually looks like — turn podo into a
multi-user sharing platform.

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

### Phase 2 — Get podo off your laptop

#### 4. Deploying podo
- **Effort:** Small–Medium
- **Depends on:** —
- **Assumption made:** you said "no idea how I do this" — I'm
  assuming this means getting *your own* personal instance reachable
  outside localhost (from your phone, or to show someone), still
  single-user, still your own API keys. That's a much smaller,
  well-trodden problem (docker-compose already exists) than what
  [#13](#13-sharing-platform) needs (accounts, multi-tenancy,
  billing). If what's actually wanted is "have this ready to onboard
  other users," that's really #13, and this item is a lightweight
  prerequisite for it rather than a substitute.
- **Why here:** Pure ops work — it doesn't touch the same files as
  any feature phase, so it can land anytime without conflicting with
  anything. Doing it early means finding deploy issues (host binding,
  CORS, storage paths that currently assume local disk, secrets
  handling) while the codebase is still small, instead of after
  several more features have added moving parts. It also unlocks
  real personal value immediately — usable away from your laptop —
  for comparatively little work.
- **Watch out for:** a deployed instance is reachable by anyone who
  finds the URL, and every episode costs real Anthropic + ElevenLabs
  API usage. Put at least a basic access gate (password / basic auth)
  in front of it before it's reachable from the internet — this is a
  much lighter requirement than the full account system #13 will
  eventually need, and shouldn't be confused with it.
- **What it involves:** pick a host (a small VPS, or a platform like
  Fly.io/Railway that runs docker-compose-shaped apps directly), a
  persistent volume for the SQLite DB + episode audio, env vars for
  the API keys, a basic access gate, and pointing
  `PODO_BACKEND_URL`/CORS at the real (non-localhost) origin.

---

### Phase 3 — Buy speed while the pipeline is still simple

#### 5. Faster generation
- **Effort:** Medium
- **Depends on:** —
- **Why here:** `_run_generation()` today is strictly sequential —
  generate a line, then synthesize it, then generate the next line —
  with no overlap. That's the easiest version of the pipeline to
  optimize (pipeline TTS for turn *N* while generating dialogue for
  turn *N+1*; cut the `max_attempts = num_turns * 3` retry waste).
  Doing this now matters because every later item that adds more LLM
  round-trips per episode — natural conversational flow
  ([#9](#9-more-natural-conversational-flow), more/shorter turns) and
  especially interactive interruptions
  ([#12](#12-interactive-interruptions), which needs low per-turn
  latency to feel "live") — inherits whatever latency floor exists
  here. Fix the floor before building more on top of it, not after.
- **What it involves:** Overlap TTS synthesis with next-turn dialogue
  generation, reduce retry waste, consider streaming synthesis.

---

### Phase 4 — Product breadth (independent, cheap to build in Gradio today)

These three are self-contained, don't depend on each other except
where noted, and are all comfortably buildable in the current Gradio
frontend — a `gr.File` drop zone or an extra textbox is a few lines.
Building them now, before the React rewrite
([#10](#10-react-frontend)), means they get built once instead of
built in Gradio and then re-ported.

#### 6. Document-grounded episodes
- **Effort:** Medium–Large
- **Depends on:** —
- **Why here:** Biggest standalone product value in the backlog — it
  directly serves the project's stated goal (README: "personalized,
  multi-expert podcasts... calibrated to what I already know").
  Fully independent of the other items, and the upload UI is cheap in
  Gradio (`gr.File`) right now; a custom drop zone is more work to
  build well from scratch in React later, so there's a real cost to
  deferring this past #10.
- **What it involves:** Upload endpoint + storage for the source
  file, PDF text extraction (e.g. `pypdf`), chunking for
  token-limit-sized context, feeding extracted content into the
  system/topic prompt in `generate_turn()`.

#### 7. AI-assisted prompt generation
- **Effort:** Medium
- **Depends on:** —
- **Why here:** Standalone addition to the existing Agent Lab tab;
  reuses the same Anthropic client pattern already in `generation.py`
  for a new "draft a persona prompt from keywords" call. Sequenced
  next to #8 because both touch the agent-creation form — doing them
  in the same pass avoids touching that UI twice.
- **What it involves:** New endpoint (e.g. `POST /agents/generate`)
  that takes keywords/traits and returns a drafted persona prompt;
  Agent Lab flow to review/edit the draft before saving.

#### 8. Agent personalization
- **Effort:** Medium, **but scope is genuinely ambiguous — flagging
  the assumption below rather than guessing silently and building the
  wrong thing.**
- **Depends on:** Loose synergy with #7 (same form), not a hard
  dependency.
- **Assumption made:** The request says "extra personal touches...
  exact form is still open." I'm assuming this means a small set of
  additional *optional structured fields* on an agent — e.g.
  backstory, catchphrases/quirks, an avatar/icon image — surfaced in
  Agent Lab and folded into the system prompt at generation time.
  That's a schema migration on `agents` (a few nullable columns) plus
  form fields — Medium effort. This also matters for
  [#13](#13-sharing-platform) later, which explicitly wants an icon
  as part of what's shared.
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

### Phase 5 — Rework the conversational engine

#### 9. More natural conversational flow
- **Effort:** Medium–Large
- **Depends on:** Sequenced after #5 (speed) and Phase 4, before #10
  and #12.
- **Why here:** Today's "turn" is a whole utterance, generated in
  full, then synthesized in full, then handed to the next speaker —
  the model already picks who speaks next (see `NEXT:` in
  `parse_response()`), but there's no mechanism for an agent to break
  in mid-turn. Letting agents genuinely interrupt each other means
  a real rework of the transcript/turn data model (from
  one-turn-per-utterance to something more granular) and the
  prompting strategy (agents need to be able to decide *mid-context*
  whether to jump in). That's exactly the plumbing that listener
  interruptions (#12) needs too — #12 is really "let the *listener*
  be one of the interrupters" — so building the general mechanism
  here first, once, means #12 doesn't have to invent it under
  pressure later. Sequenced after Phase 4 so those features don't
  have to be rebuilt against a moving transcript model; sequenced
  after speed work (#5) because finer-grained turns mean more, not
  fewer, LLM round-trips per episode.
- **What it involves:** Rework the turn/transcript data model to
  support sub-turn interjections, rework prompting so agents can
  decide to interrupt given partial context, rework audio stitching
  to handle interjected segments.

---

### Phase 6 — Rebuild the UI platform

#### 10. React frontend
- **Effort:** Large
- **Depends on:** Best done after Phase 1–5 so the UI is built once
  against a settled feature set and the final transcript/turn data
  model from #9, not rebuilt mid-flight as those land.
- **Why here:** This is a full rewrite of `frontend/app.py`, so
  timing matters more than effort. Doing it too early means every
  Gradio-cheap feature in Phase 4 gets built twice. Doing it here
  means: the product surface (uploads, duration, toggles, agent
  fields, AI-assisted prompts) has stabilized, the turn/transcript
  data model from #9 is final, and the rewrite directly sets up both
  #11 (a PWA install shell) and #12 — real-time interruptions need
  custom audio/mic UI primitives (streaming playback, push-to-talk)
  that are a much better fit for a custom React app than for Gradio's
  component set.
- **What it involves:** New React frontend consuming the existing
  FastAPI JSON API (`/episodes`, `/agents`, `/voices`, ...); check
  CORS and audio file serving work cleanly from a separate origin/dev
  server.

#### 11. Make an app out of podo
- **Effort:** Small–Medium
- **Depends on:** #10 (React frontend) — hard dependency under the
  assumed scope below.
- **Assumption made:** also flagged as "no idea how" — I'm assuming
  this means an installable **Progressive Web App** (a manifest +
  service worker layered on the React frontend, so it can be added to
  a phone's home screen and opens like a standalone app), not a
  separate native iOS/Android codebase (React Native, Swift, Kotlin),
  which would be a materially larger, separate project. Confirm which
  one is actually wanted before picking this up — if it's a real App
  Store/Play Store app, this needs its own re-scoping.
- **Why here:** A PWA manifest + service worker is something you add
  to a real frontend app; it's not practical to retrofit onto
  Gradio's component model. So it has to follow the React rewrite,
  and it's small enough to be a direct follow-on in the same phase
  rather than warranting its own separate slot later.
- **What it involves:** web app manifest, icons, a service worker (at
  minimum caching the app shell / Library for offline browsing),
  "Add to Home Screen" support.

---

### Phase 7 — The flagship single-user feature

#### 12. Interactive interruptions
- **Effort:** Large
- **Depends on:** #9 (interrupt-aware conversational engine), #10
  (custom real-time UI for mic/audio input mid-playback); benefits
  from #5 (per-turn latency needs to be low for an interruption-and-
  resume to feel natural rather than laggy).
- **Why here:** The most ambitious and most architecturally
  open-ended single-user item in the list — it turns podo from
  "generates an episode you play back" into "a live session you can
  talk to," which is a different interaction model, not just a new
  parameter. It's also the item with the most reuse from everything
  before it: the interrupt/interject mechanism from #9 extends
  naturally to a human interrupter once it exists, and it needs #10's
  UI primitives to capture and inject listener input mid-playback.
  Building it without those first means solving all of that from
  scratch under one feature instead of inheriting it.
- **What it involves:** Live/streaming generation instead of
  generate-then-play, a listener input channel (text or voice) during
  playback, injecting listener input into the transcript context, and
  resuming generation naturally afterward.

---

### Phase 8 — The flagship multi-user feature

#### 13. Sharing platform
- **Effort:** Large — likely the single largest item on this roadmap,
  possibly larger than #10 and #12 combined.
- **Depends on:** #4 (deployed somewhere reachable by others — hard
  prerequisite, you can't share from localhost), #10 (React frontend
  — a browse/profile/import UI is a much bigger surface than Gradio's
  component model comfortably handles); soft dependency on #8 (agent
  personalization) for the "icon" field this item explicitly wants to
  share.
- **Why last:** This is a genuine pivot from "single-user tool" to
  "multi-user social product," and it carries more open product
  questions than everything else in this roadmap combined — see
  below. Those are exactly the kind of decisions worth making once
  the smaller, well-scoped bets elsewhere in this plan have already
  shipped and validated the app, rather than upfront. It's also
  amplified by nearly everything before it: richer agents (from #7,
  #8) and richer episodes (from #6, #9, #12) are what make other
  people's libraries actually worth browsing in the first place.
- **The open question that matters most — flagging rather than
  deciding silently: who pays for generation?** Every episode
  currently costs real Anthropic + ElevenLabs API usage against
  *your* keys. If other people can generate episodes with agents on a
  platform you host, that's your bill unless something changes. I'm
  leaning toward **bring-your-own-API-key per user** (each person
  supplies and stores their own keys, encrypted server-side) over a
  shared pool, since BYOK avoids you personally underwriting
  strangers' usage — but a shared pool with quotas is possible too,
  and is a meaningfully different (bigger) piece of work. **This
  needs an explicit decision before implementation starts,** not an
  assumption baked into the build.
- **Other open questions worth deciding at spec time:** does
  "download" an agent mean a *copy* (importer can freely edit, no
  link back to the original) or a *reference* (stays linked, updates
  from the original flow through)? Defaulting to copy-on-import as
  the simpler, safer option unless you want the reference model.
  Also worth at least a lightweight report/hide mechanism once
  prompts and agents are visible to people other than you.
- **What it involves (high level — deserves its own follow-up
  planning pass once picked up):** user accounts/auth; visibility
  (public/private) on agents and episodes; a browse/directory UI for
  other users' agents and episodes; a "cast" display on an episode
  linking back to the agents (and their owners) used in it; an
  import/"download" flow that copies an agent into your own
  collection; per-user API key storage if BYOK is confirmed; a more
  concurrency-friendly data store (SQLite is fine solo, but this is
  the item where a real multi-user database, e.g. Postgres, starts to
  matter); basic content moderation/reporting.

---

## Idea backlog

_New ideas land here as a single line, no formatting required. Groom
into the prioritized list above periodically._

_(empty — all current ideas are prioritized above)_

## Shipped

_Move items here once merged, with a link to the PR._

_(nothing shipped from this roadmap yet)_
