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
ArynoxTech AI Agent - Database Tool
===================================
Production-grade multi-engine database tool supporting SQLite, PostgreSQL, and MySQL.
Provides querying, schema management, data import/export, backup, migration,
and memory persistence for the AI agent.
"""

import asyncio
import csv
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from tools.base_tool import BaseTool, ToolResult
from config.settings import BASE_DIR, DIRS, MEMORY_CONFIG

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500


class DatabaseTool(BaseTool):
    name: str = "database_tool"
    description: str = (
        "Multi-engine database tool for SQL queries, schema management, "
        "data import/export, backup, migrations, and memory persistence."
    )
    version: str = "2.0.0"

    DESTRUCTIVE_KEYWORDS = frozenset({"DROP", "TRUNCATE", "ALTER", "DELETE"})
    SUPPORTED_EXPORT_FORMATS = frozenset({".csv", ".xlsx", ".xls", ".json", ".parquet"})
    SUPPORTED_IMPORT_FORMATS = frozenset({".csv", ".xlsx", ".xls", ".json"})

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._conn: Any = None
        self._conn_config: Dict[str, Any] = {}
        db_path = MEMORY_CONFIG.get(
            "long_term_db_path", BASE_DIR / "memory" / "agent_memory.db"
        )
        if isinstance(db_path, str):
            db_path = Path(db_path)
        self._default_db_path: Path = db_path
        self._internal_schema_initialized: bool = False

    # ── Connection Management (Sync, called under lock) ────────────────────

    def _get_connection_sync(self) -> Any:
        if self._conn is None:
            self._connect_sync()
        return self._conn

    def _connect_sync(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config is not None:
            self._conn_config.update(config)

        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            db_path = self._conn_config.get("database", str(self._default_db_path))
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._conn = conn
            self._init_internal_schema_sync()

        elif engine == "postgresql":
            try:
                import psycopg2
                import psycopg2.extras
            except ImportError:
                raise ImportError(
                    "psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary"
                )
            conn = psycopg2.connect(
                host=self._conn_config.get("host", "localhost"),
                port=self._conn_config.get("port", 5432),
                dbname=self._conn_config.get("database", "postgres"),
                user=self._conn_config.get("user", "postgres"),
                password=self._conn_config.get("password", ""),
                connect_timeout=10,
            )
            conn.autocommit = False
            self._conn = conn
            self._init_internal_schema_sync()

        elif engine == "mysql":
            try:
                import pymysql
                from pymysql.cursors import DictCursor
            except ImportError:
                raise ImportError(
                    "pymysql is required for MySQL. Install with: pip install pymysql"
                )
            conn = pymysql.connect(
                host=self._conn_config.get("host", "localhost"),
                port=self._conn_config.get("port", 3306),
                database=self._conn_config.get("database", "mysql"),
                user=self._conn_config.get("user", "root"),
                password=self._conn_config.get("password", ""),
                cursorclass=DictCursor,
                connect_timeout=10,
                charset="utf8mb4",
            )
            self._conn = conn
            self._init_internal_schema_sync()

        else:
            raise ValueError(f"Unsupported database engine: {engine}")

        self._internal_schema_initialized = True
        self.logger.info(
            "Connected to %s database (db: %s)",
            engine,
            self._conn_config.get("database", str(self._default_db_path)),
        )

    def _init_internal_schema_sync(self) -> None:
        engine = self._conn_config.get("engine", "sqlite")

        memories_ddl = self._get_memories_ddl(engine)
        conversations_ddl = self._get_conversations_ddl(engine)
        preferences_ddl = self._get_preferences_ddl(engine)
        migrations_ddl = self._get_migrations_ddl(engine)

        if engine == "sqlite":
            self._conn.executescript(
                memories_ddl
                + "\n"
                + conversations_ddl
                + "\n"
                + preferences_ddl
                + "\n"
                + migrations_ddl
            )
            self._conn.commit()
        else:
            cursor = self._conn.cursor()
            cursor.execute(memories_ddl)
            cursor.execute(conversations_ddl)
            cursor.execute(preferences_ddl)
            cursor.execute(migrations_ddl)
            self._conn.commit()

    @staticmethod
    def _get_memories_ddl(engine: str) -> str:
        if engine == "sqlite":
            return """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT
                );
            """
        elif engine == "postgresql":
            return """
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT
                );
            """
        else:
            return """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """

    @staticmethod
    def _get_conversations_ddl(engine: str) -> str:
        if engine == "sqlite":
            return """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT
                );
            """
        elif engine == "postgresql":
            return """
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT
                );
            """
        else:
            return """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """

    @staticmethod
    def _get_preferences_ddl(engine: str) -> str:
        if engine == "sqlite":
            return """
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """
        elif engine == "postgresql":
            return """
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """
        else:
            return """
                CREATE TABLE IF NOT EXISTS preferences (
                    key VARCHAR(255) PRIMARY KEY,
                    value TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """

    @staticmethod
    def _get_migrations_ddl(engine: str) -> str:
        if engine == "sqlite":
            return """
                CREATE TABLE IF NOT EXISTS _migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    executed_at TEXT DEFAULT (datetime('now'))
                );
            """
        elif engine == "postgresql":
            return """
                CREATE TABLE IF NOT EXISTS _migrations (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
        else:
            return """
                CREATE TABLE IF NOT EXISTS _migrations (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(255) UNIQUE,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """

    def _close_connection_sync(self) -> None:
        if self._conn is None:
            return
        try:
            engine = self._conn_config.get("engine", "sqlite")
            if engine == "sqlite":
                self._conn.close()
            else:
                self._conn.close()
        except Exception:
            logger.warning("Error closing database connection", exc_info=True)
        finally:
            self._conn = None
            self._internal_schema_initialized = False
            self.logger.info("Database connection closed")

    # ── Async Helper ───────────────────────────────────────────────────────

    async def _run_sync(self, fn, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_event_loop()

        def _wrapper():
            with self._lock:
                return fn(*args, **kwargs)

        return await loop.run_in_executor(None, _wrapper)

    # ── Safety Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _is_destructive(sql: str) -> bool:
        cleaned = sql.strip().upper()
        for kw in DatabaseTool.DESTRUCTIVE_KEYWORDS:
            if cleaned.startswith(kw):
                return True
        return False

    @staticmethod
    def _is_select(sql: str) -> bool:
        cleaned = sql.strip().upper()
        return cleaned.startswith("SELECT") or cleaned.startswith("PRAGMA") or cleaned.startswith("EXPLAIN")

    # ── Main Execute Dispatcher ────────────────────────────────────────────

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = kwargs.get("action", "")

        try:
            if action == "connect":
                return await self._connect(kwargs, start_time)
            elif action == "disconnect":
                return await self._disconnect(start_time)
            elif action == "query":
                return await self._query(kwargs, start_time)
            elif action == "execute_sql":
                return await self._execute_sql(kwargs, start_time)
            elif action == "list_tables":
                return await self._list_tables(start_time)
            elif action == "describe_table":
                return await self._describe_table(kwargs, start_time)
            elif action == "create_table":
                return await self._create_table(kwargs, start_time)
            elif action == "import_data":
                return await self._import_data(kwargs, start_time)
            elif action == "export_data":
                return await self._export_data(kwargs, start_time)
            elif action == "backup_database":
                return await self._backup_database(kwargs, start_time)
            elif action == "run_migration":
                return await self._run_migration(kwargs, start_time)
            elif action == "store_memory":
                return await self._store_memory(kwargs, start_time)
            elif action == "get_history":
                return await self._get_history(kwargs, start_time)
            elif action == "search":
                return await self._search_memories(kwargs, start_time)
            elif action == "store_preference":
                return await self._store_preference(kwargs, start_time)
            elif action == "get_preference":
                return await self._get_preference(kwargs, start_time)
            elif action == "get_stats":
                return await self._get_stats(start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except ImportError as e:
            self.logger.error("Missing dependency: %s", e)
            return ToolResult.error_result(
                f"Missing dependency: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except ValueError as e:
            self.logger.warning("Validation error: %s", e)
            return ToolResult.failure(
                str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.exception("Database tool error: %s", e)
            return ToolResult.error_result(
                f"Database operation failed: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── 10. Connect ────────────────────────────────────────────────────────

    async def _connect(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        config = {
            "engine": kwargs.get("engine", "sqlite"),
            "host": kwargs.get("host", "localhost"),
            "port": kwargs.get("port"),
            "database": kwargs.get("database", str(self._default_db_path)),
            "user": kwargs.get("user", ""),
            "password": kwargs.get("password", ""),
        }
        # Remove None port so defaults apply
        if config["port"] is None:
            config.pop("port")

        try:
            result = await self._run_sync(self._test_connection_sync, config)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Connected to {config['engine']} database",
                data={"engine": config["engine"], "status": result},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Connection failed: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _test_connection_sync(self, config: Dict[str, Any]) -> str:
        self._close_connection_sync()
        self._connect_sync(config)
        engine = self._conn_config.get("engine", "sqlite")
        if engine == "sqlite":
            cursor = self._conn.execute("SELECT 1")
            cursor.fetchone()
        else:
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return f"{engine} connected"

    # ── 11. Disconnect ─────────────────────────────────────────────────────

    async def _disconnect(self, start_time: float) -> ToolResult:
        await self._run_sync(self._close_connection_sync)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            "Database connection closed",
            execution_time_ms=elapsed,
        )

    # ── 1. Query ───────────────────────────────────────────────────────────

    async def _query(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        sql = kwargs.get("sql", "")
        params = kwargs.get("params", None)
        allow_destructive = kwargs.get("allow_destructive", False)

        if not sql:
            return ToolResult.failure(
                "No SQL query provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not allow_destructive and self._is_destructive(sql):
            return ToolResult.failure(
                "Destructive queries require allow_destructive=True",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        params = params or []
        result = await self._run_sync(self._query_sync, sql, params, allow_destructive)
        elapsed = (time.time() - start_time) * 1000

        return ToolResult.success(
            f"Query returned {result['row_count']} row(s)",
            data=result,
            execution_time_ms=elapsed,
        )

    def _query_sync(
        self, sql: str, params: List[Any], allow_destructive: bool
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            cursor = conn.execute(sql, params)
            if self._is_select(sql):
                rows = cursor.fetchall()
                columns = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )
                return {
                    "columns": columns,
                    "rows": [dict(r) for r in rows],
                    "row_count": len(rows),
                }
            else:
                conn.commit()
                return {"affected_rows": cursor.rowcount, "row_count": 0}
        else:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                dict_rows = []
                for r in rows:
                    if isinstance(r, dict):
                        dict_rows.append(r)
                    else:
                        dict_rows.append(dict(zip(columns, r)))
                conn.commit()
                return {
                    "columns": columns,
                    "rows": dict_rows,
                    "row_count": len(dict_rows),
                }
            else:
                conn.commit()
                return {"affected_rows": cursor.rowcount, "row_count": 0}

    # ── 2. Execute ─────────────────────────────────────────────────────────

    async def _execute_sql(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        sql = kwargs.get("sql", "")
        statements = kwargs.get("statements", None)
        params = kwargs.get("params", None)
        allow_destructive = kwargs.get("allow_destructive", False)

        if not sql and not statements:
            return ToolResult.failure(
                "No SQL or statements provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        params = params or []

        if statements:
            result = await self._run_sync(
                self._execute_batch_sync, statements, allow_destructive
            )
        else:
            if not allow_destructive and self._is_destructive(sql):
                return ToolResult.failure(
                    "Destructive execution requires allow_destructive=True",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            result = await self._run_sync(
                self._execute_single_sync, sql, params, allow_destructive
            )

        elapsed = (time.time() - start_time) * 1000
        row_count = result.get("affected_rows", 0)
        return ToolResult.success(
            f"Executed successfully, affected {row_count} row(s)",
            data=result,
            execution_time_ms=elapsed,
        )

    def _execute_single_sync(
        self, sql: str, params: List[Any], allow_destructive: bool
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            cursor = conn.execute(sql, params)
            conn.commit()
            return {"affected_rows": cursor.rowcount}
        else:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return {"affected_rows": cursor.rowcount}

    def _execute_batch_sync(
        self, statements: List[str], allow_destructive: bool
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if not allow_destructive:
            for stmt in statements:
                if self._is_destructive(stmt):
                    raise ValueError(
                        "Destructive statements in batch require allow_destructive=True"
                    )

        total_affected = 0
        try:
            for stmt in statements:
                if engine == "sqlite":
                    cursor = conn.execute(stmt)
                else:
                    cursor = conn.cursor()
                    cursor.execute(stmt)
                total_affected += cursor.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return {"affected_rows": total_affected, "statements_count": len(statements)}

    # ── 3. List Tables ─────────────────────────────────────────────────────

    async def _list_tables(self, start_time: float) -> ToolResult:
        result = await self._run_sync(self._list_tables_sync)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Found {len(result)} table(s)",
            data={"tables": result},
            execution_time_ms=elapsed,
        )

    def _list_tables_sync(self) -> List[Dict[str, Any]]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            table_names = [r["name"] for r in cursor.fetchall()]
        elif engine == "postgresql":
            cursor = conn.cursor()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            )
            table_names = [r[0] for r in cursor.fetchall()]
        else:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            table_names = [list(r.values())[0] for r in cursor.fetchall()]

        tables = []
        for name in table_names:
            tables.append(self._get_table_info_sync(name))

        return tables

    def _get_table_info_sync(self, table_name: str) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            cursor = conn.execute(f"SELECT COUNT(*) AS cnt FROM [{table_name}]")
            row_count = cursor.fetchone()["cnt"]
            schema_cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
            columns = [dict(r) for r in schema_cursor.fetchall()]
        elif engine == "postgresql":
            c = conn.cursor()
            c.execute(f'SELECT COUNT(*) AS cnt FROM "{table_name}"')
            row_count = c.fetchone()[0]
            c.execute(
                "SELECT column_name, data_type, is_nullable, "
                "column_default, ordinal_position "
                "FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table_name,),
            )
            columns = [
                {
                    "cid": r[4],
                    "name": r[0],
                    "type": r[1],
                    "notnull": 0 if r[2] == "YES" else 1,
                    "dflt_value": r[3],
                    "pk": 0,
                }
                for r in c.fetchall()
            ]
        else:
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
            row_count = list(c.fetchone().values())[0]
            c.execute(f"DESCRIBE `{table_name}`")
            columns = []
            for r in c.fetchall():
                columns.append(
                    {
                        "cid": r.get("Field"),
                        "name": r.get("Field"),
                        "type": r.get("Type"),
                        "notnull": 0 if r.get("Null") == "YES" else 1,
                        "dflt_value": r.get("Default"),
                        "pk": 1 if r.get("Key") == "PRI" else 0,
                    }
                )

        return {
            "name": table_name,
            "row_count": row_count,
            "columns": columns,
        }

    # ── 4. Describe Table ──────────────────────────────────────────────────

    async def _describe_table(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        table_name = kwargs.get("table_name", "")
        if not table_name:
            return ToolResult.failure(
                "No table_name provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        result = await self._run_sync(self._describe_table_sync, table_name)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Schema for table '{table_name}'",
            data=result,
            execution_time_ms=elapsed,
        )

    def _describe_table_sync(self, table_name: str) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        info = {"name": table_name, "columns": [], "indexes": [], "foreign_keys": []}

        if engine == "sqlite":
            cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
            for r in cursor.fetchall():
                info["columns"].append({
                    "name": r["name"],
                    "type": r["type"],
                    "nullable": not r["notnull"],
                    "default": r["dflt_value"],
                    "primary_key": bool(r["pk"]),
                })
            idx_cursor = conn.execute(f"PRAGMA index_list([{table_name}])")
            for idx in idx_cursor.fetchall():
                idx_detail = conn.execute(
                    f"PRAGMA index_info([{idx['name']}])"
                ).fetchall()
                info["indexes"].append({
                    "name": idx["name"],
                    "unique": bool(idx["unique"]),
                    "columns": [c["name"] for c in idx_detail],
                })
            fk_cursor = conn.execute(f"PRAGMA foreign_key_list([{table_name}])")
            for fk in fk_cursor.fetchall():
                info["foreign_keys"].append({
                    "from": fk["from"],
                    "to": fk["to"],
                    "table": fk["table"],
                })

        elif engine == "postgresql":
            c = conn.cursor()
            c.execute(
                "SELECT column_name, data_type, is_nullable, "
                "column_default, character_maximum_length "
                "FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table_name,),
            )
            for r in c.fetchall():
                info["columns"].append({
                    "name": r[0],
                    "type": f"{r[1]}({r[4]})" if r[4] else r[1],
                    "nullable": r[2] == "YES",
                    "default": r[3],
                    "primary_key": False,
                })
            c.execute(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename = %s",
                (table_name,),
            )
            for r in c.fetchall():
                info["indexes"].append({"name": r[0], "definition": r[1]})
        else:
            c = conn.cursor()
            c.execute(f"DESCRIBE `{table_name}`")
            for r in c.fetchall():
                info["columns"].append({
                    "name": r.get("Field"),
                    "type": r.get("Type"),
                    "nullable": r.get("Null") == "YES",
                    "default": r.get("Default"),
                    "primary_key": r.get("Key") == "PRI",
                })
            c.execute(f"SHOW INDEX FROM `{table_name}`")
            for r in c.fetchall():
                info["indexes"].append(dict(r))

        return info

    # ── 5. Create Table ────────────────────────────────────────────────────

    async def _create_table(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        table_name = kwargs.get("table_name", "")
        schema = kwargs.get("schema", {})
        if_not_exists = kwargs.get("if_not_exists", True)
        auto_increment_col = kwargs.get("auto_increment", None)

        if not table_name:
            return ToolResult.failure(
                "No table_name provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        if not schema:
            return ToolResult.failure(
                "No schema provided (dict of column: type_string)",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        ddl = await self._run_sync(
            self._generate_create_table_sync,
            table_name,
            schema,
            if_not_exists,
            auto_increment_col,
        )
        result = await self._run_sync(
            self._execute_single_sync, ddl, [], True
        )
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Table '{table_name}' created",
            data={"ddl": ddl, "affected_rows": result.get("affected_rows", 0)},
            execution_time_ms=elapsed,
        )

    def _generate_create_table_sync(
        self,
        table_name: str,
        schema: Dict[str, str],
        if_not_exists: bool,
        auto_increment_col: Optional[str],
    ) -> str:
        engine = self._conn_config.get("engine", "sqlite")
        columns = []
        pk_cols = []
        fk_refs = []
        has_autoinc = False

        for col, type_str in schema.items():
            parts = type_str.strip().split()
            base_type = parts[0].upper()
            col_def = f"[{col}]"

            if base_type == "INTEGER":
                if engine == "sqlite":
                    col_def += " INTEGER"
                elif engine == "postgresql":
                    col_def += " INTEGER"
                else:
                    col_def += " INT"
            elif base_type == "TEXT":
                col_def += " TEXT"
            elif base_type == "REAL":
                col_def += " REAL"
            elif base_type == "BOOLEAN":
                if engine == "sqlite":
                    col_def += " INTEGER"
                elif engine == "postgresql":
                    col_def += " BOOLEAN"
                else:
                    col_def += " TINYINT(1)"
            elif base_type == "DATE":
                col_def += " DATE"
            elif base_type == "TIMESTAMP":
                col_def += " TIMESTAMP"
            elif base_type == "BLOB":
                col_def += " BLOB"
            else:
                col_def += f" {base_type}"

            modifiers = parts[1:] if len(parts) > 1 else []
            for mod in modifiers:
                upper_mod = mod.upper()
                if upper_mod == "PRIMARY" and "KEY" in [m.upper() for m in modifiers]:
                    pk_cols.append(col)
                elif upper_mod == "NOT" and "NULL" in [m.upper() for m in modifiers]:
                    col_def += " NOT NULL"
                elif upper_mod == "UNIQUE":
                    col_def += " UNIQUE"
                elif upper_mod.startswith("DEFAULT"):
                    # value follows as separate token or attached
                    pass

            # Parse default from schema type string
            for i, p in enumerate(parts):
                if p.upper() == "DEFAULT" and i + 1 < len(parts):
                    val = parts[i + 1]
                    if val.upper() == "CURRENT_TIMESTAMP":
                        col_def += " DEFAULT CURRENT_TIMESTAMP"
                    else:
                        col_def += f" DEFAULT {val}"

            # Parse foreign key
            for i, p in enumerate(parts):
                if p.upper() == "REFERENCES" and i + 2 < len(parts):
                    fk_refs.append((col, parts[i + 1], parts[i + 2]))
                    col_def += f" REFERENCES [{parts[i + 1]}]({parts[i + 2]})"

            # Auto-increment support
            if auto_increment_col and col == auto_increment_col:
                has_autoinc = True
                if engine == "sqlite":
                    col_def = col_def.replace("INTEGER", "INTEGER PRIMARY KEY AUTOINCREMENT")
                elif engine == "postgresql":
                    col_def = f"[{col}] SERIAL PRIMARY KEY"
                else:
                    col_def += " AUTO_INCREMENT"

            columns.append(col_def)

        if not has_autoinc and pk_cols:
            pk_str = ", ".join(f"[{c}]" for c in pk_cols)
            columns.append(f"PRIMARY KEY ({pk_str})")

        ife = " IF NOT EXISTS" if if_not_exists else ""
        engine_clause = ""
        if engine == "mysql":
            engine_clause = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

        ddl = f"CREATE TABLE{ife} [{table_name}] (\n  " + ",\n  ".join(columns) + f"\n){engine_clause};"
        return ddl

    # ── 6. Import Data ─────────────────────────────────────────────────────

    async def _import_data(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        table_name = kwargs.get("table_name", "")
        mode = kwargs.get("mode", "append")
        schema = kwargs.get("schema", None)
        pandas_kwargs = kwargs.get("pandas_kwargs", {})

        if not file_path:
            return ToolResult.failure(
                "No file_path provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        if not table_name:
            return ToolResult.failure(
                "No table_name provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult.failure(
                f"File not found: {file_path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_IMPORT_FORMATS:
            return ToolResult.failure(
                f"Unsupported import format: {ext}. Supported: {', '.join(self.SUPPORTED_IMPORT_FORMATS)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            result = await self._run_sync(
                self._import_data_sync,
                str(path),
                table_name,
                mode,
                ext,
                schema,
                pandas_kwargs,
            )
        except ImportError as e:
            return ToolResult.error_result(
                f"Import failed: missing dependency - {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Import complete: {result['inserted']} inserted, "
            f"{result['skipped']} skipped, {result['errors']} errors",
            data=result,
            execution_time_ms=elapsed,
        )

    def _import_data_sync(
        self,
        file_path: str,
        table_name: str,
        mode: str,
        ext: str,
        schema: Optional[Dict[str, str]],
        pandas_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for data import. Install with: pip install pandas openpyxl"
            )

        if ext == ".csv":
            df = pd.read_csv(file_path, **pandas_kwargs)
        elif ext in (".xls", ".xlsx"):
            df = pd.read_excel(file_path, **pandas_kwargs)
        elif ext == ".json":
            df = pd.read_json(file_path, **pandas_kwargs)
        else:
            raise ValueError(f"Unsupported extension: {ext}")

        if df.empty:
            return {"inserted": 0, "skipped": 0, "errors": 0, "total_rows": 0}

        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if mode == "replace" or not self._table_exists_sync(conn, engine, table_name):
            actual_schema = schema or self._infer_schema_from_df(df)
            ddl = self._generate_create_table_sync(
                table_name, actual_schema, if_not_exists=True, auto_increment_col=None
            )
            if engine == "sqlite":
                conn.executescript(ddl.replace(";\n", ";") if ";\n" in ddl else ddl)
            else:
                c = conn.cursor()
                c.execute(ddl)
            conn.commit()

        if mode == "replace":
            self._delete_all_rows_sync(conn, engine, table_name)

        stats = self._batch_insert_sync(conn, engine, table_name, df, DEFAULT_CHUNK_SIZE)
        return stats

    def _table_exists_sync(self, conn: Any, engine: str, table_name: str) -> bool:
        if engine == "sqlite":
            c = conn.execute(
                "SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return c.fetchone()["cnt"] > 0
        elif engine == "postgresql":
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s",
                (table_name,),
            )
            return c.fetchone()[0] > 0
        else:
            c = conn.cursor()
            c.execute(f"SHOW TABLES LIKE '{table_name}'")
            return c.fetchone() is not None

    def _delete_all_rows_sync(self, conn: Any, engine: str, table_name: str) -> None:
        if engine == "sqlite":
            conn.execute(f"DELETE FROM [{table_name}]")
        elif engine == "postgresql":
            c = conn.cursor()
            c.execute(f'DELETE FROM "{table_name}"')
        else:
            c = conn.cursor()
            c.execute(f"DELETE FROM `{table_name}`")
        conn.commit()

    @staticmethod
    def _infer_schema_from_df(df: "pd.DataFrame") -> Dict[str, str]:
        import numpy as np

        type_map = {
            np.dtype("int64"): "INTEGER",
            np.dtype("int32"): "INTEGER",
            np.dtype("float64"): "REAL",
            np.dtype("float32"): "REAL",
            np.dtype("bool"): "BOOLEAN",
            np.dtype("datetime64[ns]"): "TIMESTAMP",
            np.dtype("object"): "TEXT",
        }
        schema = {}
        for col in df.columns:
            dt = df[col].dtype
            mapped = "TEXT"
            for np_type, sql_type in type_map.items():
                if dt == np_type or (hasattr(dt, "kind") and dt.kind == np_type.kind):
                    mapped = sql_type
                    break
            if "int" in str(dt) and "64" in str(dt):
                mapped = "INTEGER"
            schema[str(col)] = mapped
        return schema

    def _batch_insert_sync(
        self, conn: Any, engine: str, table_name: str, df: "pd.DataFrame", chunk_size: int
    ) -> Dict[str, Any]:
        inserted = 0
        skipped = 0
        errors = 0
        columns = list(df.columns)
        placeholders = self._placeholders(engine, len(columns))
        col_list = self._col_list(engine, columns)
        sql = f"INSERT INTO {col_list[0]} ({col_list[1]}) VALUES ({placeholders})"

        for start in range(0, len(df), chunk_size):
            chunk = df.iloc[start : start + chunk_size]
            chunk_data = chunk.values.tolist()

            try:
                if engine == "sqlite":
                    conn.executemany(sql, [tuple(None if pd.isna(v) else v for v in row) for row in chunk_data])
                else:
                    c = conn.cursor()
                    for row in chunk_data:
                        try:
                            c.execute(sql, tuple(None if pd.isna(v) else v for v in row))
                            inserted += 1
                        except Exception:
                            errors += 1
                    if engine != "sqlite":
                        conn.commit()
                        continue
                if engine == "sqlite":
                    conn.commit()
                inserted += len(chunk)
            except Exception as e:
                conn.rollback()
                self.logger.warning(
                    "Batch insert failed at row %d: %s. Trying row-by-row.", start, e
                )
                for row in chunk_data:
                    try:
                        if engine == "sqlite":
                            conn.execute(sql, tuple(None if pd.isna(v) else v for v in row))
                        else:
                            c = conn.cursor()
                            c.execute(sql, tuple(None if pd.isna(v) else v for v in row))
                        conn.commit()
                        inserted += 1
                    except Exception:
                        conn.rollback()
                        errors += 1

        return {
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "total_rows": len(df),
        }

    @staticmethod
    def _placeholders(engine: str, count: int) -> str:
        if engine == "postgresql":
            return ", ".join(f"${i+1}" for i in range(count))
        return ", ".join("?" for _ in range(count))

    @staticmethod
    def _col_list(engine: str, columns: List[str]) -> Tuple[str, str]:
        if engine == "postgresql":
            quoted = ", ".join(f'"{c}"' for c in columns)
            return ("", quoted)
        elif engine == "mysql":
            quoted = ", ".join(f"`{c}`" for c in columns)
            return ("", quoted)
        else:
            quoted = ", ".join(f"[{c}]" for c in columns)
            return ("", quoted)

    # ── 7. Export Data ─────────────────────────────────────────────────────

    async def _export_data(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        table_name = kwargs.get("table_name", "")
        query = kwargs.get("query", None)
        file_path = kwargs.get("file_path", "")
        export_format = kwargs.get("format", None)
        csv_delimiter = kwargs.get("csv_delimiter", ",")

        if not table_name and not query:
            return ToolResult.failure(
                "Provide table_name or query to export",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        path = Path(file_path)
        ext = export_format or path.suffix.lower()
        if ext.startswith("."):
            ext = ext
        else:
            ext = f".{ext}" if ext else None

        if ext is None and table_name:
            ext = ".csv"
        elif ext is None and query:
            ext = ".json"

        if ext not in self.SUPPORTED_EXPORT_FORMATS:
            return ToolResult.failure(
                f"Unsupported export format: {ext}. Supported: {', '.join(self.SUPPORTED_EXPORT_FORMATS)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not file_path:
            file_path = str(Path.cwd() / f"{table_name or 'export'}{ext}")
            path = Path(file_path)

        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            result = await self._run_sync(
                self._export_data_sync,
                table_name,
                query,
                str(path),
                ext,
                csv_delimiter,
            )
        except ImportError as e:
            return ToolResult.error_result(
                f"Export failed: missing dependency - {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Exported {result['row_count']} rows to {path.name} ({result['file_size']} bytes)",
            data=result,
            execution_time_ms=elapsed,
        )

    def _export_data_sync(
        self,
        table_name: str,
        query: Optional[str],
        file_path: str,
        ext: str,
        csv_delimiter: str,
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        sql = query or self._select_all_sql(engine, table_name)

        if engine == "sqlite":
            cursor = conn.execute(sql)
            rows = [dict(r) for r in cursor.fetchall()]
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
        else:
            c = conn.cursor()
            c.execute(sql)
            columns = [desc[0] for desc in c.description] if c.description else []
            raw = c.fetchall()
            rows = []
            for r in raw:
                if isinstance(r, dict):
                    rows.append(r)
                else:
                    rows.append(dict(zip(columns, r)))

        path = Path(file_path)

        if ext == ".csv":
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=columns, delimiter=csv_delimiter)
                writer.writeheader()
                writer.writerows(rows)
        elif ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
            except ImportError:
                raise ImportError(
                    "pandas and openpyxl are required for Excel export. "
                    "Install with: pip install pandas openpyxl"
                )
            df = pd.DataFrame(rows)
            df.to_excel(path, index=False, engine="openpyxl")
        elif ext == ".json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, default=str)
        elif ext == ".parquet":
            try:
                import pandas as pd
            except ImportError:
                raise ImportError(
                    "pandas and pyarrow are required for Parquet export. "
                    "Install with: pip install pandas pyarrow"
                )
            df = pd.DataFrame(rows)
            df.to_parquet(path, index=False)

        file_size = path.stat().st_size
        return {
            "columns": columns,
            "row_count": len(rows),
            "file_path": file_path,
            "file_size": file_size,
            "format": ext,
        }

    @staticmethod
    def _select_all_sql(engine: str, table_name: str) -> str:
        if engine == "postgresql":
            return f'SELECT * FROM "{table_name}"'
        elif engine == "mysql":
            return f"SELECT * FROM `{table_name}`"
        return f"SELECT * FROM [{table_name}]"

    # ── 8. Backup Database ─────────────────────────────────────────────────

    async def _backup_database(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        backup_path = kwargs.get("backup_path", None)
        result = await self._run_sync(self._backup_database_sync, backup_path)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Database backed up to {result['backup_path']} ({result['file_size']} bytes)",
            data=result,
            execution_time_ms=elapsed,
        )

    def _backup_database_sync(self, backup_path: Optional[str]) -> Dict[str, Any]:
        engine = self._conn_config.get("engine", "sqlite")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if engine == "sqlite":
            db_path = self._conn_config.get("database", str(self._default_db_path))
            src = Path(db_path)
            if not src.exists():
                raise FileNotFoundError(f"Database file not found: {src}")

            dst = Path(backup_path) if backup_path else src.parent / f"{src.stem}_backup_{timestamp}{src.suffix}"
            dst = dst.resolve()

            conn = self._get_connection_sync()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            backup_conn = sqlite3.connect(str(dst), timeout=30)
            conn.backup(backup_conn, pages=0)
            backup_conn.close()
            file_size = dst.stat().st_size

        elif engine == "postgresql":
            dst = Path(backup_path) if backup_path else Path(f"pg_backup_{timestamp}.sql")
            db_name = self._conn_config.get("database", "postgres")
            dst.parent.mkdir(parents=True, exist_ok=True)
            import subprocess
            env = os.environ.copy()
            env["PGPASSWORD"] = self._conn_config.get("password", "")
            cmd = [
                "pg_dump",
                "-h", self._conn_config.get("host", "localhost"),
                "-p", str(self._conn_config.get("port", 5432)),
                "-U", self._conn_config.get("user", "postgres"),
                "-f", str(dst),
                db_name,
            ]
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            file_size = dst.stat().st_size

        elif engine == "mysql":
            dst = Path(backup_path) if backup_path else Path(f"mysql_backup_{timestamp}.sql")
            db_name = self._conn_config.get("database", "mysql")
            dst.parent.mkdir(parents=True, exist_ok=True)
            import subprocess
            cmd = [
                "mysqldump",
                "-h", self._conn_config.get("host", "localhost"),
                "-P", str(self._conn_config.get("port", 3306)),
                "-u", self._conn_config.get("user", "root"),
                f"-p{self._conn_config.get('password', '')}",
                db_name,
            ]
            with open(str(dst), "w") as f:
                subprocess.run(cmd, stdout=f, check=True)
            file_size = dst.stat().st_size
        else:
            raise ValueError(f"Backup not supported for engine: {engine}")

        return {
            "backup_path": str(dst),
            "file_size": file_size,
            "engine": engine,
        }

    # ── 9. Run Migration ───────────────────────────────────────────────────

    async def _run_migration(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        statements = kwargs.get("statements", [])
        migration_name = kwargs.get(
            "migration_name", f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        if not statements:
            return ToolResult.failure(
                "No migration statements provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        result = await self._run_sync(
            self._run_migration_sync, migration_name, statements
        )
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Migration '{migration_name}': {result['executed']} / {result['total']} statements executed",
            data=result,
            execution_time_ms=elapsed,
        )

    def _run_migration_sync(
        self, migration_name: str, statements: List[str]
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        cursor = conn.execute("SELECT COUNT(*) AS cnt FROM _migrations WHERE name = ?", (migration_name,))
        count = cursor.fetchone() if engine == "sqlite" else cursor.fetchone()[0]
        if isinstance(count, dict):
            count = count.get("cnt", 0)
        if count and count > 0:
            return {
                "migration_name": migration_name,
                "executed": 0,
                "skipped": len(statements),
                "total": len(statements),
                "message": "Migration already executed, skipped",
            }

        executed = 0
        try:
            for stmt in statements:
                if engine == "sqlite":
                    conn.execute(stmt)
                else:
                    c = conn.cursor()
                    c.execute(stmt)
                executed += 1

            if engine == "sqlite":
                conn.execute(
                    "INSERT INTO _migrations (name) VALUES (?)", (migration_name,)
                )
            else:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO _migrations (name, executed_at) VALUES (%s, CURRENT_TIMESTAMP)",
                    (migration_name,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return {
            "migration_name": migration_name,
            "executed": executed,
            "skipped": 0,
            "total": len(statements),
        }

    # ── Memory Operations ──────────────────────────────────────────────────

    async def _store_memory(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        content = kwargs.get("content", "")
        memory_type = kwargs.get("memory_type", "conversation")
        session_id = kwargs.get("session_id", "")

        if not content:
            return ToolResult.failure(
                "No content provided to store",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            result = await self._run_sync(
                self._store_memory_sync,
                content,
                memory_type,
                session_id,
            )
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Memory stored (ID: {result['memory_id']})",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to store memory: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _store_memory_sync(
        self, content: str, memory_type: str, session_id: str
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")
        timestamp = datetime.now().isoformat()
        role = memory_type  # map memory_type -> role

        if engine == "sqlite":
            cursor = conn.execute(
                "INSERT INTO memories (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
                (role, content, timestamp, session_id),
            )
            conn.commit()
            memory_id = cursor.lastrowid
        else:
            c = conn.cursor()
            c.execute(
                "INSERT INTO memories (role, content, timestamp, session_id) VALUES (%s, %s, %s, %s)",
                (role, content, timestamp, session_id),
            )
            conn.commit()
            memory_id = c.lastrowid

        return {"memory_id": memory_id, "role": role, "timestamp": timestamp}

    async def _get_history(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        limit = kwargs.get("limit", 20)
        session_id = kwargs.get("session_id", None)

        try:
            result = await self._run_sync(
                self._get_history_sync, limit, session_id
            )
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Retrieved {result['total']} conversation entries",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get history: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _get_history_sync(
        self, limit: int, session_id: Optional[str]
    ) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if session_id:
            sql = "SELECT * FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?"
            params = (session_id, limit)
        else:
            sql = "SELECT * FROM conversations ORDER BY id DESC LIMIT ?"
            params = (limit,)

        if engine == "sqlite":
            cursor = conn.execute(sql, params)
            rows = [dict(r) for r in cursor.fetchall()]
        else:
            c = conn.cursor()
            c.execute(
                sql.replace("?", "%s") if engine != "sqlite" else sql,
                params,
            )
            rows = [dict(r) for r in c.fetchall()] if c.description else []

        return {"conversations": rows, "total": len(rows)}

    async def _search_memories(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 10)

        if not query:
            return ToolResult.failure(
                "No search query provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            result = await self._run_sync(self._search_memories_sync, query, limit)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Found {result['total']} results for '{query}'",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Search failed: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _search_memories_sync(self, query: str, limit: int) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        search_sql = (
            "SELECT * FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?"
        )
        params = (f"%{query}%", limit)

        if engine == "sqlite":
            cursor = conn.execute(search_sql, params)
            rows = [dict(r) for r in cursor.fetchall()]
        else:
            c = conn.cursor()
            c.execute(
                search_sql.replace("?", "%s") if engine != "sqlite" else search_sql,
                params,
            )
            rows = [dict(r) for r in c.fetchall()] if c.description else []

        return {"query": query, "results": rows, "total": len(rows)}

    # ── Preference Operations ──────────────────────────────────────────────

    async def _store_preference(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")

        if not key:
            return ToolResult.failure(
                "No preference key provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            await self._run_sync(self._store_preference_sync, key, str(value))
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Preference '{key}' saved",
                data={"key": key, "value": value},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to store preference: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _store_preference_sync(self, key: str, value: str) -> None:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            conn.execute(
                "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()
        elif engine == "postgresql":
            c = conn.cursor()
            c.execute(
                "INSERT INTO preferences (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )
            conn.commit()
        else:
            c = conn.cursor()
            c.execute(
                "REPLACE INTO preferences (key, value) VALUES (%s, %s)",
                (key, value),
            )
            conn.commit()

    async def _get_preference(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        key = kwargs.get("key", "")

        if not key:
            return ToolResult.failure(
                "No preference key provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            value = await self._run_sync(self._get_preference_sync, key)
            elapsed = (time.time() - start_time) * 1000
            if value is not None:
                return ToolResult.success(
                    f"Preference '{key}': {value}",
                    data={"key": key, "value": value},
                    execution_time_ms=elapsed,
                )
            else:
                return ToolResult.success(
                    f"Preference '{key}' not found",
                    data={"key": key, "value": None},
                    execution_time_ms=elapsed,
                )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get preference: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _get_preference_sync(self, key: str) -> Optional[str]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")

        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else None
        else:
            c = conn.cursor()
            c.execute(
                "SELECT value FROM preferences WHERE key = %s", (key,)
            )
            row = c.fetchone()
            return row.get("value") if row else None

    # ── Stats ──────────────────────────────────────────────────────────────

    async def _get_stats(self, start_time: float) -> ToolResult:
        try:
            result = await self._run_sync(self._get_stats_sync)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Database stats: {result.get('total_memories', 0)} memories, "
                f"{result.get('total_preferences', 0)} preferences",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get stats: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _get_stats_sync(self) -> Dict[str, Any]:
        conn = self._get_connection_sync()
        engine = self._conn_config.get("engine", "sqlite")
        stats: Dict[str, Any] = {}

        def _count(table: str) -> int:
            if engine == "sqlite":
                c = conn.execute(f"SELECT COUNT(*) AS cnt FROM [{table}]")
                return c.fetchone()["cnt"]
            elif engine == "postgresql":
                c = conn.cursor()
                c.execute(f'SELECT COUNT(*) AS cnt FROM "{table}"')
                return c.fetchone()[0]
            else:
                c = conn.cursor()
                c.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
                return list(c.fetchone().values())[0]

        try:
            stats["total_memories"] = _count("memories")
        except Exception:
            stats["total_memories"] = 0

        try:
            stats["total_preferences"] = _count("preferences")
        except Exception:
            stats["total_preferences"] = 0

        try:
            stats["total_conversations"] = _count("conversations")
        except Exception:
            stats["total_conversations"] = 0

        # Database file size (SQLite only)
        if self._conn_config.get("engine", "sqlite") == "sqlite":
            db_path = self._conn_config.get("database", str(self._default_db_path))
            db_file = Path(db_path)
            stats["db_size_bytes"] = db_file.stat().st_size if db_file.exists() else 0

        stats["engine"] = self._conn_config.get("engine", "sqlite")
        return stats
