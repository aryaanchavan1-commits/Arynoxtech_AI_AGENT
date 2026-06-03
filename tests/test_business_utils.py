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

"""Tests for the BusinessUtilsTool."""

import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
import pandas as pd
import numpy as np

from tools.business_utils import BusinessUtilsTool
from tools.base_tool import ToolResultStatus


class TestBusinessUtilsTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = BusinessUtilsTool()

    # ── Data Quality Report ────────────────────────────────────────────

    async def test_data_quality_report_with_dataframe(self):
        df = pd.DataFrame({
            "name": ["Alice", "Bob", "Charlie", "Diana", None],
            "age": [25, 30, 35, 40, 45],
            "salary": [50000, 60000, None, 80000, 90000],
            "city": ["NYC", "LA", "NYC", "LA", "CHI"],
        })
        result = await self.tool.execute(action="data_quality_report", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("quality_score", result.data)
        self.assertIn("overview", result.data)
        self.assertEqual(result.data["overview"]["rows"], 5)
        self.assertEqual(result.data["overview"]["columns"], 4)

    async def test_data_quality_report_with_csv_fixture(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("id,value,category\n1,100,A\n2,200,B\n3,300,A\n4,400,C\n5,500,B\n")
            csv_path = f.name
        try:
            result = await self.tool.execute(action="data_quality_report", file_path=csv_path)
            self.assertEqual(result.status, ToolResultStatus.SUCCESS)
            self.assertEqual(result.data["overview"]["rows"], 5)
            self.assertEqual(result.data["overview"]["columns"], 3)
        finally:
            os.unlink(csv_path)

    async def test_data_quality_report_quality_score(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = await self.tool.execute(action="data_quality_report", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertGreaterEqual(result.data["quality_score"], 0)
        self.assertLessEqual(result.data["quality_score"], 100)

    # ── Schema Validation ──────────────────────────────────────────────

    async def test_schema_validation_valid_data(self):
        df = pd.DataFrame({"age": [25, 30, 35], "name": ["Alice", "Bob", "Charlie"]})
        schema = {"age": "int", "name": "string"}
        result = await self.tool.execute(action="schema_validation", data=df, schema=schema)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(result.data["passed"])

    async def test_schema_validation_invalid_data(self):
        df = pd.DataFrame({"age": ["not_a_number", 30, 35]})
        schema = {"age": "integer"}
        result = await self.tool.execute(action="schema_validation", data=df, schema=schema)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertFalse(result.data["passed"])

    async def test_schema_validation_with_nullable(self):
        df = pd.DataFrame({"email": ["test@example.com", None, "user@domain.org"]})
        schema = {"email": {"type": "email", "nullable": True}}
        result = await self.tool.execute(action="schema_validation", data=df, schema=schema)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(result.data["passed"])

    async def test_schema_validation_with_enum(self):
        df = pd.DataFrame({"status": ["active", "active", "inactive"]})
        schema = {"status": {"type": "string", "enum": ["active", "inactive", "pending"]}}
        result = await self.tool.execute(action="schema_validation", data=df, schema=schema)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(result.data["passed"])

    async def test_schema_validation_without_schema_fails(self):
        df = pd.DataFrame({"a": [1]})
        result = await self.tool.execute(action="schema_validation", data=df)
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    # ── Data Profiling ─────────────────────────────────────────────────

    async def test_data_profiling_returns_stats(self):
        df = pd.DataFrame({
            "numeric_col": [1.0, 2.0, 3.0, 4.0, 5.0],
            "text_col": ["a", "b", "c", "d", "e"],
            "cat_col": ["x", "x", "y", "y", "z"],
        })
        result = await self.tool.execute(action="data_profiling", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("column_statistics", result.data)
        self.assertIn("column_types", result.data)
        stats = result.data["column_statistics"]
        self.assertIn("numeric_col", stats)
        self.assertIn("mean", stats["numeric_col"])
        self.assertAlmostEqual(stats["numeric_col"]["mean"], 3.0, places=2)
        self.assertIn("text_col", stats)

    async def test_data_profiling_correlation_matrix(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]})
        result = await self.tool.execute(action="data_profiling", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("correlation_matrix", result.data)

    # ── PII Detection ──────────────────────────────────────────────────

    async def test_pii_detection_finds_emails(self):
        df = pd.DataFrame({
            "contact": ["alice@example.com", "bob@test.org", "charlie@domain.com"],
            "name": ["Alice", "Bob", "Charlie"],
        })
        result = await self.tool.execute(action="pii_detection", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(result.data["pii_found"])
        detected = result.data["pii_types_detected"]
        self.assertIn("email", detected)

    async def test_pii_detection_finds_phones(self):
        df = pd.DataFrame({
            "phone": ["123-456-7890", "987-654-3210", "555-123-4567"],
        })
        result = await self.tool.execute(action="pii_detection", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        detected = result.data["pii_types_detected"]
        self.assertIn("phone", detected)

    async def test_pii_detection_no_pii(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = await self.tool.execute(action="pii_detection", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertFalse(result.data["pii_found"])

    # ── Anomaly Detection ──────────────────────────────────────────────

    async def test_anomaly_detection_finds_outliers_zscore(self):
        rng = np.random.default_rng(42)
        values = list(rng.normal(50, 5, 50)) + [200, -100]
        df = pd.DataFrame({"value": values})
        result = await self.tool.execute(
            action="anomaly_detection", data=df, method="zscore", threshold=3.0
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertGreater(result.data["total_anomalies"], 0)

    async def test_anomaly_detection_iqr_method(self):
        df = pd.DataFrame({"value": [10, 12, 11, 13, 200, 14, 11, 12]})
        result = await self.tool.execute(
            action="anomaly_detection", data=df, method="iqr", iqr_multiplier=1.5
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertGreater(result.data["total_anomalies"], 0)

    async def test_anomaly_detection_no_numeric_columns(self):
        df = pd.DataFrame({"text": ["a", "b", "c"]})
        result = await self.tool.execute(action="anomaly_detection", data=df)
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    # ── Data Schema Inference ──────────────────────────────────────────

    async def test_data_schema_inference_infers_types(self):
        df = pd.DataFrame({
            "age": [25, 30, 35],
            "name": ["Alice", "Bob", "Charlie"],
            "salary": [50000.0, 60000.0, 70000.0],
            "is_active": [True, False, True],
        })
        result = await self.tool.execute(action="data_schema_inference", data=df)
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        schema = result.data["schema"]
        self.assertIn("properties", schema)
        props = schema["properties"]
        self.assertIn("age", props)
        self.assertIn("name", props)
        self.assertIn("salary", props)
        self.assertIn("is_active", props)
        self.assertIn("validation_schema", result.data)

    async def test_data_schema_inference_with_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("id,value,label\n1,10.5,foo\n2,20.3,bar\n3,30.1,baz\n")
            csv_path = f.name
        try:
            result = await self.tool.execute(action="data_schema_inference", file_path=csv_path)
            self.assertEqual(result.status, ToolResultStatus.SUCCESS)
            self.assertEqual(result.data["columns_inferred"], 3)
        finally:
            os.unlink(csv_path)

    # ── Merge Datasets ─────────────────────────────────────────────────

    async def test_merge_datasets_inner(self):
        left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        right = [{"id": 1, "age": 25}, {"id": 3, "age": 30}]
        result = await self.tool.execute(
            action="merge_datasets", left_data=left, right_data=right, how="inner", on="id"
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.data["merge_statistics"]["result_rows"], 1)

    async def test_merge_datasets_outer(self):
        left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        right = [{"id": 1, "age": 25}, {"id": 3, "age": 30}]
        result = await self.tool.execute(
            action="merge_datasets", left_data=left, right_data=right, how="outer", on="id"
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.data["merge_statistics"]["result_rows"], 3)

    async def test_merge_datasets_auto_detect_columns(self):
        left = [{"key": "a", "val": 1}, {"key": "b", "val": 2}]
        right = [{"key": "a", "score": 10}, {"key": "c", "score": 20}]
        result = await self.tool.execute(
            action="merge_datasets", left_data=left, right_data=right
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertTrue(result.data["merge_statistics"]["auto_detected_columns"])

    async def test_merge_datasets_no_common_columns_fails(self):
        left = [{"a": 1}]
        right = [{"b": 2}]
        result = await self.tool.execute(action="merge_datasets", left_data=left, right_data=right)
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_merge_datasets_with_left_only_provided_fails(self):
        left = [{"id": 1, "name": "Alice"}]
        result = await self.tool.execute(action="merge_datasets", left_data=left)
        self.assertEqual(result.status, ToolResultStatus.FAILURE)


if __name__ == "__main__":
    unittest.main()
