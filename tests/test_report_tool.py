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

"""Tests for the ReportTool."""

import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
import pandas as pd

from tools.report_tool import ReportTool
from tools.base_tool import ToolResultStatus


class TestReportTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = ReportTool()
        self._orig_reports_dir = self.tool._reports_dir
        self._tmpdir = tempfile.mkdtemp()
        self.tool._reports_dir = type(self.tool._reports_dir)(self._tmpdir)
        self.tool._reports_dir.mkdir(parents=True, exist_ok=True)

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ── Generate CSV ───────────────────────────────────────────────────

    async def test_generate_csv_outputs_valid_csv_string(self):
        data = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}]
        result = await self.tool.execute(
            action="generate_csv", title="test_csv", data=data
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("path", result.data)
        self.assertIn("format", result.data)
        self.assertEqual(result.data["format"], "csv")

        path = result.data["path"]
        self.assertTrue(os.path.isfile(path))
        df = pd.read_csv(path)
        self.assertEqual(len(df), 3)
        self.assertIn("a", df.columns)

    async def test_generate_csv_with_columns_filter(self):
        data = [{"name": "Alice", "age": 30, "city": "NYC"}]
        result = await self.tool.execute(
            action="generate_csv", title="filtered", data=data, columns=["name", "age"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        path = result.data["path"]
        df = pd.read_csv(path)
        self.assertEqual(list(df.columns), ["name", "age"])

    async def test_generate_csv_no_data_fails(self):
        result = await self.tool.execute(action="generate_csv", title="empty")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    # ── Generate Chart ─────────────────────────────────────────────────

    async def test_generate_chart_creates_image_file(self):
        data = [{"category": "A", "value": 10}, {"category": "B", "value": 20}, {"category": "C", "value": 15}]
        result = await self.tool.execute(
            action="generate_chart", title="test_chart", data=data,
            chart_type="bar", x_column="category", y_columns=["value"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("path", result.data)
        self.assertTrue(os.path.isfile(result.data["path"]))
        ext = os.path.splitext(result.data["path"])[1]
        self.assertIn(ext, [".png", ".svg", ".jpg"])

    async def test_generate_chart_no_data_fails(self):
        result = await self.tool.execute(action="generate_chart", title="chart_fail")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_generate_chart_line_type(self):
        data = [{"x": 1, "y1": 100, "y2": 50}, {"x": 2, "y1": 200, "y2": 75}, {"x": 3, "y1": 150, "y2": 60}]
        result = await self.tool.execute(
            action="generate_chart", title="line_chart", data=data,
            chart_type="line", x_column="x", y_columns=["y1", "y2"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(os.path.isfile(result.data["path"]))

    async def test_generate_chart_pie_type(self):
        data = [{"label": "A", "val": 30}, {"label": "B", "val": 50}, {"label": "C", "val": 20}]
        result = await self.tool.execute(
            action="generate_chart", title="pie_chart", data=data,
            chart_type="pie", x_column="label", y_columns=["val"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

    # ── List Reports ───────────────────────────────────────────────────

    async def test_list_reports_returns_list(self):
        result = await self.tool.execute(action="list_reports")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("reports", result.data)
        self.assertIsInstance(result.data["reports"], list)

    async def test_list_reports_after_generation(self):
        data = {"col": [1, 2]}
        await self.tool.execute(action="generate_csv", title="list_test", data=data)
        result = await self.tool.execute(action="list_reports")
        self.assertGreater(len(result.data["reports"]), 0)

    async def test_list_reports_with_format_filter(self):
        data = {"x": [1]}
        await self.tool.execute(action="generate_csv", title="format_filter_test", data=data)
        result = await self.tool.execute(action="list_reports", format="csv")
        self.assertGreater(len(result.data["reports"]), 0)
        result2 = await self.tool.execute(action="list_reports", format="pdf")
        self.assertEqual(len(result2.data["reports"]), 0)

    # ── Unknown Action ─────────────────────────────────────────────────

    async def test_unknown_action_fails(self):
        result = await self.tool.execute(action="nonexistent_action")
        self.assertEqual(result.status, ToolResultStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()
