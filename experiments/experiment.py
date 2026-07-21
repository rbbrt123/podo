from anthropic import Anthropic

client = Anthropic()

question = "what is the cause of rising sea levels?"

pirate_response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=200,
    system="You are a pirate. Speak and act like one.",
    messages=[
        {"role": "user", "content": question}
    ]
)

scientist_response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=200,
    system="You are a famous scientist. Speak and act like one.",
    messages=[
        {"role": "user", "content": question}
    ]
)

print("Pirate response: ", pirate_response.content[0].text)
print("Scientist response: ", scientist_response.content[0].text)