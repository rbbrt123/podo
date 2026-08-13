# Podo

Podo generates a multi-agent podcast episode: a set of AI personas hold a
spoken conversation about a topic, scripted turn-by-turn by an LLM and
synthesized to voice.

## Language

**Agent**:
A reusable persona — a name, a system prompt, and a voice — that can
participate in any number of episodes. Three locked built-in agents (Nova,
Professor Okafor, Sam) ship by default; users can create and edit their own.
_Avoid_: Persona (fine in prose, but "Agent" is the schema/code term)

**Episode**:
One generated podcast conversation: a topic, a target duration, and the set
of participating agents, produced as a single stitched MP3.

**Turn**:
One agent's single spoken utterance within an episode, generated and
synthesized in sequence.

**Host**:
The one agent designated, per episode, to drive the conversation — opening
and closing the episode, and periodically steering the conversation back on
topic when it drifts. Host is a per-episode role assignment, not a
permanent trait: only agents flagged as host-capable are eligible to be
selected as host, and the same agent can host one episode and be a guest in
another.
_Avoid_: Moderator

**Guest**:
An agent participating in an episode without that episode's host role.
_Avoid_: Panelist, participant
