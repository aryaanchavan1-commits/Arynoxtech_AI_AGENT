# Copyright (c) 2026 Aryan Chavan (ArynoxTech)
# Licensed under the MIT License. See LICENSE file in the project root.

"""
ArynoxTech AI Agent - Configuration Settings
===========================================
Centralized configuration for the entire application.
All paths, model settings, and application constants are defined here.
"""

import os
from pathlib import Path
from typing import Final, Dict, Any, Optional

# Fix OpenBLAS / MKL memory allocation errors (especially on Windows)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

from dotenv import load_dotenv

load_dotenv()  # Load .env file

# ── Project Base Path ──────────────────────────────────────────────────────
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent

# ── Directory Paths ────────────────────────────────────────────────────────
DIRS: Final[Dict[str, Path]] = {
    "agent": BASE_DIR / "agent",
    "models": BASE_DIR / "models",
    "tools": BASE_DIR / "tools",
    "memory": BASE_DIR / "memory",
    "database": BASE_DIR / "database",
    "ui": BASE_DIR / "ui",
    "logs": BASE_DIR / "logs",
    "config": BASE_DIR / "config",
    "assets": BASE_DIR / "assets",
    "utils": BASE_DIR / "utils",
}

# ── Ensure all directories exist ───────────────────────────────────────────
for _dir in DIRS.values():
    _dir.mkdir(parents=True, exist_ok=True)

# ── Groq API Configuration ───────────────────────────────────────────────────
GROQ_API_KEY: Final[str] = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: Final[str] = "llama-3.1-8b-instant"

LLM_CONFIG: Final[Dict[str, Any]] = {
    "api_key": GROQ_API_KEY,
    "model": GROQ_MODEL,
    "max_tokens": 512,
    "temperature": 0.7,
    "top_p": 0.95,
    "stream": False,
}

# ── Local / Offline Model Configuration ──────────────────────────────────────
LOCAL_MODEL_ENABLED: Final[bool] = os.getenv("LOCAL_MODEL_ENABLED", "0") == "1"
LOCAL_MODEL_PATH: Final[str] = os.getenv("LOCAL_MODEL_PATH", str(BASE_DIR / "models" / "local-model.gguf"))
LOCAL_MODEL_N_CTX: Final[int] = int(os.getenv("LOCAL_MODEL_N_CTX", "2048"))
LOCAL_MODEL_N_THREADS: Final[int] = int(os.getenv("LOCAL_MODEL_N_THREADS", "4"))
LOCAL_MODEL_MAX_TOKENS: Final[int] = int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "512"))
LOCAL_MODEL_TEMPERATURE: Final[float] = float(os.getenv("LOCAL_MODEL_TEMPERATURE", "0.7"))
LOCAL_MODEL_TOP_P: Final[float] = float(os.getenv("LOCAL_MODEL_TOP_P", "0.95"))
LOCAL_MODEL_GPU_LAYERS: Final[int] = int(os.getenv("LOCAL_MODEL_GPU_LAYERS", "0"))

# ── Application Settings ───────────────────────────────────────────────────
APP_CONFIG: Final[Dict[str, Any]] = {
    "app_name": "ArynoxTech AI Agent",
    "app_version": "1.0.0",
    "app_author": "Aryan Chavan (ArynoxTech)",
    "window_width": 1280,
    "window_height": 800,
    "min_window_width": 900,
    "min_window_height": 600,
    "theme": "dark",  # 'dark' or 'light'
    "language": "en",
}

# ── Memory Settings ────────────────────────────────────────────────────────
MEMORY_CONFIG: Final[Dict[str, Any]] = {
    "short_term_max_messages": 50,
    "long_term_db_path": str(DIRS["database"] / "localmind_memory.db"),
    "semantic_enabled": True,
    "memory_ttl_days": 30,
}

# ── Logging Settings ───────────────────────────────────────────────────────
LOGGING_CONFIG: Final[Dict[str, Any]] = {
    "log_dir": str(DIRS["logs"]),
    "log_level": "DEBUG",          # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "max_file_size_mb": 10,
    "backup_count": 5,
    "console_output": True,
}

# ── Security Settings ──────────────────────────────────────────────────────
SECURITY_CONFIG: Final[Dict[str, Any]] = {
    "require_confirmation_for": [
        "delete_file",
        "modify_system_folder",
        "run_system_command",
        "install_software",
        "modify_registry",
    ],
    "blocked_paths": [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "/System",
        "/etc",
        "/usr",
    ],
    "max_input_length": 4000,
}

# ── Tool Settings ──────────────────────────────────────────────────────────
UPLOADS_DIR: Final[Path] = DIRS["assets"] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Supported upload extensions in the UI/agent
# (Storage is always done locally; extraction is best-effort in DocumentIngestionTool)
UPLOAD_ALLOWED_EXTENSIONS: Final[list[str]] = [
    ".pdf", 
    ".xlsx", ".xls", ".csv", ".ods",
    ".doc", ".docx", ".rtf",
    ".ppt", ".pptx", ".key",
    ".txt", ".md", ".html", ".htm", ".xml",
    ".json", ".yaml", ".yml",
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp",
    ".zip", ".rar", ".7z", ".tar", ".gz",
]

