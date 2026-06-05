# Copyright (c) 2026 Aryan Chavan (ArynoxTech)
# Licensed under the MIT License. See LICENSE file in the project root.

"""
ArynoxTech AI Agent - Agent Core
===================================
Central orchestrator that coordinates the LLM, planner, task manager,
memory systems, and tools. This is the main entry point for all
user interactions with the agent.
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from agent.planner import Planner
from agent.task_manager import TaskManager, Task, TaskStatus
from tools.base_tool import ToolRegistry
from tools.excel_tool import ExcelTool
from tools.file_tool import FileTool
from tools.pdf_tool import PDFTool
from tools.browser_tool import BrowserTool
from tools.system_tool import SystemTool
from tools.database_tool import DatabaseTool
from tools.web_search_tool import WebSearchTool
from tools.data_analysis_tool import DataAnalysisTool
from tools.data_entry_tool import DataEntryTool
from tools.personal_assistant_tool import PersonalAssistantTool
from tools.report_tool import ReportTool
from tools.app_automation_tool import AppAutomationTool
from tools.document_ingestion_tool import DocumentIngestionTool
from tools.camera_tool import CameraTool
from tools.ml_tool import MLTool
from tools.business_utils import BusinessUtilsTool


from memory.short_term_memory import ShortTermMemory
from memory.long_term_memory import LongTermMemory
from memory.semantic_memory import SemanticMemory
from utils.llm_factory import get_llm_factory, LLMMode
from utils.logger import get_logger
from config.settings import SECURITY_CONFIG
from memory.rag_retrieval import RAGRetriever

logger = get_logger(__name__)


class AgentCore:
    """
    The central orchestrator of the ArynoxTech AI Agent.
    Manages all subsystems and provides the main interaction interface.
    """

    _instance: Optional["AgentCore"] = None

    def __new__(cls) -> "AgentCore":
        """Singleton pattern for the agent core."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize all agent subsystems."""
        if self._initialized:
            return

        # Initialize LLM via factory (auto-detects online/offline)
        self._llm_factory = get_llm_factory()
        self.llm_mode = self._llm_factory.detect_mode()
        if self.llm_mode != LLMMode.UNAVAILABLE:
            self.llm = self._llm_factory.get_client()
        else:
            self.llm = None
        self._model_connected = self.llm_mode != LLMMode.UNAVAILABLE

        # Initialize memory systems
        self.short_term_memory = ShortTermMemory()
        self.long_term_memory = LongTermMemory()
        self.semantic_memory = SemanticMemory()

        # Initialize tool registry and register all tools
        self.tool_registry = ToolRegistry()
        self._register_tools()

        # Initialize planner and task manager
        self.planner = Planner(self.llm)
        self.task_manager = TaskManager(self.tool_registry, llm_client=self.llm)
        self.task_manager.set_task_update_callback(self._on_task_update)

        # Agent state
        self._processing = False
        self._model_connected = False
        self._on_message: Optional[Callable] = None
        self._on_processing_change: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        self._initialized = True
        logger.info("AgentCore initialized with all subsystems")

    def _register_tools(self) -> None:
        """Register all available tools in the tool registry."""
        tools = [
            ExcelTool(),
            FileTool(),
            PDFTool(),
            BrowserTool(),
            SystemTool(),
            DatabaseTool(),
            WebSearchTool(),
            DataAnalysisTool(),
            DataEntryTool(),
            PersonalAssistantTool(),
            ReportTool(),
            # Universal app/web automation
            # (best-effort open/extract/type/send)
            AppAutomationTool(),
            DocumentIngestionTool(),
            CameraTool(),
            MLTool(),
            BusinessUtilsTool(),
        ]

        for tool in tools:
            self.tool_registry.register(tool)
        logger.info(f"Registered {len(tools)} tools")

    # ── Callback Setters ──────────────────────────────────────────────────

    def set_message_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for new messages (user/assistant)."""
        self._on_message = callback

    def set_processing_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for processing state changes."""
        self._on_processing_change = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for error notifications."""
        self._on_error = callback

    def start_task_worker(self) -> None:
        """Start the background task worker."""
        try:
            asyncio.get_running_loop()
            self.task_manager.start_worker()
            return
        except RuntimeError:
            pass
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.task_manager.start_worker()
                return
        except Exception:
            loop = None
        try:
            logger.info("Event loop not running yet; scheduling worker start via QTimer")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, self.start_task_worker)
        except Exception as e:
            logger.warning(f"Could not start task worker (no event loop): {e}")

    # ── Model Connection ─────────────────────────────────────────────────

    def check_model_connection(self) -> bool:
        """Check if any LLM backend (online or offline) is available."""
        mode = self._llm_factory.detect_mode()
        self._model_connected = mode != LLMMode.UNAVAILABLE
        self.llm_mode = mode
        if self._model_connected:
            try:
                self.llm = self._llm_factory.get_client()
            except RuntimeError:
                pass
        return self._model_connected

    def wait_for_model(self, timeout: int = 60) -> bool:
        """Wait for any LLM backend to become available."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if self.check_model_connection():
                return True
            time.sleep(2)
        return False

    @property
    def is_model_connected(self) -> bool:
        return self._model_connected

    @property
    def current_llm_mode(self) -> str:
        """Returns 'online' or 'offline' or 'unavailable'."""
        return self._llm_factory.mode_name

    # ── Helper: execute a single-step plan ───────────────────────────────

    async def _run_plan_step(self, tool_name: str, tool_params: dict, description: str = "") -> str:
        """Execute a single deterministic tool step immediately (bypasses LLM planning)."""
        from agent.planner import Plan, PlanStep
        step = PlanStep(
            description=description or f"{tool_name}: {tool_params}",
            tool_name=tool_name,
            tool_params=tool_params,
            order=1,
        )
        plan = Plan(original_request=description, steps=[step])
        task = await self.task_manager.create_task(description=description, plan=plan)
        await self.task_manager.execute_task(task)
        return task.result or "✅ Done."

    # ── Main Interaction ─────────────────────────────────────────────────

    async def process_user_input(self, user_input: str) -> str:
        """
        Process user input - FAST PATH for compound commands,
        then fallback to LLM planning for complex tasks.
        """
        max_length = SECURITY_CONFIG.get("max_input_length", 4000)
        if len(user_input) > max_length:
            return f"❌ Input too long ({len(user_input)} chars). Maximum is {max_length} characters."

        self._processing = True
        if self._on_processing_change:
            self._on_processing_change(True)

        try:
            self.short_term_memory.add_message(role="user", content=user_input)
            if self._on_message:
                self._on_message("user", user_input)

            normalized = user_input.strip().lower()

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 1: Compound "open X and type Y / create / save" etc
            # ═══════════════════════════════════════════════════════════════
            if normalized.startswith("open ") and (" and " in normalized or " type " in normalized or " write " in normalized or " create " in normalized or " save " in normalized):
                response = await self._handle_compound_command(user_input, normalized)
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 2: Simple "open <app>"
            # ═══════════════════════════════════════════════════════════════
            if normalized.startswith("open ") and " and " not in normalized and " type" not in normalized:
                app = normalized.replace("open ", "").strip()
                if app:
                    response = await self._run_plan_step("system_tool", {"action": "open_app", "app_name": app}, f"open {app}")
                else:
                    response = await self._generate_response(user_input)
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 3: "open <app> and type <text>"
            # ═══════════════════════════════════════════════════════════════
            if " and " in normalized and "type" in normalized:
                lower = user_input.lower()
                idx = lower.find("type")
                typed = user_input[idx + len("type"):].strip() if idx != -1 else ""
                before = lower.split(" and ", 1)[0].strip()
                app = before.replace("open ", "").strip() if before.startswith("open ") else before.strip()
                app = app.replace("app", "").strip()
                if app and typed:
                    response = await self._run_plan_step("system_tool", {
                        "action": "open_app_and_type", "app_name": app, "text": typed
                    }, f"open {app} and type")
                else:
                    response = await self._generate_response(user_input)
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 4: "type <text>"
            # ═══════════════════════════════════════════════════════════════
            if normalized.startswith("type "):
                typed = user_input[len("type "):].strip()
                if typed:
                    response = await self._run_plan_step("system_tool", {"action": "type_text", "text": typed}, f"type text")
                else:
                    response = await self._generate_response(user_input)
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 5: "open <app> type <text>" (without 'and')
            # ═══════════════════════════════════════════════════════════════
            if normalized.startswith("open ") and " type " in normalized:
                orig_after_open = user_input[len("open "):]
                app_part_orig, _, text_part_orig = orig_after_open.partition(" type ")
                app = app_part_orig.strip()
                typed = text_part_orig.strip()
                if app and typed:
                    response = await self._run_plan_step("system_tool", {
                        "action": "open_app_and_type", "app_name": app, "text": typed
                    }, f"open {app} and type")
                else:
                    response = await self._generate_response(user_input)
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 6: Camera / webcam commands
            # ═══════════════════════════════════════════════════════════════
            if any(normalized.startswith(p) for p in ["take photo", "take picture", "capture photo", "open camera", "snap photo", "click photo"]):
                response = await self._run_plan_step("camera_tool", {"action": "capture_photo"}, "take photo")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["record video", "record a video"]):
                dur = 5
                import re
                dur_match = re.search(r"(\d+)\s*seconds?", normalized)
                if dur_match:
                    dur = int(dur_match.group(1))
                response = await self._run_plan_step("camera_tool", {"action": "record_video", "duration": dur}, "record video")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["detect face", "face detect", "scan face"]):
                response = await self._run_plan_step("camera_tool", {"action": "detect_faces"}, "detect faces")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["detect object", "scan object", "what objects"]):
                response = await self._run_plan_step("camera_tool", {"action": "detect_objects"}, "detect objects")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["what is this", "what is that", "identify this", "identify object"]):
                response = await self._run_plan_step("camera_tool", {"action": "identify_object"}, "identify object")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["recognize person", "recognize face", "recognize me", "who am i", "who is this"]):
                response = await self._run_plan_step("camera_tool", {"action": "recognize_person"}, "recognize person")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["learn this person", "learn this face", "learn new person", "teach my face"]):
                response = await self._run_plan_step("camera_tool", {"action": "learn_new_person"}, "learn new person")
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["save face as", "teach face name"]):
                name_part = user_input
                for prefix in ["save face as ", "teach face name "]:
                    if name_part.lower().startswith(prefix):
                        name = name_part[len(prefix):].strip()
                        if name:
                            response = await self._run_plan_step("camera_tool", {"action": "save_face", "name": name}, f"save face as {name}")
                            self._finish(user_input, response)
                            return response

            if any(normalized.startswith(p) for p in ["who do you know", "list known people", "list people", "known faces"]):
                response = await self._run_plan_step("camera_tool", {"action": "list_known_people"}, "list known people")
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 7: ML engineer commands
            # ═══════════════════════════════════════════════════════════════
            ml_create = ["train model", "train a model", "train ml", "train machine learning"]
            if any(normalized.startswith(p) for p in ml_create):
                response = await self._run_plan_step("ml_tool", {"action": "train_model"}, user_input[:60])
                self._finish(user_input, response)
                return response

            if any(normalized.startswith(p) for p in ["forecast", "forecasting", "predict future"]):
                response = await self._run_plan_step("data_analysis_tool", {"action": "forecasting"}, "forecasting")
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 8: File system commands - list/open/navigate
            # ═══════════════════════════════════════════════════════════════
            _USER_HOME = os.path.expanduser("~")
            file_system_actions = {
                "list files": ("file_tool", {"action": "search", "path": ".", "pattern": "*"}),
                "list folder": ("file_tool", {"action": "search", "path": ".", "pattern": "*"}),
                "show files": ("file_tool", {"action": "search", "path": ".", "pattern": "*"}),
                "list directory": ("file_tool", {"action": "search", "path": ".", "pattern": "*"}),
                "show folders": ("file_tool", {"action": "search", "path": ".", "pattern": "*"}),
                "browse files": ("file_tool", {"action": "search", "path": _USER_HOME, "pattern": "*"}),
                "open downloads": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": f'start "" "{os.path.join(_USER_HOME, "Downloads")}"'}),
                "open desktop": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": f'start "" "{os.path.join(_USER_HOME, "Desktop")}"'}),
                "open documents": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": f'start "" "{os.path.join(_USER_HOME, "Documents")}"'}),
                "open this pc": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": "start \"\" \"::{20D04FE0-3AEA-1069-A2D8-08002B30309D}\""}),
                "my computer": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": "start \"\" \"::{20D04FE0-3AEA-1069-A2D8-08002B30309D}\""}),
                "open c drive": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": 'start "" "C:\\"'}),
                "open d drive": ("system_tool", {"action": "open_app", "app_name": "explorer", "command": 'start "" "D:\\"'}),
                "show my files": ("file_tool", {"action": "search", "path": os.path.join(_USER_HOME, "Documents"), "pattern": "*"}),
            }
            for prefix, (tool_nm, tool_params) in file_system_actions.items():
                if normalized.startswith(prefix):
                    response = await self._run_plan_step(tool_nm, tool_params, prefix)
                    self._finish(user_input, response)
                    return response

            # ═══════════════════════════════════════════════════════════════
            # FAST PATH 9: Generate/create reports instantly (no LLM needed)
            # ═══════════════════════════════════════════════════════════════
            create_patterns = [
                "generate pdf", "generate a pdf", "create pdf", "create a pdf",
                "generate excel", "generate a excel", "create excel", "create a excel",
                "generate csv", "generate a csv", "create csv", "create a csv",
                "generate image", "generate an image", "create image", "create an image",
                "generate chart", "generate a chart", "create chart", "create a chart",
                "generate report", "create report", "make a pdf", "make pdf",
                "make a csv", "make csv", "make a excel", "make excel",
            ]
            is_create_request = any(normalized.startswith(p) or p in normalized for p in create_patterns)

            if is_create_request:
                response = await self._handle_report_generation(user_input, normalized)
                self._finish(user_input, response)
                return response

            # ═══════════════════════════════════════════════════════════════
            # FALLBACK: LLM-based tool routing
            # ═══════════════════════════════════════════════════════════════
            tool_keywords = [
                "upload", "ingest", "document", "documents", "index", "semantic search",

                "excel", "spreadsheet", "gst", "inventory",
                "pdf", "extract text", "file", "folder", "rename", "move",
                "delete", "create", "write", "cpu", "ram", "system", "launch",
                "disk", "process", "remember", "memory", "preference", "history",
                "website", "browser", "open url", "http",
                "notepad", "type", "type in", "write in", "search", "google",
                "look up", "find online", "what is", "who is", "news", "latest",
                "real-time", "current", "weather", "definition", "meaning",
                "information about", "analyze", "analysis", "statistics",
                "statistical", "correlation", "regression", "clean data",
                "data cleaning", "data transformation", "etl", "pipeline",
                "report", "describe data", "summary", "aggregate", "group by",
                "data mining", "insights", "data set", "dataset",
                "data entry", "csv", "json", "record", "database entry",
                "import data", "export data", "batch", "validate",
                "form", "template", "contact", "spreadsheet entry",
                "remind", "reminder", "note", "notes", "todo", "to-do",
                "to do", "task list", "calendar", "schedule", "event",
                "timer", "stopwatch", "set alarm", "quick info", "what time",
                "today's date", "open app", "calculator", "calc.exe",
                # Business keywords
                "data quality", "data profiling", "schema validation",
                "pii detection", "compliance", "anomaly detection",
                "merge data", "forecast", "forecasting", "kpi",
                "business intelligence", "business report", "dashboard",
                "pivot table", "gst", "inventory report", "stock report",
            ]
            looks_tool_request = any(k in normalized for k in tool_keywords)

            if looks_tool_request:
                task = await self.task_manager.create_task(description=user_input)
                response = await self._wait_for_task_result(task.id)
            else:
                response = await self._generate_response(user_input)

            self._finish(user_input, response)
            return response

        except ModelNotAvailableError:
            error_msg = (
                "⚠️ Groq API is not available.\n\n"
                "Please set the GROQ_API_KEY environment variable with your Groq API key."
            )
            if self._on_error:
                self._on_error(error_msg)
            return error_msg

        except Exception as e:
            logger.exception(f"Error processing user input: {e}")
            error_msg = f"❌ An error occurred: {str(e)}"
            if self._on_error:
                self._on_error(error_msg)
            return error_msg

        finally:
            self._processing = False
            if self._on_processing_change:
                self._on_processing_change(False)

    # ── Compound Command Handler ──────────────────────────────────────────

    async def _handle_compound_command(self, original: str, normalized: str) -> str:
        """
        Handle compound commands like:
        "open excel and create a new file save as demo and type customer name and address"
        """
        # Extract app name (first word after "open ")
        after_open = normalized.replace("open ", "", 1)
        app_name = after_open.split()[0] if after_open.split() else "notepad"
        app_name_clean = app_name.rstrip("s")
        
        try:
            # Step 1: Open the app
            open_result = await self._run_plan_step(
                "system_tool",
                {"action": "open_app", "app_name": app_name_clean},
                f"open {app_name_clean}"
            )
            
            # Wait for app to launch
            await asyncio.sleep(0.8)
            
            actions_taken = [f"✅ Opened {app_name_clean}"]
            
            # Step 2: Check if we need to type text
            type_keywords = [" type ", " write ", " enter "]
            text_to_type = None
            for kw in type_keywords:
                if kw in normalized:
                    idx = normalized.rfind(kw) + len(kw)
                    text_to_type = original[idx:].strip() if idx < len(original) else None
                    if text_to_type:
                        # Clean: remove trailing filler
                        for filler in [" in the file", " in it", " in excel", " in notepad", " and save", " and create"]:
                            if text_to_type.lower().endswith(filler):
                                text_to_type = text_to_type[:-len(filler)].strip()
                        break
            
            # Step 3: Determine save path (Downloads by default)
            import os
            downloads_path = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Downloads")
            save_dir = downloads_path
            
            # Check if user specified a custom path
            for path_prefix in [" in c drive ", " in c:\\", " in d:\\", " in downloads ", " on desktop "]:
                if path_prefix in normalized:
                    if "download" in normalized:
                        save_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Downloads")
                    elif "desktop" in normalized:
                        save_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")
                    elif "c:\\" in normalized or "c:" in normalized:
                        save_dir = "C:\\"
                    break
            
            # Step 4: Excel-specific - create file with data
            if "excel" in app_name_clean:
                filename = "demo_created"
                # Try to extract filename
                for prefix in ["save as ", "save it as ", "filename ", "name it ", "save as name "]:
                    if prefix in normalized:
                        idx = normalized.find(prefix) + len(prefix)
                        name_part = normalized[idx:].split()[0] if normalized[idx:].split() else ""
                        if name_part:
                            filename = name_part.replace(".xlsx", "").replace(".csv", "")
                            break
                
                file_path = os.path.join(save_dir, f"{filename}.xlsx")
                
                # Create the Excel file with sample data
                try:
                    et = ExcelTool()
                    
                    # Determine what columns/data to put in
                    if text_to_type:
                        import re
                        # Clean the text for parsing
                        clean_text = text_to_type
                        # Remove common filler words
                        for fw in ["heading ", "headings ", "column ", "columns ", "and "]:
                            clean_text = clean_text.replace(fw, "")
                        columns = re.split(r'\s+and\s+|\s*,\s*', clean_text)
                        columns = [c.strip().title() for c in columns if c.strip() and len(c) > 1]
                        if not columns:
                            columns = ["Customer Name", "Address"]
                        
                        # Add a sample row so content is visible
                        sample_values = [f"Sample {c}" for c in columns]
                        data_record = {col: val for col, val in zip(columns, sample_values)}
                        
                        result = await et.execute(
                            action="create",
                            file_path=file_path,
                            data=[data_record],
                            sheet_name="Sheet1"
                        )
                        
                        if result.status.value == "success":
                            actions_taken.append(f"✅ Created file at: {file_path}")
                            
                            # Now open the saved file in Excel
                            await asyncio.sleep(0.5)
                            try:
                                # Close Excel first if already opened (we opened it earlier)
                                import subprocess
                                subprocess.run("taskkill /f /im EXCEL.EXE 2>nul", shell=True, capture_output=True)
                                await asyncio.sleep(0.5)
                            except:
                                pass
                            
                            # Open the actual file in Excel
                            subprocess.Popen(f'start "" "{file_path}"', shell=True)
                            await asyncio.sleep(0.8)
                            actions_taken.append(f"✅ Opened file in Excel with sample data")
                            return "\n".join(actions_taken)
                        else:
                            actions_taken.append(f"❌ File creation failed: {result.message}")
                    else:
                        # No text_to_type, create empty file with default headers
                        result = await et.execute(
                            action="create",
                            file_path=file_path,
                            data=[{"Customer Name": "Sample Customer", "Address": "123 Main Street"}],
                            sheet_name="Sheet1"
                        )
                        if result.status.value == "success":
                            actions_taken.append(f"✅ Created file at: {file_path}")
                        else:
                            actions_taken.append(f"❌ File creation failed: {result.message}")
                except Exception as e:
                    actions_taken.append(f"❌ File error: {e}")
            
            # Step 4: Type text if needed (for any app)
            if text_to_type and "❌" not in " ".join(actions_taken):
                await asyncio.sleep(0.3)
                type_result = await self._run_plan_step(
                    "system_tool",
                    {"action": "type_text", "text": text_to_type, "delay_seconds": 0.5},
                    "type text"
                )
                actions_taken.append(f"✅ Typed: {text_to_type[:50]}{'...' if len(text_to_type) > 50 else ''}")
            
            return "\n".join(actions_taken)

        except Exception as e:
            return f"❌ Error executing command: {str(e)}"

    # ── Report Generation Handler ─────────────────────────────────────────

    async def _handle_report_generation(self, original: str, normalized: str) -> str:
        """Handle report generation requests instantly without LLM."""
        try:
            tool = self.tool_registry.get_tool("report_tool")
            if not tool:
                return await self._generate_response(original)
            
            # Determine format
            ext = ""
            if "pdf" in normalized:
                ext = "pdf"
            elif "excel" in normalized or "xlsx" in normalized:
                ext = "xlsx"
            elif "csv" in normalized:
                ext = "csv"
            elif "image" in normalized or "img" in normalized:
                ext = "png"
            elif "chart" in normalized:
                ext = "chart"
            
            if not ext:
                return await self._generate_response(original)
            
            params = {"title": original.replace("generate", "").replace("create", "").replace("make", "").strip()[:50]}
            
            if ext == "chart":
                params["action"] = "generate_chart"
                params["chart_type"] = "bar"
                params["data"] = [{"x": "A", "y": 10}, {"x": "B", "y": 20}, {"x": "C", "y": 15}]
                params["x_column"] = "x"
                params["y_column"] = "y"
            elif ext == "png":
                params["action"] = "generate_image"
                params["text"] = original
            else:
                params["action"] = f"generate_{ext}"
                # Try to provide some sample data
                if ext == "xlsx":
                    params["data"] = [{"Customer Name": "Example", "Address": "123 Main St"}]
                elif ext == "csv":
                    params["data"] = [{"Name": "Sample", "Value": 100}]
                elif ext == "pdf":
                    params["content"] = original
                    params["data"] = [{"Item": "Example", "Details": "Sample data"}]
            
            result = await tool.execute(**params)
            path = result.data.get("path", "")
            filename = result.data.get("filename", "file")
            return (
                f"✅ **{ext.upper()} generated instantly!**\n\n"
                f"📄 File: `{filename}`\n"
                f"📁 Location: `{path}`\n\n"
                f"🔽 **Download from sidebar → Reports section**"
            )
        except Exception as e:
            return f"❌ Generation failed: {str(e)}"

    # ── Finish processing ────────────────────────────────────────────────

    def _finish(self, user_input: str, response: str) -> None:
        """Store conversation and notify UI."""
        self.short_term_memory.add_message(role="assistant", content=response)
        self.long_term_memory.store(
            content=f"User: {user_input}\nAssistant: {response}",
            memory_type="interaction",
        )
        if self._on_message:
            self._on_message("assistant", response)

    # ── Wait for Task Result ──────────────────────────────────────────────

    async def _wait_for_task_result(self, task_id: str, timeout_seconds: int = 180) -> str:
        """Poll until the TaskManager task reaches a terminal state."""
        start = time.time()
        while time.time() - start < timeout_seconds:
            task = self.task_manager.get_task(task_id)
            if task is None:
                return f"❌ Task '{task_id}' not found."
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.status == TaskStatus.COMPLETED:
                    return task.result or "✅ Task completed."
                if task.status == TaskStatus.WAITING_CONFIRMATION:
                    return "⏸️ Action requires confirmation."
                if task.status == TaskStatus.CANCELLED:
                    return "⚠️ Task cancelled."
                return f"❌ Task failed: {task.error or task.result or ''}".strip()
            if task.status == TaskStatus.WAITING_CONFIRMATION:
                return "⏸️ Action requires confirmation."
            await asyncio.sleep(0.3)
        return "⏳ Timed out waiting for task completion."

    async def _generate_response(self, user_input: str) -> str:
        """Generate a response using the LLM with conversation context."""
        # Optional RAG context (dense+sparse+rerank) from ingested documents.
        # Best-effort: if dependencies aren't available, it returns empty.
        rag_context = ""
        try:
            retriever = getattr(self, "_rag_retriever", None)
            if retriever is None:
                self._rag_retriever = RAGRetriever()
                retriever = self._rag_retriever

            # Fetch a larger candidate set from DB by lexical search.
            # We then rerank in-memory.
            candidate_rows = self.semantic_memory.search(user_input, limit=40)
            chunks = [
                {"content": r.get("content", ""), "metadata": r.get("metadata", {})}
                for r in candidate_rows
                if isinstance(r.get("content"), str)
            ]
            ranked = retriever.retrieve(user_input, chunks, top_k_dense=20, top_k_sparse=20, top_k_final=6)
            if ranked:
                rag_context = "\n".join([f"- {r.content[:500]}" for r in ranked])
                rag_context = f"[RAG retrieved chunks]\n{rag_context}"
        except Exception:
            rag_context = ""

        recent_messages = self.short_term_memory.get_messages(limit=6)
        conversation_lines = []
        for msg in recent_messages:
            role = {"user": "User", "assistant": "Assistant", "system": "System"}.get(msg.role, msg.role)
            conversation_lines.append(f"{role}: {msg.content}")
        conversation_context = "\n".join(conversation_lines)
        response = await self.llm.generate_async(
            prompt=user_input,
            conversation_context=conversation_context,
            temperature=0.7,
        )

        return response

    # ── Task Management ──────────────────────────────────────────────────

    async def create_and_execute_task(self, description: str) -> Task:
        """Create a task and add it to the execution queue."""
        return await self.task_manager.create_task(description)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        return self.task_manager.cancel_task(task_id)

    def get_active_tasks(self) -> List[Task]:
        """Get currently active tasks."""
        return self.task_manager.get_active_tasks()

    def get_task_history(self, limit: int = 20) -> List[Task]:
        """Get task execution history."""
        return self.task_manager.get_completed_tasks(limit=limit)

    def _on_task_update(self, task: Task) -> None:
        """Handle task status updates."""
        logger.debug(f"Task {task.id} status: {task.status.value}")

    # ── System Information ──────────────────────────────────────────────

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status information."""
        status = {
            "model_connected": self._model_connected,
            "llm_mode": self.current_llm_mode,
            "processing": self._processing,
            "memory_usage": {
                "short_term_count": self.short_term_memory.message_count,
            },
            "active_tasks": len(self.task_manager.get_active_tasks()),
            "total_tasks": len(self.task_manager.get_all_tasks()),
            "registered_tools": len(self.tool_registry.get_all_tools()),
        }
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            status["database"] = db.get_stats()
        except Exception:
            pass
        return status

    # ── Cleanup ──────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Clean up all agent resources."""
        logger.info("Cleaning up agent resources...")
        self.task_manager.stop_worker()
        self.long_term_memory.cleanup_expired()
        logger.info("Agent cleanup complete")
