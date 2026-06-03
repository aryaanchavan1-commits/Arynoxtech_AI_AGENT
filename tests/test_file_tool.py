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

"""Tests for the FileTool."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio

from tools.file_tool import FileTool
from tools.base_tool import ToolResultStatus


class TestFileTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = FileTool()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name

    async def asyncTearDown(self):
        self._tmpdir.cleanup()

    async def test_create_file(self):
        path = os.path.join(self.tmpdir, "test_create.txt")
        result = await self.tool.execute(action="create", path=path, content="hello world")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(os.path.isfile(path))

    async def test_create_directory(self):
        path = os.path.join(self.tmpdir, "new_dir")
        result = await self.tool.execute(action="create", path=path, is_directory=True)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(os.path.isdir(path))

    async def test_read_file(self):
        path = os.path.join(self.tmpdir, "test_read.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1\nline2\nline3")
        result = await self.tool.execute(action="read", path=path)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("line2", result.data["content"])
        self.assertEqual(result.data["lines"], 3)

    async def test_read_nonexistent_file_fails(self):
        path = os.path.join(self.tmpdir, "nonexistent.txt")
        result = await self.tool.execute(action="read", path=path)
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_rename_file(self):
        src = os.path.join(self.tmpdir, "old_name.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("test")
        result = await self.tool.execute(action="rename", path=src, new_path="new_name.txt")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertFalse(os.path.isfile(src))
        renamed = os.path.join(self.tmpdir, "new_name.txt")
        self.assertTrue(os.path.isfile(renamed))

    async def test_search_files(self):
        for name in ["file_a.txt", "file_b.txt", "data.csv"]:
            with open(os.path.join(self.tmpdir, name), "w", encoding="utf-8") as f:
                f.write("content")
        result = await self.tool.execute(action="search", path=self.tmpdir, pattern="*.txt")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.data["total"], 2)

    async def test_search_nonexistent_directory_fails(self):
        result = await self.tool.execute(action="search", path=r"C:\NONEXISTENT_DIR_XYZ", pattern="*")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_write_file(self):
        path = os.path.join(self.tmpdir, "test_write.txt")
        result = await self.tool.execute(action="write", path=path, content="written content")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "written content")

    async def test_delete_returns_pending_confirmation(self):
        path = os.path.join(self.tmpdir, "to_delete.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("delete me")
        result = await self.tool.execute(action="delete", path=path)
        self.assertEqual(result.status, ToolResultStatus.PENDING_CONFIRMATION)
        self.assertTrue(result.requires_confirmation)

    async def test_move_file(self):
        src = os.path.join(self.tmpdir, "source.txt")
        dst_dir = os.path.join(self.tmpdir, "subdir")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, "dest.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("move me")
        result = await self.tool.execute(action="move", path=src, new_path=dst)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertFalse(os.path.isfile(src))
        self.assertTrue(os.path.isfile(dst))


if __name__ == "__main__":
    unittest.main()
