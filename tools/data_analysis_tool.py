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
ArynoxTech AI Agent - Data Analysis & Business Intelligence Tool
================================================================
Production-grade tool for comprehensive data analysis, statistics,
ETL pipelines, forecasting, hypothesis testing, regression analysis,
and business KPI calculations.
"""

import copy
import io
import json
import logging
import math
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from tools.base_tool import BaseTool, ToolResult
from config.settings import BASE_DIR, DIRS, TOOL_CONFIG, SECURITY_CONFIG


try:
    from scipy import stats as scipy_stats
    from scipy.stats import (
        ttest_ind,
        ttest_1samp,
        ttest_rel,
        f_oneway,
        chi2_contingency,
        shapiro,
        pearsonr,
        spearmanr,
        kendalltau,
        normaltest,
        levene,
    )
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from statsmodels.tsa.stattools import acf, pacf, adfuller, kpss
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.stats.diagnostic import het_breuschpagan
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

try:
    from sqlalchemy import create_engine, text as sa_text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


logger = logging.getLogger(__name__)


class DataAnalysisTool(BaseTool):
    """
    Comprehensive data analysis and business intelligence tool.

    Provides 12 action categories:
    - load_data, clean_data, analyze, correlation, forecasting
    - hypothesis_test, regression_analysis, kpi_metrics
    - etl_pipeline, filter_query, time_series_analysis, export_data
    """

    name: str = "data_analysis_tool"
    description: str = (
        "Advanced data analysis & BI: load, clean, analyze, correlate, forecast, "
        "hypothesis test, regression, KPI metrics, ETL pipelines, time-series, export."
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG.get("data_analysis", {})
        self._max_rows = self.config.get("max_rows", 500000)
        self._memory_limit_mb = self.config.get("memory_limit_mb", 500)
        self._dataframes: Dict[str, pd.DataFrame] = {}

    # ── Dispatcher ──────────────────────────────────────────────────────────

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = kwargs.get("action", "analyze")

        try:
            dispatcher = {
                "load_data": self._load_data,
                "clean_data": self._clean_data,
                "analyze": self._analyze,
                "correlation": self._correlation,
                "forecasting": self._forecasting,
                "hypothesis_test": self._hypothesis_test,
                "regression_analysis": self._regression_analysis,
                "kpi_metrics": self._kpi_metrics,
                "etl_pipeline": self._etl_pipeline,
                "filter_query": self._filter_query,
                "time_series_analysis": self._time_series_analysis,
                "export_data": self._export_data,
            }
            handler = dispatcher.get(action)
            if handler is None:
                return ToolResult.failure(
                    f"Unknown action: {action}. Available: {list(dispatcher.keys())}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            return await handler(kwargs, start_time)
        except Exception as e:
            self.logger.exception(f"DataAnalysisTool error: {e}")
            return ToolResult.error_result(
                f"Data analysis failed: {e}",
                error=traceback.format_exc(),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── DataFrame resolution helper ─────────────────────────────────────────

    def _get_df(self, kwargs: Dict) -> pd.DataFrame:
        df_name = kwargs.get("df_name", "default")
        data = kwargs.get("data")
        if data is not None:
            if isinstance(data, pd.DataFrame):
                return data.copy()
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            raise ValueError("Unsupported data type; expected DataFrame, list of dicts, or dict.")

        file_path = kwargs.get("file_path", "")
        if file_path:
            path = Path(file_path)
            if path.exists():
                return self._read_file(path)
            raise ValueError(f"File not found: {file_path}")

        if df_name in self._dataframes:
            return self._dataframes[df_name].copy()

        if self._dataframes:
            return next(iter(self._dataframes.values())).copy()

        raise ValueError(
            "No data source available. Provide data, file_path, or "
            "load data first with action='load_data'."
        )

    def _read_file(self, path: Path, **read_kwargs) -> pd.DataFrame:
        ext = path.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(path, **read_kwargs)
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(path, **read_kwargs)
        if ext == ".json":
            return pd.read_json(path, **read_kwargs)
        if ext in (".parquet", ".pq"):
            return pd.read_parquet(path, **read_kwargs)
        raise ValueError(f"Unsupported file format: {ext}")

    # ── 1. load_data ────────────────────────────────────────────────────────

    async def _load_data(self, kwargs: Dict, start_time: float) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        data_format = kwargs.get("format", "auto")
        df_name = kwargs.get("df_name", "default")
        read_kwargs = {k: v for k, v in kwargs.items() if k in (
            "sheet_name", "header", "encoding", "sep", "delimiter", "skiprows",
            "nrows", "usecols", "parse_dates", "index_col",
        )}

        if not file_path:
            raw = kwargs.get("data")
            if raw is not None:
                if isinstance(raw, pd.DataFrame):
                    df = raw.copy()
                elif isinstance(raw, list):
                    df = pd.DataFrame(raw)
                elif isinstance(raw, dict):
                    df = pd.DataFrame([raw])
                else:
                    return ToolResult.failure(
                        "Unsupported data type",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                self._dataframes[df_name] = df
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"Loaded inline data: {len(df)} rows, {len(df.columns)} columns",
                    data=self._build_preview(df, df_name),
                    execution_time_ms=elapsed,
                )
            return ToolResult.failure(
                "Provide file_path or data",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult.failure(
                f"File not found: {file_path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        ext = path.suffix.lower() if data_format == "auto" else f".{data_format}"
        try:
            if ext == ".csv":
                df = pd.read_csv(file_path, **read_kwargs)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path, **read_kwargs)
            elif ext == ".json":
                df = pd.read_json(file_path, **read_kwargs)
            elif ext in (".parquet", ".pq"):
                df = pd.read_parquet(file_path, **read_kwargs)
            elif ext == ".sql":
                query = kwargs.get("query", "SELECT * FROM data")
                if not HAS_SQLALCHEMY:
                    return ToolResult.failure(
                        "sqlalchemy required for SQL sources",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                conn_str = kwargs.get("connection_string", "")
                engine = create_engine(conn_str)
                df = pd.read_sql(query, engine)
            else:
                return ToolResult.failure(
                    f"Unsupported format: {ext}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if len(df) > self._max_rows:
                self.logger.warning(
                    "Data truncated from %d to %d rows (max_rows)",
                    len(df), self._max_rows,
                )
                df = df.head(self._max_rows)

            self._dataframes[df_name] = df
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Loaded {len(df)} rows, {len(df.columns)} columns from {path.name}",
                data=self._build_preview(df, df_name),
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to load {path.name}: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _build_preview(self, df: pd.DataFrame, df_name: str = "default") -> Dict:
        mem = df.memory_usage(deep=True).sum() / 1024 / 1024
        return {
            "df_name": df_name,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "dtypes": {c: str(dt) for c, dt in df.dtypes.items()},
            "memory_usage_mb": round(mem, 2),
            "missing_cells": int(df.isnull().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()),
            "head": df.head(5).to_dict(orient="records"),
            "tail": df.tail(5).to_dict(orient="records"),
        }

    # ── 2. clean_data ───────────────────────────────────────────────────────

    async def _clean_data(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        df = df.copy()
        report = {"before": {"rows": len(df), "columns": len(df.columns)}}
        original_cols = set(df.columns)

        # Drop columns with >threshold% missing
        threshold = kwargs.get("missing_threshold", 80.0)
        max_missing = kwargs.get("max_missing_pct", threshold)
        before_drop = len(df.columns)
        null_pct = df.isnull().mean() * 100
        drop_cols = null_pct[null_pct > max_missing].index.tolist()
        if drop_cols:
            df = df.drop(columns=drop_cols)
            report["columns_dropped_high_missing"] = {"columns": drop_cols, "count": len(drop_cols)}

        # Remove duplicate rows
        subset = kwargs.get("subset")
        keep = kwargs.get("keep", "first")
        before_dedup = len(df)
        df = df.drop_duplicates(subset=subset, keep=keep)
        dup_removed = before_dedup - len(df)
        if dup_removed:
            report["duplicates_removed"] = dup_removed

        # Fill missing values
        fill_strategy = kwargs.get("fill_strategy", "auto")
        fill_value = kwargs.get("fill_value")
        missing_before = int(df.isnull().sum().sum())

        if missing_before > 0:
            if fill_strategy == "auto":
                for col in df.columns:
                    if df[col].dtype in ("object", "category"):
                        mode_vals = df[col].mode(dropna=True)
                        df[col] = df[col].fillna(mode_vals.iloc[0] if not mode_vals.empty else "")
                    elif np.issubdtype(df[col].dtype, np.number):
                        df[col] = df[col].fillna(df[col].median())
                    else:
                        df[col] = df[col].ffill()
            elif fill_strategy == "drop":
                df = df.dropna()
            elif fill_strategy == "constant" and fill_value is not None:
                df = df.fillna(fill_value)
            elif fill_strategy == "ffill":
                df = df.ffill()
            elif fill_strategy == "bfill":
                df = df.bfill()
            elif fill_strategy == "mean":
                for col in df.select_dtypes(include=[np.number]).columns:
                    df[col] = df[col].fillna(df[col].mean())
            elif fill_strategy == "median":
                for col in df.select_dtypes(include=[np.number]).columns:
                    df[col] = df[col].fillna(df[col].median())
            elif fill_strategy == "mode":
                for col in df.columns:
                    mode_vals = df[col].mode(dropna=True)
                    df[col] = df[col].fillna(mode_vals.iloc[0] if not mode_vals.empty else "")
            report["missing_filled"] = missing_before - int(df.isnull().sum().sum())

        report["remaining_missing"] = int(df.isnull().sum().sum())

        # Fix data types
        if kwargs.get("fix_types", True):
            type_changes = {}
            for col in df.columns:
                if df[col].dtype == "object":
                    orig = df[col].dtype
                    try:
                        converted = pd.to_datetime(df[col], errors="ignore")
                        if converted.dtype != df[col].dtype:
                            df[col] = converted
                            type_changes[col] = "datetime"
                            continue
                    except Exception:
                        pass
                    try:
                        converted = pd.to_numeric(df[col], errors="ignore")
                        if converted.dtype != df[col].dtype:
                            df[col] = converted
                            type_changes[col] = "numeric"
                    except Exception:
                        pass
            if type_changes:
                report["types_fixed"] = type_changes

        # Strip whitespace from string columns
        if kwargs.get("strip_whitespace", True):
            stripped_cols = []
            for col in df.select_dtypes(include=["object"]).columns:
                before_strip = df[col].iloc[:100].tolist()
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace("", np.nan)
                if df[col].iloc[:100].tolist() != before_strip:
                    stripped_cols.append(col)
            if stripped_cols:
                report["whitespace_stripped"] = stripped_cols

        # Remove outliers (IQR method)
        if kwargs.get("remove_outliers", False):
            outlier_cols = kwargs.get("outlier_columns") or df.select_dtypes(include=[np.number]).columns.tolist()
            iqr_mult = kwargs.get("iqr_multiplier", 1.5)
            before_out = len(df)
            outlier_mask = pd.Series(True, index=df.index)
            for col in outlier_cols:
                if col in df.columns and np.issubdtype(df[col].dtype, np.number):
                    q1 = df[col].quantile(0.25)
                    q3 = df[col].quantile(0.75)
                    iqr = q3 - q1
                    lo = q1 - iqr_mult * iqr
                    hi = q3 + iqr_mult * iqr
                    outlier_mask &= (df[col] >= lo) & (df[col] <= hi)
            df = df[outlier_mask]
            report["outliers_removed"] = before_out - len(df)

        self._dataframes[kwargs.get("df_name", "default")] = df
        report["after"] = {"rows": len(df), "columns": len(df.columns)}
        report["rows_removed"] = report["before"]["rows"] - len(df)
        dropped_final = original_cols - set(df.columns)
        if dropped_final:
            report["columns_dropped"] = list(dropped_final)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Cleaned: {report['before']['rows']} -> {len(df)} rows, "
            f"{report['before']['columns']} -> {len(df.columns)} columns",
            data={
                "cleaning_report": report,
                "preview": df.head(10).to_dict(orient="records"),
                "column_names": list(df.columns),
                "df_name": kwargs.get("df_name", "default"),
            },
            execution_time_ms=elapsed,
        )

    # ── 3. analyze ──────────────────────────────────────────────────────────

    async def _analyze(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        result: Dict[str, Any] = {}
        analysis_type = kwargs.get("analysis_type", "descriptive")

        if analysis_type in ("descriptive", "all"):
            numeric = df.select_dtypes(include=[np.number])
            categorical = df.select_dtypes(include=["object", "category"])
            result["descriptive"] = {
                "count": len(df),
                "columns": len(df.columns),
                "numeric_columns": list(numeric.columns),
                "categorical_columns": list(categorical.columns),
                "missing_summary": {
                    "total_missing": int(df.isnull().sum().sum()),
                    "missing_per_column": df.isnull().sum().to_dict(),
                    "missing_pct_per_column": (df.isnull().mean() * 100).round(2).to_dict(),
                },
                "duplicate_count": int(df.duplicated().sum()),
                "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            }
            if not numeric.empty:
                desc = numeric.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).round(4)
                desc.index = desc.index.astype(str)
                result["descriptive"]["numeric_describe"] = desc.to_dict()
                result["descriptive"]["skewness"] = numeric.skew().round(4).to_dict()
                result["descriptive"]["kurtosis"] = numeric.kurtosis().round(4).to_dict()

        if analysis_type in ("groupby", "all"):
            by = kwargs.get("groupby", [])
            agg = kwargs.get("agg", {})
            if by:
                if agg:
                    grp = df.groupby(by).agg(agg).reset_index()
                else:
                    grp = df.groupby(by).size().reset_index(name="count")
                result["groupby"] = {
                    "grouped_by": by,
                    "rows": len(grp),
                    "preview": grp.head(50).to_dict(orient="records"),
                }

        if analysis_type in ("pivot", "all"):
            pivot_params = {
                "index": kwargs.get("pivot_index"),
                "columns": kwargs.get("pivot_columns"),
                "values": kwargs.get("pivot_values"),
                "aggfunc": kwargs.get("pivot_aggfunc", "mean"),
            }
            if all(pivot_params.values()):
                try:
                    pt = df.pivot_table(**pivot_params).reset_index()
                    result["pivot"] = {
                        "params": pivot_params,
                        "shape": list(pt.shape),
                        "preview": pt.head(50).to_dict(orient="records"),
                    }
                except Exception as e:
                    result["pivot"] = {"error": str(e)}

        if analysis_type in ("crosstab", "all"):
            idx = kwargs.get("crosstab_index")
            col = kwargs.get("crosstab_columns")
            if idx and col:
                try:
                    ct = pd.crosstab(df[idx], df[col])
                    result["crosstab"] = {
                        "index": idx,
                        "columns": col,
                        "preview": ct.head(50).to_dict(orient="records"),
                    }
                except Exception as e:
                    result["crosstab"] = {"error": str(e)}

        if analysis_type in ("value_counts", "all"):
            vc_cols = kwargs.get("value_counts_columns") or df.select_dtypes(include=["object", "category"]).columns[:5].tolist()
            vc_result = {}
            for c in vc_cols:
                if c in df.columns:
                    counts = df[c].value_counts(dropna=False).head(20)
                    vc_result[c] = {
                        "unique": int(df[c].nunique()),
                        "top_values": counts.to_dict(),
                    }
            result["value_counts"] = vc_result

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Analysis complete ({analysis_type})",
            data=result,
            execution_time_ms=elapsed,
        )

    # ── 4. correlation ──────────────────────────────────────────────────────

    async def _correlation(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        method = kwargs.get("method", "pearson")
        numeric = df.select_dtypes(include=[np.number])

        if numeric.empty or numeric.shape[1] < 2:
            return ToolResult.failure(
                "Need at least 2 numeric columns for correlation analysis",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if method not in ("pearson", "spearman", "kendall"):
            return ToolResult.failure(
                f"Method must be pearson, spearman, or kendall; got {method}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        corr_matrix = numeric.corr(method=method)

        pairs = []
        cols = corr_matrix.columns
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                c1, c2 = cols[i], cols[j]
                r = corr_matrix.iloc[i, j]
                p_val = None
                if HAS_SCIPY:
                    try:
                        clean = numeric[[c1, c2]].dropna()
                        if method == "pearson":
                            _, p_val = pearsonr(clean[c1], clean[c2])
                        elif method == "spearman":
                            _, p_val = spearmanr(clean[c1], clean[c2])
                        else:
                            _, p_val = kendalltau(clean[c1], clean[c2])
                    except Exception:
                        pass
                pair = {
                    "col1": c1,
                    "col2": c2,
                    "r_value": round(r, 4),
                    "p_value": round(p_val, 6) if p_val is not None else None,
                    "strong": abs(r) > 0.7,
                    "direction": "positive" if r > 0 else "negative",
                    "strength": (
                        "very_strong" if abs(r) > 0.9 else
                        "strong" if abs(r) > 0.7 else
                        "moderate" if abs(r) > 0.5 else
                        "weak"
                    ),
                }
                pairs.append(pair)

        pairs.sort(key=lambda x: abs(x["r_value"]), reverse=True)
        top_n = kwargs.get("top_n", 10)
        top_pairs = pairs[:top_n]

        heatmap_data = [
            {"col1": p["col1"], "col2": p["col2"], "r_value": p["r_value"]}
            for p in pairs
        ]

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Correlation ({method}): {len(cols)} variables, {len(pairs)} pairs, "
            f"{sum(1 for p in pairs if p['strong'])} strong",
            data={
                "method": method,
                "variables": list(cols),
                "correlation_matrix": corr_matrix.round(4).to_dict(),
                "top_correlations": top_pairs,
                "all_pairs": pairs,
                "heatmap_data": heatmap_data,
                "strong_correlations": [p for p in pairs if p["strong"]],
            },
            execution_time_ms=elapsed,
        )

    # ── 5. forecasting ──────────────────────────────────────────────────────

    async def _forecasting(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)

        date_col = kwargs.get("date_column") or self._auto_detect_date_col(df)
        if not date_col:
            return ToolResult.failure(
                "Could not auto-detect date column. Provide date_column parameter.",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        value_col = kwargs.get("value_column")
        if not value_col:
            numeric = df.select_dtypes(include=[np.number]).columns
            if len(numeric) == 0:
                return ToolResult.failure(
                    "No numeric column found for forecasting",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            value_col = numeric[0]

        try:
            ts = df[[date_col, value_col]].copy()
            ts[date_col] = pd.to_datetime(ts[date_col])
            ts = ts.set_index(date_col).sort_index()
            ts = ts[~ts.index.duplicated(keep="first")]

            if ts.index.isna().any():
                ts = ts.dropna()

            freq = kwargs.get("resample_freq", "auto")
            if freq == "auto":
                freq = self._infer_freq(ts)
            if freq:
                ts = ts.resample(freq).mean().interpolate(method="linear")

            ts = ts.dropna()
            if len(ts) < 4:
                return ToolResult.failure(
                    f"Need at least 4 data points after resampling; got {len(ts)}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            window = kwargs.get("window", min(7, max(3, len(ts) // 10)))
            sma = ts.rolling(window=window).mean()
            ema = ts.ewm(span=window, adjust=False).mean()

            x = np.arange(len(ts))
            y = ts.values.flatten()
            slope, intercept = np.polyfit(x, y, 1)
            trend_line = pd.Series(intercept + slope * x, index=ts.index, name="linear_trend")

            forecast_steps = kwargs.get("forecast_steps", min(30, max(1, len(ts) // 4)))
            future_x = np.arange(len(ts), len(ts) + forecast_steps)
            forecast_values = intercept + slope * future_x
            residuals = y - (intercept + slope * x)
            rmse = float(np.sqrt(np.mean(residuals ** 2)))
            std_resid = float(np.std(residuals))
            future_idx = pd.date_range(
                start=ts.index[-1] + (ts.index[1] - ts.index[0]),
                periods=forecast_steps,
                freq=ts.index[1] - ts.index[0],
            )
            forecast_series = pd.Series(forecast_values, index=future_idx, name="forecast")

            lower_bound = forecast_series - 1.96 * std_resid
            upper_bound = forecast_series + 1.96 * std_resid

            plot_data = []
            for dt, val in ts.items():
                plot_data.append({
                    "date": str(dt.date()) if hasattr(dt, "date") else str(dt),
                    "actual": float(val),
                    "forecast": None,
                    "lower": None,
                    "upper": None,
                    "sma": float(sma.loc[dt]) if dt in sma.index and not pd.isna(sma.loc[dt]) else None,
                    "ema": float(ema.loc[dt]) if dt in ema.index and not pd.isna(ema.loc[dt]) else None,
                    "trend": float(trend_line.loc[dt]) if dt in trend_line.index else None,
                })
            for i, dt in enumerate(future_idx):
                plot_data.append({
                    "date": str(dt.date()) if hasattr(dt, "date") else str(dt),
                    "actual": None,
                    "forecast": float(forecast_series.iloc[i]),
                    "lower": float(lower_bound.iloc[i]),
                    "upper": float(upper_bound.iloc[i]),
                    "sma": None,
                    "ema": None,
                    "trend": float(trend_line.iloc[-1] + slope * (i + 1)) if i < len(trend_line) - len(ts) + forecast_steps else None,
                })

            result: Dict[str, Any] = {
                "date_column": date_col,
                "value_column": value_col,
                "resample_freq": freq or "none",
                "data_points": len(ts),
                "forecast_horizon": forecast_steps,
                "model": "linear_trend",
                "slope": round(float(slope), 6),
                "intercept": round(float(intercept), 6),
                "rmse": round(rmse, 4),
                "std_residual": round(std_resid, 4),
                "last_actual": float(y[-1]),
                "next_forecast": float(forecast_values[0]),
                "sma_window": window,
                "actuals": {str(k.date() if hasattr(k, "date") else k): float(v) for k, v in ts.items()},
                "forecast": {str(k.date() if hasattr(k, "date") else k): float(v) for k, v in forecast_series.items()},
                "lower_bound": {str(k.date() if hasattr(k, "date") else k): float(v) for k, v in lower_bound.items()},
                "upper_bound": {str(k.date() if hasattr(k, "date") else k): float(v) for k, v in upper_bound.items()},
                "plot_data": plot_data,
            }

            if HAS_STATSMODELS and len(ts) >= 14:
                try:
                    decomp = seasonal_decompose(ts, model="additive", period=min(7, len(ts) // 2))
                    result["seasonal_decomposition"] = {
                        "trend": {str(k.date() if hasattr(k, "date") else k): (
                            float(v) if not pd.isna(v) else None
                        ) for k, v in decomp.trend.items()},
                        "seasonal": {str(k.date() if hasattr(k, "date") else k): (
                            float(v) if not pd.isna(v) else None
                        ) for k, v in decomp.seasonal.items()},
                        "residual": {str(k.date() if hasattr(k, "date") else k): (
                            float(v) if not pd.isna(v) else None
                        ) for k, v in decomp.resid.items()},
                    }
                except Exception:
                    pass

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Forecast generated: {len(ts)} data points, {forecast_steps} forecast steps",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Forecasting failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _auto_detect_date_col(self, df: pd.DataFrame) -> Optional[str]:
        for col in df.columns:
            if df[col].dtype == "object":
                try:
                    pd.to_datetime(df[col].dropna().head(100))
                    return col
                except Exception:
                    pass
            if "date" in col.lower() or "time" in col.lower() or "timestamp" in col.lower():
                return col
        return None

    def _infer_freq(self, ts: pd.Series) -> Optional[str]:
        if len(ts) < 4:
            return None
        diffs = pd.Series(ts.index).diff().dropna()
        if diffs.empty:
            return None
        median_gap = diffs.median()
        if median_gap <= pd.Timedelta(hours=2):
            return "h"
        if median_gap <= pd.Timedelta(hours=28):
            return "D"
        if median_gap <= pd.Timedelta(days=14):
            return "W"
        if median_gap <= pd.Timedelta(days=60):
            return "ME"
        return "QE"

    # ── 6. hypothesis_test ──────────────────────────────────────────────────

    async def _hypothesis_test(self, kwargs: Dict, start_time: float) -> ToolResult:
        if not HAS_SCIPY:
            return ToolResult.failure(
                "scipy is required for hypothesis testing. Install with: pip install scipy",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        df = self._get_df(kwargs)
        test_type = kwargs.get("test_type", "ttest")
        result: Dict[str, Any] = {"test_type": test_type}

        if test_type == "ttest":
            test_subtype = kwargs.get("subtype", "independent")
            col1 = kwargs.get("column1")
            col2 = kwargs.get("column2")
            popmean = kwargs.get("popmean")

            if test_subtype == "one_sample":
                if not col1 or popmean is None:
                    return ToolResult.failure(
                        "one_sample ttest requires column1 and popmean",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                data = df[col1].dropna()
                stat, p = ttest_1samp(data, popmean)
                result.update({
                    "subtype": "one_sample",
                    "column": col1,
                    "population_mean": popmean,
                    "sample_mean": round(float(data.mean()), 4),
                    "test_statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "significant": p < 0.05,
                    "interpretation": (
                        f"Reject H0: sample mean differs from {popmean}"
                        if p < 0.05 else
                        f"Fail to reject H0: sample mean not significantly different from {popmean}"
                    ),
                })
            elif test_subtype == "independent":
                if not col1 or not col2:
                    return ToolResult.failure(
                        "independent ttest requires column1 and column2",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                d1, d2 = df[col1].dropna(), df[col2].dropna()
                stat, p = ttest_ind(d1, d2, equal_var=kwargs.get("equal_var", True))
                result.update({
                    "subtype": "independent",
                    "group1_column": col1,
                    "group2_column": col2,
                    "group1_mean": round(float(d1.mean()), 4),
                    "group2_mean": round(float(d2.mean()), 4),
                    "test_statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "significant": p < 0.05,
                    "interpretation": (
                        "Reject H0: significant difference between groups"
                        if p < 0.05 else
                        "Fail to reject H0: no significant difference between groups"
                    ),
                })
            elif test_subtype == "paired":
                if not col1 or not col2:
                    return ToolResult.failure(
                        "paired ttest requires column1 and column2",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                paired = df[[col1, col2]].dropna()
                stat, p = ttest_rel(paired[col1], paired[col2])
                result.update({
                    "subtype": "paired",
                    "column1": col1,
                    "column2": col2,
                    "mean_difference": round(float((paired[col1] - paired[col2]).mean()), 4),
                    "test_statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "significant": p < 0.05,
                    "interpretation": (
                        "Reject H0: significant difference between paired measurements"
                        if p < 0.05 else
                        "Fail to reject H0: no significant difference between paired measurements"
                    ),
                })

        elif test_type == "anova":
            groups_col = kwargs.get("groups_column")
            value_col = kwargs.get("value_column")
            if not groups_col or not value_col:
                return ToolResult.failure(
                    "ANOVA requires groups_column and value_column",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            groups = [g.dropna().values for _, g in df.groupby(groups_col)[value_col]]
            if len(groups) < 2:
                return ToolResult.failure(
                    "Need at least 2 groups for ANOVA",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            stat, p = f_oneway(*groups)
            result.update({
                "subtype": "one_way",
                "groups_column": groups_col,
                "value_column": value_col,
                "num_groups": len(groups),
                "group_means": {
                    str(name): round(float(g.mean()), 4)
                    for name, g in zip(df[groups_col].unique(), groups)
                },
                "test_statistic": round(float(stat), 4),
                "p_value": round(float(p), 6),
                "significant": p < 0.05,
                "interpretation": (
                    "Reject H0: significant difference between group means"
                    if p < 0.05 else
                    "Fail to reject H0: no significant difference between group means"
                ),
            })

        elif test_type == "chi_square":
            col_a = kwargs.get("column1")
            col_b = kwargs.get("column2")
            if not col_a or not col_b:
                return ToolResult.failure(
                    "chi_square requires column1 and column2",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            contingency = pd.crosstab(df[col_a], df[col_b])
            stat, p, dof, expected = chi2_contingency(contingency)
            result.update({
                "subtype": "independence",
                "column1": col_a,
                "column2": col_b,
                "degrees_of_freedom": int(dof),
                "test_statistic": round(float(stat), 4),
                "p_value": round(float(p), 6),
                "significant": p < 0.05,
                "expected_frequencies": pd.DataFrame(
                    expected,
                    index=contingency.index,
                    columns=contingency.columns,
                ).round(2).to_dict(),
                "interpretation": (
                    "Reject H0: variables are not independent (significant association)"
                    if p < 0.05 else
                    "Fail to reject H0: no significant association between variables"
                ),
            })

        elif test_type == "normality":
            col = kwargs.get("column")
            if not col:
                cols = df.select_dtypes(include=[np.number]).columns[:1]
                if len(cols) == 0:
                    return ToolResult.failure(
                        "No numeric columns found for normality test",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                col = cols[0]
            data = df[col].dropna()
            if len(data) < 3:
                return ToolResult.failure(
                    "Need at least 3 samples for normality test",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            if len(data) > 5000:
                data = data.sample(5000)
            stat, p = shapiro(data)
            result.update({
                "subtype": "shapiro_wilk",
                "column": col,
                "sample_size": len(data),
                "test_statistic": round(float(stat), 4),
                "p_value": round(float(p), 6),
                "significant": p < 0.05,
                "interpretation": (
                    "Data is NOT normally distributed (p < 0.05)"
                    if p < 0.05 else
                    "Data appears normally distributed (p >= 0.05)"
                ),
            })
        else:
            return ToolResult.failure(
                f"Unknown test_type: {test_type}. Choose: ttest, anova, chi_square, normality",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Hypothesis test ({result.get('subtype', test_type)}) complete",
            data=result,
            execution_time_ms=elapsed,
        )

    # ── 7. regression_analysis ──────────────────────────────────────────────

    async def _regression_analysis(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        target = kwargs.get("target")
        if not target:
            return ToolResult.failure(
                "regression_analysis requires a target column",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        features = kwargs.get("features")
        if not features:
            features = [
                c for c in df.select_dtypes(include=[np.number]).columns
                if c != target
            ]
        if not features:
            return ToolResult.failure(
                "No feature columns available for regression",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        model_df = df[[target] + features].dropna()
        if len(model_df) < 10:
            return ToolResult.failure(
                f"Need at least 10 samples after dropping NA; got {len(model_df)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        X = model_df[features].values
        y = model_df[target].values
        X_with_const = np.column_stack([np.ones(len(X)), X])
        n, k = X_with_const.shape

        try:
            beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
            y_pred = X_with_const @ beta
            residuals = y - y_pred
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k)
            mse = ss_res / (n - k)
            se_beta = np.sqrt(np.diag(np.linalg.inv(X_with_const.T @ X_with_const) * mse))
            t_stats = beta / se_beta
            p_values = 2 * (1 - scipy_stats.t.cdf(np.abs(t_stats), df=n - k)) if HAS_SCIPY else [None] * len(beta)

            f_stat = (ss_tot - ss_res) / (k - 1) / mse if mse > 0 else 0
            f_p_value = 1 - scipy_stats.f.cdf(f_stat, k - 1, n - k) if HAS_SCIPY else None

            coef_list = []
            feature_importance = []
            names = ["const"] + features
            for i, name in enumerate(names):
                coef_list.append({
                    "feature": name,
                    "coefficient": round(float(beta[i]), 6),
                    "std_error": round(float(se_beta[i]), 6),
                    "t_statistic": round(float(t_stats[i]), 4),
                    "p_value": round(float(p_values[i]), 6) if p_values[i] is not None else None,
                    "significant": p_values[i] is not None and p_values[i] < 0.05,
                })
                if i > 0:
                    feature_importance.append({
                        "feature": name,
                        "importance": round(abs(float(beta[i])), 6),
                    })

            feature_importance.sort(key=lambda x: x["importance"], reverse=True)

            residual_analysis = {}
            if HAS_SCIPY:
                try:
                    _, sw_p = shapiro(residuals)
                    residual_analysis["normality_test"] = {
                        "test": "shapiro_wilk",
                        "statistic": round(float(sw_p), 6),
                        "normal": sw_p > 0.05,
                        "interpretation": "Residuals are normal" if sw_p > 0.05 else "Residuals are NOT normal",
                    }
                except Exception:
                    pass
                try:
                    _, levene_p = levene(y_pred, residuals)
                    residual_analysis["homoscedasticity"] = {
                        "test": "levene",
                        "statistic": round(float(levene_p), 6),
                        "homoscedastic": levene_p > 0.05,
                    }
                except Exception:
                    pass

            result: Dict[str, Any] = {
                "target": target,
                "features": features,
                "num_samples": n,
                "num_features": k - 1,
                "r_squared": round(float(r_squared), 6),
                "adjusted_r_squared": round(float(adj_r_squared), 6),
                "f_statistic": round(float(f_stat), 4),
                "f_p_value": round(float(f_p_value), 6) if f_p_value is not None else None,
                "f_significant": f_p_value is not None and f_p_value < 0.05,
                "rmse": round(float(np.sqrt(mse)), 4),
                "mae": round(float(np.mean(np.abs(residuals))), 4),
                "coefficients": coef_list,
                "feature_importance_ranking": feature_importance,
                "residual_analysis": residual_analysis,
                "mean_target": round(float(np.mean(y)), 4),
                "std_target": round(float(np.std(y)), 4),
            }

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Regression: R²={r_squared:.4f}, adjR²={adj_r_squared:.4f}, "
                f"F={f_stat:.2f}, features={len(features)}",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Regression failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── 8. kpi_metrics ─────────────────────────────────────────────────────

    async def _kpi_metrics(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        metrics = kwargs.get("metrics", ["growth_rate", "running_total"])
        date_col = kwargs.get("date_column") or self._auto_detect_date_col(df)
        value_col = kwargs.get("value_column")
        group_col = kwargs.get("group_column")

        if not value_col:
            numeric = df.select_dtypes(include=[np.number]).columns
            if len(numeric) == 0:
                return ToolResult.failure(
                    "No numeric column found",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            value_col = numeric[0]

        result: Dict[str, Any] = {"metrics_computed": [], "data": {}}
        temp = df.copy()

        if date_col:
            try:
                temp[date_col] = pd.to_datetime(temp[date_col])
                if group_col:
                    temp = temp.sort_values([group_col, date_col])
                else:
                    temp = temp.sort_values(date_col)
            except Exception:
                pass

        for metric in metrics:
            if metric == "growth_rate":
                grp = temp.groupby(group_col) if group_col else temp
                grp = grp[value_col]
                growth = grp.pct_change() * 100
                result["data"]["growth_rate"] = {
                    "values": growth.round(2).tolist(),
                    "mean_growth": round(float(growth.mean()), 2) if not growth.isna().all() else 0,
                    "description": "Period-over-period percentage change",
                }
                result["metrics_computed"].append("growth_rate")

            elif metric == "running_total":
                grp = temp.groupby(group_col)[value_col].cumsum() if group_col else temp[value_col].cumsum()
                result["data"]["running_total"] = {
                    "values": grp.round(2).tolist(),
                    "final_total": round(float(grp.iloc[-1]), 2) if len(grp) > 0 else 0,
                    "description": "Cumulative sum",
                }
                result["metrics_computed"].append("running_total")

            elif metric == "yoy_comparison":
                if date_col:
                    temp["_year"] = temp[date_col].dt.year
                    if group_col:
                        yoy = temp.groupby([group_col, "_year"])[value_col].sum().groupby(group_col).pct_change() * 100
                    else:
                        yoy = temp.groupby("_year")[value_col].sum().pct_change() * 100
                    result["data"]["yoy_comparison"] = {
                        "values": yoy.round(2).to_dict() if isinstance(yoy, pd.Series) else yoy.round(2).tolist(),
                        "description": "Year-over-Year percentage change",
                    }
                    result["metrics_computed"].append("yoy_comparison")
                else:
                    result["data"]["yoy_comparison"] = {"error": "date_column required"}

            elif metric == "moving_average":
                window = kwargs.get("window", 7)
                grp = temp.groupby(group_col)[value_col] if group_col else temp[value_col]
                if group_col:
                    ma = grp.transform(lambda x: x.rolling(window, min_periods=1).mean())
                else:
                    ma = grp.rolling(window, min_periods=1).mean()
                result["data"]["moving_average"] = {
                    "window": window,
                    "values": ma.round(2).tolist(),
                    "description": f"Rolling {window}-period moving average",
                }
                result["metrics_computed"].append("moving_average")

            elif metric == "ema":
                span = kwargs.get("span", 7)
                grp = temp.groupby(group_col)[value_col] if group_col else temp[value_col]
                if group_col:
                    ema = grp.transform(lambda x: x.ewm(span=span, adjust=False).mean())
                else:
                    ema = grp.ewm(span=span, adjust=False).mean()
                result["data"]["ema"] = {
                    "span": span,
                    "values": ema.round(2).tolist(),
                    "description": f"Exponential moving average (span={span})",
                }
                result["metrics_computed"].append("ema")

            elif metric in ("pct_change", "percentage_change"):
                grp = temp.groupby(group_col)[value_col] if group_col else temp[value_col]
                pct = grp.pct_change() * 100
                result["data"]["percentage_change"] = {
                    "values": pct.round(2).tolist(),
                    "description": "Period-over-period percentage change",
                }
                result["metrics_computed"].append("percentage_change")

            elif metric == "rank":
                method = kwargs.get("rank_method", "dense")
                ascending = kwargs.get("rank_ascending", False)
                grp = temp.groupby(group_col)[value_col] if group_col else temp[value_col]
                rank = grp.rank(method=method, ascending=ascending)
                result["data"]["rank"] = {
                    "method": method,
                    "ascending": ascending,
                    "values": rank.astype(int).tolist(),
                    "description": f"Rank ({method} method)",
                }
                result["metrics_computed"].append("rank")

            elif metric == "rolling_stat":
                window = kwargs.get("window", 7)
                stat = kwargs.get("rolling_stat", "mean")
                grp = temp.groupby(group_col)[value_col] if group_col else temp[value_col]
                if stat == "mean":
                    rolled = grp.rolling(window, min_periods=1).mean()
                elif stat == "std":
                    rolled = grp.rolling(window, min_periods=1).std()
                elif stat == "min":
                    rolled = grp.rolling(window, min_periods=1).min()
                elif stat == "max":
                    rolled = grp.rolling(window, min_periods=1).max()
                else:
                    rolled = grp.rolling(window, min_periods=1).mean()
                result["data"]["rolling_stat"] = {
                    "window": window,
                    "stat": stat,
                    "values": rolled.round(2).tolist(),
                    "description": f"Rolling {stat} (window={window})",
                }
                result["metrics_computed"].append("rolling_stat")

        result["summary"] = {
            "value_column": value_col,
            "total_rows": len(temp),
            "metrics_count": len(result["metrics_computed"]),
        }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Computed {len(result['metrics_computed'])} KPI metric(s): {', '.join(result['metrics_computed'])}",
            data=result,
            execution_time_ms=elapsed,
        )

    # ── 9. etl_pipeline ─────────────────────────────────────────────────────

    async def _etl_pipeline(self, kwargs: Dict, start_time: float) -> ToolResult:
        log: List[str] = []
        log.append(f"ETL Pipeline started: {datetime.now().isoformat()}")

        source = kwargs.get("source", "")
        source_format = kwargs.get("source_format", "auto")
        transforms = kwargs.get("transforms", kwargs.get("transformations", []))
        target = kwargs.get("target", "")
        target_format = kwargs.get("target_format", "auto")
        df_name = kwargs.get("df_name", "etl_output")

        df: Optional[pd.DataFrame] = None

        # EXTRACT
        if source:
            path = Path(source)
            if not path.exists():
                return ToolResult.failure(
                    f"Source file not found: {source}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            ext = path.suffix.lower() if source_format == "auto" else f".{source_format}"
            try:
                if ext == ".csv":
                    df = pd.read_csv(source)
                elif ext in (".xlsx", ".xls"):
                    df = pd.read_excel(source)
                elif ext == ".json":
                    df = pd.read_json(source)
                elif ext in (".parquet", ".pq"):
                    df = pd.read_parquet(source)
                elif ext == ".sql":
                    if not HAS_SQLALCHEMY:
                        return ToolResult.failure(
                            "sqlalchemy required for SQL sources",
                            execution_time_ms=(time.time() - start_time) * 1000,
                        )
                    query = kwargs.get("query", "SELECT * FROM data")
                    conn_str = kwargs.get("connection_string", "")
                    engine = create_engine(conn_str)
                    df = pd.read_sql(query, engine)
                else:
                    return ToolResult.failure(
                        f"Unsupported source format: {ext}",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                log.append(f"Extracted: {len(df)} rows, {len(df.columns)} columns from {path.name}")
            except Exception as e:
                return ToolResult.error_result(
                    f"Extract failed: {e}", error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        else:
            try:
                df = self._get_df(kwargs)
                log.append(f"Using in-memory DataFrame: {len(df)} rows, {len(df.columns)} columns")
            except ValueError as e:
                return ToolResult.failure(
                    f"No source provided: {e}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        # TRANSFORM
        for t in transforms:
            op = t.get("operation", t.get("op", ""))
            step_start = time.time()
            before_rows = len(df)
            try:
                if op == "filter":
                    query_expr = t.get("query", "")
                    if query_expr:
                        df = df.query(query_expr)
                        log.append(f"  Filter [query='{query_expr}']: {before_rows} -> {len(df)} rows ({time.time() - step_start:.3f}s)")

                elif op == "sort":
                    by = t.get("by", t.get("columns", []))
                    ascending = t.get("ascending", t.get("asc", True))
                    df = df.sort_values(by=by, ascending=ascending)
                    log.append(f"  Sort by {by}: {time.time() - step_start:.3f}s")

                elif op == "groupby":
                    by = t.get("by", [])
                    agg = t.get("agg", t.get("aggregations", {}))
                    if by:
                        df = df.groupby(by).agg(agg).reset_index()
                        log.append(f"  GroupBy {by}: {before_rows} -> {len(df)} rows ({time.time() - step_start:.3f}s)")

                elif op == "aggregate":
                    by = t.get("by", [])
                    agg = t.get("agg", t.get("aggregations", {}))
                    if by:
                        df = df.groupby(by).agg(agg).reset_index()
                        log.append(f"  Aggregate {by}: {before_rows} -> {len(df)} rows ({time.time() - step_start:.3f}s)")

                elif op == "pivot":
                    idx = t.get("index")
                    cols = t.get("columns")
                    vals = t.get("values")
                    aggfunc = t.get("aggfunc", "mean")
                    if idx and cols and vals:
                        df = df.pivot_table(index=idx, columns=cols, values=vals, aggfunc=aggfunc).reset_index()
                        log.append(f"  Pivot: {before_rows} -> {len(df)} rows ({time.time() - step_start:.3f}s)")

                elif op in ("join", "merge"):
                    other_source = t.get("other_source")
                    other_df = None
                    if other_source:
                        other_path = Path(other_source)
                        if other_path.exists():
                            oext = other_path.suffix.lower()
                            if oext == ".csv":
                                other_df = pd.read_csv(other_source)
                            elif oext in (".xlsx", ".xls"):
                                other_df = pd.read_excel(other_source)
                            elif oext == ".json":
                                other_df = pd.read_json(other_source)
                            else:
                                other_df = pd.read_csv(other_source)
                    elif t.get("other_df_name"):
                        other_df = self._dataframes.get(t["other_df_name"])
                    elif t.get("other_data"):
                        other_df = pd.DataFrame(t["other_data"])
                    if other_df is not None:
                        on = t.get("on")
                        how = t.get("how", "inner")
                        df = df.merge(other_df, on=on, how=how)
                        log.append(f"  Merge ({how}): {before_rows} -> {len(df)} rows ({time.time() - step_start:.3f}s)")

                elif op == "add_column":
                    name = t.get("name", "")
                    expr = t.get("expression", t.get("value"))
                    if name and expr is not None:
                        try:
                            df[name] = eval(expr, {"df": df, "np": np, "pd": pd})
                        except Exception:
                            df[name] = expr
                        log.append(f"  Add column '{name}': {time.time() - step_start:.3f}s")

                elif op == "drop_column":
                    cols = t.get("columns", [])
                    df = df.drop(columns=[c for c in cols if c in df.columns])
                    log.append(f"  Drop columns {cols}: {time.time() - step_start:.3f}s")

                elif op == "rename":
                    mapping = t.get("mapping", {})
                    df = df.rename(columns=mapping)
                    log.append(f"  Rename columns: {time.time() - step_start:.3f}s")

                elif op == "fill_na":
                    strategy = t.get("strategy", "ffill")
                    value = t.get("value")
                    if strategy == "ffill":
                        df = df.ffill()
                    elif strategy == "bfill":
                        df = df.bfill()
                    elif strategy == "value" and value is not None:
                        df = df.fillna(value)
                    elif strategy == "mean":
                        df = df.fillna(df.select_dtypes(include=[np.number]).mean())
                    elif strategy == "median":
                        df = df.fillna(df.select_dtypes(include=[np.number]).median())
                    log.append(f"  Fill NA ({strategy}): {time.time() - step_start:.3f}s")

                elif op == "convert_type":
                    column = t.get("column", "")
                    dtype = t.get("dtype", "")
                    if column and dtype:
                        try:
                            if dtype == "datetime":
                                df[column] = pd.to_datetime(df[column])
                            elif dtype == "numeric":
                                df[column] = pd.to_numeric(df[column])
                            elif dtype == "str":
                                df[column] = df[column].astype(str)
                            elif dtype == "int":
                                df[column] = df[column].astype(int)
                            elif dtype == "float":
                                df[column] = df[column].astype(float)
                            log.append(f"  Convert '{column}' to {dtype}: {time.time() - step_start:.3f}s")
                        except Exception as e:
                            log.append(f"  Convert '{column}' to {dtype} FAILED: {e}")

                elif op == "drop_duplicates":
                    subset = t.get("subset")
                    df = df.drop_duplicates(subset=subset)
                    log.append(f"  Drop duplicates: {before_rows} -> {len(df)} rows ({time.time() - step_start:.3f}s)")

                else:
                    log.append(f"  Unknown operation '{op}' — skipped")

            except Exception as e:
                log.append(f"  ERROR in step '{op}': {e}")
                return ToolResult.error_result(
                    f"ETL transform '{op}' failed: {e}", error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        self._dataframes[df_name] = df

        # LOAD
        load_result = {}
        if target:
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                if target_format == "auto":
                    target_format = target_path.suffix.lower().lstrip(".")
                if target_format in ("csv", ""):
                    df.to_csv(target, index=False)
                elif target_format in ("xlsx", "excel"):
                    df.to_excel(target, index=False)
                elif target_format == "json":
                    df.to_json(target, orient="records", indent=2)
                elif target_format in ("parquet", "pq"):
                    df.to_parquet(target, index=False)
                elif target_format == "html":
                    df.to_html(target, index=False)
                else:
                    df.to_csv(target, index=False)
                log.append(f"Loaded: {len(df)} rows to {target}")
                load_result = {
                    "path": str(target_path.resolve()),
                    "format": target_format,
                    "file_size_kb": round(target_path.stat().st_size / 1024, 2) if target_path.exists() else 0,
                }
            except Exception as e:
                log.append(f"Load FAILED: {e}")
                return ToolResult.error_result(
                    f"ETL load failed: {e}", error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        else:
            log.append("No target specified; data cached in memory")

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"ETL Pipeline complete: {len(df)} rows output",
            data={
                "pipeline_log": log,
                "output_rows": len(df),
                "output_columns": len(df.columns),
                "output_columns_list": list(df.columns),
                "data_preview": df.head(5).to_dict(orient="records"),
                "load": load_result if load_result else None,
                "df_name": df_name,
            },
            execution_time_ms=elapsed,
        )

    # ── 10. filter_query ────────────────────────────────────────────────────

    async def _filter_query(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        original_rows = len(df)

        # Column selection
        columns = kwargs.get("columns")
        if columns:
            valid = [c for c in columns if c in df.columns]
            if not valid:
                return ToolResult.failure(
                    f"No valid columns found in {columns}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            df = df[valid]

        # Row filtering via pandas query
        query = kwargs.get("query", "")
        if query:
            try:
                df = df.query(query)
            except Exception as e:
                return ToolResult.failure(
                    f"Query syntax error: {e}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        # Row filtering via conditions
        conditions = kwargs.get("conditions", [])
        for cond in conditions:
            col = cond.get("column", "")
            op = cond.get("op", "==")
            val = cond.get("value")
            if col not in df.columns:
                continue
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > val]
            elif op == ">=":
                df = df[df[col] >= val]
            elif op == "<":
                df = df[df[col] < val]
            elif op == "<=":
                df = df[df[col] <= val]
            elif op == "in":
                df = df[df[col].isin(val)]
            elif op == "not_in":
                df = df[~df[col].isin(val)]
            elif op == "between":
                low, high = val[0], val[1]
                df = df[(df[col] >= low) & (df[col] <= high)]
            elif op == "contains":
                df = df[df[col].astype(str).str.contains(val, na=False, case=kwargs.get("case_sensitive", True))]
            elif op == "startswith":
                df = df[df[col].astype(str).str.startswith(val)]
            elif op == "endswith":
                df = df[df[col].astype(str).str.endswith(val)]
            elif op == "matches":
                df = df[df[col].astype(str).str.match(val)]

        # Null filtering
        null_handling = kwargs.get("null_handling")
        if null_handling == "drop":
            df = df.dropna()
        elif null_handling == "keep_only_null":
            df = df[df.isnull().any(axis=1)]

        # Sorting
        sort_by = kwargs.get("sort_by", [])
        if sort_by:
            ascending = kwargs.get("ascending", True)
            if isinstance(sort_by, str):
                sort_by = [sort_by]
            if isinstance(ascending, bool):
                ascending = [ascending] * len(sort_by)
            valid_sort = [(c, a) for c, a in zip(sort_by, ascending) if c in df.columns]
            if valid_sort:
                df = df.sort_values(by=[c for c, _ in valid_sort], ascending=[a for _, a in valid_sort])

        # Pagination
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", kwargs.get("max_results", 1000))
        total_filtered = len(df)
        df = df.iloc[offset:offset + limit]

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Filtered: {original_rows} -> {total_filtered} rows (showing {len(df)})",
            data={
                "original_rows": original_rows,
                "total_filtered_rows": total_filtered,
                "displayed_rows": len(df),
                "columns": list(df.columns),
                "offset": offset,
                "limit": limit,
                "data": df.to_dict(orient="records"),
                "query": query,
                "df_name": kwargs.get("df_name", "default"),
            },
            execution_time_ms=elapsed,
        )

    # ── 11. time_series_analysis ────────────────────────────────────────────

    async def _time_series_analysis(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)

        date_col = kwargs.get("date_column") or self._auto_detect_date_col(df)
        if not date_col:
            return ToolResult.failure(
                "Could not auto-detect date column",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        value_col = kwargs.get("value_column")
        if not value_col:
            numeric = df.select_dtypes(include=[np.number]).columns
            if len(numeric) == 0:
                return ToolResult.failure("No numeric column found", execution_time_ms=(time.time() - start_time) * 1000)
            value_col = numeric[0]

        try:
            ts = df[[date_col, value_col]].copy()
            ts[date_col] = pd.to_datetime(ts[date_col])
            ts = ts.set_index(date_col).sort_index()
            ts = ts[~ts.index.duplicated(keep="first")].dropna()
            ts = ts.squeeze()

            if len(ts) < 4:
                return ToolResult.failure(
                    f"Need at least 4 data points; got {len(ts)}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            result: Dict[str, Any] = {
                "date_column": date_col,
                "value_column": value_col,
                "data_points": len(ts),
                "start_date": str(ts.index[0].date()) if hasattr(ts.index[0], "date") else str(ts.index[0]),
                "end_date": str(ts.index[-1].date()) if hasattr(ts.index[-1], "date") else str(ts.index[-1]),
                "date_range_days": (ts.index[-1] - ts.index[0]).days,
                "basic_stats": {
                    "mean": round(float(ts.mean()), 4),
                    "std": round(float(ts.std()), 4),
                    "min": round(float(ts.min()), 4),
                    "max": round(float(ts.max()), 4),
                    "median": round(float(ts.median()), 4),
                    "skewness": round(float(ts.skew()), 4),
                    "kurtosis": round(float(ts.kurtosis()), 4),
                },
            }

            if HAS_STATSMODELS:
                try:
                    acf_vals = acf(ts, nlags=min(40, len(ts) // 2 - 1))
                    pacf_vals = pacf(ts, nlags=min(40, len(ts) // 2 - 1))
                    result["autocorrelation"] = {
                        "acf": {f"lag_{i}": round(float(v), 4) for i, v in enumerate(acf_vals) if not np.isnan(v)},
                        "pacf": {f"lag_{i}": round(float(v), 4) for i, v in enumerate(pacf_vals) if not np.isnan(v)},
                    }
                except Exception as e:
                    result["autocorrelation"] = {"error": str(e)}

                try:
                    adf_result = adfuller(ts.dropna(), autolag="AIC")
                    result["stationarity"] = {
                        "adf_test": {
                            "test_statistic": round(float(adf_result[0]), 6),
                            "p_value": round(float(adf_result[1]), 6),
                            "critical_values": {k: round(float(v), 4) for k, v in adf_result[4].items()},
                            "is_stationary": adf_result[1] < 0.05,
                            "interpretation": "Series is stationary" if adf_result[1] < 0.05 else "Series is NOT stationary (has unit root)",
                        },
                    }
                except Exception as e:
                    result["stationarity"] = {"adf_error": str(e)}

                try:
                    kpss_result = kpss(ts.dropna(), regression="c", nlags="auto")
                    result["stationarity"]["kpss_test"] = {
                        "test_statistic": round(float(kpss_result[0]), 6),
                        "p_value": round(float(kpss_result[1]), 6),
                        "is_stationary": kpss_result[1] >= 0.05,
                        "interpretation": "Series is stationary" if kpss_result[1] >= 0.05 else "Series is NOT stationary",
                    }
                except Exception as e:
                    result["stationarity"]["kpss_error"] = str(e)

                if len(ts) >= 14:
                    try:
                        period = kwargs.get("seasonal_period", min(7, len(ts) // 3))
                        decomp = seasonal_decompose(ts, model="additive", period=period)
                        trend_vals = {str(k.date()): (
                            float(v) if not pd.isna(v) else None
                        ) for k, v in decomp.trend.items()}
                        seasonal_vals = {str(k.date()): (
                            float(v) if not pd.isna(v) else None
                        ) for k, v in decomp.seasonal.items()}
                        resid_vals = {str(k.date()): (
                            float(v) if not pd.isna(v) else None
                        ) for k, v in decomp.resid.items()}

                        residual_vals = [v for v in decomp.resid.values if not pd.isna(v)]
                        randomness = float(np.std(residual_vals)) / float(ts.std()) if len(residual_vals) > 0 and float(ts.std()) > 0 else 0

                        result["seasonal_decomposition"] = {
                            "period": period,
                            "trend": trend_vals,
                            "seasonal": seasonal_vals,
                            "residual": resid_vals,
                            "residual_std_ratio": round(randomness, 4),
                            "has_strong_seasonality": randomness < 0.5,
                        }
                    except Exception as e:
                        result["seasonal_decomposition"] = {"error": str(e)}

            if not HAS_STATSMODELS:
                result["note"] = "Install statsmodels for ACF/PACF, ADF/KPSS, and seasonal decomposition"

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Time series analysis: {len(ts)} data points from {result['start_date']} to {result['end_date']}",
                data=result,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Time series analysis failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── 12. export_data ─────────────────────────────────────────────────────

    async def _export_data(self, kwargs: Dict, start_time: float) -> ToolResult:
        df = self._get_df(kwargs)
        output_path = kwargs.get("output_path", "")
        export_format = kwargs.get("export_format", kwargs.get("format", "auto"))

        if not output_path:
            output_path = str(DIRS.get("assets", BASE_DIR / "assets") / "exports" / f"export_{int(time.time())}.csv")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        output = Path(output_path)

        if export_format == "auto":
            export_format = output.suffix.lower().lstrip(".")

        if export_format in ("csv", ""):
            df.to_csv(output_path, index=False)
        elif export_format in ("xlsx", "excel"):
            df.to_excel(output_path, index=False)
        elif export_format == "json":
            orient = kwargs.get("json_orient", "records")
            df.to_json(output_path, orient=orient, indent=2)
        elif export_format in ("parquet", "pq"):
            df.to_parquet(output_path, index=False)
        elif export_format == "html":
            df.to_html(output_path, index=False)
        elif export_format == "markdown":
            output.write_text(df.to_markdown(index=False), encoding="utf-8")
        elif export_format == "clipboard":
            df.to_clipboard(index=False)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Copied {len(df)} rows to clipboard",
                data={"rows": len(df), "columns": list(df.columns)},
                execution_time_ms=elapsed,
            )
        else:
            return ToolResult.failure(
                f"Unsupported format: {export_format}. Supported: csv, xlsx, json, parquet, html, markdown, clipboard",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        file_size = round(output.stat().st_size / 1024, 2) if output.exists() else 0
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Exported {len(df)} rows to {output.name} ({export_format}, {file_size} KB)",
            data={
                "path": str(output.resolve()),
                "format": export_format,
                "rows": len(df),
                "columns": list(df.columns),
                "file_size_kb": file_size,
            },
            execution_time_ms=elapsed,
        )

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        self._dataframes.clear()
        self.logger.info("DataAnalysisTool cleaned up")
