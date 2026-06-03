# Copyright (c) 2026 Aryan Chavan (ArynoxTech)
# Licensed under the MIT License. See LICENSE file in the project root.

"""
ArynoxTech AI Agent AI Agent - Task Manager
==================================
Manages task execution lifecycle: creation, queuing, execution,
monitoring, and completion. Handles background tasks with
async support and error recovery.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from agent.planner import Plan, PlanStep, Planner, StepStatus
from tools.base_tool import BaseTool, ToolRegistry, ToolResult, ToolResultStatus
from config.settings import TASK_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Status of a managed task."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_CONFIRMATION = "waiting_confirmation"


@dataclass
class Task:
    """
    A managed task with full lifecycle tracking.

    Attributes:
        id: Unique task identifier
        description: Task description
        plan: Execution plan (if multi-step)
        status: Current task status
        created_at: Creation timestamp
        started_at: Execution start timestamp
        completed_at: Completion timestamp
        result: Final result text
        error: Error message if failed
        progress: Progress percentage (0-100)
        current_step: Currently executing step number
        on_status_change: Callback for status updates
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    plan: Optional[Plan] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0
    current_step: int = 0
    on_status_change: Optional[Callable[["Task"], None]] = None

    def update_status(self, new_status: TaskStatus) -> None:
        """Update task status and trigger callback."""
        self.status = new_status
        if new_status == TaskStatus.RUNNING and not self.started_at:
            self.started_at = datetime.now()
        if new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.completed_at = datetime.now()
        if self.on_status_change:
            try:
                self.on_status_change(self)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "description": self.description[:100],
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "total_steps": len(self.plan.steps) if self.plan else 1,
            "result": self.result[:500] if self.result else None,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskManager:
    """
    Manages all task lifecycle operations including creation,
    queuing, concurrent execution, monitoring, and cleanup.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None) -> None:
        """
        Initialize the task manager.

        Args:
            tool_registry: Tool registry for executing steps
        """
        self.tool_registry = tool_registry or ToolRegistry()
        self.planner = Planner()
        self._tasks: Dict[str, Task] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running_tasks: Set[str] = set()
        self._max_concurrent: int = TASK_CONFIG.get("max_concurrent_tasks", 3)
        self._worker_task: Optional[asyncio.Task] = None
        self._on_task_update: Optional[Callable[[Task], None]] = None
        logger.info("TaskManager initialized")

    def set_task_update_callback(self, callback: Callable[[Task], None]) -> None:
        """Set a callback for task status updates."""
        self._on_task_update = callback

    async def create_task(
        self,
        description: str,
        plan: Optional[Plan] = None,
    ) -> Task:
        """
        Create a new task and add to execution queue.

        Args:
            description: Task description
            plan: Optional pre-built plan (auto-planned if None)

        Returns:
            Created Task object
        """
        # Create plan if not provided
        if plan is None:
            plan = await self.planner.create_plan(description)

        task = Task(
            description=description,
            plan=plan,
            on_status_change=self._handle_task_status_change,
        )
        task.update_status(TaskStatus.QUEUED)

        # Save to database
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            db.store_task(description)
        except Exception as e:
            logger.warning(f"Could not save task to database: {e}")

        self._tasks[task.id] = task
        await self._queue.put(task)

        logger.info(f"Task {task.id} created and queued: {description[:80]}")
        return task

    async def execute_task(self, task: Task) -> None:
        """
        Execute a task through its plan steps.

        Args:
            task: The task to execute
        """
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return

        task.update_status(TaskStatus.RUNNING)
        self._running_tasks.add(task.id)

        start_time = time.time()
        step_results = []

        try:
            plan = task.plan
            if not plan or not plan.steps:
                task.result = "No steps in plan"
                task.update_status(TaskStatus.COMPLETED)
                return

            for i, step in enumerate(plan.steps):
                if task.status == TaskStatus.CANCELLED:
                    break

                # Mark step running
                task.current_step = i + 1
                task.progress = int((i / len(plan.steps)) * 100)
                step.status = StepStatus.IN_PROGRESS

                # Ensure the worker has a chance to update UI and keep things responsive
                await asyncio.sleep(0)

                # Find and execute the tool
                tool = self.tool_registry.get_tool(step.tool_name)
                if tool is None:
                    step.status = StepStatus.FAILED
                    step.result = f"Tool '{step.tool_name}' not found"
                    task.error = step.result
                    continue

                # Execute the tool step
                try:
                    logger.info(
                        f"Executing step {i+1}/{len(plan.steps)}: "
                        f"{step.description} ({step.tool_name})"
                    )

                    tool_result = await tool.execute(**step.tool_params)

                    step.result = tool_result.message
                    step.status = (
                        StepStatus.COMPLETED
                        if tool_result.status == ToolResultStatus.SUCCESS
                        else StepStatus.FAILED
                    )

                    step_results.append(tool_result.to_dict())

                    # Check if confirmation is needed
                    if tool_result.requires_confirmation:
                        task.update_status(TaskStatus.WAITING_CONFIRMATION)
                        # Wait for user confirmation (handled by UI layer)
                        logger.info(f"Task {task.id} waiting for confirmation")
                        return

                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.result = str(e)
                    task.error = f"Step {i+1} failed: {e}"
                    logger.error(f"Step {i+1} failed: {e}")

            # Task complete
            execution_time = (time.time() - start_time) * 1000
            task.progress = 100
            completed_steps = sum(
                1 for s in plan.steps if s.status == StepStatus.COMPLETED
            )
            task.result = (
                f"Completed {completed_steps}/{len(plan.steps)} steps "
                f"in {execution_time:.0f}ms"
            )
            task.update_status(TaskStatus.COMPLETED)
            logger.info(f"Task {task.id} completed: {task.result}")

        except Exception as e:
            logger.exception(f"Task {task.id} failed: {e}")
            task.error = str(e)
            task.update_status(TaskStatus.FAILED)

        finally:
            self._running_tasks.discard(task.id)

    async def confirm_task(self, task_id: str) -> None:
        """Resume a task waiting for confirmation."""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.WAITING_CONFIRMATION:
            task.update_status(TaskStatus.RUNNING)
            await self.execute_task(task)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or queued task."""
        task = self._tasks.get(task_id)
        if task and task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.PENDING):
            task.update_status(TaskStatus.CANCELLED)
            logger.info(f"Task {task_id} cancelled")
            return True
        return False

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """Get all managed tasks."""
        return list(self._tasks.values())

    def get_active_tasks(self) -> List[Task]:
        """Get currently active tasks."""
        return [
            t for t in self._tasks.values()
            if t.status in (TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.WAITING_CONFIRMATION)
        ]

    def get_completed_tasks(self, limit: int = 20) -> List[Task]:
        """Get recently completed tasks."""
        completed = [
            t for t in self._tasks.values()
            if t.status == TaskStatus.COMPLETED
        ]
        completed.sort(key=lambda t: t.completed_at or datetime.min, reverse=True)
        return completed[:limit]

    async def _worker(self) -> None:
        """Background worker that processes queued tasks."""
        while True:
            try:
                # Check concurrent task limit
                while len(self._running_tasks) >= self._max_concurrent:
                    await asyncio.sleep(0.5)

                task = await self._queue.get()
                await self.execute_task(task)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task worker error: {e}")
                await asyncio.sleep(1)

    def start_worker(self) -> None:
        """Start the background task worker. Must be called after event loop is running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Task worker started")

    def stop_worker(self) -> None:
        """Stop the background task worker."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            logger.info("Task worker stopped")

    def _handle_task_status_change(self, task: Task) -> None:
        """Internal handler for task status changes."""
        if self._on_task_update:
            try:
                self._on_task_update(task)
            except Exception as e:
                logger.error(f"Task update callback error: {e}")

    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """Remove old completed tasks from memory."""
        now = datetime.now()
        to_remove = []
        for task_id, task in self._tasks.items():
            if task.status == TaskStatus.COMPLETED and task.completed_at:
                age = (now - task.completed_at).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(task_id)
        for task_id in to_remove:
            del self._tasks[task_id]
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")
        return len(to_remove)
