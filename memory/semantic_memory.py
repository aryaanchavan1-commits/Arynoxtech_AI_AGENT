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
ArynoxTech AI Agent AI Agent - Semantic Memory
=====================================
Enables semantic search across past interactions using SQLite FTS5.
Provides context relevance scoring for intelligent memory retrieval.
"""

from typing import Any, Dict, List, Optional

from database.db_manager import DatabaseManager
from memory.long_term_memory import LongTermMemory
from config.settings import MEMORY_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class SemanticMemory:
    """
    Semantic memory enables searching past interactions using
    full-text search. It bridges short-term and long-term memory
    by finding relevant past experiences for the current context.
    """

    def __init__(self) -> None:
        """Initialize semantic memory with database access."""
        self.db = DatabaseManager()
        self.ltm = LongTermMemory()
        self.enabled: bool = MEMORY_CONFIG.get("semantic_enabled", True)
        logger.debug(f"SemanticMemory initialized (enabled: {self.enabled})")

    def search(
        self,
        query: str,
        limit: int = 10,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across all memories using semantic matching.

        Args:
            query: Natural language search query
            limit: Maximum results
            memory_type: Optional type filter

        Returns:
            List of relevant memory dictionaries with relevance scores
        """
        if not self.enabled:
            logger.debug("Semantic memory is disabled")
            return []

        try:
            results = self.db.search_memories(query, limit=limit)

            # Filter by type if specified
            if memory_type and results:
                results = [r for r in results if r.get("memory_type") == memory_type]

            logger.debug(f"Semantic search '{query[:50]}': {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def find_related_tasks(self, task_description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find tasks similar to the current task description.

        Args:
            task_description: The current task to find related tasks for
            limit: Maximum results

        Returns:
            List of related task memories
        """
        return self.search(
            query=task_description,
            limit=limit,
            memory_type="task_outcome",
        )

    def find_similar_conversations(
        self, topic: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find past conversations on similar topics.

        Args:
            topic: Topic text to match
            limit: Maximum results

        Returns:
            List of related conversation memories
        """
        return self.search(
            query=topic,
            limit=limit,
            memory_type="conversation_summary",
        )

    def get_context_for_prompt(
        self,
        current_query: str,
        max_memories: int = 3,
    ) -> str:
        """
        Build a context string from relevant past memories
        to include in the model prompt.

        Args:
            current_query: Current user query
            max_memories: Maximum memories to include

        Returns:
            Formatted context string
        """
        if not self.enabled:
            return ""

        results = self.search(current_query, limit=max_memories)
        if not results:
            return ""

        context_parts = ["[Relevant past experiences:]"]
        for mem in results:
            # Extract a concise version
            content = mem.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            context_parts.append(f"- {content}")

        return "\n".join(context_parts)

    def store_interaction(
        self,
        user_message: str,
        assistant_response: str,
        tools_used: Optional[List[str]] = None,
    ) -> int:
        """
        Store an interaction for future semantic retrieval.

        Args:
            user_message: User's input
            assistant_response: AI's response
            tools_used: Tools used during this interaction

        Returns:
            Memory ID
        """
        content = f"User: {user_message}\nAssistant: {assistant_response}"
        metadata = {
            "tools_used": tools_used or [],
            "interaction_type": "chat",
        }
        return self.db.store_memory(content, "interaction", metadata)

    def clear(self) -> None:
        """Clear all semantic memory entries."""
        # Semantic memory is read-only search; deletion handled by LTM cleanup
        logger.debug("Semantic memory clear requested (delegated to LTM)")