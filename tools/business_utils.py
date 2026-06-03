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
ArynoxTech AI Agent - Business Data Utilities Tool
==================================================
Production-grade tool for data quality, profiling, validation,
PII detection, compliance checking, anomaly detection,
schema inference, and dataset merging.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

from tools.base_tool import BaseTool, ToolResult
from config.settings import DIRS, TOOL_CONFIG, SECURITY_CONFIG

logger = __import__("logging").getLogger(__name__)

try:
    import pandas as pd
except ImportError:
    pd = None


EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PHONE_PATTERN = re.compile(
    r"^\+?1?\d{9,15}$|^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$"
)
SSN_PATTERN = re.compile(r"^\d{3}-\d{2}-\d{4}$")
CC_PATTERN = re.compile(r"^\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}$")
IP_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)
PASSPORT_PATTERN = re.compile(r"^[A-Z]\d{7}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
AADHAAR_PATTERN = re.compile(r"^\d{4}\s?\d{4}\s?\d{4}$")
URL_PATTERN = re.compile(
    r"^https?://(?:[\w-]+\.)+[\w-]+(?:/[\w\-./?%&=]*)?$"
)


class BusinessUtilsTool(BaseTool):
    """
    Business data utilities tool providing data quality reports,
    schema validation, profiling, PII detection, compliance checks,
    anomaly detection, schema inference, and dataset merging.
    """

    name: str = "business_utils"
    description: str = (
        "Business data utilities: quality reports, schema validation, "
        "profiling, PII detection, compliance checks, anomaly detection, "
        "schema inference, and dataset merging."
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG.get("business_utils", {})
        self.supported_actions = {
            "data_quality_report": self._data_quality_report,
            "schema_validation": self._schema_validation,
            "data_profiling": self._data_profiling,
            "pii_detection": self._pii_detection,
            "compliance_check": self._compliance_check,
            "anomaly_detection": self._anomaly_detection,
            "data_schema_inference": self._data_schema_inference,
            "merge_datasets": self._merge_datasets,
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = kwargs.get("action", "data_quality_report")

        if pd is None:
            return ToolResult.failure(
                "pandas is required. Install with: pip install pandas",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        handler = self.supported_actions.get(action)
        if handler is None:
            return ToolResult.failure(
                f"Unknown action: {action}. "
                f"Supported: {list(self.supported_actions.keys())}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            return await handler(kwargs, start_time)
        except Exception as e:
            self.logger.exception(f"BusinessUtilsTool.{action} error: {e}")
            return ToolResult.error_result(
                f"{action} failed: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_df(self, kwargs: Dict) -> pd.DataFrame:
        data = kwargs.get("data")
        file_path = kwargs.get("file_path", "")

        if data is not None:
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return data

        if file_path:
            p = Path(file_path)
            if not p.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            ext = p.suffix.lower()
            if ext == ".csv":
                return pd.read_csv(file_path)
            if ext in (".xlsx", ".xls"):
                return pd.read_excel(file_path)
            if ext == ".json":
                return pd.read_json(file_path)
            raise ValueError(f"Unsupported file format: {ext}")

        raise ValueError(
            "No data source provided. Pass 'data' (list/dict/DataFrame) "
            "or 'file_path' (CSV/Excel/JSON)."
        )

    def _get_columns_or_all(
        self, df: pd.DataFrame, kwargs: Dict, dtype_filter: str = None
    ) -> List[str]:
        columns = kwargs.get("columns")
        if columns:
            cols = [c for c in columns if c in df.columns]
        else:
            cols = list(df.columns)
        if dtype_filter and cols:
            numeric = set(df.select_dtypes(include=[np.number]).columns)
            if dtype_filter == "numeric":
                cols = [c for c in cols if c in numeric]
            elif dtype_filter == "non_numeric":
                cols = [c for c in cols if c not in numeric]
        return cols

    # ── 1. Data Quality Report ──────────────────────────────────────────────

    async def _data_quality_report(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        total_rows = len(df)
        total_cells = total_rows * len(df.columns)
        report = {
            "overview": {
                "rows": total_rows,
                "columns": len(df.columns),
                "total_cells": total_cells,
                "column_names": list(df.columns),
            },
            "missing_values": {},
            "duplicates": {},
            "outliers": {},
            "constant_columns": [],
            "high_cardinality_columns": [],
            "skewed_columns": [],
            "mixed_type_columns": [],
            "recommendations": [],
            "quality_score": 100.0,
        }

        missing_penalty = 0.0
        duplicate_penalty = 0.0
        outlier_penalty = 0.0
        cardinality_penalty = 0.0
        constant_penalty = 0.0
        mixed_type_penalty = 0.0
        skew_penalty = 0.0

        # Missing values
        for col in df.columns:
            missing_count = int(df[col].isnull().sum())
            missing_pct = round(missing_count / total_rows * 100, 2) if total_rows else 0.0
            report["missing_values"][col] = {
                "count": missing_count,
                "percentage": missing_pct,
            }
            if missing_pct > 50:
                missing_penalty += 15
                report["recommendations"].append(
                    f"Column '{col}' has {missing_pct}% missing — consider dropping or imputing."
                )
            elif missing_pct > 20:
                missing_penalty += 8
                report["recommendations"].append(
                    f"Column '{col}' has {missing_pct}% missing — consider imputation."
                )
            elif missing_pct > 0:
                missing_penalty += 2

        # Duplicates
        dup_count = int(df.duplicated().sum())
        dup_pct = round(dup_count / total_rows * 100, 2) if total_rows else 0.0
        report["duplicates"] = {
            "count": dup_count,
            "percentage": dup_pct,
        }
        if dup_pct > 10:
            duplicate_penalty = 15
            report["recommendations"].append(
                f"Data has {dup_pct}% duplicate rows — consider deduplication."
            )
        elif dup_pct > 0:
            duplicate_penalty = dup_pct
            if dup_count > 0:
                report["recommendations"].append(
                    f"Found {dup_count} duplicate row(s)."
                )

        # Outliers (IQR)
        iqr_multiplier = float(kwargs.get("iqr_multiplier", 1.5))
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        total_outliers = 0
        outlier_columns = 0
        for col in numeric_cols:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - iqr_multiplier * iqr
            upper = q3 + iqr_multiplier * iqr
            outliers = df[(df[col] < lower) | (df[col] > upper)][col]
            outlier_count = int(outliers.notna().sum())
            outlier_pct = round(outlier_count / total_rows * 100, 2) if total_rows else 0.0
            report["outliers"][col] = {
                "count": outlier_count,
                "percentage": outlier_pct,
                "lower_bound": round(float(lower), 4) if not np.isnan(lower) else None,
                "upper_bound": round(float(upper), 4) if not np.isnan(upper) else None,
            }
            if outlier_pct > 5:
                outlier_columns += 1
                total_outliers += outlier_count
                outlier_penalty += 5
                report["recommendations"].append(
                    f"Column '{col}' has {outlier_pct}% outliers (IQR × {iqr_multiplier})."
                )

        # Constant columns
        for col in df.columns:
            if df[col].nunique(dropna=False) <= 1:
                report["constant_columns"].append(col)
                constant_penalty += 5
                report["recommendations"].append(
                    f"Column '{col}' is constant — consider dropping."
                )

        # High-cardinality columns
        high_card_threshold = kwargs.get("high_cardinality_threshold", 50)
        for col in df.columns:
            unique_count = df[col].nunique()
            if unique_count > high_card_threshold:
                report["high_cardinality_columns"].append({
                    "column": col,
                    "unique_count": unique_count,
                })
                cardinality_penalty += 3
                if unique_count > total_rows * 0.9:
                    report["recommendations"].append(
                        f"Column '{col}' has {unique_count} unique values "
                        f"(~{unique_count/total_rows*100:.0f}% cardinality) — possible ID column."
                    )

        # Skewed columns
        for col in numeric_cols:
            valid = df[col].dropna()
            if len(valid) < 2:
                continue
            skew = float(valid.skew())
            if abs(skew) > 1.0:
                report["skewed_columns"].append({
                    "column": col,
                    "skewness": round(skew, 4),
                    "direction": "right (positive)" if skew > 0 else "left (negative)",
                })
                skew_penalty += 4
                report["recommendations"].append(
                    f"Column '{col}' is skewed ({skew:.2f}) — consider log or Box-Cox transform."
                )

        # Mixed-type columns
        for col in df.columns:
            non_null = df[col].dropna()
            if len(non_null) < 2:
                continue
            types: Set[str] = set()
            for val in non_null.head(100):
                types.add(type(val).__name__)
            if len(types) > 1:
                report["mixed_type_columns"].append({
                    "column": col,
                    "types_found": sorted(types),
                })
                mixed_type_penalty += 8
                report["recommendations"].append(
                    f"Column '{col}' has mixed types ({', '.join(sorted(types))}) "
                    f"— consider type standardization."
                )

        # Overall quality score
        total_penalty = (
            missing_penalty
            + duplicate_penalty
            + outlier_penalty
            + cardinality_penalty
            + constant_penalty
            + mixed_type_penalty
            + skew_penalty
        )
        report["quality_score"] = max(0, min(100, round(100.0 - total_penalty, 2)))
        report["penalty_breakdown"] = {
            "missing_values": round(missing_penalty, 2),
            "duplicates": round(duplicate_penalty, 2),
            "outliers": round(outlier_penalty, 2),
            "high_cardinality": round(cardinality_penalty, 2),
            "constant_columns": round(constant_penalty, 2),
            "mixed_types": round(mixed_type_penalty, 2),
            "skewness": round(skew_penalty, 2),
            "total_penalty": round(total_penalty, 2),
        }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Data quality report generated — score: {report['quality_score']}/100, "
            f"{len(report['recommendations'])} recommendation(s)",
            data=report,
            execution_time_ms=elapsed,
        )

    # ── 2. Schema Validation ────────────────────────────────────────────────

    async def _schema_validation(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        schema = kwargs.get("schema")
        if schema is None:
            return ToolResult.failure(
                "Schema is required. Provide a dict of {column: type} or "
                "a JSON file path via 'schema_file'.",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        schema_file = kwargs.get("schema_file", "")
        if schema_file:
            sp = Path(schema_file)
            if not sp.exists():
                return ToolResult.failure(
                    f"Schema file not found: {schema_file}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            with open(sp, "r", encoding="utf-8") as f:
                schema = json.load(f)

        type_map: Dict[str, Any] = {
            "int": int,
            "integer": int,
            "float": float,
            "double": float,
            "str": str,
            "string": str,
            "text": str,
            "bool": bool,
            "boolean": bool,
            "datetime": "datetime",
            "email": "email",
            "phone": "phone",
            "url": "url",
        }

        nullable_default = kwargs.get("nullable_default", False)
        strict = kwargs.get("strict", False)

        results = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns_validated": list(schema.keys()),
            "errors": [],
            "row_errors": [],
            "passed": True,
            "summary": {},
        }

        for col, expected_type_raw in schema.items():
            if isinstance(expected_type_raw, dict):
                expected_type = expected_type_raw.get("type", "str")
                nullable = expected_type_raw.get("nullable", nullable_default)
                required = expected_type_raw.get("required", False)
                min_val = expected_type_raw.get("min")
                max_val = expected_type_raw.get("max")
                enum_vals = expected_type_raw.get("enum")
                pattern_str = expected_type_raw.get("pattern")
            else:
                expected_type = expected_type_raw
                nullable = nullable_default
                required = False
                min_val = max_val = enum_vals = pattern_str = None

            py_type = type_map.get(expected_type.lower() if isinstance(expected_type, str) else expected_type)
            if py_type is None:
                results["errors"].append(f"Unknown type '{expected_type}' for column '{col}'")
                continue

            if col not in df.columns:
                if required:
                    results["errors"].append(f"Required column '{col}' not found in data")
                    results["passed"] = False
                continue

            col_errors = []
            valid_count = 0
            null_count = 0
            invalid_count = 0

            for idx, val in df[col].items():
                row_idx = int(idx)
                if pd.isna(val) or val is None:
                    if not nullable:
                        col_errors.append({
                            "row": row_idx,
                            "value": None,
                            "error": f"Column '{col}' is null but not nullable",
                        })
                        invalid_count += 1
                    else:
                        null_count += 1
                    continue

                row_valid = True
                if py_type == int:
                    try:
                        float_val = float(val)
                        if float_val != int(float_val):
                            raise ValueError
                        val = int(float_val)
                    except (ValueError, TypeError):
                        row_valid = False
                elif py_type == float:
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        row_valid = False
                elif py_type == str:
                    val = str(val)
                elif py_type == bool:
                    if isinstance(val, str):
                        val = val.lower() in ("true", "1", "yes", "y")
                    elif isinstance(val, (int, float)):
                        val = bool(val)
                    elif not isinstance(val, bool):
                        row_valid = False
                elif py_type == "datetime":
                    try:
                        pd.to_datetime(val)
                    except (ValueError, TypeError):
                        row_valid = False
                elif py_type == "email":
                    if not isinstance(val, str) or not EMAIL_PATTERN.match(val):
                        row_valid = False
                elif py_type == "phone":
                    s = re.sub(r"[\s\-\(\)]", "", str(val))
                    if not PHONE_PATTERN.match(s):
                        row_valid = False
                elif py_type == "url":
                    if not isinstance(val, str) or not URL_PATTERN.match(val):
                        row_valid = False

                if not row_valid:
                    col_errors.append({
                        "row": row_idx,
                        "value": str(val)[:200] if not isinstance(val, str) else val[:200],
                        "error": f"Expected {expected_type}, got {type(val).__name__}",
                    })
                    invalid_count += 1
                else:
                    valid_count += 1

                if min_val is not None and isinstance(val, (int, float)):
                    if val < min_val:
                        col_errors.append({
                            "row": row_idx,
                            "value": val,
                            "error": f"Value {val} < minimum {min_val}",
                        })
                if max_val is not None and isinstance(val, (int, float)):
                    if val > max_val:
                        col_errors.append({
                            "row": row_idx,
                            "value": val,
                            "error": f"Value {val} > maximum {max_val}",
                        })
                if enum_vals is not None and val not in enum_vals:
                    col_errors.append({
                        "row": row_idx,
                        "value": val,
                        "error": f"Value not in allowed enum: {enum_vals}",
                    })
                if pattern_str is not None and isinstance(val, str):
                    if not re.match(pattern_str, val):
                        col_errors.append({
                            "row": row_idx,
                            "value": val[:200],
                            "error": f"Value does not match pattern '{pattern_str}'",
                        })

            if col_errors:
                results["passed"] = False
                if strict:
                    results["row_errors"].extend(col_errors)
                else:
                    results["row_errors"].append({
                        "column": col,
                        "error_count": len(col_errors),
                        "sample_errors": col_errors[:5],
                    })

            results["summary"][col] = {
                "expected_type": expected_type,
                "nullable": nullable,
                "required": required,
                "valid": valid_count,
                "null": null_count if nullable else 0,
                "invalid": invalid_count,
                "pass_rate": round(
                    valid_count / (valid_count + invalid_count) * 100, 2
                ) if (valid_count + invalid_count) > 0 else 0,
            }

        results["total_errors"] = len(results["row_errors"])

        elapsed = (time.time() - start_time) * 1000
        status = "passed" if results["passed"] else "failed"
        return ToolResult.success(
            f"Schema validation {status}: {results['total_errors']} error(s) "
            f"across {len(results['columns_validated'])} column(s)",
            data=results,
            execution_time_ms=elapsed,
        )

    # ── 3. Data Profiling ───────────────────────────────────────────────────

    async def _data_profiling(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        profile: Dict[str, Any] = {
            "overview": {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "memory_usage_mb": round(
                    df.memory_usage(deep=True).sum() / 1024 / 1024, 2
                ),
                "duplicate_rows": int(df.duplicated().sum()),
                "total_missing_cells": int(df.isnull().sum().sum()),
            },
            "column_statistics": {},
            "column_types": {},
            "correlation_matrix": {},
            "quantile_summary": {},
            "value_distributions": {},
        }

        # Auto-detect column types
        for col in df.columns:
            col_type = self._detect_column_type(df[col])
            profile["column_types"][col] = col_type

        # Column statistics
        for col in df.columns:
            s = df[col]
            non_null = s.dropna()
            stats: Dict[str, Any] = {
                "count": int(s.count()),
                "nulls": int(s.isnull().sum()),
                "null_pct": round(s.isnull().sum() / len(s) * 100, 2) if len(s) else 0.0,
                "unique": int(s.nunique()),
                "dtype": str(s.dtype),
                "inferred_type": profile["column_types"][col],
            }

            if s.nunique() > 0:
                mode_series = s.mode()
                stats["mode"] = (
                    str(mode_series.iloc[0]) if not mode_series.empty else None
                )
                freq = (s == stats["mode"]).sum() if stats["mode"] is not None else None
                stats["mode_frequency"] = int(freq) if freq is not None else None

            if np.issubdtype(s.dtype, np.number) and len(non_null) > 0:
                stats.update({
                    "mean": round(float(non_null.mean()), 4),
                    "std": round(float(non_null.std()), 4),
                    "min": round(float(non_null.min()), 4),
                    "max": round(float(non_null.max()), 4),
                    "median": round(float(non_null.median()), 4),
                    "sum": round(float(non_null.sum()), 4),
                    "skewness": round(float(non_null.skew()), 4),
                    "kurtosis": round(float(non_null.kurtosis()), 4),
                    "variance": round(float(non_null.var()), 4),
                    "range": round(float(non_null.max() - non_null.min()), 4),
                })

            profile["column_statistics"][col] = stats

        # Quantile summary (numeric only)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols):
            profile["quantile_summary"] = df[numeric_cols].describe(
                percentiles=[0.05, 0.25, 0.50, 0.75, 0.95]
            ).round(4).to_dict()

        # Correlation matrix
        if len(numeric_cols) >= 2:
            corr = df[numeric_cols].corr()
            profile["correlation_matrix"] = {
                str(c): corr[c].round(4).to_dict() for c in corr.columns
            }

        # Value distributions for categorical columns
        for col in df.columns:
            ctype = profile["column_types"][col]
            if ctype in ("categorical", "text") or df[col].nunique() <= 50:
                vc = df[col].value_counts(dropna=False).head(10)
                profile["value_distributions"][col] = {
                    "top_values": {
                        str(k): int(v) for k, v in vc.items()
                    },
                    "unique_count": int(df[col].nunique()),
                }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Profiled {len(df)} rows × {len(df.columns)} columns",
            data=profile,
            execution_time_ms=elapsed,
        )

    def _detect_column_type(self, series: pd.Series) -> str:
        if np.issubdtype(series.dtype, np.number):
            return "numeric"
        if series.dtype == bool:
            return "boolean"
        if series.dtype == "datetime64[ns]" or series.dtype == "<M8[ns]":
            return "datetime"

        non_null = series.dropna()
        if len(non_null) < 2:
            return "text"

        try:
            pd.to_datetime(non_null.head(100), errors="raise")
            return "datetime"
        except (ValueError, TypeError):
            pass

        if series.nunique() <= 50:
            return "categorical"

        return "text"

    # ── 4. PII Detection ────────────────────────────────────────────────────

    async def _pii_detection(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        sample_size = kwargs.get("sample_size", 1000)

        pii_patterns: Dict[str, Tuple[re.Pattern, float]] = {
            "email": (EMAIL_PATTERN, 0.95),
            "phone": (PHONE_PATTERN, 0.85),
            "ssn": (SSN_PATTERN, 0.98),
            "credit_card": (CC_PATTERN, 0.90),
            "ip_address": (IP_PATTERN, 0.80),
            "passport": (PASSPORT_PATTERN, 0.85),
            "pan": (PAN_PATTERN, 0.95),
            "aadhaar": (AADHAAR_PATTERN, 0.90),
        }

        column_names_lower = {c: c.lower() for c in df.columns}

        # Name-based hints
        name_hints: Dict[str, List[str]] = {
            "email": ["email", "e-mail", "mail"],
            "phone": ["phone", "mobile", "cell", "telephone", "contact"],
            "ssn": ["ssn", "social security", "socialsecurity"],
            "credit_card": ["credit", "card", "cc", "cc_number", "cardnumber"],
            "ip_address": ["ip", "ip_address", "ipaddress"],
            "passport": ["passport"],
            "pan": ["pan", "pan_number"],
            "aadhaar": ["aadhaar", "aadhar", "uid", "uidai"],
        }

        results: Dict[str, Dict[str, Any]] = {}
        sample_df = df.head(sample_size)

        for pii_type, (pattern, base_confidence) in pii_patterns.items():
            matching_columns = []

            for col in df.columns:
                col_lower = column_names_lower[col]
                confidence = 0.0
                match_count = 0
                total_valid = 0

                # Name-based boost
                hints = name_hints.get(pii_type, [])
                hint_match = any(h in col_lower for h in hints)
                if hint_match:
                    confidence += 0.3

                # Content-based check
                non_null = sample_df[col].dropna().astype(str)
                total_valid = len(non_null)
                if total_valid == 0:
                    continue

                matches = non_null.str.match(pattern)
                match_count = int(matches.sum())
                match_rate = match_count / total_valid if total_valid else 0

                if match_rate >= 0.5:
                    confidence += 0.6 * match_rate
                elif match_rate > 0.1:
                    confidence += 0.2

                if confidence > 0:
                    matching_columns.append({
                        "column": col,
                        "confidence": round(min(confidence, 1.0), 4),
                        "match_rate": round(match_rate, 4),
                        "sample_matches": non_null[matches].head(5).tolist()
                        if match_count > 0 else [],
                    })

            if matching_columns:
                results[pii_type] = {
                    "columns": matching_columns,
                    "max_confidence": max(c["confidence"] for c in matching_columns),
                    "detected": True,
                }

        # Masking suggestions
        masking_suggestions = []
        for pii_type, info in results.items():
            for col_info in info["columns"]:
                if col_info["confidence"] >= 0.7:
                    masking_suggestions.append({
                        "column": col_info["column"],
                        "pii_type": pii_type,
                        "confidence": col_info["confidence"],
                        "suggested_mask": self._get_mask_pattern(pii_type),
                    })

        pii_found = len(results) > 0
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"PII detection complete: {len(results)} PII type(s) detected"
            if pii_found else "No PII detected in the dataset",
            data={
                "pii_found": pii_found,
                "pii_types_detected": list(results.keys()),
                "details": results,
                "masking_suggestions": masking_suggestions,
            },
            execution_time_ms=elapsed,
        )

    def _get_mask_pattern(self, pii_type: str) -> str:
        masks = {
            "email": "****@***.***",
            "phone": "***-***-****",
            "ssn": "***-**-****",
            "credit_card": "****-****-****-****",
            "ip_address": "***.***.*.*",
            "passport": "*******",
            "pan": "*********",
            "aadhaar": "****-****-****",
        }
        return masks.get(pii_type, "***")

    # ── 5. Compliance Check ─────────────────────────────────────────────────

    async def _compliance_check(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        retention_days = kwargs.get("retention_days", 365)
        data_purpose = kwargs.get("data_purpose", "Not specified")
        data_controller = kwargs.get("data_controller", "ArynoxTech")

        # Run PII detection first
        pii_data = None
        try:
            pii_result = await self._pii_detection({**kwargs, "data": df}, start_time)
            if pii_result.status.name == "SUCCESS":
                pii_data = pii_result.data
        except Exception:
            pass

        report: Dict[str, Any] = {
            "compliance_framework": "GDPR (General Data Protection Regulation)",
            "data_controller": data_controller,
            "data_purpose": data_purpose,
            "retention_period_days": retention_days,
            "dataset_overview": {
                "rows": len(df),
                "columns": len(df.columns),
            },
            "pii_assessment": pii_data or {"pii_found": False},
            "checks": {},
            "violations": [],
            "recommendations": [],
            "overall_status": "compliant",
        }

        checks = report["checks"]

        # 1. Data retention check
        checks["data_retention"] = {
            "status": "pass",
            "retention_days": retention_days,
            "message": f"Data retention period set to {retention_days} days.",
        }

        # 2. PII consent tracking
        if pii_data and pii_data.get("pii_found"):
            pii_types = pii_data.get("pii_types_detected", [])
            checks["consent_tracking"] = {
                "status": "review",
                "pii_types_found": pii_types,
                "message": (
                    f"Found {len(pii_types)} PII type(s): {', '.join(pii_types)}. "
                    "Ensure consent records are maintained.",
                ),
            }
            report["violations"].append(
                f"PII data detected ({', '.join(pii_types)}) — consent tracking required."
            )
            report["recommendations"].append(
                "Maintain consent records for all PII data subjects. "
                "Implement 'right to be forgotten' mechanism."
            )
        else:
            checks["consent_tracking"] = {
                "status": "pass",
                "message": "No PII detected — consent tracking not required.",
            }

        # 3. Data anonymization
        anonymization_checks = []
        for col in df.columns:
            s = df[col]
            if s.nunique() == len(s):
                anonymization_checks.append(
                    f"Column '{col}' has all unique values — possible identifier."
                )
        if anonymization_checks:
            checks["anonymization"] = {
                "status": "review",
                "details": anonymization_checks[:5],
                "message": "Potential identifiers found — consider anonymization.",
            }
            for ac in anonymization_checks[:3]:
                report["violations"].append(ac)
            report["recommendations"].append(
                "Apply anonymization or pseudonymization to direct identifiers."
            )
        else:
            checks["anonymization"] = {
                "status": "pass",
                "message": "No obvious identifiers detected.",
            }

        # 4. Data minimization
        total_cells = len(df) * len(df.columns)
        useful_cells = int(df.notna().sum().sum())
        utility_pct = round(useful_cells / total_cells * 100, 2) if total_cells else 0
        checks["data_minimization"] = {
            "status": "pass" if utility_pct > 50 else "review",
            "completeness_pct": utility_pct,
            "message": (
                f"Data completeness is {utility_pct}%."
                if utility_pct > 50
                else f"Data completeness is only {utility_pct}% — review collection practices."
            ),
        }
        if utility_pct <= 50:
            report["recommendations"].append(
                "Review data collection practices — only collect data necessary "
                "for the stated purpose."
            )

        # 5. Storage security
        checks["storage_security"] = {
            "status": "info",
            "message": "Ensure data is encrypted at rest and in transit. "
            "Implement access controls.",
        }

        if report["violations"]:
            report["overall_status"] = "non_compliant"
        elif any(
            chk.get("status") == "review" for chk in checks.values()
        ):
            report["overall_status"] = "needs_review"

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Compliance check ({report['compliance_framework']}): "
            f"{report['overall_status']} — {len(report['violations'])} violation(s)",
            data=report,
            execution_time_ms=elapsed,
        )

    # ── 6. Anomaly Detection ────────────────────────────────────────────────

    async def _anomaly_detection(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        method = kwargs.get("method", "zscore")
        threshold = float(kwargs.get("threshold", 3.0))
        columns = self._get_columns_or_all(df, kwargs, dtype_filter="numeric")

        if not columns:
            return ToolResult.failure(
                "No numeric columns found for anomaly detection",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        per_column: Dict[str, Any] = {}
        all_anomalous_rows: Set[int] = set()
        total_anomalies = 0

        for col in columns:
            valid = df[col].dropna()
            if len(valid) < 3:
                per_column[col] = {
                    "error": "Insufficient data (need >= 3 non-null values)",
                    "anomaly_count": 0,
                }
                continue

            scores = None
            anomaly_mask = None

            if method == "zscore":
                mean = valid.mean()
                std = valid.std()
                if std == 0:
                    per_column[col] = {
                        "error": "Zero variance — all values identical",
                        "anomaly_count": 0,
                    }
                    continue
                scores = (valid - mean).abs() / std
                anomaly_mask = scores > threshold

            elif method == "iqr":
                q1 = valid.quantile(0.25)
                q3 = valid.quantile(0.75)
                iqr = q3 - q1
                if iqr == 0:
                    per_column[col] = {
                        "error": "Zero IQR — insufficient variation",
                        "anomaly_count": 0,
                    }
                    continue
                iqr_threshold = float(kwargs.get("iqr_multiplier", 1.5))
                lower = q1 - iqr_threshold * iqr
                upper = q3 + iqr_threshold * iqr
                scores = valid.copy()
                anomaly_mask = (valid < lower) | (valid > upper)

            elif method == "mad":
                median = valid.median()
                abs_dev = (valid - median).abs()
                mad = abs_dev.median()
                if mad == 0:
                    per_column[col] = {
                        "error": "Zero MAD — all identical values",
                        "anomaly_count": 0,
                    }
                    continue
                scores = abs_dev / mad
                anomaly_mask = scores > threshold

            else:
                return ToolResult.failure(
                    f"Unknown anomaly method: {method}. "
                    f"Supported: zscore, iqr, mad",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if anomaly_mask is not None:
                anomaly_indices = set(valid[anomaly_mask].index.tolist())
                all_anomalous_rows |= anomaly_indices
                anomaly_count = len(anomaly_indices)
                total_anomalies += anomaly_count

                per_column[col] = {
                    "anomaly_count": anomaly_count,
                    "anomaly_pct": round(
                        anomaly_count / len(valid) * 100, 2
                    ),
                    "threshold_used": threshold,
                    "method": method,
                    "anomaly_indices": sorted(anomaly_indices)[:100],
                    "stats": {
                        "mean": round(float(valid.mean()), 4),
                        "std": round(float(valid.std()), 4) if method == "zscore" else None,
                        "q1": round(float(valid.quantile(0.25)), 4) if method == "iqr" else None,
                        "q3": round(float(valid.quantile(0.75)), 4) if method == "iqr" else None,
                        "median": round(float(valid.median()), 4) if method == "mad" else None,
                        "mad": round(float(mad), 4) if method == "mad" else None,
                    },
                }

        # Build anomalous rows output
        anomalous_rows_df = df.iloc[list(all_anomalous_rows)]
        anomalous_rows = []
        for idx, row in anomalous_rows_df.iterrows():
            row_dict = {"row_index": int(idx)}
            for col in columns:
                if idx in per_column.get(col, {}).get("anomaly_indices", []):
                    row_dict[col] = {
                        "value": row[col],
                        "is_anomaly": True,
                    }
                else:
                    row_dict[col] = {
                        "value": row[col] if pd.notna(row[col]) else None,
                        "is_anomaly": False,
                    }
            anomalous_rows.append(row_dict)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Anomaly detection ({method}): {total_anomalies} anomaly(ies) "
            f"across {len(columns)} column(s)",
            data={
                "method": method,
                "threshold": threshold,
                "columns_analyzed": columns,
                "total_anomalies": total_anomalies,
                "anomalous_row_count": len(all_anomalous_rows),
                "per_column": per_column,
                "anomalous_rows": anomalous_rows[:200],
            },
            execution_time_ms=elapsed,
        )

    # ── 7. Data Schema Inference ─────────────────────────────────────────────

    async def _data_schema_inference(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        df = self._get_df(kwargs)
        sample_size = kwargs.get("sample_size", 1000)
        include_stats = kwargs.get("include_stats", True)

        schema: Dict[str, Any] = {
            "title": "Inferred Schema",
            "type": "object",
            "properties": {},
            "required": [],
            "statistics": {} if include_stats else None,
        }

        sample_df = df.head(sample_size)

        for col in df.columns:
            s = sample_df[col]
            non_null = s.dropna()
            col_type = self._detect_column_type(s)
            prop: Dict[str, Any] = {
                "type": col_type,
                "dtype": str(s.dtype),
                "nullable": bool(s.isnull().any()),
                "unique_count": int(s.nunique()),
                "null_count": int(s.isnull().sum()),
            }

            if col_type == "numeric":
                prop["numeric_type"] = "float" if "float" in str(s.dtype) else "integer"
                if len(non_null) > 0:
                    prop["minimum"] = round(float(non_null.min()), 6)
                    prop["maximum"] = round(float(non_null.max()), 6)
                    prop["mean"] = round(float(non_null.mean()), 6)
                if s.nunique() <= 20:
                    uniq_vals = sorted(non_null.unique())
                    prop["enum"] = [
                        float(v) if isinstance(v, (np.floating,)) else int(v)
                        for v in uniq_vals
                    ]

            elif col_type == "categorical":
                uniq_vals = non_null.unique().tolist()
                if len(uniq_vals) <= 50:
                    prop["enum"] = [str(v) for v in uniq_vals]
                prop["categorical"] = True

            elif col_type == "datetime":
                if len(non_null) > 0:
                    try:
                        parsed = pd.to_datetime(non_null)
                        prop["minimum"] = parsed.min().isoformat()
                        prop["maximum"] = parsed.max().isoformat()
                    except Exception:
                        pass

            elif col_type == "boolean":
                prop["type"] = "boolean"
                prop["enum"] = [True, False]

            else:
                prop["type"] = "string"
                if s.nunique() <= 50 and len(non_null) > 0:
                    prop["enum"] = [str(v) for v in non_null.unique()]
                if s.nunique() == len(non_null):
                    prop["is_unique"] = True

            # Detect nested/list types
            if len(non_null) > 0:
                sample_val = non_null.iloc[0]
                if isinstance(sample_val, (list, tuple)):
                    prop["type"] = "array"
                    elem_types = set()
                    for v in non_null.head(100):
                        if isinstance(v, (list, tuple)) and len(v) > 0:
                            elem_types.add(type(v[0]).__name__)
                    prop["items"] = {"type": list(elem_types) if elem_types else "unknown"}
                elif isinstance(sample_val, dict):
                    prop["type"] = "object"

            schema["properties"][col] = prop

            if not prop.get("nullable", True):
                schema["required"].append(col)

        if include_stats:
            schema["statistics"] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "memory_mb": round(
                    df.memory_usage(deep=True).sum() / 1024 / 1024, 2
                ),
            }

        # Generate compatibility mapping for schema_validation
        type_mapping: Dict[str, str] = {}
        for col, prop in schema["properties"].items():
            type_mapping[col] = prop.get("type", "string")

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Schema inferred for {len(df.columns)} column(s) from {len(df)} rows",
            data={
                "schema": schema,
                "validation_schema": type_mapping,
                "columns_inferred": len(df.columns),
            },
            execution_time_ms=elapsed,
        )

    # ── 8. Merge Datasets ───────────────────────────────────────────────────

    async def _merge_datasets(
        self, kwargs: Dict, start_time: float
    ) -> ToolResult:
        left_data = kwargs.get("left_data")
        right_data = kwargs.get("right_data")
        left_file = kwargs.get("left_file", "")
        right_file = kwargs.get("right_file", "")

        # Load left
        if left_data is not None:
            left_df = pd.DataFrame(left_data) if isinstance(left_data, list) else left_data
        elif left_file:
            left_df = self._get_df({"file_path": left_file})
        else:
            return ToolResult.failure(
                "Left dataset required: pass 'left_data' or 'left_file'",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Load right
        if right_data is not None:
            right_df = pd.DataFrame(right_data) if isinstance(right_data, list) else right_data
        elif right_file:
            right_df = self._get_df({"file_path": right_file})
        else:
            return ToolResult.failure(
                "Right dataset required: pass 'right_data' or 'right_file'",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        how = kwargs.get("how", "inner")
        if how not in ("inner", "left", "right", "outer"):
            return ToolResult.failure(
                f"Invalid join type '{how}'. Supported: inner, left, right, outer",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        on = kwargs.get("on")
        left_on = kwargs.get("left_on")
        right_on = kwargs.get("right_on")
        suffixes = kwargs.get("suffixes", ("_x", "_y"))
        indicator = kwargs.get("indicator", False)

        # Auto-detect common columns if 'on' not specified
        auto_detected = False
        if on is None and left_on is None:
            common = set(left_df.columns) & set(right_df.columns)
            if not common:
                return ToolResult.failure(
                    "No common columns found for merge. Specify 'on', "
                    "'left_on'/'right_on', or ensure datasets share column names.",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            on = list(common)
            auto_detected = True

        left_before = len(left_df)
        right_before = len(right_df)

        merge_kwargs: Dict[str, Any] = {
            "how": how,
            "suffixes": suffixes,
            "indicator": indicator,
        }
        if on is not None:
            merge_kwargs["on"] = on
        if left_on is not None and right_on is not None:
            merge_kwargs["left_on"] = left_on
            merge_kwargs["right_on"] = right_on

        result_df = left_df.merge(right_df, **merge_kwargs)

        merge_stats: Dict[str, Any] = {
            "left_rows_before": left_before,
            "right_rows_before": right_before,
            "result_rows": len(result_df),
            "join_type": how,
            "merge_columns": on if on else {"left_on": left_on, "right_on": right_on},
            "auto_detected_columns": auto_detected,
        }

        if indicator:
            _indicator_col = "_merge" if indicator is True else indicator
            if _indicator_col in result_df.columns:
                merge_stats["merge_indicator"] = (
                    result_df[_indicator_col].value_counts().to_dict()
                )

        # Validate merge integrity
        if on:
            for col in on if isinstance(on, list) else [on]:
                if col in result_df.columns:
                    left_only = left_before - result_df[col].isin(left_df[col]).sum()
                    merge_stats[f"{col}_integrity"] = {
                        "left_unique": int(left_df[col].nunique()),
                        "right_unique": int(right_df[col].nunique()),
                        "result_unique": int(result_df[col].nunique()),
                    }

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Merge ({how}): {left_before} × {right_before} → {len(result_df)} rows, "
            f"{len(result_df.columns)} columns",
            data={
                "merge_statistics": merge_stats,
                "result_columns": list(result_df.columns),
                "result_preview": result_df.head(20).to_dict(orient="records"),
                "result_rows": len(result_df),
                "result_columns_count": len(result_df.columns),
            },
            execution_time_ms=elapsed,
        )
