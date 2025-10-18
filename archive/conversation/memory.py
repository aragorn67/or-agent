# conversation/memory.py
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
from collections import deque

class ConversationMemory:
    """Simple in-memory conversation storage with recent message history"""

    def __init__(self, max_history: int = 3):
        self.conversations: Dict[str, Dict] = {}
        self.max_history = max_history  # Keep last N messages for context

    def create_conversation(self) -> str:
        """Create new conversation and return session ID"""
        session_id = str(uuid.uuid4())
        self.conversations[session_id] = {
            "session_id": session_id,
            "messages": deque(maxlen=self.max_history),  # Keep only recent messages
            "last_solution": None,
            "last_params": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        return session_id

    def add_message(self, session_id: str, role: str, content: str, data: Optional[Dict] = None):
        """Add message to conversation"""
        if session_id not in self.conversations:
            return False

        message = {
            "role": role,  # "user" or "assistant"
            "content": content,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        # Add to deque (automatically maintains max length)
        self.conversations[session_id]["messages"].append(message)
        self.conversations[session_id]["updated_at"] = datetime.now().isoformat()

        # If this is an assistant message with solution data, store it
        if role == "assistant" and data:
            if data.get("success") and data.get("solution"):
                self.conversations[session_id]["last_solution"] = data
                self.conversations[session_id]["last_params"] = data.get("extracted_params")

        return True

    def get_conversation(self, session_id: str) -> Optional[Dict]:
        """Get conversation by session ID"""
        return self.conversations.get(session_id)

    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get conversation context for LLM processing"""
        conversation = self.get_conversation(session_id)
        if not conversation:
            return {}

        # Convert deque to list for JSON serialization
        messages_list = list(conversation["messages"])

        return {
            "messages": messages_list,
            "last_solution": conversation["last_solution"],
            "last_params": conversation["last_params"]
        }

    def get_recent_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get recent messages for context"""
        conversation = self.get_conversation(session_id)
        if not conversation:
            return []

        return list(conversation["messages"])

    def list_conversations(self) -> List[str]:
        """List all conversation session IDs"""
        return list(self.conversations.keys())

    def clear_solution_context(self, session_id: str) -> bool:
        """Clear solution context for new problem while keeping conversation history"""
        if session_id not in self.conversations:
            return False

        self.conversations[session_id]["last_solution"] = None
        self.conversations[session_id]["last_params"] = None
        return True

    def delete_conversation(self, session_id: str) -> bool:
        """Delete a conversation"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            return True
        return False

# Global memory instance (for development)
conversation_memory = ConversationMemory()