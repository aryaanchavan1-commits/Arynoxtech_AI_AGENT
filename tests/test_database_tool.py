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

"""Tests for the DatabaseTool using in-memory SQLite."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio

from tools.database_tool import DatabaseTool
from tools.base_tool import ToolResultStatus


class TestDatabaseTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = DatabaseTool()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "test_memory.db")

    async def asyncTearDown(self):
        await self.tool.execute(action="disconnect")
        self._tmpdir.cleanup()

    async def test_connect_sqlite(self):
        result = await self.tool.execute(
            action="connect", engine="sqlite", database=self.db_path
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

    async def test_create_table(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        schema = {"id": "INTEGER", "name": "TEXT", "age": "INTEGER"}
        result = await self.tool.execute(
            action="create_table", table_name="users", schema=schema
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

    async def test_create_table_no_schema_fails(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        result = await self.tool.execute(action="create_table", table_name="bad")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_execute_insert_and_query(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        schema = {"id": "INTEGER", "name": "TEXT", "age": "INTEGER"}
        await self.tool.execute(action="create_table", table_name="users", schema=schema)

        insert_result = await self.tool.execute(
            action="execute_sql",
            sql="INSERT INTO [users] (id, name, age) VALUES (1, 'Alice', 30)",
            allow_destructive=True,
        )
        self.assertEqual(insert_result.status, ToolResultStatus.SUCCESS)

        query_result = await self.tool.execute(
            action="query", sql="SELECT * FROM [users]"
        )
        self.assertEqual(query_result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(query_result.data["row_count"], 1)
        self.assertEqual(query_result.data["rows"][0]["name"], "Alice")

    async def test_execute_insert_batch(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        await self.tool.execute(
            action="create_table",
            table_name="users",
            schema={"id": "INTEGER", "name": "TEXT"},
        )
        result = await self.tool.execute(
            action="execute_sql",
            statements=[
                "INSERT INTO [users] (id, name) VALUES (1, 'Alice')",
                "INSERT INTO [users] (id, name) VALUES (2, 'Bob')",
                "INSERT INTO [users] (id, name) VALUES (3, 'Charlie')",
            ],
            allow_destructive=True,
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

    async def test_list_tables(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        schema = {"id": "INTEGER"}
        await self.tool.execute(action="create_table", table_name="test_table", schema=schema)
        result = await self.tool.execute(action="list_tables")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        table_names = [t["name"] for t in result.data["tables"]]
        self.assertIn("test_table", table_names)

    async def test_describe_table(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        schema = {"id": "INTEGER PRIMARY KEY", "email": "TEXT NOT NULL", "score": "REAL"}
        await self.tool.execute(action="create_table", table_name="scores", schema=schema)
        result = await self.tool.execute(action="describe_table", table_name="scores")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        col_names = [c["name"] for c in result.data["columns"]]
        self.assertIn("id", col_names)
        self.assertIn("email", col_names)
        self.assertIn("score", col_names)

    async def test_describe_table_no_name_fails(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        result = await self.tool.execute(action="describe_table")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_destructive_query_blocked(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        result = await self.tool.execute(
            action="query", sql="DROP TABLE IF EXISTS [sqlite_master]"
        )
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_get_stats(self):
        await self.tool.execute(action="connect", engine="sqlite", database=self.db_path)
        result = await self.tool.execute(action="get_stats")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

    async def test_unknown_action_fails(self):
        result = await self.tool.execute(action="nonexistent_action")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()
