"""
LLM Factory - Auto-detects API availability and falls back to local model.
"""

import os
import sys
from enum import Enum
from typing import Any, Optional

from utils.logger import get_logger
from config.settings import LLM_CONFIG, LOCAL_MODEL_ENABLED, LOCAL_MODEL_PATH, BASE_DIR

logger = get_logger(__name__)


class LLMMode(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"


class LLMFactory:
    """
    Factory that provides the best available LLM client.
    Detects Groq API availability and falls back to local Hugging Face model.
    """

    def __init__(self) -> None:
        self._online_client: Any = None
        self._local_client: Any = None
        self._mode: LLMMode = LLMMode.UNAVAILABLE
        self._checked: bool = False

    def _import_online(self):
        if self._online_client is None:
            from utils.llama_client import LlamaClient
            self._online_client = LlamaClient()

    def _import_local(self):
        if self._local_client is None:
            from utils.local_llm_client import LocalLLMClient
            self._local_client = LocalLLMClient()

    def detect_mode(self) -> LLMMode:
        """Detect which LLM mode is available. Checks API first, then local model."""
        if self._checked:
            return self._mode

        # 1) Check Groq API
        api_key = LLM_CONFIG.get("api_key", "")
        if api_key:
            try:
                self._import_online()
                if self._online_client.check_connection():
                    self._mode = LLMMode.ONLINE
                    self._checked = True
                    logger.info("LLM mode: ONLINE (Groq API)")
                    return self._mode
            except Exception as e:
                logger.warning(f"Groq API check failed: {e}")

        # 2) Check local model
        if LOCAL_MODEL_ENABLED:
            try:
                self._import_local()
                if self._local_client.check_connection():
                    self._mode = LLMMode.OFFLINE
                    self._checked = True
                    logger.info("LLM mode: OFFLINE (local Hugging Face model)")
                    return self._mode
            except Exception as e:
                logger.warning(f"Local model check failed: {e}")

        # 3) Force local even if LOCAL_MODEL_ENABLED is not set, if model file exists
        model_path = LOCAL_MODEL_PATH
        if os.path.exists(model_path):
            try:
                self._import_local()
                if self._local_client.check_connection():
                    self._mode = LLMMode.OFFLINE
                    self._checked = True
                    logger.info("LLM mode: OFFLINE (auto-detected local model)")
                    return self._mode
            except Exception as e:
                logger.warning(f"Local model load failed: {e}")

        self._checked = True
        self._mode = LLMMode.UNAVAILABLE
        logger.error("No LLM backend available (no API key and no local model)")
        return self._mode

    def get_client(self):
        """Get the best available LLM client."""
        mode = self.detect_mode()
        if mode == LLMMode.ONLINE:
            self._import_online()
            self._mode = LLMMode.ONLINE
            return self._online_client
        elif mode == LLMMode.OFFLINE:
            self._import_local()
            self._mode = LLMMode.OFFLINE
            return self._local_client
        raise RuntimeError(
            "No LLM backend available.\n"
            "  • Set GROQ_API_KEY in .env for online mode, OR\n"
            "  • Set LOCAL_MODEL_ENABLED=1 and LOCAL_MODEL_PATH in .env for offline mode\n"
            "  • Download a Hugging Face model and place it at the path specified in LOCAL_MODEL_PATH"
        )

    @property
    def mode(self) -> LLMMode:
        return self._mode

    @property
    def mode_name(self) -> str:
        return {
            LLMMode.ONLINE: "Online (Groq API)",
            LLMMode.OFFLINE: "Offline (Local Model)",
            LLMMode.UNAVAILABLE: "No Backend",
        }.get(self._mode, "Unknown")

    def reset(self) -> None:
        """Force re-detection on next call."""
        self._checked = False


# Singleton instance
_factory: Optional[LLMFactory] = None


def get_llm_factory() -> LLMFactory:
    global _factory
    if _factory is None:
        _factory = LLMFactory()
    return _factory


def get_llm_client():
    """Convenience function to get the best available LLM client."""
    return get_llm_factory().get_client()
