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
ArynoxTech AI Agent AI Agent - Database Manager
======================================
Manages all SQLite database operations including memory storage,
conversation history, task tracking, and user preferences.
Supports FTS5 for semantic search on stored memories.
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import MEMORY_CONFIG
from database.schema import ALL_SCHEMAS, ALL_FTS_SCHEMAS, ALL_TRIGGERS
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Singleton database manager for all SQLite operations.
    Thread-safe with connection pooling for concurrent access.
    """

    _instance: Optional["DatabaseManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        """Singleton pattern for database manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the database connection and schema."""
        if self._initialized:
            return

        self.db_path: str = MEMORY_CONFIG["long_term_db_path"]
        self._local = threading.local()
        self._init_database()
        self._initialized = True
        logger.info(f"Database initialized at: {self.db_path}")

    @property
    def _connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA busy_timeout=5000;")
            self._local.conn.execute("PRAGMA foreign_keys=ON;")
        return self._local.conn

    def _init_database(self) -> None:
        """Create database directory and initialize schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create main tables (use executescript for multi-statement schemas)
        conn = self._connection
        for schema in ALL_SCHEMAS:
            try:
                conn.executescript(schema)
            except sqlite3.OperationalError as e:
                logger.warning(f"Schema warning: {e}")

        # Create FTS5 tables (if supported)
        try:
            for schema in ALL_FTS_SCHEMAS:
                if schema.strip():
                    try:
                        conn.executescript(schema)
                    except sqlite3.OperationalError as e:
                        logger.warning(f"FTS5 schema warning (may be unsupported): {e}")
        except Exception as e:
            logger.warning(f"FTS5 initialization skipped: {e}")

        # Create FTS triggers (each as separate executescript)
        for trigger in ALL_TRIGGERS:
            try:
                conn.executescript(trigger)
            except sqlite3.OperationalError as e:
                logger.warning(f"Trigger creation warning: {e}")

        conn.commit()
        logger.debug("Database schema initialized")

    def store_memory(
        self,
        content: str,
        memory_type: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Store a memory entry in the database.

        Args:
            content: Memory content text
            memory_type: Type of memory (conversation, task, preference, etc.)
            metadata: Optional metadata dictionary

        Returns:
            ID of the inserted memory
        """
        if metadata is None:
            metadata = {}

        conn = self._connection
        cursor = conn.execute(
            "INSERT INTO memories (memory_type, content, metadata) VALUES (?, ?, ?)",
            (memory_type, content, json.dumps(metadata, default=str)),
        )
        conn.commit()
        memory_id = cursor.lastrowid
        logger.debug(f"Stored memory (ID: {memory_id}, type: {memory_type})")
        return memory_id

    def get_memories(
        self,
        limit: int = 20,
        offset: int = 0,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memory entries.

        Args:
            limit: Maximum number of results
            offset: Pagination offset
            memory_type: Filter by memory type (None = all types)

        Returns:
            List of memory dictionaries
        """
        conn = self._connection

        if memory_type:
            cursor = conn.execute(
                "SELECT * FROM memories WHERE memory_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (memory_type, limit, offset),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "memory_type": row["memory_type"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "created_at": row["created_at"],
            })
        return results

    def search_memories(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search memories using FTS5 full-text search.
        Falls back to LIKE search if FTS5 is unavailable.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching memory dictionaries
        """
        conn = self._connection

        # Try FTS5 search first
        try:
            cursor = conn.execute(
                """
                SELECT m.id, m.memory_type, m.content, m.metadata, m.created_at,
                       rank as relevance
                FROM memories_fts f
                JOIN memories m ON f.rowid = m.id
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "memory_type": row["memory_type"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "relevance": row["relevance"],
                })
            return results
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            logger.debug("FTS5 unavailable, using LIKE search")
            cursor = conn.execute(
                """
                SELECT * FROM memories
                WHERE content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "memory_type": row["memory_type"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                })
            return results

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        conn = self._connection
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"Deleted memory (ID: {memory_id})")
        return deleted

    def store_preference(self, key: str, value: str) -> None:
        """Store a user preference (upsert)."""
        conn = self._connection
        conn.execute(
            """
            INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        conn.commit()
        logger.debug(f"Stored preference: {key} = {value}")

    def get_preference(self, key: str) -> Optional[str]:
        """Get a stored user preference value."""
        conn = self._connection
        cursor = conn.execute(
            "SELECT value FROM preferences WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    def store_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        tools_used: Optional[List[str]] = None,
    ) -> int:
        """Store a conversation message."""
        conn = self._connection
        cursor = conn.execute(
            "INSERT INTO conversations (session_id, role, content, tools_used) VALUES (?, ?, ?, ?)",
            (session_id, role, content, json.dumps(tools_used or [])),
        )
        conn.commit()
        return cursor.lastrowid

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        conn = self._connection
        cursor = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY created_at LIMIT ?",
            (session_id, limit),
        )
        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "tools_used": json.loads(row["tools_used"]),
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]

    def store_task(self, description: str) -> int:
        """Create a new task entry."""
        conn = self._connection
        cursor = conn.execute(
            "INSERT INTO tasks (description) VALUES (?)",
            (description,),
        )
        conn.commit()
        return cursor.lastrowid

    def update_task(
        self,
        task_id: int,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        steps_completed: Optional[List[str]] = None,
        execution_time_ms: float = 0.0,
    ) -> None:
        """Update task status and result."""
        conn = self._connection
        completed_at = datetime.now().isoformat() if status in ("completed", "failed") else None
        
        conn.execute(
            """
            UPDATE tasks SET
                status = ?,
                result = COALESCE(?, result),
                error = COALESCE(?, error),
                steps_completed = COALESCE(?, steps_completed),
                completed_at = COALESCE(?, completed_at),
                execution_time_ms = ?
            WHERE id = ?
            """,
            (status, result, error,
             json.dumps(steps_completed) if steps_completed else None,
             completed_at, execution_time_ms, task_id),
        )
        conn.commit()

    def get_tasks(
        self,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get task history."""
        conn = self._connection
        if status_filter:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status_filter, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [
            {
                "id": row["id"],
                "description": row["description"],
                "status": row["status"],
                "steps_planned": json.loads(row["steps_planned"]),
                "steps_completed": json.loads(row["steps_completed"]),
                "tools_used": json.loads(row["tools_used"]),
                "result": row["result"],
                "error": row["error"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "execution_time_ms": row["execution_time_ms"],
            }
            for row in cursor.fetchall()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._connection
        stats = {}

        cursor = conn.execute("SELECT COUNT(*) as count FROM memories")
        stats["total_memories"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM conversations")
        stats["total_conversations"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM preferences")
        stats["total_preferences"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM tasks")
        stats["total_tasks"] = cursor.fetchone()["count"]

        cursor = conn.execute(
            "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
        )
        stats["task_statuses"] = {
            row["status"]: row["count"] for row in cursor.fetchall()
        }

        # Database file size
        db_file = Path(self.db_path)
        stats["db_size_bytes"] = db_file.stat().st_size if db_file.exists() else 0

        return stats

    def clear_all(self) -> None:
        """Clear all data from the database (for testing/cleanup)."""
        conn = self._connection
        tables = ["memories", "preferences", "conversations", "tasks"]
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        logger.warning("All database tables cleared")

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
            logger.info("Database connection closed")