"""Keeps each technician's conversation between requests.

Conversations live in memory: fine for a single server and a demo. Running several servers
would need a shared store such as Redis or the database."""

import threading
from collections import OrderedDict

from maia.agent.agent import Conversation

MAX_CONVERSATIONS = 200


class ConversationStore:
    def __init__(self, max_conversations: int = MAX_CONVERSATIONS) -> None:
        self.max_conversations = max_conversations
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def create(self) -> Conversation:
        conversation = Conversation()
        with self._guard:
            self._conversations[conversation.session_id] = conversation
            self._locks[conversation.session_id] = threading.Lock()
            while len(self._conversations) > self.max_conversations:
                oldest, _ = self._conversations.popitem(last=False)  # forget the least recent
                self._locks.pop(oldest, None)
        return conversation

    def get(self, session_id: str) -> Conversation | None:
        with self._guard:
            conversation = self._conversations.get(session_id)
            if conversation is not None:
                self._conversations.move_to_end(session_id)  # mark as recently used
            return conversation

    def lock_for(self, session_id: str) -> threading.Lock:
        """One request at a time per conversation, so two quick messages cannot interleave."""
        with self._guard:
            return self._locks[session_id]
