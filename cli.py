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
ArynoxTech AI Agent - CLI Entry Point
====================================
Command-line interface version using Groq API.
Run commands: python main.py (GUI) or python cli.py (CLI)
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

logger = get_logger("cli")


async def chat_loop():
    """Main CLI chat loop."""
    agent = AgentCore()
    
    # Check model connection
    connected = agent.check_model_connection()
    if not connected:
        print("[ERROR] Cannot connect to Groq API. Check your GROQ_API_KEY in .env file.")
        return
    
    print("\n" + "=" * 60)
    print("ArynoxTech AI Agent (CLI Mode)")
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
    print("=" * 60)
    print("  ArynoxTech AI Agent")
    print("  CLI Mode - Powered by Groq")
    print("=" * 60)
    
    # Check API key
    if not LLM_CONFIG.get("api_key"):
        print("\n[WARN] GROQ_API_KEY not set in .env file")
        print("Please add your key to .env: GROQ_API_KEY=your_key_here")
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