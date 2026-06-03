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

"""Tests for the ExcelTool."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio

from tools.excel_tool import ExcelTool
from tools.base_tool import ToolResultStatus


class TestExcelTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = ExcelTool()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name

    async def asyncTearDown(self):
        self._tmpdir.cleanup()

    async def _make_xlsx_path(self, name="test.xlsx"):
        return os.path.join(self.tmpdir, name)

    async def test_create_excel(self):
        path = await self._make_xlsx_path("create_test.xlsx")
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        result = await self.tool.execute(action="create", file_path=path, data=data)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(os.path.isfile(path))
        self.assertIn("sheets", result.data)

    async def test_create_and_read_excel(self):
        path = await self._make_xlsx_path("crud_test.xlsx")
        data = [{"col_a": 1, "col_b": "x"}, {"col_a": 2, "col_b": "y"}]
        create_result = await self.tool.execute(action="create", file_path=path, data=data)
        self.assertEqual(create_result.status, ToolResultStatus.SUCCESS)

        read_result = await self.tool.execute(action="read", file_path=path)
        self.assertEqual(read_result.status, ToolResultStatus.SUCCESS)
        self.assertIn("Sheet1", read_result.data)
        sheet = read_result.data["Sheet1"]
        self.assertEqual(sheet["rows"], 2)

    async def test_modify_cell(self):
        path = await self._make_xlsx_path("modify_test.xlsx")
        data = [{"val": 10}]
        await self.tool.execute(action="create", file_path=path, data=data)

        modify_result = await self.tool.execute(
            action="modify", file_path=path, mod_type="update_cells",
            updates={"B2": "modified"}
        )
        self.assertEqual(modify_result.status, ToolResultStatus.SUCCESS)

    async def test_gst_calc_output_structure(self):
        result = await self.tool.execute(
            action="gst_calc",
            line_items=[
                {"description": "Product A", "amount": 1180, "gst_rate": 18},
                {"description": "Product B", "amount": 590, "gst_rate": 18},
            ],
            business_name="TestCorp",
            gstin="27AAACH1234A1Z8",
            invoice_no="INV-001",
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        data = result.data
        self.assertIn("summary", data)
        self.assertIn("grand_total", data["summary"])
        self.assertIn("total_gst", data["summary"])
        self.assertIn("total_taxable_value", data["summary"])
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 2)

    async def test_gst_calc_with_amount(self):
        result = await self.tool.execute(
            action="gst_calc", amount=1180, default_gst_rate=18
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertAlmostEqual(result.data["summary"]["total_taxable_value"], 1000.0, places=0)

    async def test_gst_calc_with_output_path(self):
        path = await self._make_xlsx_path("gst_output.xlsx")
        result = await self.tool.execute(
            action="gst_calc",
            line_items=[{"description": "Item", "amount": 1180, "gst_rate": 18}],
            output_path=path,
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(os.path.isfile(path))

    async def test_analyze_dataframe(self):
        data = [{"a": 10, "b": 20}, {"a": 15, "b": 25}, {"a": 20, "b": 30}]
        result = await self.tool.execute(action="analyze", data=data)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("overview", result.data)
        self.assertEqual(result.data["overview"]["rows"], 3)
        self.assertEqual(result.data["overview"]["columns"], 2)

    async def test_read_nonexistent_file_fails(self):
        path = await self._make_xlsx_path("nonexistent.xlsx")
        result = await self.tool.execute(action="read", file_path=path)
        self.assertEqual(result.status, ToolResultStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()
