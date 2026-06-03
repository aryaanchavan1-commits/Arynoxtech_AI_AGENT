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

"""ArynoxTech AI Agent - Document Ingestion Tool
================================================
Ingests user documents from the local filesystem (typically assets/uploads),
extracts text (best-effort) and stores extracted chunks into the agent's
semantic memory (SQLite FTS5).

Supported (best-effort):
- .pdf (via existing PDFTool)
- .txt/.md/.html/.xml/.json/.yaml/.yml (treated as text)
- .doc/.docx/.rtf (best-effort; requires optional dependencies)
- images (best-effort OCR; requires optional dependencies)

If a file type cannot be extracted, it will still store a metadata entry.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG, UPLOADS_DIR
from tools.pdf_tool import PDFTool
from memory.semantic_memory import SemanticMemory


@dataclass
class Chunk:
    text: str
    index: int


class DocumentIngestionTool(BaseTool):
    name: str = "document_ingestion_tool"
    description: str = (
        "Ingest documents from local path (e.g., assets/uploads). "
        "Extracts text best-effort and indexes content into semantic memory for later Q&A/search." 
    )
    version: str = "1.0.0"
    requires_confirmation: bool = False

    def __init__(self) -> None:
        super().__init__()
        self.semantic = SemanticMemory()

        # Use optional limits if present
        di_cfg = (TOOL_CONFIG or {}).get("document_ingestion", {}) if isinstance(TOOL_CONFIG, dict) else {}
        self.max_file_size_mb: int = int(di_cfg.get("max_file_size_mb", 50))
        self.max_total_chars: int = int(di_cfg.get("max_total_chars", 300000))
        self.chunk_size: int = int(di_cfg.get("chunk_size", 2500))
        self.chunk_overlap: int = int(di_cfg.get("chunk_overlap", 250))
        self.max_chunks: int = int(di_cfg.get("max_chunks", 250))

        # Allow ingesting from uploads by default; still allow absolute paths if user provides.
        self.default_base_dir: Path = UPLOADS_DIR.resolve()

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _chunk_text(self, text: str) -> List[Chunk]:
        if not text:
            return []

        chunks: List[Chunk] = []
        start = 0
        idx = 0
        n = len(text)
        while start < n and len(chunks) < self.max_chunks:
            end = min(n, start + self.chunk_size)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(text=chunk_text, index=idx))
                idx += 1
            if end >= n:
                break
            start = max(0, end - self.chunk_overlap)
        return chunks

    def _validate(self, file_path: Path) -> Tuple[bool, str]:
        if not file_path.exists():
            return False, f"File not found: {file_path}"
        if not file_path.is_file():
            return False, f"Not a file: {file_path}"
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            return False, f"File too large ({size_mb:.1f}MB, max {self.max_file_size_mb}MB)"
        return True, ""

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = kwargs.get("action", "ingest_file")

        try:
            if action == "ingest_file":
                return await self._ingest_file(kwargs, start_time)
            if action == "ingest_directory":
                return await self._ingest_directory(kwargs, start_time)

            return ToolResult.failure(
                f"Unknown action: {action}. Use ingest_file or ingest_directory",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Document ingestion failed: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _ingest_directory(self, kwargs: Dict[str, Any], start_time: float) -> ToolResult:
        dir_path = kwargs.get("dir_path") or str(self.default_base_dir)
        path = Path(dir_path).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            return ToolResult.failure(
                f"Directory not found: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        pattern = kwargs.get("pattern", "*")
        recursive = bool(kwargs.get("recursive", True))

        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))

        # Keep only files
        files = [f for f in files if f.is_file()]

        ingested = 0
        skipped = 0
        errors: List[str] = []

        # Ingestion sequentially to reduce memory spikes
        for f in files:
            res = await self._ingest_file(
                {
                    "file_path": str(f),
                    "collection": kwargs.get("collection", "documents"),
                },
                start_time,
                allow_silent_fail=True,
            )
            if res.status.value == "success":
                ingested += 1
            elif res.status.value in ("failure", "error"):
                # treat failures as skipped unless it's our own validation error
                if "File not found" in res.message:
                    skipped += 1
                else:
                    skipped += 1
                    errors.append(res.message)

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Directory ingestion done: ingested={ingested}, skipped={skipped}",
            data={
                "dir_path": str(path),
                "ingested": ingested,
                "skipped": skipped,
                "errors": errors[:5],
            },
            execution_time_ms=elapsed,
        )

    async def _ingest_file(
        self,
        kwargs: Dict[str, Any],
        start_time: float,
        allow_silent_fail: bool = False,
    ) -> ToolResult:
        file_path = Path(kwargs["file_path"]).expanduser().resolve()
        collection = kwargs.get("collection", "documents")
        desired_extension = file_path.suffix.lower()

        ok, reason = self._validate(file_path)
        if not ok:
            if allow_silent_fail:
                return ToolResult.failure(reason)
            return ToolResult.failure(
                reason,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        extracted_text = ""
        extraction_method = ""
        extraction_error = None

        # Route extraction
        try:
            if desired_extension == ".pdf":
                extraction_method = "pdf_tool"
                pt = PDFTool()
                pdf_res = await pt.execute(action="extract_all", file_path=str(file_path))
                if pdf_res.status.value == "success":
                    extracted_text = (pdf_res.data or {}).get("text", "") or ""
                else:
                    extraction_error = pdf_res.message

            elif desired_extension in {".txt", ".md", ".html", ".htm", ".xml", ".json", ".yaml", ".yml"}:
                extraction_method = "text_read"
                # best effort: assume utf-8 first, then latin-1
                try:
                    extracted_text = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    extracted_text = file_path.read_text(encoding="latin-1")

            elif desired_extension in {".doc", ".docx", ".rtf"}:
                extraction_method = "docx_rtf_best_effort"
                extracted_text = await asyncio.to_thread(self._extract_doc_like, file_path)

            elif desired_extension in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}:
                extraction_method = "ocr_best_effort"
                extracted_text = await asyncio.to_thread(self._extract_image_ocr, file_path)

            else:
                # Unknown/binary: no extraction, but store metadata
                extraction_method = "metadata_only"

        except Exception as e:
            extraction_error = str(e)

        extracted_text = self._normalize_text(extracted_text) if extracted_text else ""

        if extracted_text and len(extracted_text) > self.max_total_chars:
            extracted_text = extracted_text[: self.max_total_chars]

        # Prepare metadata wrapper
        base_metadata = {
            "source_file": str(file_path.name),
            "source_path": str(file_path),
            "collection": collection,
            "extension": desired_extension,
            "extraction_method": extraction_method,
            "extraction_error": extraction_error,
        }

        if extracted_text:
            chunks = self._chunk_text(extracted_text)
            stored = 0
            # Store each chunk as a separate memory entry for better search
            for ch in chunks:
                content = (
                    f"[Document: {collection}]\n"
                    f"Chunk {ch.index}\n"
                    f"{ch.text}"
                )
                self.semantic.db.store_memory(
                    content=content,
                    memory_type="document_chunk",
                    metadata={
                        **base_metadata,
                        "chunk_index": ch.index,
                    },
                )
                stored += 1

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Ingested '{file_path.name}' ({stored} chunks) into semantic memory",
                data={
                    "file": file_path.name,
                    "chunks_stored": stored,
                    "extraction_method": extraction_method,
                },
                execution_time_ms=elapsed,
            )

        # If no text extracted, still store a small metadata note so user can see it.
        note = (
            f"[Document: {collection}]\n"
            f"No extractable text found for file: {file_path.name}\n"
            f"Extraction method: {extraction_method}\n"
        )
        note_meta = {**base_metadata, "chunk_index": None}
        self.semantic.db.store_memory(
            content=note,
            memory_type="document_ingestion_result",
            metadata=note_meta,
        )

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Stored ingestion note for '{file_path.name}' (no text extracted)",
            data={
                "file": file_path.name,
                "chunks_stored": 0,
                "extraction_method": extraction_method,
            },
            execution_time_ms=elapsed,
        )

    def _extract_doc_like(self, file_path: Path) -> str:
        """Extract text from .doc/.docx/.rtf with optional dependencies."""
        # python-docx works for docx; .doc and .rtf may not be supported.
        try:
            if file_path.suffix.lower() == ".docx":
                from docx import Document  # type: ignore

                doc = Document(str(file_path))
                parts: List[str] = []
                for p in doc.paragraphs:
                    if p.text:
                        parts.append(p.text)
                return "\n".join(parts)

            # Fallback: attempt rtf/plain read
            # Many .rtf files are text-based.
            try:
                return file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return file_path.read_text(encoding="latin-1")
        except Exception:
            # Last resort: binary -> no extraction
            return ""

    def _extract_image_ocr(self, file_path: Path) -> str:
        """Extract text from image via OCR with optional dependencies."""
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore

            img = Image.open(str(file_path))
            text = pytesseract.image_to_string(img)
            return text or ""
        except Exception:
            return ""

