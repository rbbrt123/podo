# Introduce a structural host role for episode turn-taking

**Status:** accepted

## Context

Today, every turn in `_run_generation()` (`backend/app/generation.py`) is
fully peer-to-peer: whichever agent just spoke picks who speaks next via a
`NEXT: <name>` field the LLM emits itself. In practice, two guest agents
often pick each other repeatedly and go deep into a tangent, drifting the
conversation away from the topic, while one agent (usually Nova, whose
built-in prompt already casts it as "a podcast host... who interrupts
politely") ends up unofficially opening and closing the episode just
because of turn order — not because the system gives it that role.

This is a separate problem from the already-diagnosed bug where a turn is
silently discarded on an invalid `next_speaker` match and reassigned via
`random.choice()` (see `ROADMAP.md`, Phase 2 / item #4). That bug fix and
an accompanying speed improvement (overlapping TTS synthesis with dialogue
generation) are sequenced to land first — it's unsafe to build new
turn-taking logic on a loop that's still silently dropping or misattributing
turns.

## Decision

Introduce **Host** as a first-class, per-episode role (see `CONTEXT.md`):

- `Agent` gains an `is_host` flag marking it *eligible* to be selected as
  host. It is not a permanent type — the same agent can host one episode
  and guest in another. Setting the flag prepends a fixed host-instruction
  block before the agent's own persona prompt at generation time. Nova
  ships pre-seeded `is_host=True`; Okafor and Sam stay guests.
- Episode creation requires designating exactly one host from among the
  selected, host-eligible agents. Selecting no host-eligible agent is a
  hard validation error — there is no fallback to the old fully
  peer-to-peer behavior.
- Turn-taking becomes a **capped window**: guests may still pick each other
  via `NEXT:` and riff, same as today, but after a small hardcoded cap of
  consecutive non-host turns (e.g. 2), the loop forcibly returns control to
  the host regardless of what the last guest's `NEXT:` said.
- The host also takes over what `generate_intro()` / `generate_outro()` do
  implicitly today (looping speakers in list order / hardcoding
  `speakers[0]`): the host explicitly owns the opening frame and the
  closing wrap-up.
- Keeping the conversation on-topic and covering breadth rather than depth
  is handled purely through the host's injected prompt instructions — no
  algorithmic subtopic tracking.

## Considered options

- **Strict alternation** (host speaks every other turn) — rejected: makes
  the host ~50% of all airtime, closer to an interview format than the
  panel conversation podo is going for.
- **Subtopic-checklist tracking** (decompose the topic up front, track
  coverage, inject remaining subtopics into the host's prompt each turn) —
  rejected for v1 as meaningfully more engineering for a problem not yet
  confirmed that prompting alone can't solve. Left as a fog item to revisit
  if prompt-only steering proves insufficient in practice.
- **Silent fallback to peer-to-peer when no host is selected** — rejected:
  keeps two turn-taking engines alive indefinitely and risks users landing
  in the old broken behavior without knowing why.

## Consequences

- Explicitly out of scope: mid-turn interruption (cutting a guest off
  mid-utterance) belongs to the separate, larger "more natural
  conversational flow" rework (`ROADMAP.md` Phase 5 — sub-turn
  interjections); multi-host or rotating-host models are deferred until a
  fixed single host has been used in practice.
- `episodes` needs a `host_agent_id`-shaped reference to the chosen host;
  `agents` needs the `is_host` column. Both are additive schema changes.
- Implementation is intentionally blocked on the Phase 2 reliability/speed
  fix landing first (see Context above) — this ADR records the design, not
  a green light to build immediately.
