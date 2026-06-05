"""
ArynoxTech AI Agent - CLI Entry Point
====================================
Command-line interface supporting both online (Groq) and offline (local GGUF) modes.
Run: python cli.py
"""

import sys
import asyncio
from pathlib import Path

# Initialize logging first
from utils.logger import LoggerFactory
LoggerFactory.initialize()

from utils.logger import get_logger
from agent.agent_core import AgentCore
from config.settings import LLM_CONFIG
from utils.llm_factory import get_llm_factory, LLMMode

logger = get_logger("cli")


async def chat_loop():
    """Main CLI chat loop."""
    agent = AgentCore()

    # Check model connection (auto-detects online/offline)
    connected = agent.check_model_connection()
    if not connected:
        print("[ERROR] No LLM backend available.")
        print("  • Set GROQ_API_KEY in .env for online mode")
        print("  • OR set LOCAL_MODEL_ENABLED=1 and LOCAL_MODEL_PATH in .env for offline mode")
        return

    mode_name = agent.current_llm_mode

    print("\n" + "=" * 60)
    print(f"ArynoxTech AI Agent (CLI Mode) — {mode_name}")
    print("=" * 60)
    print("Type 'exit', 'quit', or Ctrl+C to end the session.")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "bye"):
                print("\nGoodbye!")
                break

            print("\nAssistant: ", end="", flush=True)
            response = await agent.process_user_input(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")


def main():
    """CLI entry point."""
    # Detect available mode
    factory = get_llm_factory()
    mode = factory.detect_mode()

    if mode == LLMMode.UNAVAILABLE:
        print("=" * 60)
        print("  ArynoxTech AI Agent")
        print("=" * 60)
        print("\n[WARN] No LLM backend available.")
        print()
        print("  Option 1 — Online (Groq API):")
        print("    Set GROQ_API_KEY in .env file")
        print()
        print("  Option 2 — Offline (Local Model):")
        print("    1. Download a GGUF model (e.g., Phi-3-mini-4k-instruct-q4.gguf)")
        print("    2. Set in .env:")
        print("       LOCAL_MODEL_ENABLED=1")
        print("       LOCAL_MODEL_PATH=D:\\path\\to\\model.gguf")
        print()
        sys.exit(1)

    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
