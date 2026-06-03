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
ArynoxTech AI Agent AI Agent - PDF Tool
==============================
Tool for extracting text content from PDF files.
Uses PyPDF2 for local PDF processing.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


class PDFTool(BaseTool):
    """
    Tool for PDF file operations:
    - Extract text from PDF files
    - Read PDF metadata
    - Get page count and structure
    """

    name: str = "pdf_tool"
    description: str = "Extract text from PDF files. Read PDF content and metadata."
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG["pdf"]
        # Lazy import to avoid loading if not needed
        self._PyPDF2 = None

    @property
    def pypdf2(self):
        """Lazy import PyPDF2 module."""
        if self._PyPDF2 is None:
            import PyPDF2
            self._PyPDF2 = PyPDF2
        return self._PyPDF2

    def _validate_path(self, file_path: str) -> Path:
        """Validate and return a safe Path object."""
        path = Path(file_path).resolve()
        ext = path.suffix.lower()
        if ext not in self.config["allowed_extensions"]:
            raise ValueError(
                f"Invalid file extension '{ext}'. Allowed: {self.config['allowed_extensions']}"
            )
        if path.stat().st_size > self.config["max_file_size_mb"] * 1024 * 1024:
            raise ValueError(
                f"File too large: {path.stat().st_size / 1024 / 1024:.1f}MB "
                f"(max: {self.config['max_file_size_mb']}MB)"
            )
        return path

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute PDF tool operation.

        Args:
            action: 'extract_text', 'extract_all', 'get_metadata'
            file_path: Path to PDF file
            pages: Optional list of page numbers to extract (0-indexed)

        Returns:
            ToolResult with extracted text or metadata
        """
        start_time = time.time()
        action = kwargs.get("action", "extract_text")

        try:
            if action == "extract_text":
                return await self._extract_text(kwargs, start_time)
            elif action == "extract_all":
                return await self._extract_all(kwargs, start_time)
            elif action == "get_metadata":
                return await self._get_metadata(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.logger.exception(f"PDF tool error: {e}")
            return ToolResult.error_result(
                f"PDF operation failed: {str(e)}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _extract_text(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Extract text from specified pages of a PDF."""
        file_path = self._validate_path(kwargs["file_path"])
        pages = kwargs.get("pages", None)

        if not file_path.exists():
            return ToolResult.failure(
                f"File not found: {file_path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            with open(file_path, "rb") as f:
                reader = self.pypdf2.PdfReader(f)
                num_pages = len(reader.pages)

                if pages is None:
                    pages = list(range(num_pages))

                extracted_text = []
                for page_num in pages:
                    if 0 <= page_num < num_pages:
                        page = reader.pages[page_num]
                        text = page.extract_text()
                        extracted_text.append({
                            "page": page_num + 1,
                            "text": text.strip(),
                            "chars": len(text),
                        })

                total_chars = sum(p["chars"] for p in extracted_text)
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"Extracted {total_chars} chars from {len(extracted_text)} pages of {file_path.name}",
                    data={
                        "file": file_path.name,
                        "total_pages": num_pages,
                        "extracted_pages": len(extracted_text),
                        "total_chars": total_chars,
                        "text": "\n\n".join(p["text"] for p in extracted_text),
                        "pages_detail": extracted_text,
                    },
                    execution_time_ms=elapsed,
                )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to extract text from PDF: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _extract_all(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Extract all text and structure from PDF."""
        return await self._extract_text(kwargs, start_time)

    async def _get_metadata(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get PDF metadata without extracting full text."""
        file_path = self._validate_path(kwargs["file_path"])

        if not file_path.exists():
            return ToolResult.failure(
                f"File not found: {file_path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            with open(file_path, "rb") as f:
                reader = self.pypdf2.PdfReader(f)
                metadata = reader.metadata or {}
                num_pages = len(reader.pages)

                # Get text preview from first page
                first_page_text = ""
                if num_pages > 0:
                    first_page_text = reader.pages[0].extract_text()[:500]

                info = {
                    "file": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "num_pages": num_pages,
                    "title": metadata.get("/Title", ""),
                    "author": metadata.get("/Author", ""),
                    "subject": metadata.get("/Subject", ""),
                    "creator": metadata.get("/Creator", ""),
                    "producer": metadata.get("/Producer", ""),
                    "preview": first_page_text.strip(),
                }

                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"PDF Info: {file_path.name} - {num_pages} pages, {info['size_bytes'] / 1024:.1f}KB",
                    data=info,
                    execution_time_ms=elapsed,
                )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to read PDF metadata: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )