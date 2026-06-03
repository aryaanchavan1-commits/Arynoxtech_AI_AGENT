# MIT License
#
# Copyright (c) 2026 Aryan Chavan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
ArynoxTech AI Agent AI Agent - Long Term Memory
======================================
Manages persistent memory storage using SQLite database.
Stores conversation summaries, task outcomes, and user preferences
for long-term recall across sessions.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.settings import MEMORY_CONFIG
from database.db_manager import DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)


class LongTermMemory:
    """
    Persistent memory that stores important information across sessions.
    Uses the SQLite database for durable storage.
    Manages memory lifecycle with TTL (time-to-live) for automatic cleanup.
    """

    def __init__(self) -> None:
        """Initialize long-term memory with database connection."""
        self.db = DatabaseManager()
        self.ttl_days: int = MEMORY_CONFIG.get("memory_ttl_days", 30)
        logger.debug(
            f"LongTermMemory initialized (TTL: {self.ttl_days} days)"
        )

    def store(
        self,
        content: str,
        memory_type: str = "long_term",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Store a memory permanently.

        Args:
            content: Memory content
            memory_type: Type classification
            metadata: Additional context

        Returns:
            Memory ID
        """
        return self.db.store_memory(content, memory_type, metadata)

    def retrieve(
        self,
        limit: int = 20,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve stored memories.

        Args:
            limit: Maximum results
            memory_type: Filter by type

        Returns:
            List of memory dictionaries
        """
        return self.db.get_memories(limit=limit, memory_type=memory_type)

    def store_conversation_summary(
        self,
        summary: str,
        session_id: str,
        message_count: int,
    ) -> int:
        """
        Store a summary of a conversation session.

        Args:
            summary: Conversation summary text
            session_id: Session identifier
            message_count: Number of messages in session

        Returns:
            Memory ID
        """
        return self.db.store_memory(
            content=summary,
            memory_type="conversation_summary",
            metadata={
                "session_id": session_id,
                "message_count": message_count,
                "type": "summary",
            },
        )

    def store_task_outcome(
        self,
        task_description: str,
        status: str,
        result: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
    ) -> int:
        """
        Store the outcome of a completed task.

        Args:
            task_description: What the task was
            status: 'completed', 'failed', 'cancelled'
            result: Task result summary
            tools_used: Tools that were used

        Returns:
            Memory ID
        """
        return self.db.store_memory(
            content=f"Task: {task_description}\nStatus: {status}\nResult: {result or 'N/A'}",
            memory_type="task_outcome",
            metadata={
                "task_description": task_description,
                "status": status,
                "result": result,
                "tools_used": tools_used or [],
            },
        )

    def store_user_preference(self, key: str, value: str) -> None:
        """
        Store a user preference permanently.

        Args:
            key: Preference key
            value: Preference value
        """
        self.db.store_preference(key, value)

    def get_user_preference(self, key: str) -> Optional[str]:
        """
        Retrieve a stored user preference.

        Args:
            key: Preference key

        Returns:
            Value or None if not found
        """
        return self.db.get_preference(key)

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search across stored memories.

        Args:
            query: Search text
            limit: Maximum results

        Returns:
            List of matching memories
        """
        return self.db.search_memories(query, limit=limit)

    def cleanup_expired(self) -> int:
        """
        Remove memories older than TTL.

        Returns:
            Number of memories cleaned up
        """
        cutoff = datetime.now() - timedelta(days=self.ttl_days)
        conn = self.db._connection

        cursor = conn.execute(
            "DELETE FROM memories WHERE created_at < ? AND memory_type != 'user_preference'",
            (cutoff.isoformat(),),
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired memories")
        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.

        Returns:
            Dictionary with memory stats
        """
        return self.db.get_stats()

    def get_relevant_context(
        self,
        current_topic: str,
        max_results: int = 5,
    ) -> str:
        """
        Get relevant past context for the current conversation.

        Args:
            current_topic: Current topic or query
            max_results: Maximum past memories to include

        Returns:
            Formatted context string from past memories
        """
        # Search for related memories
        results = self.search(current_topic, limit=max_results)

        if not results:
            return ""

        context_parts = ["[Previous relevant memories:]"]
        for mem in results:
            context_parts.append(f"- {mem['content'][:300]}")

        return "\n".join(context_parts)