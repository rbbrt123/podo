# Roadmap

_Last reviewed: 2026-08-21_

The living plan for podo: what's next, roughly in order, and why. Add
new ideas as a single line in [Idea backlog](#idea-backlog) — don't
stop to scope them. Groom periodically: fold backlog items in,
re-sequence if priorities changed, bump the date above.

Status values: `Not started` / `In progress` (link the branch/PR) /
`Awaiting merge` / done items move to [Shipped](#shipped) with a link
— only once the PR is actually in `main`.

## Priority order

| # | Feature | Effort | Status | Depends on |
|---|---|---|---|---|
| 1 | [Episode-level extra instructions](#1-episode-level-extra-instructions) | Small | Awaiting merge (`feature/episode-instructions`) | — |
| 2 | [Deploying podo](#2-deploying-podo) | Small–Medium | Not started | — |
| 3 | [Document-grounded episodes](#3-document-grounded-episodes) | Medium–Large | Not started | — |
| 4 | [AI-assisted prompt generation](#4-ai-assisted-prompt-generation) | Medium | Not started | — |
| 5 | [Agent personalization](#5-agent-personalization) | Medium (scope assumed) | Not started | loose synergy with #4 |
| 6 | [More natural conversational flow](#6-more-natural-conversational-flow) | Medium–Large | Not started | — |
| 7 | [React frontend](#7-react-frontend) | Large | Not started | best after #1–6 |
| 8 | [Make an app out of podo](#8-make-an-app-out-of-podo) | Small–Medium (scope assumed) | Not started | #7 |
| 9 | [Interactive interruptions](#9-interactive-interruptions) | Large | Not started | #6, #7 |
| 10 | [Sharing platform](#10-sharing-platform) | Large — biggest item here | Not started | #2, #7 |

**Order logic:** cheapest steering win first (#1), then get podo
reachable off your laptop now that generation is reliable and
reasonably fast (#2), then product breadth that's still cheap to
build in today's Gradio UI (#3–#5), then rework the conversational
engine (#6) before rebuilding the UI (#7–#8) against a settled data
model, then the flagship single-user feature (#9), then the flagship
multi-user feature (#10) last — it carries the most open product
questions and is worth more once everything else has de-risked it.

---

#### 1. Episode-level extra instructions
A free-text "extra instructions" field on episode creation, folded
into every chunk's system prompt (`_build_chunk_system_prompt()` in
`backend/app/generation.py`). Split off from #3 because it's a
fraction of the effort — one column, one textbox — for most of the
steering value.

#### 2. Deploying podo
Get your own instance reachable outside localhost (phone, demo) —
still single-user, still your own API keys. Add a basic auth gate
first: a public URL burns real Anthropic + ElevenLabs usage. Pure ops
work, doesn't collide with feature branches, can land anytime.

#### 3. Document-grounded episodes
Upload a source doc (PDF etc.), extract and chunk its text, ground
the conversation in it. Biggest standalone product value in the
backlog — directly serves podo's "calibrated to what I already know"
goal. Upload UI (`gr.File`) is cheap in Gradio now; costlier to build
well from scratch after the React rewrite (#7).

#### 4. AI-assisted prompt generation
A "draft a persona prompt from a few keywords/traits" pass in Agent
Lab, reviewed/edited before saving. Fixes "I don't know how to write
an agent prompt." Reuses the existing Anthropic client pattern.

#### 5. Agent personalization
**Scope assumption:** a handful of optional structured fields
(backstory, quirks, an icon) on an agent — a small schema migration
plus form fields. If instead this means cross-episode memory/continuity,
that's a materially bigger, different feature — re-scope before
starting.

#### 6. More natural conversational flow
Let agents interrupt each other mid-turn instead of one full turn at
a time. Needs a real rework of the transcript/turn data model and of
prompting (deciding mid-context whether to jump in). Do this before
#7 so the UI isn't rebuilt against a moving data model, and before #9,
which needs the same interrupt mechanism for a human listener.

#### 7. React frontend
Rewrite `frontend/app.py` once the feature set from #1–6 has settled
and the transcript model from #6 is final, so it's built once instead
of built in Gradio and re-ported.

#### 8. Make an app out of podo
**Scope assumption:** a PWA (manifest + service worker) on top of #7,
not a native iOS/Android app — confirm before starting if a real app
store app is actually wanted; that's a separate, larger project.

#### 9. Interactive interruptions
Live/streaming generation with a listener input channel (text or
voice) during playback, instead of generate-then-play. The flagship
single-user feature — needs #6's interrupt mechanism and #7's
mic/audio UI primitives.

#### 10. Sharing platform
User accounts, agent/episode visibility, browse + import. **Open
question:** who pays for generation — leaning bring-your-own-API-key
per user over a shared pool. **Open question:** does "download" an
agent copy it or link back to the original — defaulting to
copy-on-import. Last because it's a genuine pivot to a multi-user
product, amplified by everything shipped before it, and because these
questions are worth deciding once the smaller bets have validated the
app rather than upfront.

---

## Idea backlog

_New ideas land here as a single line, no formatting required._

- Cancel an in-progress episode generation from the Generate tab
- Episodes can share the same title, with no way to tell them apart in the dropdown
- A "cast" view showing which agents took part in a given episode
- Improve the agent self-introduction prompt
- Support other languages for episode generation
- Feedback/progress indicator while introductions are being generated

## Shipped

- Phase 1 quick wins: delete episodes, self-introduction toggle, duration-based length — [PR #10](https://github.com/rbbrt123/podo/pull/10)
- Generation reliability: stop discarding good turns on a `NEXT`-speaker mismatch, log rejections, lock in the host/moderator design ([ADR-0001](docs/adr/0001-structural-host-role-for-turn-taking.md)) — [PR #11](https://github.com/rbbrt123/podo/pull/11)
- Chunked, pipelined generation: batched multi-turn dialogue and TTS calls, host turn-taking enforcement, overlapped synthesis/generation, retry hardening against malformed chunks — [PRs #18–24](https://github.com/rbbrt123/podo/pull/24)
