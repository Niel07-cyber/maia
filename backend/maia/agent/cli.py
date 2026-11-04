"""Chat with the agent in the terminal, using the real models.

Usage:
    uv run python -m maia.agent.cli
"""

import logging

from maia.agent.agent import AgentReply, Conversation, MaintenanceAgent
from maia.agent.llm import LiteLLMChat
from maia.db.session import transaction
from maia.manual.embeddings import LiteLLMEmbedder


def show(reply: AgentReply) -> None:
    for event in reply.events:
        status = "ok" if event.ok else "refused"
        print(f"   [{event.name}: {status}]")
    print(f"MAIA: {reply.text}")
    for action in reply.pending:
        print(f"   To confirm: {action.description}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    agent = MaintenanceAgent(LiteLLMChat(), LiteLLMEmbedder(), transaction)
    conversation = Conversation()
    print("MAIA maintenance assistant. Type 'quit' to stop.\n")

    while True:
        text = input("You: ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        reply = agent.send(conversation, text)
        show(reply)
        while reply.pending:
            answer = input("Confirm? [y/n]: ").strip().lower()
            reply = agent.resolve(conversation, approved=answer in {"y", "yes", "o", "oui"})
            show(reply)


if __name__ == "__main__":
    main()