TOOL_CONFIG: Final[Dict[str, Any]] = {
    "excel": {
        "max_rows": 100000,
        "max_columns": 50,
        "allowed_extensions": [".xlsx", ".xls", ".csv"],
    },
    "pdf": {
        "max_file_size_mb": 50,
        "allowed_extensions": [".pdf"],
    },
    "browser": {
        "headless": False,
        "timeout_seconds": 30,
    },
    "file": {
        "max_search_results": 100,
        "allowed_extensions": None,  # None = all extensions allowed
    },
    "web_search": {
        "max_results": 10,
        "request_timeout": 15,
    },
    "data_analysis": {
        "max_rows": 500000,
        "memory_limit_mb": 500,
    },
    "data_entry": {
        "data_dir": "data/records",
        "auto_save": True,
    },
    "camera": {
        "output_dir": "assets/captures",
        "default_camera_id": 0,
        "max_video_duration": 30,
    },
    "ml": {
        "models_dir": "models/ml_models",
        "default_test_size": 0.2,
        "max_training_rows": 100000,
    },
    "personal_assistant": {
        "data_dir": "data/assistant",
        "reminder_check_interval": 30,
    },
    "report": {
        "reports_dir": "reports",
        "max_chart_rows": 1000,
    },
    "business_utils": {
        "outlier_multiplier": 1.5,
        "quality_thresholds": {
            "missing_percent_warn": 20,
            "high_cardinality": 50,
            "skew_threshold": 1.0,
        },
        "pii_patterns": ["email", "phone", "ssn", "credit_card", "ip", "passport", "pan", "aadhaar"],
    },
}

# ── Task Queue Settings ────────────────────────────────────────────────────
TASK_CONFIG: Final[Dict[str, Any]] = {
    "max_concurrent_tasks": 3,
    "task_timeout_minutes": 30,
    "retry_attempts": 2,
    "retry_delay_seconds": 5,
}

# ── Prompt Template ────────────────────────────────────────────────────────
SYSTEM_PROMPT: Final[str] = (
    "You are ArynoxTech AI Agent, a friendly and intelligent AI assistant created by Aryan Chavan (ArynoxTech).\n\n"
    "YOUR PERSONALITY:\n"
    "- Speak naturally and warmly, like a helpful human friend\n"
    "- Use casual, conversational language (contractions, varied tone)\n"
    "- Never sound robotic or like a corporate assistant\n"
    "- Be enthusiastic and encouraging\n"
    "- Adapt your tone: formal for work topics, casual for everyday chat\n"
    "- Use emojis in chat responses to show emotion 😊\n"
    "- Show personality! You can joke, be excited, be thoughtful\n"
    "- When you don't know something, say so honestly\n\n"
    "BEHAVIOR:\n"
    "- Only use tools when the user asks for file/excel/PDF/browser/system/web/search/camera/ML/automation tasks\n"
    "- For general conversation, reply naturally without tools\n"
    "- Never invent results - report what tools return honestly\n"
    "- Be concise but thorough\n"
    "- When someone asks who made you, say: 'I was created by Aryan Chavan (ArynoxTech)!'\n\n"
    "AVAILABLE TOOLS (15 total):\n"
    "1. file_tool - Create/rename/move/delete files, search, organize\n"
    "2. excel_tool - Read/create/modify Excel, GST calc, inventory\n"
    "3. pdf_tool - Extract text from PDF files\n"
    "4. browser_tool - Open websites, browser automation\n"
    "5. system_tool - Open any app, CPU/RAM/disk monitoring, type text\n"
    "6. database_tool - Store/retrieve memories, preferences\n"
    "7. web_search_tool - Search web, get page content, smart summaries\n"
    "8. data_analysis_tool - Statistics, cleaning, ETL, correlations\n"
    "9. data_entry_tool - CSV/JSON CRUD, batch import, validation\n"
    "10. personal_assistant_tool - Reminders, notes, timers, todos, calendar\n"
    "11. report_tool - Generate PDF/Excel/CSV/chart/image reports\n"
    "12. app_automation_tool - Social media (Instagram/FB/WhatsApp), web automation\n"
    "13. document_ingestion_tool - Ingest files into searchable memory\n"
    "14. camera_tool - Take photos, record video, detect objects, recognize faces\n"
    "15. ml_tool - Train ML models, predict, evaluate, preprocess data\n"
    "16. business_utils_tool - Data quality, profiling, PII detection, compliance, anomaly detection, schema validation, merge datasets\n\n"
    "Conversation so far:\n"
    "{conversation}\n"
    "User: {task}\n"
    "Assistant:"
)
