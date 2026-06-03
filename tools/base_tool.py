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
ArynoxTech AI Agent AI Agent - Base Tool Class
====================================
Abstract base class for all tools with registration, execution,
and result handling functionality.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type


class ToolResultStatus(Enum):
    """Status of a tool execution result."""
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    PENDING_CONFIRMATION = "pending_confirmation"
    CANCELLED = "cancelled"


@dataclass
class ToolResult:
    """
    Standardized result object returned by all tool executions.

    Attributes:
        status: Execution status
        message: Human-readable result description
        data: Optional structured data returned by the tool
        error: Error message if status is ERROR or FAILURE
        execution_time_ms: Time taken to execute in milliseconds
        requires_confirmation: Whether user confirmation is needed
        timestamp: When the execution occurred
    """
    status: ToolResultStatus
    message: str
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    requires_confirmation: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "requires_confirmation": self.requires_confirmation,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def success(
        cls,
        message: str,
        data: Any = None,
        execution_time_ms: float = 0.0,
    ) -> "ToolResult":
        """Create a success result."""
        return cls(
            status=ToolResultStatus.SUCCESS,
            message=message,
            data=data,
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def failure(
        cls,
        message: str,
        error: Optional[str] = None,
        execution_time_ms: float = 0.0,
    ) -> "ToolResult":
        """Create a failure result."""
        return cls(
            status=ToolResultStatus.FAILURE,
            message=message,
            error=error or message,
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def error_result(
        cls,
        message: str,
        error: str,
        execution_time_ms: float = 0.0,
    ) -> "ToolResult":
        """Create an error result."""
        return cls(
            status=ToolResultStatus.ERROR,
            message=message,
            error=error,
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def needs_confirmation(
        cls,
        message: str,
        data: Any = None,
    ) -> "ToolResult":
        """Create a result requiring user confirmation."""
        return cls(
            status=ToolResultStatus.PENDING_CONFIRMATION,
            message=message,
            data=data,
            requires_confirmation=True,
        )


class BaseTool(ABC):
    """
    Abstract base class that all tools must inherit from.
    Provides registration, validation, and execution framework.
    """

    # Tool metadata - subclasses must override these
    name: str = "base_tool"
    description: str = "Base tool class"
    version: str = "1.0.0"
    requires_confirmation: bool = False  # Default: no confirmation needed

    def __init__(self) -> None:
        """Initialize the tool with logger."""
        from utils.logger import get_logger
        self.logger = get_logger(f"tool.{self.name}")

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool's primary function.
        Must be implemented by all subclasses.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with execution outcome
        """
        pass

    def validate_parameters(self, **kwargs: Any) -> List[str]:
        """
        Validate input parameters before execution.
        Override in subclasses for custom validation.

        Args:
            **kwargs: Parameters to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        return []

    def get_metadata(self) -> Dict[str, Any]:
        """Get tool metadata for registration and display."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "requires_confirmation": self.requires_confirmation,
        }

    def __str__(self) -> str:
        return f"{self.name} ({self.description})"


class ToolRegistry:
    """
    Registry that maintains all available tools and provides
    discovery, lookup, and execution management.
    """

    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, BaseTool] = {}

    def __new__(cls) -> "ToolRegistry":
        """Singleton pattern to ensure single registry instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def __init__(self) -> None:
        """Initialize registry logger."""
        if not hasattr(self, "_initialized"):
            from utils.logger import get_logger
            self.logger = get_logger("tools.registry")
            self._initialized = True

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool instance in the registry.

        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            self.logger.warning(f"Tool '{tool.name}' already registered. Overwriting.")
        self._tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")

    def register_class(self, tool_class: Type[BaseTool]) -> None:
        """Register a tool by class - creates an instance."""
        instance = tool_class()
        self.register(instance)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a registered tool by name.

        Args:
            name: Tool name to look up

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return dict(self._tools)

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """Get list of all tool metadata for UI display."""
        return [
            tool.get_metadata()
            for tool in self._tools.values()
        ]

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
            self.logger.info(f"Unregistered tool: {name}")
            return True
        return False

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self.logger.info("Tool registry cleared")