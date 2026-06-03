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
ArynoxTech AI Agent - Data Entry Tool
======================================
Tool for automated data entry, form filling, batch data import/export,
and data validation. Handles structured data operations efficiently.
"""

import asyncio
import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


class DataEntryTool(BaseTool):
    """
    Tool for data entry and data management tasks.
    - CSV/JSON file creation and editing
    - Batch data import from multiple formats
    - Data validation and cleaning
    - Form data generation and management
    - Contact/record management (CRUD operations)
    - Auto-fill and template-based data entry
    """

    name: str = "data_entry_tool"
    description: str = "Create, edit, validate, and manage data entries. Supports CSV, JSON, batch imports, and contact management."
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG.get("data_entry", {})
        self._records: Dict[str, List[Dict]] = {}  # Named records collections
        self._data_dir = Path(self.config.get("data_dir", "data/records"))
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute data entry operation.

        Args:
            action: 'create_csv', 'create_json', 'import_data', 'validate_data',
                    'add_record', 'update_record', 'delete_record', 'list_records',
                    'batch_import', 'generate_form', 'export_records', 'search_records'
            file_path: Path for file operations
            data: Data to process (list of dicts or single dict)
            collection: Name of record collection
            query: Search/filter query
            format: Data format (csv, json)

        Returns:
            ToolResult with operation outcome
        """
        start_time = time.time()
        action = kwargs.get("action", "import_data")

        try:
            if action == "create_csv":
                return await self._create_csv(kwargs, start_time)
            elif action == "create_json":
                return await self._create_json(kwargs, start_time)
            elif action == "import_data":
                return await self._import_data(kwargs, start_time)
            elif action == "validate_data":
                return await self._validate_data(kwargs, start_time)
            elif action == "add_record":
                return await self._add_record(kwargs, start_time)
            elif action == "update_record":
                return await self._update_record(kwargs, start_time)
            elif action == "delete_record":
                return await self._delete_record(kwargs, start_time)
            elif action == "list_records":
                return await self._list_records(kwargs, start_time)
            elif action == "batch_import":
                return await self._batch_import(kwargs, start_time)
            elif action == "generate_form":
                return await self._generate_form(kwargs, start_time)
            elif action == "export_records":
                return await self._export_records(kwargs, start_time)
            elif action == "search_records":
                return await self._search_records(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.logger.exception(f"Data entry tool error: {e}")
            return ToolResult.error_result(
                f"Data entry failed: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _create_csv(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Create a CSV file from data."""
        file_path = kwargs.get("file_path", "data.csv")
        data = kwargs.get("data", [])
        fieldnames = kwargs.get("fieldnames", [])

        if not data:
            return ToolResult.failure(
                "No data provided for CSV creation",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Convert single dict to list
            if isinstance(data, dict):
                data = [data]

            # Auto-detect fieldnames if not provided
            if not fieldnames and data:
                fieldnames = list(data[0].keys())

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Created CSV: {path.name} with {len(data)} records",
                data={
                    "path": str(path.resolve()),
                    "records": len(data),
                    "fieldnames": fieldnames,
                    "file_size_kb": round(path.stat().st_size / 1024, 2),
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"CSV creation failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _create_json(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Create a JSON file from data."""
        file_path = kwargs.get("file_path", "data.json")
        data = kwargs.get("data", [])
        pretty = kwargs.get("pretty", True)

        if not data:
            return ToolResult.failure(
                "No data provided for JSON creation",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                if pretty:
                    json.dump(data, f, indent=2, default=str)
                else:
                    json.dump(data, f, default=str)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Created JSON: {path.name} with {len(data) if isinstance(data, list) else 1} records",
                data={
                    "path": str(path.resolve()),
                    "type": "list" if isinstance(data, list) else "object",
                    "file_size_kb": round(path.stat().st_size / 1024, 2),
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"JSON creation failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _import_data(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Import data from a file and store in memory/cache."""
        file_path = kwargs.get("file_path", "")
        collection = kwargs.get("collection", "default")
        file_format = kwargs.get("format", "auto")

        if not file_path:
            return ToolResult.failure(
                "No file_path provided for import",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult.failure(
                    f"File not found: {file_path}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            ext = path.suffix.lower() if file_format == "auto" else f".{file_format}"
            records = []

            if ext == ".csv":
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    records = list(reader)
            elif ext == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    records = data if isinstance(data, list) else [data]
            elif ext == ".txt":
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append({"line": line})
            else:
                return ToolResult.failure(
                    f"Unsupported import format: {ext}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            self._records[collection] = records

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Imported {len(records)} records from {path.name} into collection '{collection}'",
                data={
                    "collection": collection,
                    "records_imported": len(records),
                    "source": path.name,
                    "preview": records[:5] if records else [],
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Import failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _validate_data(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Validate data against rules and constraints."""
        data = kwargs.get("data", [])
        rules = kwargs.get("rules", {})
        collection = kwargs.get("collection", "default")

        # Get data from collection if no direct data
        if not data and collection in self._records:
            data = self._records[collection]

        if not data:
            return ToolResult.failure(
                "No data to validate",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if isinstance(data, dict):
            data = [data]

        try:
            validation_results = {
                "total_records": len(data),
                "valid_records": 0,
                "invalid_records": 0,
                "errors": [],
                "warnings": [],
            }

            for i, record in enumerate(data):
                record_errors = []
                
                # Required fields validation
                required_fields = rules.get("required_fields", [])
                for field in required_fields:
                    if field not in record or record[field] in (None, "", " "):
                        record_errors.append(f"Record {i+1}: Missing required field '{field}'")

                # Type validation
                type_rules = rules.get("types", {})
                for field, expected_type in type_rules.items():
                    if field in record and record[field] not in (None, ""):
                        value = record[field]
                        if expected_type == "number":
                            try:
                                float(value)
                            except (ValueError, TypeError):
                                record_errors.append(f"Record {i+1}: Field '{field}' should be a number, got '{value}'")
                        elif expected_type == "email":
                            if "@" not in str(value):
                                record_errors.append(f"Record {i+1}: Field '{field}' should be an email, got '{value}'")
                        elif expected_type == "phone":
                            cleaned = str(value).replace("-", "").replace(" ", "").replace("+", "")
                            if not cleaned.isdigit() or len(cleaned) < 7:
                                record_errors.append(f"Record {i+1}: Field '{field}' should be a valid phone number")

                # Range validation
                range_rules = rules.get("ranges", {})
                for field, range_def in range_rules.items():
                    if field in record and record[field] not in (None, ""):
                        try:
                            value = float(record[field])
                            if "min" in range_def and value < range_def["min"]:
                                record_errors.append(f"Record {i+1}: Field '{field}' is below minimum ({range_def['min']})")
                            if "max" in range_def and value > range_def["max"]:
                                record_errors.append(f"Record {i+1}: Field '{field}' exceeds maximum ({range_def['max']})")
                        except (ValueError, TypeError):
                            pass

                # Uniqueness validation
                unique_fields = rules.get("unique_fields", [])
                for field in unique_fields:
                    if field in record and record[field]:
                        # Check if value is unique across all records
                        for j, other in enumerate(data):
                            if i != j and other.get(field) == record[field]:
                                record_errors.append(
                                    f"Record {i+1}: Field '{field}' must be unique, "
                                    f"duplicate with record {j+1}"
                                )

                if record_errors:
                    validation_results["invalid_records"] += 1
                    validation_results["errors"].extend(record_errors[:3])  # Limit errors per record
                else:
                    validation_results["valid_records"] += 1

            # Summary
            pct_valid = round(validation_results["valid_records"] / len(data) * 100, 1) if data else 0
            validation_results["validity_percentage"] = pct_valid

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Validation complete: {validation_results['valid_records']}/{len(data)} valid ({pct_valid}%)",
                data=validation_results,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Validation failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _add_record(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Add a record to a collection."""
        collection = kwargs.get("collection", "default")
        record = kwargs.get("data", {})

        if not record:
            return ToolResult.failure(
                "No record data provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if isinstance(record, list):
            records = record
        else:
            records = [record]

        if collection not in self._records:
            self._records[collection] = []

        # Add timestamps
        timestamp = datetime.now().isoformat()
        for r in records:
            if "created_at" not in r:
                r["created_at"] = timestamp
            if "updated_at" not in r:
                r["updated_at"] = timestamp
            if "id" not in r:
                r["id"] = f"rec_{len(self._records[collection]) + 1}_{int(time.time())}"

        self._records[collection].extend(records)

        # Auto-save to file
        self._auto_save(collection)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Added {len(records)} record(s) to collection '{collection}' (total: {len(self._records[collection])})",
            data={
                "collection": collection,
                "added": len(records),
                "total": len(self._records[collection]),
                "preview": records[:3],
            },
            execution_time_ms=elapsed,
        )

    async def _update_record(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Update an existing record in a collection."""
        collection = kwargs.get("collection", "default")
        record_id = kwargs.get("id", "")
        updates = kwargs.get("data", {})

        if collection not in self._records:
            return ToolResult.failure(
                f"Collection '{collection}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not record_id:
            return ToolResult.failure(
                "No record ID provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            updated = False
            for i, record in enumerate(self._records[collection]):
                if record.get("id") == record_id or record.get("id") == f"rec_{record_id}":
                    self._records[collection][i].update(updates)
                    self._records[collection][i]["updated_at"] = datetime.now().isoformat()
                    updated = True
                    updated_record = self._records[collection][i]
                    break

            if not updated:
                return ToolResult.failure(
                    f"Record with ID '{record_id}' not found in collection '{collection}'",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            self._auto_save(collection)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Updated record '{record_id}' in collection '{collection}'",
                data={"collection": collection, "id": record_id, "record": updated_record},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Update failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _delete_record(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Delete a record from a collection."""
        collection = kwargs.get("collection", "default")
        record_id = kwargs.get("id", "")

        if collection not in self._records:
            return ToolResult.failure(
                f"Collection '{collection}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not record_id:
            return ToolResult.failure(
                "No record ID provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            before = len(self._records[collection])
            self._records[collection] = [
                r for r in self._records[collection]
                if r.get("id") != record_id and r.get("id") != f"rec_{record_id}"
            ]
            removed = before - len(self._records[collection])

            if removed == 0:
                return ToolResult.failure(
                    f"Record with ID '{record_id}' not found",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            self._auto_save(collection)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Deleted record '{record_id}' from collection '{collection}'",
                data={"collection": collection, "id": record_id, "remaining": len(self._records[collection])},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Delete failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _list_records(self, kwargs: Dict, start_time: float) -> ToolResult:
        """List all records in a collection."""
        collection = kwargs.get("collection", "default")
        limit = kwargs.get("limit", 50)
        offset = kwargs.get("offset", 0)

        if collection not in self._records:
            # Try to load from file
            self._load_collection(collection)

        if collection not in self._records or not self._records[collection]:
            return ToolResult.success(
                f"Collection '{collection}' is empty or not found",
                data={"collection": collection, "records": [], "total": 0},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        records = self._records[collection][offset:offset + limit]
        total = len(self._records[collection])

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Collection '{collection}': {total} total records (showing {len(records)})",
            data={
                "collection": collection,
                "total": total,
                "offset": offset,
                "limit": limit,
                "records": records,
                "fields": list(records[0].keys()) if records else [],
            },
            execution_time_ms=elapsed,
        )

    async def _batch_import(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Import multiple data files at once."""
        file_paths = kwargs.get("file_paths", [])
        collection = kwargs.get("collection", "batch_import")

        if not file_paths:
            return ToolResult.failure(
                "No file paths provided for batch import",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if isinstance(file_paths, str):
            # Single path, could be glob pattern
            import glob
            file_paths = glob.glob(file_paths)

        try:
            total_records = 0
            import_log = []

            for fp in file_paths:
                path = Path(fp)
                if not path.exists():
                    import_log.append(f"Skipped {fp}: not found")
                    continue

                ext = path.suffix.lower()
                records = []

                if ext == ".csv":
                    with open(path, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        records = list(reader)
                elif ext == ".json":
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        records = data if isinstance(data, list) else [data]
                else:
                    import_log.append(f"Skipped {path.name}: unsupported format")
                    continue

                if collection not in self._records:
                    self._records[collection] = []
                self._records[collection].extend(records)
                total_records += len(records)
                import_log.append(f"Imported {len(records)} records from {path.name}")

            self._auto_save(collection)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Batch import complete: {total_records} records from {len(import_log)} files",
                data={
                    "collection": collection,
                    "total_records": total_records,
                    "files_processed": len(import_log),
                    "log": import_log,
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Batch import failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _generate_form(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Generate a data entry form template."""
        form_name = kwargs.get("form_name", "entry_form")
        fields = kwargs.get("fields", [])
        num_entries = kwargs.get("num_entries", 1)

        if not fields:
            return ToolResult.failure(
                "No fields defined for form",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Generate template
            template = []
            for i in range(num_entries):
                entry = {}
                for field in fields:
                    field_name = field if isinstance(field, str) else field.get("name", "field")
                    field_type = field.get("type", "text") if isinstance(field, dict) else "text"
                    field_default = field.get("default", "") if isinstance(field, dict) else ""
                    
                    if field_type == "auto_number":
                        entry[field_name] = i + 1
                    elif field_type == "timestamp":
                        entry[field_name] = datetime.now().isoformat()
                    elif field_type == "text":
                        entry[field_name] = field_default or ""
                    elif field_type == "number":
                        entry[field_name] = field_default or 0
                    elif field_type == "choice":
                        options = field.get("options", []) if isinstance(field, dict) else []
                        entry[field_name] = options[0] if options else ""
                    else:
                        entry[field_name] = field_default or ""
                template.append(entry)

            # Save template as CSV
            output_path = self._data_dir / f"{form_name}_template.csv"
            if template:
                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    field_names = list(template[0].keys())
                    writer = csv.DictWriter(f, fieldnames=field_names)
                    writer.writeheader()
                    writer.writerows(template)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Generated form template '{form_name}' with {len(fields)} fields",
                data={
                    "form_name": form_name,
                    "fields": fields,
                    "template": template,
                    "output_path": str(output_path),
                    "num_entries": num_entries,
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Form generation failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _export_records(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Export records from a collection to a file."""
        collection = kwargs.get("collection", "default")
        output_path = kwargs.get("output_path", "")
        export_format = kwargs.get("format", "csv")

        if collection not in self._records:
            return ToolResult.failure(
                f"Collection '{collection}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        records = self._records[collection]
        if not records:
            return ToolResult.failure(
                f"Collection '{collection}' is empty",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not output_path:
            output_path = str(self._data_dir / f"{collection}.{export_format}")

        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            if export_format == "csv":
                with open(path, "w", newline="", encoding="utf-8") as f:
                    fieldnames = list(records[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)
            elif export_format == "json":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2, default=str)
            else:
                return ToolResult.failure(
                    f"Unsupported export format: {export_format}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Exported {len(records)} records to {path.name}",
                data={
                    "collection": collection,
                    "records_exported": len(records),
                    "output_path": str(path.resolve()),
                    "format": export_format,
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Export failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _search_records(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Search records in a collection by query."""
        collection = kwargs.get("collection", "default")
        query = kwargs.get("query", "").lower()
        field = kwargs.get("field", "")

        if collection not in self._records:
            return ToolResult.success(
                f"Collection '{collection}' is empty",
                data={"collection": collection, "results": [], "total": 0},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        records = self._records[collection]
        if not query:
            results = records[:20]
        else:
            results = []
            for r in records:
                if field:
                    # Search specific field
                    val = str(r.get(field, "")).lower()
                    if query in val:
                        results.append(r)
                else:
                    # Search all fields
                    if any(query in str(v).lower() for v in r.values()):
                        results.append(r)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Found {len(results)} matching records in '{collection}'",
            data={
                "collection": collection,
                "query": query,
                "total_matches": len(results),
                "results": results[:20],
                "has_more": len(results) > 20,
            },
            execution_time_ms=elapsed,
        )

    def _auto_save(self, collection: str) -> None:
        """Automatically save collection to a JSON file."""
        try:
            if collection in self._records and self._records[collection]:
                save_path = self._data_dir / f"{collection}.json"
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(self._records[collection], f, indent=2, default=str)
        except Exception as e:
            self.logger.warning(f"Auto-save failed for '{collection}': {e}")

    def _load_collection(self, collection: str) -> None:
        """Load a collection from file if it exists."""
        try:
            load_path = self._data_dir / f"{collection}.json"
            if load_path.exists():
                with open(load_path, "r", encoding="utf-8") as f:
                    self._records[collection] = json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load collection '{collection}': {e}")

    def cleanup(self) -> None:
        """Save all collections and clean up."""
        for collection in list(self._records.keys()):
            self._auto_save(collection)
        self.logger.info("Data entry tool cleaned up")