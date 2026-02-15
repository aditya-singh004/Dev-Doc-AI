"""
Conversation memory service for maintaining chat context.
"""

from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from app.config import settings
from app.utils.logger import logger


class ConversationMemory:
    """Service for managing conversation history per user."""
    
    def __init__(self):
        """Initialize conversation memory storage."""
        self._conversations: Dict[str, List[dict]] = defaultdict(list)
        self._timestamps: Dict[str, datetime] = {}
        self._max_history = settings.MAX_CONVERSATION_HISTORY
        self._session_timeout = timedelta(hours=1)
    
    def add_message(
        self,
        user_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            user_id: Unique user identifier
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        if not settings.ENABLE_MEMORY:
            return
        
        # Check for session timeout
        if self._is_session_expired(user_id):
            self.clear_history(user_id)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._conversations[user_id].append(message)
        self._timestamps[user_id] = datetime.utcnow()
        
        # Trim history if exceeds max
        if len(self._conversations[user_id]) > self._max_history * 2:
            self._conversations[user_id] = self._conversations[user_id][-self._max_history * 2:]
        
        logger.debug(f"Added message for user {user_id}, history size: {len(self._conversations[user_id])}")
    
    def get_history(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get conversation history for a user.
        
        Args:
            user_id: Unique user identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries
        """
        if not settings.ENABLE_MEMORY:
            return []
        
        if self._is_session_expired(user_id):
            self.clear_history(user_id)
            return []
        
        history = self._conversations.get(user_id, [])
        
        if limit:
            return history[-limit:]
        
        return history[-self._max_history * 2:]
    
    def get_formatted_history(self, user_id: str) -> List[dict]:
        """
        Get history formatted for LLM consumption.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            List of messages formatted for LLM API
        """
        history = self.get_history(user_id)
        
        # Return only role and content for LLM
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
        ]
    
    def clear_history(self, user_id: str) -> None:
        """
        Clear conversation history for a user.
        
        Args:
            user_id: Unique user identifier
        """
        if user_id in self._conversations:
            del self._conversations[user_id]
        if user_id in self._timestamps:
            del self._timestamps[user_id]
        
        logger.info(f"Cleared conversation history for user {user_id}")
    
    def _is_session_expired(self, user_id: str) -> bool:
        """Check if user's session has expired."""
        if user_id not in self._timestamps:
            return False
        
        last_activity = self._timestamps[user_id]
        return datetime.utcnow() - last_activity > self._session_timeout
    
    def get_stats(self) -> dict:
        """Get memory service statistics."""
        return {
            "active_conversations": len(self._conversations),
            "memory_enabled": settings.ENABLE_MEMORY,
            "max_history": self._max_history
        }


# Global memory instance
conversation_memory = ConversationMemory()
