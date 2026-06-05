"""
Local LLM Client using Hugging Face transformers for offline inference.
Fully offline, no API key required. Uses PyTorch (CUDA if available).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import (
    LOCAL_MODEL_PATH, LOCAL_MODEL_N_CTX, LOCAL_MODEL_N_THREADS,
    LOCAL_MODEL_MAX_TOKENS, LOCAL_MODEL_TEMPERATURE, LOCAL_MODEL_TOP_P,
    LOCAL_MODEL_GPU_LAYERS, SYSTEM_PROMPT, BASE_DIR,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class LocalModelError(Exception):
    pass


class LocalModelNotAvailableError(LocalModelError):
    pass


class LocalLLMClient:
    """
    Client for running local models via Hugging Face transformers.
    Fully offline, no API key required. Supports CUDA GPU acceleration.
    """

    def __init__(self) -> None:
        self.model_path: str = LOCAL_MODEL_PATH
        self.max_tokens: int = LOCAL_MODEL_MAX_TOKENS
        self.temperature: float = LOCAL_MODEL_TEMPERATURE
        self.top_p: float = LOCAL_MODEL_TOP_P
        self._pipe: Any = None
        self._tokenizer: Any = None
        self._model: Any = None
        self._connected: bool = False

    def check_connection(self) -> bool:
        """Check if a local model can be loaded."""
        path = Path(self.model_path)
        if path.exists() and path.is_dir():
            # Hugging Face model directory
            has_model = any(path.glob("*.safetensors")) or any(path.glob("*.bin")) or any(path.glob("*.gguf"))
            if has_model:
                self._connected = True
                logger.info(f"Local model found at: {self.model_path}")
                return True
        elif path.exists() and path.suffix == ".gguf":
            # GGUF file exists - we can use it with transformers if needed
            self._connected = True
            logger.info(f"Local model file found at: {self.model_path}")
            return True
        else:
            # Try as HuggingFace repo ID
            repo_id = self.model_path.replace("\\", "/").split("/")
            if len(repo_id) >= 2 and "." not in repo_id[-1]:
                # Looks like a HuggingFace model ID (e.g., "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
                self._connected = True
                return True
            logger.error(f"Local model not found at: {self.model_path}")
            self._connected = False
            return False

    def _ensure_loaded(self) -> None:
        """Lazy-load the model via transformers."""
        if self._pipe is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading local model from {self.model_path} on {device}...")

            path = Path(self.model_path)
            model_id = str(path) if path.exists() else self.model_path

            # Use 4-bit if GPU VRAM < 8GB (fits RTX 3050 4GB)
            vram_gb = 0
            if device == "cuda":
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            use_4bit = device == "cuda" and vram_gb < 8

            # Limit CPU memory to avoid Windows page file errors
            max_memory = {0: "3.5GiB", "cpu": "8GiB"} if device == "cuda" else None

            if use_4bit:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
                model_kwargs = {
                    "quantization_config": quantization_config,
                    "device_map": "sequential",
                    "max_memory": max_memory,
                    "torch_dtype": torch.float16,
                    "low_cpu_mem_usage": True,
                }
            else:
                model_kwargs = {
                    "device_map": "sequential" if device == "cuda" else None,
                    "max_memory": max_memory,
                    "torch_dtype": torch.float16 if device == "cuda" else "auto",
                    "low_cpu_mem_usage": True,
                }

            self._tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            self._model = AutoModelForCausalLM.from_pretrained(
                model_id,
                trust_remote_code=True,
                **model_kwargs,
            )

            self._model.eval()

            self._pipe = pipeline(
                "text-generation",
                model=self._model,
                tokenizer=self._tokenizer,
                device=None if device == "cuda" else -1,
            )

            self._connected = True
            logger.info("Local model loaded successfully via transformers")

        except Exception as e:
            self._connected = False
            raise LocalModelError(f"Failed to load local model: {e}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_context: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Generate a response using the local model via transformers.

        Args:
            prompt: The user input / task description
            system_prompt: Optional system prompt override
            conversation_context: Recent conversation history for context
            **kwargs: Additional model parameters to override defaults

        Returns:
            Generated text response from the model
        """
        self._ensure_loaded()

        if system_prompt is None:
            system_prompt = SYSTEM_PROMPT

        # Build the full prompt with system context
        full_system = system_prompt.replace("{conversation}", conversation_context)
        full_system = full_system.replace("{task}", prompt)

        # Format as chat
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ]

        gen_kwargs = {
            "max_new_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "do_sample": kwargs.get("temperature", self.temperature) > 0,
            "pad_token_id": self._tokenizer.eos_token_id,
        }

        logger.debug(f"Sending prompt to local model ({len(str(messages))} chars)")

        try:
            output = self._pipe(
                messages,
                **gen_kwargs,
            )
            generated_text = output[0]["generated_text"][-1]["content"].strip()
            if not generated_text:
                logger.warning("Local model returned empty response")
                return "I could not generate a response. Please try rephrasing."
            logger.debug(f"Local model response ({len(generated_text)} chars)")
            return generated_text
        except Exception as e:
            logger.exception(f"Local model generation failed: {e}")
            raise LocalModelError(f"Model generation failed: {e}")

    async def generate_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_context: str = "",
        **kwargs: Any,
    ) -> str:
        """Async wrapper for generate()."""
        import asyncio
        return await asyncio.to_thread(
            self.generate,
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_context=conversation_context,
            **kwargs,
        )

    def is_connected(self) -> bool:
        return self._connected

    def is_model_loaded(self) -> bool:
        return self._pipe is not None

    def unload(self) -> None:
        """Unload the model to free memory."""
        import gc
        import torch
        self._pipe = None
        self._model = None
        self._tokenizer = None
        self._connected = False
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Local model unloaded from memory")
