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

"""Tests for the MLTool."""

import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
import pandas as pd
import numpy as np

from tools.ml_tool import MLTool
from tools.base_tool import ToolResultStatus


class TestMLTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tool = MLTool()
        self._orig_models_dir = self.tool._models_dir
        self._tmpdir = tempfile.mkdtemp()
        self.tool._models_dir = type(self.tool._models_dir)(self._tmpdir)
        self.tool._models_dir.mkdir(parents=True, exist_ok=True)

    async def asyncTearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_train_classifier(self):
        from sklearn.datasets import make_classification
        X, y = make_classification(
            n_samples=100, n_features=4, n_informative=3,
            n_redundant=0, n_classes=2, random_state=42
        )
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        df["target"] = y
        result = await self.tool.execute(
            action="train_model", data=df, target_column="target",
            model_type="classifier", model_name="test_clf"
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("metrics", result.data)
        self.assertIn("accuracy", result.data["metrics"])

    async def test_train_regressor(self):
        np.random.seed(42)
        df = pd.DataFrame({
            "feature1": np.random.randn(80),
            "feature2": np.random.randn(80),
            "target": np.random.randn(80) * 10 + 100,
        })
        result = await self.tool.execute(
            action="train_model", data=df, target_column="target",
            model_name="test_reg"
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("r2_score", result.data["metrics"])

    async def test_predict_with_trained_model(self):
        from sklearn.datasets import make_classification
        X, y = make_classification(
            n_samples=100, n_features=4, n_informative=3,
            n_redundant=0, n_classes=2, random_state=42
        )
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        df["target"] = y
        await self.tool.execute(
            action="train_model", data=df, target_column="target",
            model_type="classifier", model_name="pred_model"
        )
        input_data = {f"f{i}": 0.0 for i in range(4)}
        result = await self.tool.execute(
            action="predict", model_name="pred_model", data=input_data
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertEqual(result.data["count"], 1)
        self.assertIn("predictions", result.data)

    async def test_predict_without_model_fails(self):
        result = await self.tool.execute(
            action="predict", model_name="nonexistent_model", data={"x": 1}
        )
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_evaluate_returns_metrics(self):
        from sklearn.datasets import make_classification
        X, y = make_classification(
            n_samples=50, n_features=4, n_informative=3,
            n_redundant=0, n_classes=2, random_state=42
        )
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        df["target"] = y
        await self.tool.execute(
            action="train_model", data=df, target_column="target",
            model_type="classifier", model_name="eval_model"
        )
        result = await self.tool.execute(
            action="evaluate", data=df, target_column="target",
            model_name="eval_model"
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("metrics", result.data)

    async def test_preprocess_handles_missing_values(self):
        df = pd.DataFrame({
            "numeric": [1.0, 2.0, None, 4.0, 5.0],
            "categorical": ["a", None, "a", "b", "c"],
        })
        result = await self.tool.execute(
            action="preprocess", data=df,
            operations=["fill_missing"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("preprocessing_report", result.data)
        self.assertGreater(result.data["preprocessing_report"].get("missing_filled", 0), 0)

    async def test_preprocess_scale_numeric(self):
        df = pd.DataFrame({
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [10.0, 20.0, 30.0, 40.0, 50.0],
        })
        result = await self.tool.execute(
            action="preprocess", data=df,
            operations=["scale_numeric"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("scaled_columns", result.data["preprocessing_report"])

    async def test_preprocess_encode_categorical(self):
        df = pd.DataFrame({
            "cat": ["a", "b", "a", "c"],
            "val": [1, 2, 3, 4],
        })
        result = await self.tool.execute(
            action="preprocess", data=df,
            operations=["encode_categorical"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)

    async def test_train_missing_target_fails(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = await self.tool.execute(
            action="train_model", data=df, target_column="nonexistent"
        )
        self.assertEqual(result.status, ToolResultStatus.FAILURE)

    async def test_feature_engineering(self):
        df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [4, 5, 6],
            "c": [7, 8, 9],
        })
        result = await self.tool.execute(
            action="feature_engineering", data=df,
            operations=["create_interactions", "binning"]
        )
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIn("new_columns", result.data)

    async def test_list_models_returns_list(self):
        result = await self.tool.execute(action="list_models")
        self.assertEqual(result.status, ToolResultStatus.SUCCESS)
        self.assertIsInstance(result.data["models"], list)


if __name__ == "__main__":
    unittest.main()
