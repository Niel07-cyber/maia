"""Objects the API routes depend on. Tests replace them through app.dependency_overrides."""

from functools import lru_cache

from maia.agent.agent import MaintenanceAgent, TransactionFactory
from maia.agent.llm import LiteLLMChat
from maia.agent.sessions import ConversationStore
from maia.db.session import transaction
from maia.manual.embeddings import LiteLLMEmbedder
from maia.speech import LiteLLMTranscriber, Transcriber


def get_transaction() -> TransactionFactory:
    return transaction


@lru_cache
def get_agent() -> MaintenanceAgent:
    return MaintenanceAgent(LiteLLMChat(), LiteLLMEmbedder(), transaction)


@lru_cache
def get_conversation_store() -> ConversationStore:
    return ConversationStore()


@lru_cache
def get_transcriber() -> Transcriber:
    return LiteLLMTranscriber()
