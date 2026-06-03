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

"""ArynoxTech AI Agent - ML Engineer Tool
=========================================
Tool for ML engineer tasks: train models, make predictions,
evaluate performance, preprocess data, and feature engineering.
Uses scikit-learn for lightweight ML operations.
"""

import asyncio
import json
import time
import os
import pickle
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import numpy as np

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


class MLTool(BaseTool):
    name: str = "ml_tool"
    description: str = "ML engineer tasks: train classification/regression models, make predictions, evaluate accuracy, preprocess data, feature engineering."
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        cfg = TOOL_CONFIG.get("ml", {})
        self._models_dir = Path(cfg.get("models_dir", "models/ml_models"))
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_models: Dict[str, Any] = {}

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = kwargs.get("action", "train_model")

        try:
            if action == "train_model":
                return await self._train_model(kwargs, start_time)
            elif action == "predict":
                return await self._predict(kwargs, start_time)
            elif action == "evaluate":
                return await self._evaluate(kwargs, start_time)
            elif action == "preprocess":
                return await self._preprocess(kwargs, start_time)
            elif action == "feature_engineering":
                return await self._feature_engineering(kwargs, start_time)
            elif action == "list_models":
                return await self._list_models(kwargs, start_time)
            elif action == "load_model":
                return await self._load_model(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except ImportError as e:
            return ToolResult.failure(
                f"Missing dependency: {e}. Install with: pip install scikit-learn pandas numpy",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.exception(f"ML tool error: {e}")
            return ToolResult.error_result(
                f"ML operation failed: {str(e)}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _get_df(self, kwargs: Dict) -> pd.DataFrame:
        data = kwargs.get("data")
        file_path = kwargs.get("file_path", "")
        if data is not None:
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return data
        if file_path and Path(file_path).exists():
            ext = Path(file_path).suffix.lower()
            if ext == ".csv":
                return pd.read_csv(file_path)
            elif ext in (".xlsx", ".xls"):
                return pd.read_excel(file_path)
            elif ext == ".json":
                return pd.read_json(file_path)
        raise ValueError("No data provided. Pass 'data' (list of dicts) or 'file_path'.")

    async def _train_model(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        target_column = kwargs.get("target_column", "")
        model_type = kwargs.get("model_type", "auto")
        model_name = kwargs.get("model_name", f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        test_size = float(kwargs.get("test_size", 0.2))

        if not target_column or target_column not in df.columns:
            return ToolResult.failure(
                f"target_column '{target_column}' not found in data. Columns: {list(df.columns)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder

        X = df.drop(columns=[target_column])
        y = df[target_column]

        # Encode categorical target
        le = None
        if y.dtype == "object" or y.dtype.name == "category":
            le = LabelEncoder()
            y = le.fit_transform(y)

        # Encode categorical features
        categorical_cols = X.select_dtypes(include=["object", "category"]).columns
        X = pd.get_dummies(X, columns=categorical_cols, drop_first=True)

        # Handle missing values
        X = X.fillna(X.median(numeric_only=True)).fillna(0)

        # Auto-detect model type
        if model_type == "auto":
            if le is not None or y.dtype in ("int64", "int32", "bool"):
                unique_vals = len(set(y))
                model_type = "classifier" if unique_vals <= 20 else "regressor"
            else:
                model_type = "regressor"

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.linear_model import LogisticRegression, LinearRegression
        from sklearn.svm import SVC, SVR

        if model_type == "classifier":
            n_unique = len(set(y_train))
            if n_unique == 2:
                model = LogisticRegression(max_iter=1000, random_state=42)
            else:
                model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        else:
            if len(X_train) < 100:
                model = LinearRegression()
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)

        model.fit(X_train, y_train)

        # Evaluate
        from sklearn.metrics import accuracy_score, r2_score, mean_squared_error, classification_report

        y_pred = model.predict(X_test)
        metrics = {}
        if model_type == "classifier":
            metrics["accuracy"] = round(float(accuracy_score(y_test, y_pred)), 4)
            try:
                report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
                metrics["classification_report"] = {str(k): v for k, v in report.items()}
            except:
                pass
        else:
            metrics["r2_score"] = round(float(r2_score(y_test, y_pred)), 4)
            metrics["rmse"] = round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4)

        if le:
            metrics["classes"] = le.classes_.tolist()

        # Feature importance
        feature_importance = {}
        if hasattr(model, "feature_importances_"):
            for name, imp in zip(X.columns, model.feature_importances_):
                feature_importance[name] = round(float(imp), 4)
        elif hasattr(model, "coef_"):
            if model.coef_.ndim == 1:
                for name, coef in zip(X.columns, model.coef_):
                    feature_importance[name] = round(float(coef), 4)

        # Save model
        model_path = self._models_dir / f"{model_name}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump({"model": model, "columns": list(X.columns), "label_encoder": le, "model_type": model_type}, f)

        self._loaded_models[model_name] = model

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Model '{model_name}' trained: {model_type} with {len(X.columns)} features",
            data={
                "model_name": model_name,
                "model_type": model_type,
                "features": list(X.columns),
                "training_rows": len(X_train),
                "test_rows": len(X_test),
                "metrics": metrics,
                "feature_importance": feature_importance,
                "model_path": str(model_path),
            },
            execution_time_ms=elapsed,
        )

    async def _predict(self, kwargs: Dict, start_time: float) -> ToolResult:
        model_name = kwargs.get("model_name", "")
        if not model_name:
            # Try latest saved model
            models = sorted(self._models_dir.glob("*.pkl"), key=os.path.getmtime, reverse=True)
            if not models:
                return ToolResult.failure(
                    "No model specified and no saved models found. Train a model first.",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            model_name = models[0].stem

        model_path = self._models_dir / f"{model_name}.pkl"
        if not model_path.exists():
            return ToolResult.failure(
                f"Model '{model_name}' not found at {model_path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        with open(model_path, "rb") as f:
            saved = pickle.load(f)
        model = saved["model"]
        columns = saved["columns"]
        le = saved.get("label_encoder")

        input_data = kwargs.get("data", [])
        if isinstance(input_data, dict):
            input_data = [input_data]

        if not input_data:
            return ToolResult.failure(
                "No input data provided for prediction",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        pred_df = pd.DataFrame(input_data)
        # Align columns with training
        for col in columns:
            if col not in pred_df.columns:
                pred_df[col] = 0
        pred_df = pred_df[columns]

        predictions = model.predict(pred_df)
        if le:
            predictions = le.inverse_transform(predictions)

        results = []
        for i, pred in enumerate(predictions):
            results.append({
                "row": i + 1,
                "prediction": pred.tolist() if isinstance(pred, np.ndarray) else str(pred),
            })

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Predictions for {len(results)} row(s) using model '{model_name}'",
            data={
                "model_name": model_name,
                "predictions": results,
                "count": len(results),
            },
            execution_time_ms=elapsed,
        )

    async def _evaluate(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        target_column = kwargs.get("target_column", "")
        model_name = kwargs.get("model_name", "")

        if not target_column:
            return ToolResult.failure(
                "target_column is required for evaluation",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        model_path = self._models_dir / f"{model_name}.pkl" if model_name else None
        if model_path and model_path.exists():
            with open(model_path, "rb") as f:
                saved = pickle.load(f)
            model = saved["model"]
            columns = saved["columns"]
            le = saved.get("label_encoder")

            X = df.drop(columns=[target_column], errors="ignore")
            y_true = df[target_column] if target_column in df.columns else None

            for col in columns:
                if col not in X.columns:
                    X[col] = 0
            X = X[columns]

            if le and y_true is not None:
                try:
                    y_true = le.transform(y_true)
                except:
                    pass

            y_pred = model.predict(X)
            from sklearn.metrics import accuracy_score, r2_score, mean_squared_error
            metrics = {}
            if y_true is not None:
                if saved["model_type"] == "classifier":
                    metrics["accuracy"] = round(float(accuracy_score(y_true, y_pred)), 4)
                else:
                    metrics["r2_score"] = round(float(r2_score(y_true, y_pred)), 4)
                    metrics["rmse"] = round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Evaluation complete for model '{model_name}'",
                data={"model_name": model_name, "metrics": metrics, "rows_evaluated": len(df)},
                execution_time_ms=elapsed,
            )

        return ToolResult.failure(
            f"Model '{model_name or 'latest'}' not saved. Train and save a model first.",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _preprocess(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        operations = kwargs.get("operations", ["fill_missing", "scale_numeric", "encode_categorical"])
        target_column = kwargs.get("target_column", "")

        report = {}
        for op in operations:
            if op == "fill_missing":
                before = df.isnull().sum().sum()
                for col in df.columns:
                    if df[col].dtype in ("object", "category"):
                        df[col] = df[col].fillna(df[col].mode().iloc[0] if not df[col].mode().empty else "Unknown")
                    elif np.issubdtype(df[col].dtype, np.number):
                        df[col] = df[col].fillna(df[col].median())
                report["missing_filled"] = before - df.isnull().sum().sum()

            elif op == "scale_numeric":
                from sklearn.preprocessing import StandardScaler
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if target_column and target_column in numeric_cols:
                    numeric_cols.remove(target_column)
                if numeric_cols:
                    scaler = StandardScaler()
                    df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
                    report["scaled_columns"] = numeric_cols

            elif op == "encode_categorical":
                categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
                if target_column and target_column in categorical_cols:
                    categorical_cols.remove(target_column)
                df = pd.get_dummies(df, columns=categorical_cols, drop_first=True)
                report["encoded_columns"] = categorical_cols

            elif op == "remove_outliers":
                from scipy import stats
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                before = len(df)
                for col in numeric_cols:
                    z_scores = np.abs(stats.zscore(df[col].dropna()))
                    df = df[z_scores < 3]
                report["outliers_removed"] = before - len(df)

            elif op == "remove_duplicates":
                before = len(df)
                df = df.drop_duplicates()
                report["duplicates_removed"] = before - len(df)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Preprocessing complete: {len(df)} rows, {len(df.columns)} columns",
            data={
                "rows": len(df),
                "columns": list(df.columns),
                "preprocessing_report": report,
                "preview": df.head(5).to_dict(orient="records"),
            },
            execution_time_ms=elapsed,
        )

    async def _feature_engineering(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        operations = kwargs.get("operations", ["create_interactions", "binning", "date_features"])
        target_column = kwargs.get("target_column", "")
        report = {}
        original_columns = len(df.columns)

        for op in operations:
            if op == "create_interactions":
                numeric_cols = df.select_dtypes(include=[np.number]).columns[:5]
                if len(numeric_cols) >= 2:
                    for i in range(len(numeric_cols)):
                        for j in range(i + 1, len(numeric_cols)):
                            col_a, col_b = numeric_cols[i], numeric_cols[j]
                            df[f"{col_a}_x_{col_b}"] = df[col_a] * df[col_b]
                    report["interactions_created"] = True

            elif op == "binning":
                numeric_cols = df.select_dtypes(include=[np.number]).columns[:3]
                for col in numeric_cols:
                    df[f"{col}_binned"] = pd.qcut(df[col], q=4, labels=False, duplicates="drop")
                report["binning_applied"] = list(numeric_cols)

            elif op == "date_features":
                for col in df.columns:
                    if df[col].dtype == "object":
                        try:
                            dates = pd.to_datetime(df[col], errors="coerce")
                            if dates.notna().sum() > len(df) * 0.5:
                                df[f"{col}_year"] = dates.dt.year
                                df[f"{col}_month"] = dates.dt.month
                                df[f"{col}_day"] = dates.dt.day
                                df[f"{col}_dayofweek"] = dates.dt.dayofweek
                                report["date_features_added"] = col
                                break
                        except:
                            pass

            elif op == "text_features":
                for col in df.select_dtypes(include=["object"]).columns[:2]:
                    df[f"{col}_length"] = df[col].astype(str).str.len()
                    report["text_features_added"] = col

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Feature engineering complete: {len(df)} rows, {len(df.columns)} columns ({len(df.columns) - original_columns} new features)",
            data={
                "rows": len(df),
                "columns": list(df.columns),
                "new_columns": len(df.columns),
                "operations": operations,
                "report": report,
                "preview": df.head(5).to_dict(orient="records"),
            },
            execution_time_ms=elapsed,
        )

    async def _load_model(self, kwargs: Dict, start_time: float) -> ToolResult:
        model_name = kwargs.get("model_name", "")
        if not model_name:
            models = sorted(self._models_dir.glob("*.pkl"), key=os.path.getmtime, reverse=True)
            if not models:
                return ToolResult.failure("No saved models found", execution_time_ms=(time.time() - start_time) * 1000)
            model_name = models[0].stem

        model_path = self._models_dir / f"{model_name}.pkl"
        if not model_path.exists():
            return ToolResult.failure(f"Model '{model_name}' not found", execution_time_ms=(time.time() - start_time) * 1000)

        with open(model_path, "rb") as f:
            saved = pickle.load(f)
        self._loaded_models[model_name] = saved["model"]

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Model '{model_name}' loaded",
            data={
                "model_name": model_name,
                "model_type": saved.get("model_type", "unknown"),
                "features": saved.get("columns", []),
            },
            execution_time_ms=elapsed,
        )

    async def _list_models(self, kwargs: Dict, start_time: float) -> ToolResult:
        models = []
        for f in sorted(self._models_dir.glob("*.pkl"), key=os.path.getmtime, reverse=True):
            try:
                with open(f, "rb") as fh:
                    saved = pickle.load(fh)
                models.append({
                    "name": f.stem,
                    "model_type": saved.get("model_type", "unknown"),
                    "features_count": len(saved.get("columns", [])),
                    "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "size_kb": round(f.stat().st_size / 1024, 2),
                })
            except:
                models.append({"name": f.stem, "error": "corrupted"})
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"{len(models)} ML model(s) available",
            data={"models": models, "count": len(models)},
            execution_time_ms=elapsed,
        )
