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
ArynoxTech AI Agent AI Agent - File Tool
==============================
Tool for file system operations: create, rename, move, delete files,
organize folders, and search for files.
"""

import time
import shutil
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG, SECURITY_CONFIG


class FileTool(BaseTool):
    """
    Tool for file system manipulation:
    - Create files and directories
    - Rename/move files
    - Delete files (requires confirmation)
    - Organize folders by type
    - Search for files by pattern
    - Read/write text files
    """

    name: str = "file_tool"
    description: str = "Create, rename, move, delete files. Organize folders and search files."
    version: str = "1.0.0"
    requires_confirmation: bool = True  # Sensitive operations need confirmation

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG["file"]
        self.blocked_paths = [Path(p).resolve() for p in SECURITY_CONFIG["blocked_paths"]]

    def _is_path_blocked(self, path: Path) -> bool:
        """Check if a path is in blocked system directories."""
        try:
            resolved = path.resolve()
            for blocked in self.blocked_paths:
                try:
                    if blocked in resolved.parents or resolved == blocked:
                        return True
                except (ValueError, OSError):
                    continue
            return False
        except (ValueError, OSError):
            return True

    def _get_blocked_reason(self, path: Path) -> str:
        """Get a description of why a path is blocked."""
        return f"Access denied: '{path}' is in a protected system directory"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute file tool operation.

        Args:
            action: 'create', 'rename', 'move', 'delete', 'search', 'organize', 'read', 'write'
            path: Target file/folder path
            new_path: Destination path (for rename/move)
            content: Text content (for write)
            pattern: Search pattern (for search)
            source_dir: Source directory (for organize)

        Returns:
            ToolResult with operation outcome
        """
        start_time = time.time()
        action = kwargs.get("action", "")

        try:
            if action == "create":
                return await self._create(kwargs, start_time)
            elif action == "rename":
                return await self._rename(kwargs, start_time)
            elif action == "move":
                return await self._move(kwargs, start_time)
            elif action == "delete":
                return await self._delete(kwargs, start_time)
            elif action == "search":
                return await self._search(kwargs, start_time)
            elif action == "organize":
                return await self._organize(kwargs, start_time)
            elif action == "read":
                return await self._read(kwargs, start_time)
            elif action == "write":
                return await self._write(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}. Available: create, rename, move, delete, search, organize, read, write",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.logger.exception(f"File tool error: {e}")
            return ToolResult.error_result(
                f"File operation failed: {str(e)}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _create(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Create a file or directory."""
        path = Path(kwargs["path"]).resolve()
        is_dir = kwargs.get("is_directory", False)

        if self._is_path_blocked(path):
            return ToolResult.failure(
                self._get_blocked_reason(path),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            if is_dir:
                path.mkdir(parents=True, exist_ok=True)
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"Created directory: {path}", data={"path": str(path)},
                    execution_time_ms=elapsed,
                )
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(kwargs.get("content", ""), encoding="utf-8")
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"Created file: {path.name}",
                    data={"path": str(path), "size": path.stat().st_size},
                    execution_time_ms=elapsed,
                )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to create: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _rename(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Rename a file or directory."""
        path = Path(kwargs["path"]).resolve()
        new_name = kwargs.get("new_path", "")

        if not path.exists():
            return ToolResult.failure(
                f"Path not found: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if self._is_path_blocked(path):
            return ToolResult.failure(
                self._get_blocked_reason(path),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            new_path = path.parent / new_name
            path.rename(new_path)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Renamed: {path.name} → {new_name}",
                data={"old_path": str(path), "new_path": str(new_path)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to rename: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _move(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Move a file or directory to a new location."""
        path = Path(kwargs["path"]).resolve()
        destination = Path(kwargs["new_path"]).resolve()

        if not path.exists():
            return ToolResult.failure(
                f"Source not found: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if self._is_path_blocked(path) or self._is_path_blocked(destination):
            return ToolResult.failure(
                "Access denied: protected system path involved",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(destination))
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Moved: {path.name} → {destination}",
                data={"from": str(path), "to": str(destination)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to move: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _delete(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Delete a file or directory (requires confirmation)."""
        path = Path(kwargs["path"]).resolve()

        if not path.exists():
            return ToolResult.failure(
                f"Path not found: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if self._is_path_blocked(path):
            return ToolResult.failure(
                self._get_blocked_reason(path),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            is_dir = path.is_dir()
            size_info = ""
            if path.is_file():
                size_info = f" ({path.stat().st_size / 1024:.1f} KB)"
            
            # Require user confirmation via ToolResult
            return ToolResult.needs_confirmation(
                f"Confirm deletion of '{path.name}'{size_info}?",
                data={
                    "path": str(path),
                    "is_directory": is_dir,
                    "type": "directory" if is_dir else "file",
                },
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Delete failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _search(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Search for files matching a pattern."""
        pattern = kwargs.get("pattern", "*")
        directory = kwargs.get("path", ".")
        search_path = Path(directory).resolve()

        if not search_path.exists():
            return ToolResult.failure(
                f"Directory not found: {search_path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            results = list(search_path.rglob(pattern))
            max_results = self.config.get("max_search_results", 100)
            results = results[:max_results]

            file_list = [
                {
                    "path": str(r),
                    "name": r.name,
                    "size": r.stat().st_size if r.is_file() else 0,
                    "is_dir": r.is_dir(),
                    "modified": r.stat().st_mtime,
                }
                for r in results
            ]

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Found {len(file_list)} files matching '{pattern}'",
                data={"files": file_list, "total": len(file_list)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Search failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _organize(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Organize files in a directory by type into subfolders."""
        source_dir = Path(kwargs.get("source_dir", ".")).resolve()

        if not source_dir.exists() or not source_dir.is_dir():
            return ToolResult.failure(
                f"Directory not found: {source_dir}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Extension-to-folder mapping
        type_map = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"],
            "Spreadsheets": [".xlsx", ".xls", ".csv", ".ods"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".h", ".json", ".xml", ".yaml"],
            "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"],
            "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
            "Presentations": [".pptx", ".ppt", ".key"],
            "Executables": [".exe", ".msi", ".bat", ".sh", ".app"],
        }

        try:
            organized = {}
            total_moved = 0

            for item in source_dir.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()
                    target_folder = "Other"
                    for folder, exts in type_map.items():
                        if ext in exts:
                            target_folder = folder
                            break

                    target_dir = source_dir / target_folder
                    target_dir.mkdir(exist_ok=True)
                    dest = target_dir / item.name

                    if not dest.exists():
                        shutil.move(str(item), str(dest))
                        total_moved += 1
                        organized[target_folder] = organized.get(target_folder, 0) + 1

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Organized {total_moved} files into {len(organized)} categories",
                data={"organized": organized, "categories": list(organized.keys())},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to organize: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _read(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Read the contents of a text file."""
        path = Path(kwargs["path"]).resolve()

        if not path.exists():
            return ToolResult.failure(
                f"File not found: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not path.is_file():
            return ToolResult.failure(
                f"Not a file: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            content = path.read_text(encoding="utf-8")
            line_count = content.count("\n") + 1
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Read {path.name} ({line_count} lines, {len(content)} chars)",
                data={"content": content, "lines": line_count, "size": len(content)},
                execution_time_ms=elapsed,
            )
        except UnicodeDecodeError:
            # Binary file - read bytes
            content_bytes = path.read_bytes()
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Binary file: {path.name} ({len(content_bytes)} bytes)",
                data={"type": "binary", "size": len(content_bytes)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to read file: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _write(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Write content to a text file."""
        path = Path(kwargs["path"]).resolve()
        content = kwargs.get("content", "")

        if self._is_path_blocked(path):
            return ToolResult.failure(
                self._get_blocked_reason(path),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(content), encoding="utf-8")
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Written {len(content)} chars to {path.name}",
                data={"path": str(path), "size": len(content)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to write file: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )