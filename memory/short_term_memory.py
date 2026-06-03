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
ArynoxTech AI Agent AI Agent - Short Term Memory
=======================================
Manages recent conversation history for immediate context.
Stores messages in-memory with a configurable limit.
Provides context window for model prompts.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import MEMORY_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """
    A single message in the conversation.

    Attributes:
        role: 'user', 'assistant', or 'system'
        content: Message text content
        tool_used: Name of tool used (if any)
        tool_result: Result from tool execution (if any)
        timestamp: When the message was created
        metadata: Additional message metadata
    """
    role: str  # 'user', 'assistant', 'system'
    content: str
    tool_used: Optional[str] = None
    tool_result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "tool_used": self.tool_used,
            "tool_result": self.tool_result,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def format_for_prompt(self) -> str:
        """Format message for inclusion in model prompt."""
        prefix = {"user": "User", "assistant": "Assistant", "system": "System"}
        role_prefix = prefix.get(self.role, self.role)
        text = f"{role_prefix}: {self.content}"

        if self.tool_used:
            text += f"\n[Used tool: {self.tool_used}]"

        if self.tool_result:
            text += f"\n[Result: {self.tool_result[:200]}]"

        return text


class ShortTermMemory:
    """
    Manages short-term conversation memory with a configurable
    maximum number of messages. Automatically forgets oldest messages
    when limit is exceeded.
    """

    def __init__(self, max_messages: Optional[int] = None) -> None:
        """
        Initialize short-term memory.

        Args:
            max_messages: Maximum messages to retain (default from config)
        """
        self.max_messages: int = max_messages or MEMORY_CONFIG["short_term_max_messages"]
        self._messages: deque = deque(maxlen=self.max_messages)
        self._session_id: str = self._generate_session_id()
        logger.debug(
            f"ShortTermMemory initialized (max: {self.max_messages} messages)"
        )

    def _generate_session_id(self) -> str:
        """Generate a unique session identifier."""
        import uuid
        return str(uuid.uuid4())

    def add_message(
        self,
        role: str,
        content: str,
        tool_used: Optional[str] = None,
        tool_result: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Add a message to short-term memory.

        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            tool_used: Name of tool used
            tool_result: Result from tool execution
            metadata: Additional metadata

        Returns:
            The created Message object
        """
        message = Message(
            role=role,
            content=content,
            tool_used=tool_used,
            tool_result=tool_result,
            metadata=metadata or {},
        )
        self._messages.append(message)
        logger.debug(
            f"Added {role} message ({len(content)} chars, "
            f"queue: {len(self._messages)}/{self.max_messages})"
        )
        return message

    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """
        Get recent messages.

        Args:
            limit: Number of recent messages to return

        Returns:
            List of Message objects (most recent last)
        """
        messages = list(self._messages)
        if limit:
            messages = messages[-limit:]
        return messages

    def get_recent_context(self, limit: int = 10) -> str:
        """
        Get formatted recent context for model prompts.

        Args:
            limit: Number of recent messages to include

        Returns:
            Formatted conversation context string
        """
        messages = self.get_messages(limit)
        context_parts = []

        for msg in messages:
            context_parts.append(msg.format_for_prompt())

        return "\n\n".join(context_parts)

    def get_context_for_prompt(self, max_chars: int = 3000) -> str:
        """
        Get context string trimmed to fit within token limits.

        Args:
            max_chars: Maximum characters for context

        Returns:
            Truncated context string
        """
        context = self.get_recent_context()
        if len(context) > max_chars:
            # Trim from the beginning (older messages)
            context = context[-max_chars:]
            # Try to break at a natural point
            first_newline = context.find("\n\n")
            if first_newline > 0:
                # If the trimmed version starts mid-conversation, add an indicator
                context = "...[earlier messages trimmed]...\n\n" + context
        return context

    def get_session_id(self) -> str:
        """Get the current session identifier."""
        return self._session_id

    def set_session_id(self, session_id: str) -> None:
        """Set a specific session ID (for restoring sessions)."""
        self._session_id = session_id
        logger.debug(f"Session ID set: {session_id}")

    def clear(self) -> None:
        """Clear all messages from short-term memory."""
        self._messages.clear()
        logger.debug("Short-term memory cleared")

    def to_list(self) -> List[Dict[str, Any]]:
        """Export all messages as dictionaries."""
        return [msg.to_dict() for msg in self._messages]

    def from_list(self, messages: List[Dict[str, Any]]) -> None:
        """
        Import messages from a list of dictionaries.

        Args:
            messages: List of message dictionaries
        """
        self.clear()
        for msg_data in messages:
            msg = Message(
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                tool_used=msg_data.get("tool_used"),
                tool_result=msg_data.get("tool_result"),
                timestamp=datetime.fromisoformat(msg_data["timestamp"])
                    if "timestamp" in msg_data else datetime.now(),
                metadata=msg_data.get("metadata", {}),
            )
            self._messages.append(msg)
        logger.debug(f"Loaded {len(messages)} messages into short-term memory")

    @property
    def message_count(self) -> int:
        """Get current number of messages in memory."""
        return len(self._messages)

    @property
    def is_empty(self) -> bool:
        """Check if memory is empty."""
        return len(self._messages) == 0