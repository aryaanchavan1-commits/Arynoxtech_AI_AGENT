# Copyright (c) 2026 Aryan Chavan (ArynoxTech)
# Licensed under the MIT License. See LICENSE file in the project root.

"""
ArynoxTech AI Agent AI Agent - Planner
=============================
Responsible for breaking down user requests into actionable steps
and selecting appropriate tools for each step.
Uses Groq LLM for intelligent task decomposition.
"""

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from utils.llama_client import LlamaClient
from utils.logger import get_logger

logger = get_logger(__name__)


class StepStatus(Enum):
    """Status of an individual planning step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """
    A single step in a multi-step plan.

    Attributes:
        description: What this step does
        tool_name: Which tool to use
        tool_params: Parameters for the tool
        status: Current step status
        result: Execution result
        order: Step sequence number
    """
    description: str
    tool_name: str
    tool_params: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        return {
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "status": self.status.value,
            "result": self.result,
            "order": self.order,
        }


@dataclass
class Plan:
    """
    A complete execution plan with multiple steps.

    Attributes:
        original_request: The user's original request
        steps: List of PlanStep objects
        status: Overall plan status
        created_at: When the plan was created
    """
    original_request: str
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "created"
    created_at: float = field(default_factory=time.time)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "original_request": self.original_request,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
        }


class Planner:
    """
    Creates execution plans by analyzing user requests and breaking
    them into tool-driven steps using Groq LLM.
    """

    def __init__(self, llm_client: Optional[LlamaClient] = None) -> None:
        """
        Initialize the planner.

        Args:
            llm_client: Optional Groq client instance
        """
        self.llm = llm_client or LlamaClient()
        self._planning_prompt_template = self._build_planning_prompt()

    def _build_planning_prompt(self) -> str:
        """Build the prompt template for planning."""
        return (
            "You are a task planning AI. Break the following user request into "
            "a sequence of steps that can be executed using available tools.\n\n"
            "Available tools:\n"
            "- excel_tool: Read/create/modify Excel files, GST calc, inventory reports, formulas, charts\n"
            "- file_tool: Create/rename/move/delete/search/organize files and folders\n"
            "- pdf_tool: Extract text from PDF files\n"
            "- browser_tool: Open websites, browser automation, search\n"
            "- system_tool: Monitor CPU/RAM/disk, launch apps, type text, system info\n"
            "- database_tool: Store/retrieve memories, SQL queries, multi-engine DB operations\n"
            "- web_search_tool: Search web, get page content, search and summarize\n"
            "- data_analysis_tool: Load/clean/analyze data, ETL pipelines, statistics, correlations, forecasting\n"
            "- data_entry_tool: Create/edit CSV/JSON, manage records, batch import, validate data\n"
            "- personal_assistant_tool: Reminders, notes, timers, to-do lists, calendar, weather\n"
            "- report_tool: Generate PDF/Excel/CSV/chart/image reports\n"
            "- app_automation_tool: Social media (Instagram/FB/WhatsApp), web automation\n"
            "- document_ingestion_tool: Ingest files into searchable memory storage\n"
            "- camera_tool: Take photos, record video, detect objects/faces, recognize people\n"
            "- ml_tool: Train ML models, predict, evaluate, preprocess data, feature engineering\n\n"
            "Output format (JSON only, no other text):\n"
            "{\n"
            '  "steps": [\n'
            "    {\n"
            '      "description": "Step description",\n'
            '      "tool": "tool_name",\n'
            '      "params": {"param1": "value1"}\n'
            "    }\n"
            "  ],\n"
            '  "reasoning": "Brief explanation of the plan"\n'
            "}\n\n"
            "User request: {request}\n\n"
            "Plan:"
        )

    def _create_notepad_type_plan(self, user_request: str) -> Plan:
        """Deterministic plan for: open notepad and type some text."""
        plan = Plan(original_request=user_request)
        lower = user_request.lower()

        # Extract app name (we only support notepad here)
        app_name = "notepad"

        # Extract text after the word "type" (best-effort)
        text = ""
        m = re.search(r"type\s+([^\n\r]+)", user_request, flags=re.IGNORECASE)
        if m:
            text = m.group(1).strip().strip('"\'')
        else:
            # fallback: if user says: "type pythonbyai"
            m2 = re.search(r"type\s+(.+)$", user_request, flags=re.IGNORECASE)
            if m2:
                text = m2.group(1).strip().strip('"\'')

        plan.steps.append(
            PlanStep(
                description=f"Open Notepad and type: {text[:80]}" if text else "Open Notepad",
                tool_name="system_tool",
                tool_params={
                    "action": "open_app_and_type",
                    "app_name": app_name,
                    "text": text,
                    "delay_seconds": 0.8,
                },
                order=1,
            )
        )
        return plan

    async def create_plan(self, user_request: str) -> Plan:
        """Create an execution plan for a user request."""
        logger.info(f"Creating plan for: {user_request[:100]}...")

        # Deterministic planning for obvious tool requests.
        lowered = user_request.lower()
        tool_hints = [
            "excel", "gst", "inventory", "spreadsheet",
            "pdf", "extract",
            "file", "folder", "rename", "move", "delete", "create", "write",
            "browser", "website", "url", "http",
            "cpu", "ram", "system info", "disk", "launch", "open app", "process",
            "remember", "store memory", "recall", "history", "preference",
            "instagram", "facebook", "twitter", "messages", "dm", "social",
            "whatsapp", "telegram", "messenger", "linkedin", "snapchat",
            "gmail", "outlook", "email", "inbox",
            "chrome", "search google", "search web", "web search",
            "camera", "webcam", "photo", "capture", "take picture", "take photo",
            "record video", "face detect", "detect face",
            "ml", "machine learning", "train model", "predict", "prediction",
            "classify", "classifier", "regression", "feature engineering",
            "preprocess data", "train", "evaluate model", "model accuracy",
            "file system", "browse files", "navigate", "list directory",
            "documents", "open folder", "open file", "windows", "this pc",
            "my computer", "c drive", "d drive",
        ]
        # Deterministic planning for desktop open+type commands
        if ("notepad" in lowered and "type" in lowered) or ("open notepad" in lowered and "type" in lowered):
            return self._create_notepad_type_plan(user_request)

        # App automation / social/email style requests
        if any(h in lowered for h in [
            "instagram", "snapchat", "youtube", "outlook", "gmail", "facebook",
            "dm", "direct message", "direct messages", "message", "send message",
            "check emails", "check inbox", "inbox", "followers",
            "open bluestacks", "open apps inside", "open inside",
            "extract", "messages"
        ]):
            return self._create_simple_plan(user_request)

        if any(h in lowered for h in tool_hints):
            return self._create_simple_plan(user_request)


        plan = Plan(original_request=user_request)

        # Avoid blocking forever if the model is slow/hung.
        try:
            prompt = self._planning_prompt_template.replace(
                "{request}", user_request
            )
            import asyncio
            response = await asyncio.wait_for(
                self.llm.generate_async(
                    prompt,
                    max_tokens=512,
                    temperature=0.3,
                ),
                timeout=3,
            )





            # Extract JSON from response
            steps = self._parse_llm_response(response)

            if steps:
                for i, step_data in enumerate(steps):
                    tool_name = step_data.get("tool", "").strip()
                    # Sanitize tool name
                    if not tool_name.endswith("_tool"):
                        tool_name = f"{tool_name}_tool" if "_" not in tool_name else tool_name

                    plan_step = PlanStep(
                        description=step_data.get("description", "Execute step"),
                        tool_name=tool_name,
                        tool_params=step_data.get("params", {}),
                        order=i + 1,
                    )
                    plan.steps.append(plan_step)

                logger.info(
                    f"Plan created with {len(plan.steps)} steps via LLM"
                )
            else:
                # Fallback to simple plan
                plan = self._create_simple_plan(user_request)


        except Exception as e:
            logger.warning(f"LLM planning failed ({e}), using fallback")
            plan = self._create_simple_plan(user_request)

        return plan

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response to extract plan steps.

        Args:
            response: Raw LLM response text

        Returns:
            List of step dictionaries
        """
        # Try to find JSON in the response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get("steps", [])
            except json.JSONDecodeError:
                logger.debug("Failed to parse JSON from LLM response")

        # Fallback: try to extract steps from numbered list
        steps = []
        lines = response.strip().split("\n")
        current_step = {}

        for line in lines:
            line = line.strip().lower()
            if re.match(r"^\d+[\.\)]", line):
                if current_step:
                    steps.append(current_step)
                current_step = {
                    "description": line,
                    "tool": self._guess_tool(line),
                    "params": {},
                }
            elif "tool:" in line:
                current_step["tool"] = line.split("tool:")[-1].strip()
            elif "param" in line:
                # Generic param extraction
                pass

        if current_step:
            steps.append(current_step)

        return steps

    def _guess_tool(self, description: str) -> str:
        """Guess the appropriate tool based on description keywords."""
        desc_lower = description.lower()

        # Web search routing
        if any(word in desc_lower for word in [
            "search for ", "search web", "google ", "look up", "find online",
            "what is", "who is", "news about", "latest", "weather in",
        ]):
            return "web_search_tool"

        # App/web automation routing
        if any(word in desc_lower for word in [
            "app_automation", "app automation", "instagram", "snapchat", "youtube",
            "outlook", "gmail", "facebook", "twitter", "telegram", "whatsapp",
            "dm", "direct message", "direct messages", "message", "messages",
            "send message", "send messages", "check emails", "check inbox", "inbox",
            "followers", "open bluestacks", "open apps inside", "open inside",
            "social media", "social",
        ]):
            return "app_automation_tool"

        # Camera tool routing
        if any(word in desc_lower for word in [
            "camera", "webcam", "take photo", "take picture", "capture photo",
            "record video", "detect face", "face detect", "face detection",
            "list cameras", "open camera", "show camera", "snap",
            "detect object", "object detect", "what is this", "what is that",
            "identify object", "recognize person", "recognize face",
            "recognize human", "recognize me", "who is this", "who am i",
            "learn this person", "learn face", "save face", "teach my face",
            "know this person", "new person", "who do you know",
            "who can you recognize", "list people", "known people",
        ]):
            return "camera_tool"

        # ML tool routing
        if any(word in desc_lower for word in [
            "train model", "train a model", "machine learning", "ml model",
            "predict", "make prediction", "classify", "classifier",
            "regression", "feature engineering", "feature engineer",
            "preprocess data", "preprocess", "evaluate model",
            "model accuracy", "ml engineer", "data science",
        ]):
            return "ml_tool"

        if any(word in desc_lower for word in ["excel", "sheet", "spreadsheet", "gst", "inventory"]):
            return "excel_tool"
        elif any(word in desc_lower for word in ["data quality", "quality report", "profile data", "schema validation",
            "pii detect", "compliance", "anomaly detect", "merge dataset", "merge data",
            "profiling", "data profiling", "business utils",
        ]):
            return "business_utils_tool"
        elif any(word in desc_lower for word in ["file", "folder", "directory", "create", "rename", "move", "delete"]):
            return "file_tool"
        elif "pdf" in desc_lower:
            return "pdf_tool"
        elif any(word in desc_lower for word in ["browser", "web", "website", "url", "http", "search"]):
            return "browser_tool"
        elif any(word in desc_lower for word in ["cpu", "memory", "ram", "system", "launch", "app", "program", "process"]):
            return "system_tool"
        elif any(word in desc_lower for word in ["memory", "remember", "store", "recall", "history", "preference"]):
            return "database_tool"
        elif any(word in desc_lower for word in ["analyze", "analysis", "data", "statistics", "chart", "graph"]):
            return "data_analysis_tool"
        elif any(word in desc_lower for word in ["remind", "reminder", "note", "todo", "calendar", "timer"]):
            return "personal_assistant_tool"
        elif any(word in desc_lower for word in ["report", "generate pdf", "generate excel", "generate csv"]):
            return "report_tool"
        else:
            return "system_tool"  # Default fallback

    def _create_simple_plan(self, user_request: str) -> Plan:
        """
        Create a simple single-step plan as fallback.

        Args:
            user_request: The user's request

        Returns:
            Plan with a single step
        """
        plan = Plan(original_request=user_request)
        tool_name = self._guess_tool(user_request)
        lowered = user_request.lower()

        # Smart param routing based on detected intent
        params = {"query": user_request}

        if tool_name == "app_automation_tool":
            if "check" in lowered or "see" in lowered or "read" in lowered:
                params["action"] = "check_messages"
                # Detect which platform
                for plat in ["instagram", "facebook", "messenger", "twitter", "whatsapp", "telegram", "gmail", "outlook", "linkedin"]:
                    if plat in lowered:
                        params["platform"] = plat
                        break
            elif "reply" in lowered or "send" in lowered or "message" in lowered:
                params["action"] = "reply_message"
                for plat in ["instagram", "facebook", "messenger", "twitter", "whatsapp", "telegram", "gmail", "outlook", "linkedin"]:
                    if plat in lowered:
                        params["platform"] = plat
                        break
            else:
                params["action"] = "open_social"
                for plat in ["instagram", "facebook", "messenger", "twitter", "whatsapp", "telegram", "gmail", "outlook", "linkedin"]:
                    if plat in lowered:
                        params["platform"] = plat
                        break

        elif tool_name == "web_search_tool":
            params["action"] = "search"
            # Extract search query
            for prefix in ["search for ", "search ", "look up ", "find ", "google "]:
                if prefix in lowered:
                    params["query"] = user_request[lowered.find(prefix) + len(prefix):].strip()
                    break

        elif tool_name == "camera_tool":
            if "photo" in lowered or "picture" in lowered or "capture" in lowered or "snap" in lowered:
                params["action"] = "capture_photo"
            elif "record" in lowered or "video" in lowered:
                params["action"] = "record_video"
                import re
                dur_match = re.search(r"(\d+)\s*seconds?", lowered)
                if dur_match:
                    params["duration"] = int(dur_match.group(1))
            elif "face" in lowered and ("recognize" in lowered or "who" in lowered):
                params["action"] = "recognize_person"
            elif "face" in lowered:
                params["action"] = "detect_faces"
            elif "detect object" in lowered or "object detect" in lowered:
                params["action"] = "detect_objects"
            elif "what is this" in lowered or "what is that" in lowered or "identify" in lowered:
                params["action"] = "identify_object"
            elif "recognize" in lowered or "who is" in lowered or "who am" in lowered:
                params["action"] = "recognize_person"
            elif "learn" in lowered or "teach" in lowered or "save face" in lowered or "new person" in lowered:
                params["action"] = "learn_new_person"
            elif "list" in lowered or "who do you know" in lowered or "known" in lowered:
                params["action"] = "list_known_people"
            else:
                params["action"] = "capture_photo"

        elif tool_name == "ml_tool":
            if "train" in lowered:
                params["action"] = "train_model"
            elif "predict" in lowered:
                params["action"] = "predict"
            elif "evaluate" in lowered:
                params["action"] = "evaluate"
            elif "preprocess" in lowered:
                params["action"] = "preprocess"
            elif "feature" in lowered:
                params["action"] = "feature_engineering"
            else:
                params["action"] = "train_model"

        elif tool_name == "business_utils_tool":
            if "quality" in lowered or "quality report" in lowered:
                params["action"] = "data_quality_report"
            elif "profile" in lowered:
                params["action"] = "data_profiling"
            elif "schema" in lowered or "validate" in lowered:
                params["action"] = "schema_validation"
            elif "pii" in lowered or "personal info" in lowered:
                params["action"] = "pii_detection"
            elif "complian" in lowered or "gdpr" in lowered:
                params["action"] = "compliance_check"
            elif "anomal" in lowered or "outlier" in lowered:
                params["action"] = "anomaly_detection"
            elif "merge" in lowered or "join" in lowered:
                params["action"] = "merge_datasets"
            else:
                params["action"] = "data_quality_report"

        elif tool_name == "report_tool":
            params["action"] = "generate_report"

        elif tool_name == "system_tool":
            if "open" in lowered:
                params["action"] = "open_app"
                # Extract app name after "open"
                for prefix in ["open app ", "open ", "launch "]:
                    if prefix in lowered:
                        app = user_request[lowered.find(prefix) + len(prefix):].strip()
                        params["app_name"] = app
                        break
            elif "type" in lowered:
                params["action"] = "type_text"
            elif "cpu" in lowered:
                params["action"] = "cpu"
            elif "memory" in lowered or "ram" in lowered:
                params["action"] = "memory"
            else:
                params["action"] = "system_info"

        elif tool_name == "excel_tool":
            params["action"] = "auto"

        elif tool_name == "data_analysis_tool":
            params["action"] = "analyze"

        elif tool_name == "personal_assistant_tool":
            if "remind" in lowered or "reminder" in lowered:
                params["action"] = "set_reminder"
            elif "note" in lowered:
                params["action"] = "create_note"
            elif "todo" in lowered or "task" in lowered:
                params["action"] = "add_todo"
            else:
                params["action"] = "quick_info"

        else:
            params["action"] = "auto"

        plan.steps.append(
            PlanStep(
                description=f"Process: {user_request[:100]}",
                tool_name=tool_name,
                tool_params=params,
                order=1,
            )
        )
        logger.info("Created simple plan with %s", tool_name)
        return plan

    def validate_plan(self, plan: Plan) -> bool:
        """
        Validate that a plan has executable steps.

        Args:
            plan: The plan to validate

        Returns:
            True if plan is valid
        """
        if not plan.steps:
            logger.warning("Plan has no steps")
            return False

        for step in plan.steps:
            if not step.tool_name:
                logger.warning(f"Step {step.order} has no tool assigned")
                return False
            if not step.description:
                logger.warning(f"Step {step.order} has no description")
                return False

        return True

    def get_step_summary(self, plan: Plan) -> str:
        """
        Get a human-readable summary of the plan.

        Args:
            plan: The plan to summarize

        Returns:
            Formatted plan summary string
        """
        lines = [f"📋 Plan for: {plan.original_request[:80]}", ""]
        for step in plan.steps:
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }.get(step.status, "⏳")

            lines.append(
                f"  {status_icon} Step {step.order}: {step.description}"
            )
            lines.append(f"     Tool: {step.tool_name}")

        lines.append(f"\n📊 Total: {plan.total_steps} steps")
        return "\n".join(lines)
