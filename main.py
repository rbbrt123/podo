from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

TOPIC = "Why the sky is blue"

PERSONAS = {
    "Mira" : "You are Mira, the curious host of a podcast. You ask clarifying questions and keep the conversation moving.",
    "Dr. Chen": "You are Dr. Chen, a physicist who explains concepts clearly using everyday analogies.",
}

transcript = []

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

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Conversation so far:\n{conversation_so_far}\n\nGive your next line."}
        ]
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    return text.strip()

speakers = list(PERSONAS.keys()) #just gives: ["Mira","Dr. Chen"]

for i in range(6):
    current_speaker = speakers[i % len(speakers)]
    line = generate_turn(current_speaker) #response of the current speaker
    transcript.append({"speaker": current_speaker, "text": line}) #appended to the transcript
    print(f"{current_speaker}: {line}\n")