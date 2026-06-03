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
ArynoxTech AI Agent - Groq LLM Client
====================================
Handles communication with the Groq API for fast LLM inference.
"""

from typing import Any, Dict, Optional

from groq import Groq, RateLimitError, APIError

from config.settings import LLM_CONFIG, SYSTEM_PROMPT
from utils.logger import get_logger

logger = get_logger(__name__)


class LlamaClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class ModelNotAvailableError(LlamaClientError):
    """Raised when the model API is not available or unreachable."""
    pass


class LlamaClient:
    """
    Client for communicating with Groq API for LLM inference.
    """

    def __init__(self) -> None:
        """Initialize the Groq client with API configuration."""
        self.api_key: str = LLM_CONFIG["api_key"]
        if not self.api_key:
            logger.warning("GROQ_API_KEY not set. LLM functionality will be limited.")
        self.model: str = LLM_CONFIG["model"]
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        self.default_params: Dict[str, Any] = {
            "max_tokens": LLM_CONFIG["max_tokens"],
            "temperature": LLM_CONFIG["temperature"],
            "top_p": LLM_CONFIG["top_p"],
        }
        self._connected: bool = bool(self.api_key)
        logger.info(f"LlamaClient initialized with model: {self.model}")

    def check_connection(self) -> bool:
        """Check if the Groq API is accessible with the provided API key."""
        if not self.client:
            self._connected = False
            return False
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            self._connected = True
            logger.info("Successfully connected to Groq API")
            return True
        except Exception as e:
            logger.error(f"Cannot connect to Groq API: {e}")
            self._connected = False
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_context: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Send a prompt to Groq API and get the generated response.

        Args:
            prompt: The user input / task description
            system_prompt: Optional system prompt override
            conversation_context: Recent conversation history for context
            **kwargs: Additional model parameters to override defaults

        Returns:
            Generated text response from the model
        """
        if not self.client:
            raise ModelNotAvailableError(
                "Groq API key not configured. Set GROQ_API_KEY environment variable."
            )

        # Build messages with conversation context
        messages = []
        
        # Add system prompt
        if system_prompt is None:
            system_prompt = SYSTEM_PROMPT
        
        full_system = system_prompt.replace("{conversation}", conversation_context)
        messages.append({"role": "system", "content": full_system})
        messages.append({"role": "user", "content": prompt})

        # Merge parameters and convert n_predict to max_tokens for Groq API
        params = {**self.default_params, **kwargs}
        params.pop("prompt", None)  # Remove prompt if accidentally passed
        # Convert n_predict (old llama.cpp param) to max_tokens (Groq param)
        if "n_predict" in params:
            params["max_tokens"] = params.pop("n_predict")

        logger.debug(f"Sending prompt to Groq ({len(str(messages))} chars)")

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **params,
            )
            generated_text = completion.choices[0].message.content or ""
            generated_text = generated_text.strip()

            if not generated_text:
                logger.warning("Model returned empty response")
                return "I could not generate a response. Please try rephrasing."

            logger.debug(f"Model response ({len(generated_text)} chars): {generated_text[:200]}...")
            return generated_text

        except RateLimitError as e:
            raise LlamaClientError(f"Rate limit exceeded: {e}")
        except APIError as e:
            raise LlamaClientError(f"Groq API error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error during model generation: {e}")
            raise LlamaClientError(f"Model generation failed: {e}")

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
        """Check if we have a confirmed connection to the API."""
        return self._connected

    def wait_for_server(
        self,
        timeout_seconds: int = 60,
        retry_interval: float = 2.0,
    ) -> bool:
        """Check if Groq API is available."""
        logger.info("Checking Groq API availability...")
        return self.check_connection()