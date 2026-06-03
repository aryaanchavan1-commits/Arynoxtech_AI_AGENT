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
ArynoxTech AI Agent - Personal Assistant Tool
==============================================
Tool for personal assistant features: reminders, notes, calendar,
timers, alarms, weather lookup, and productivity helpers.
"""

import asyncio
import json
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


@dataclass
class Reminder:
    """A reminder with title, time, and status."""
    id: str
    title: str
    description: str = ""
    due_time: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, completed, dismissed
    priority: str = "normal"  # low, normal, high, urgent
    category: str = "general"


@dataclass
class Note:
    """A personal note."""
    id: str
    title: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    category: str = "general"


@dataclass
class CalendarEvent:
    """A calendar event."""
    id: str
    title: str
    start_time: str
    end_time: str = ""
    description: str = ""
    location: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PersonalAssistantTool(BaseTool):
    """
    Personal assistant tool providing:
    - Reminder management (set, list, complete reminders)
    - Note taking (create, edit, search, organize notes)
    - Timer/stopwatch functionality
    - Basic scheduling and calendar management
    - Productivity helpers (todo lists, habits)
    - Quick information lookup (weather, time, date)
    """

    name: str = "personal_assistant_tool"
    description: str = "Personal assistant features: reminders, notes, timers, to-do lists, calendar events, and productivity tools."
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG.get("personal_assistant", {})
        self._data_dir = Path(self.config.get("data_dir", "data/assistant"))
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory stores
        self._reminders: List[Reminder] = []
        self._notes: List[Note] = []
        self._events: List[CalendarEvent] = []
        self._todos: List[Dict] = []
        self._timers: Dict[str, Dict] = {}
        
        # Load saved data
        self._load_data()
        
        # Start reminder checker thread
        self._reminder_checker_running = True
        self._reminder_thread = threading.Thread(target=self._check_reminders, daemon=True)
        self._reminder_thread.start()

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute personal assistant operation.

        Args:
            action: 'set_reminder', 'list_reminders', 'complete_reminder',
                    'create_note', 'get_note', 'search_notes', 'list_notes',
                    'delete_note', 'set_timer', 'get_time',
                    'add_todo', 'list_todos', 'complete_todo',
                    'add_event', 'list_events', 'today_events',
                    'quick_info', 'weather_lookup'
            Various parameters depending on action

        Returns:
            ToolResult with operation outcome
        """
        start_time = time.time()
        action = kwargs.get("action", "quick_info")

        try:
            if action == "set_reminder":
                return await self._set_reminder(kwargs, start_time)
            elif action == "list_reminders":
                return await self._list_reminders(kwargs, start_time)
            elif action == "complete_reminder":
                return await self._complete_reminder(kwargs, start_time)
            elif action == "delete_reminder":
                return await self._delete_reminder(kwargs, start_time)
            elif action == "create_note":
                return await self._create_note(kwargs, start_time)
            elif action == "get_note":
                return await self._get_note(kwargs, start_time)
            elif action == "search_notes":
                return await self._search_notes(kwargs, start_time)
            elif action == "list_notes":
                return await self._list_notes(kwargs, start_time)
            elif action == "delete_note":
                return await self._delete_note(kwargs, start_time)
            elif action == "set_timer":
                return await self._set_timer(kwargs, start_time)
            elif action == "get_time":
                return await self._get_time(kwargs, start_time)
            elif action == "add_todo":
                return await self._add_todo(kwargs, start_time)
            elif action == "list_todos":
                return await self._list_todos(kwargs, start_time)
            elif action == "complete_todo":
                return await self._complete_todo(kwargs, start_time)
            elif action == "add_event":
                return await self._add_event(kwargs, start_time)
            elif action == "list_events":
                return await self._list_events(kwargs, start_time)
            elif action == "today_events":
                return await self._today_events(kwargs, start_time)
            elif action == "quick_info":
                return await self._quick_info(kwargs, start_time)
            elif action == "weather_lookup":
                return await self._weather_lookup(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.logger.exception(f"Personal assistant tool error: {e}")
            return ToolResult.error_result(
                f"Personal assistant failed: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── Reminders ──────────────────────────────────────────────────────────

    async def _set_reminder(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Create a new reminder."""
        title = kwargs.get("title", "Reminder")
        description = kwargs.get("description", "")
        due_time = kwargs.get("due_time", "")
        priority = kwargs.get("priority", "normal")
        category = kwargs.get("category", "general")
        
        # If no due_time specified, set a relative reminder
        if not due_time:
            minutes = kwargs.get("in_minutes", 0)
            hours = kwargs.get("in_hours", 0)
            if minutes > 0 or hours > 0:
                due_time = (datetime.now() + timedelta(minutes=minutes, hours=hours)).isoformat()
            else:
                # Default: 1 hour from now
                due_time = (datetime.now() + timedelta(hours=1)).isoformat()

        reminder = Reminder(
            id=f"rem_{int(time.time())}_{len(self._reminders)}",
            title=title,
            description=description,
            due_time=due_time,
            priority=priority,
            category=category,
        )

        self._reminders.append(reminder)
        self._save_reminders()

        # Format due time for display
        try:
            dt = datetime.fromisoformat(due_time)
            due_display = dt.strftime("%Y-%m-%d %I:%M %p")
        except:
            due_display = due_time

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"✅ Reminder set: '{title}' for {due_display}",
            data={
                "reminder": asdict(reminder),
                "due_display": due_display,
            },
            execution_time_ms=elapsed,
        )

    async def _list_reminders(self, kwargs: Dict, start_time: float) -> ToolResult:
        """List all reminders, optionally filtered by status."""
        status = kwargs.get("status", "pending")  # pending, completed, all

        if status == "all":
            reminders = self._reminders
        else:
            reminders = [r for r in self._reminders if r.status == status]

        # Sort by due time
        reminders.sort(key=lambda r: r.due_time)

        # Format for display
        display = []
        for r in reminders[:20]:
            try:
                dt = datetime.fromisoformat(r.due_time)
                due_display = dt.strftime("%Y-%m-%d %I:%M %p")
            except:
                due_display = r.due_time
            display.append(asdict(r))
            display[-1]["due_display"] = due_display

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"{len(reminders)} reminder(s) found (showing {len(display)})",
            data={
                "total": len(self._reminders),
                "shown": len(display),
                "reminders": display,
                "filter": status,
            },
            execution_time_ms=elapsed,
        )

    async def _complete_reminder(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Mark a reminder as completed."""
        reminder_id = kwargs.get("id", "")

        for r in self._reminders:
            if r.id == reminder_id or r.id.endswith(f"_{reminder_id}"):
                r.status = "completed"
                self._save_reminders()
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"✅ Reminder '{r.title}' marked as completed",
                    data={"reminder": asdict(r)},
                    execution_time_ms=elapsed,
                )

        return ToolResult.failure(
            f"Reminder '{reminder_id}' not found",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _delete_reminder(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Delete a reminder."""
        reminder_id = kwargs.get("id", "")
        before = len(self._reminders)
        self._reminders = [r for r in self._reminders 
                          if r.id != reminder_id and not r.id.endswith(f"_{reminder_id}")]
        
        if len(self._reminders) < before:
            self._save_reminders()
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                "✅ Reminder deleted",
                data={"remaining": len(self._reminders)},
                execution_time_ms=elapsed,
            )
        return ToolResult.failure(
            f"Reminder '{reminder_id}' not found",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ── Notes ──────────────────────────────────────────────────────────────

    async def _create_note(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Create a new note."""
        title = kwargs.get("title", "Untitled Note")
        content = kwargs.get("content", "")
        tags = kwargs.get("tags", [])
        category = kwargs.get("category", "general")

        note = Note(
            id=f"note_{int(time.time())}_{len(self._notes)}",
            title=title,
            content=content,
            tags=tags,
            category=category,
        )

        self._notes.append(note)
        self._save_notes()

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📝 Note created: '{title}'",
            data={"note": asdict(note)},
            execution_time_ms=elapsed,
        )

    async def _get_note(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get a specific note by ID."""
        note_id = kwargs.get("id", "")
        
        for note in self._notes:
            if note.id == note_id or note.id.endswith(f"_{note_id}"):
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"📝 Note: {note.title}",
                    data={"note": asdict(note)},
                    execution_time_ms=elapsed,
                )

        return ToolResult.failure(
            f"Note '{note_id}' not found",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _search_notes(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Search notes by keyword."""
        query = kwargs.get("query", "").lower()
        if not query:
            return ToolResult.success(
                "No search query provided",
                data={"results": [], "total": 0},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        results = []
        for note in self._notes:
            if (query in note.title.lower() or 
                query in note.content.lower() or 
                any(query in tag.lower() for tag in note.tags)):
                results.append(asdict(note))

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Found {len(results)} note(s) matching '{query}'",
            data={
                "query": query,
                "results": results,
                "total": len(results),
            },
            execution_time_ms=elapsed,
        )

    async def _list_notes(self, kwargs: Dict, start_time: float) -> ToolResult:
        """List all notes."""
        category = kwargs.get("category", "")
        
        if category:
            notes = [n for n in self._notes if n.category == category]
        else:
            notes = self._notes

        notes.sort(key=lambda n: n.updated_at, reverse=True)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📚 {len(notes)} note(s) found",
            data={
                "total": len(self._notes),
                "notes": [asdict(n) for n in notes[:20]],
            },
            execution_time_ms=elapsed,
        )

    async def _delete_note(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Delete a note."""
        note_id = kwargs.get("id", "")
        before = len(self._notes)
        self._notes = [n for n in self._notes 
                      if n.id != note_id and not n.id.endswith(f"_{note_id}")]
        
        if len(self._notes) < before:
            self._save_notes()
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                "✅ Note deleted",
                data={"remaining": len(self._notes)},
                execution_time_ms=elapsed,
            )
        return ToolResult.failure(
            f"Note '{note_id}' not found",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ── Timer ──────────────────────────────────────────────────────────────

    async def _set_timer(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Set a countdown timer."""
        seconds = kwargs.get("seconds", 0)
        minutes = kwargs.get("minutes", 0)
        hours = kwargs.get("hours", 0)
        label = kwargs.get("label", "Timer")

        total_seconds = seconds + (minutes * 60) + (hours * 3600)
        if total_seconds <= 0:
            return ToolResult.failure(
                "Timer duration must be > 0",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        timer_id = f"timer_{int(time.time())}"
        end_time = datetime.now() + timedelta(seconds=total_seconds)

        self._timers[timer_id] = {
            "id": timer_id,
            "label": label,
            "duration_seconds": total_seconds,
            "end_time": end_time.isoformat(),
            "started_at": datetime.now().isoformat(),
            "status": "running",
        }

        # Start a background thread to notify when timer completes
        def _timer_thread(tid, dur, lbl):
            time.sleep(dur)
            if tid in self._timers and self._timers[tid]["status"] == "running":
                self._timers[tid]["status"] = "completed"
                self.logger.info(f"⏰ Timer '{lbl}' completed!")

        thread = threading.Thread(target=_timer_thread, args=(timer_id, total_seconds, label), daemon=True)
        thread.start()

        # Format duration for display
        h, remainder = divmod(total_seconds, 3600)
        m, s = divmod(remainder, 60)
        duration_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s" if m else f"{s}s"

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"⏰ Timer set: '{label}' for {duration_str} (ends at {end_time.strftime('%I:%M:%S %p')})",
            data={
                "timer": self._timers[timer_id],
                "duration_display": duration_str,
            },
            execution_time_ms=elapsed,
        )

    # ── Time & Date ────────────────────────────────────────────────────────

    async def _get_time(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get current time, date, and related info."""
        now = datetime.now()
        
        info = {
            "current_time": now.strftime("%I:%M:%S %p"),
            "current_date": now.strftime("%A, %B %d, %Y"),
            "timezone": "Asia/Calcutta (UTC+5:30)",
            "day_of_week": now.strftime("%A"),
            "day_of_year": now.timetuple().tm_yday,
            "week_number": now.isocalendar()[1],
            "is_weekend": now.weekday() >= 5,
            "iso_format": now.isoformat(),
            "timestamp": int(time.time()),
        }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"🕐 Current time: {info['current_time']}, {info['current_date']}",
            data=info,
            execution_time_ms=elapsed,
        )

    # ── Todo Lists ─────────────────────────────────────────────────────────

    async def _add_todo(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Add a task to a todo list."""
        task = kwargs.get("task", "")
        list_name = kwargs.get("list_name", "default")
        priority = kwargs.get("priority", "normal")

        if not task:
            return ToolResult.failure(
                "No task description provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        todo_item = {
            "id": f"todo_{int(time.time())}_{len(self._todos)}",
            "task": task,
            "list_name": list_name,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        self._todos.append(todo_item)
        self._save_todos()

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"✅ Added to '{list_name}': {task}",
            data={"todo": todo_item},
            execution_time_ms=elapsed,
        )

    async def _list_todos(self, kwargs: Dict, start_time: float) -> ToolResult:
        """List todo tasks."""
        list_name = kwargs.get("list_name", "")
        status = kwargs.get("status", "pending")

        todos = self._todos
        if list_name:
            todos = [t for t in todos if t["list_name"] == list_name]
        if status != "all":
            todos = [t for t in todos if t["status"] == status]

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📋 {len(todos)} todo item(s)",
            data={
                "todos": todos[:30],
                "total": len(todos),
                "list_name": list_name or "all",
                "filter": status,
            },
            execution_time_ms=elapsed,
        )

    async def _complete_todo(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Mark a todo as completed."""
        todo_id = kwargs.get("id", "")
        
        for todo in self._todos:
            if todo["id"] == todo_id or todo["id"].endswith(f"_{todo_id}"):
                todo["status"] = "completed"
                todo["completed_at"] = datetime.now().isoformat()
                self._save_todos()
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"✅ Completed: {todo['task']}",
                    data={"todo": todo},
                    execution_time_ms=elapsed,
                )

        return ToolResult.failure(
            f"Todo '{todo_id}' not found",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ── Calendar Events ───────────────────────────────────────────────────

    async def _add_event(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Add a calendar event."""
        title = kwargs.get("title", "Event")
        start_time_str = kwargs.get("start_time", datetime.now().isoformat())
        end_time_str = kwargs.get("end_time", "")
        description = kwargs.get("description", "")
        location = kwargs.get("location", "")

        if not end_time_str:
            # Default: 1 hour duration
            try:
                start_dt = datetime.fromisoformat(start_time_str)
                end_time_str = (start_dt + timedelta(hours=1)).isoformat()
            except:
                end_time_str = (datetime.now() + timedelta(hours=1)).isoformat()

        event = CalendarEvent(
            id=f"evt_{int(time.time())}_{len(self._events)}",
            title=title,
            start_time=start_time_str,
            end_time=end_time_str,
            description=description,
            location=location,
        )

        self._events.append(event)
        self._save_events()

        # Format for display
        try:
            st = datetime.fromisoformat(start_time_str).strftime("%Y-%m-%d %I:%M %p")
        except:
            st = start_time_str

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📅 Event added: '{title}' on {st}",
            data={"event": asdict(event)},
            execution_time_ms=elapsed,
        )

    async def _list_events(self, kwargs: Dict, start_time: float) -> ToolResult:
        """List calendar events."""
        events = sorted(self._events, key=lambda e: e.start_time)
        
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📅 {len(events)} event(s)",
            data={
                "events": [asdict(e) for e in events[:20]],
                "total": len(events),
            },
            execution_time_ms=elapsed,
        )

    async def _today_events(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get today's events."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_events = [
            asdict(e) for e in self._events
            if e.start_time.startswith(today) or e.end_time.startswith(today)
        ]

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📅 {len(today_events)} event(s) today",
            data={
                "date": today,
                "events": today_events,
                "total": len(today_events),
            },
            execution_time_ms=elapsed,
        )

    # ── Quick Info ─────────────────────────────────────────────────────────

    async def _quick_info(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get a quick summary of current info (time, pending reminders, etc.)."""
        now = datetime.now()
        
        pending = [r for r in self._reminders if r.status == "pending"]
        pending_todos = [t for t in self._todos if t["status"] == "pending"]
        
        # Check for upcoming reminders (next 24 hours)
        upcoming = []
        tomorrow = now + timedelta(hours=24)
        for r in pending:
            try:
                dt = datetime.fromisoformat(r.due_time)
                if now <= dt <= tomorrow:
                    upcoming.append(asdict(r))
            except:
                pass

        info = {
            "current_time": now.strftime("%I:%M:%S %p"),
            "current_date": now.strftime("%A, %B %d, %Y"),
            "pending_reminders": len(pending),
            "pending_todos": len(pending_todos),
            "total_notes": len(self._notes),
            "upcoming_reminders": upcoming[:5],
            "active_timers": len([t for t in self._timers.values() if t["status"] == "running"]),
        }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"📊 Quick summary - {info['current_date']} | "
            f"{info['pending_reminders']} reminders | "
            f"{info['pending_todos']} todos | "
            f"{info['total_notes']} notes",
            data=info,
            execution_time_ms=elapsed,
        )

    # ── Weather ────────────────────────────────────────────────────────────

    async def _weather_lookup(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Provide weather information (simulated / basic)."""
        # Note: Real weather API integration would require an API key
        # This provides a useful simulated response with instructions for real integration
        city = kwargs.get("city", "your area")
        
        weather_info = {
            "city": city,
            "note": "To get real-time weather data, configure a weather API key in settings.",
            "alternatives": [
                "Visit https://weather.com for current conditions",
                "Ask the web search tool to search for weather in your city",
            ],
            "current_date": datetime.now().strftime("%Y-%m-%d"),
        }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"🌤️ Weather info for {city}: Real-time weather requires API setup. "
            f"Try using the web search tool to look up current weather conditions.",
            data=weather_info,
            execution_time_ms=elapsed,
        )

    # ── Background Reminder Checker ────────────────────────────────────────

    def _check_reminders(self) -> None:
        """Background thread to check and log due reminders."""
        while self._reminder_checker_running:
            try:
                now = datetime.now()
                for reminder in self._reminders:
                    if reminder.status == "pending":
                        try:
                            due = datetime.fromisoformat(reminder.due_time)
                            # Alert if within the last minute (to avoid repeated alerts)
                            if (due - now).total_seconds() <= 60 and (due - now).total_seconds() > -10:
                                self.logger.info(
                                    f"⏰ REMINDER: {reminder.title} - {reminder.description}"
                                )
                        except:
                            pass
                time.sleep(30)  # Check every 30 seconds
            except Exception:
                time.sleep(60)

    # ── Data Persistence ──────────────────────────────────────────────────

    def _save_reminders(self) -> None:
        try:
            path = self._data_dir / "reminders.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self._reminders], f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save reminders: {e}")

    def _save_notes(self) -> None:
        try:
            path = self._data_dir / "notes.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump([asdict(n) for n in self._notes], f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save notes: {e}")

    def _save_events(self) -> None:
        try:
            path = self._data_dir / "events.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self._events], f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save events: {e}")

    def _save_todos(self) -> None:
        try:
            path = self._data_dir / "todos.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._todos, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save todos: {e}")

    def _load_data(self) -> None:
        """Load all saved data from disk."""
        try:
            path = self._data_dir / "reminders.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._reminders = [Reminder(**item) for item in data]
        except Exception as e:
            self.logger.warning(f"Failed to load reminders: {e}")

        try:
            path = self._data_dir / "notes.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._notes = [Note(**item) for item in data]
        except Exception as e:
            self.logger.warning(f"Failed to load notes: {e}")

        try:
            path = self._data_dir / "events.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._events = [CalendarEvent(**item) for item in data]
        except Exception as e:
            self.logger.warning(f"Failed to load events: {e}")

        try:
            path = self._data_dir / "todos.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self._todos = json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load todos: {e}")

    def cleanup(self) -> None:
        """Save all data and stop background thread."""
        self._reminder_checker_running = False
        self._save_reminders()
        self._save_notes()
        self._save_events()
        self._save_todos()
        self.logger.info("Personal assistant tool cleaned up")