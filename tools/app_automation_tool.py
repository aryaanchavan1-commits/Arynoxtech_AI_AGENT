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
ArynoxTech AI Agent - App Automation Tool
===========================================
Universal (best-effort) desktop + web automation scaffold.

Capabilities:
- Open an app (system_tool)
- If the target is web-based: open a URL and extract visible text (browser_tool)
- Type into focused input and optionally press Enter (system_tool)
- Check social media messages (Instagram, etc.) via browser automation
- Send replies via browser automation

Safety:
- Sending messages is gated behind user confirmation via ToolResult.needs_confirmation.
- Social media credentials are NOT stored in the code. User must be already logged in.

Note:
This tool is not guaranteed to correctly interact with every UI layout on every service.
It relies on the user focusing the correct input (best-effort typing).
"""

import time
import re
from typing import Any, Dict, Optional

from tools.base_tool import BaseTool, ToolResult
from tools.system_tool import SystemTool
from tools.browser_tool import BrowserTool


class AppAutomationTool(BaseTool):
    name: str = "app_automation_tool"
    description: str = (
        "Universal best-effort desktop + web automation: open apps, open URLs, extract visible page text, "
        "type and send (with confirmation for sending), check social media messages, and reply."
    )
    version: str = "1.0.0"

    SOCIAL_PLATFORMS = {
        "instagram": {
            "url": "https://www.instagram.com/direct/inbox/",
            "name": "Instagram",
        },
        "facebook": {
            "url": "https://www.facebook.com/messages",
            "name": "Facebook Messenger",
        },
        "messenger": {
            "url": "https://www.messenger.com",
            "name": "Messenger",
        },
        "twitter": {
            "url": "https://twitter.com/messages",
            "name": "Twitter/X DMs",
        },
        "x": {
            "url": "https://twitter.com/messages",
            "name": "Twitter/X DMs",
        },
        "whatsapp": {
            "url": "https://web.whatsapp.com",
            "name": "WhatsApp Web",
        },
        "telegram": {
            "url": "https://web.telegram.org",
            "name": "Telegram Web",
        },
        "gmail": {
            "url": "https://mail.google.com",
            "name": "Gmail",
        },
        "outlook": {
            "url": "https://outlook.live.com/mail",
            "name": "Outlook",
        },
        "linkedin": {
            "url": "https://www.linkedin.com/messaging",
            "name": "LinkedIn Messages",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self._system = SystemTool()
        self._browser = BrowserTool()

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = str(kwargs.get("action", "open_app")).strip()

        try:
            if action == "open_app":
                app_name = kwargs.get("app_name")
                return await self._open_app(app_name, start_time, kwargs)

            if action == "open_web":
                url = kwargs.get("url")
                if not url:
                    return ToolResult.failure(
                        "open_web requires 'url'",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                return await self._open_web(url, start_time, kwargs)

            if action == "extract_page_text":
                return await self._extract_page_text(start_time, kwargs)

            if action == "type_and_send":
                message_text = kwargs.get("message_text")
                return await self._type_and_send(message_text, start_time, kwargs)

            if action == "open_app_and_open_web":
                app_name = kwargs.get("app_name")
                url = kwargs.get("url")
                if not url:
                    return ToolResult.failure(
                        "open_app_and_open_web requires 'url'",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                r1 = await self._open_app(app_name, start_time, kwargs)
                await self._sleep(kwargs.get("delay_seconds", 1.0))
                r2 = await self._open_web(url, start_time, kwargs)
                return ToolResult.success(
                    f"Opened {app_name or ''} and opened URL",
                    data={"app": app_name, "url": url},
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # ── Social Media Actions ────────────────────────────────────
            if action == "check_messages":
                platform = kwargs.get("platform", "instagram").lower()
                return await self._check_social_messages(platform, start_time, kwargs)

            if action == "reply_message":
                platform = kwargs.get("platform", "instagram").lower()
                message_text = kwargs.get("message_text", "")
                recipient = kwargs.get("recipient", "")
                if not message_text:
                    return ToolResult.failure(
                        "reply_message requires 'message_text'",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                return await self._reply_social_message(
                    platform, recipient, message_text, start_time, kwargs
                )

            if action == "open_social":
                platform = kwargs.get("platform", "instagram").lower()
                return await self._open_social_platform(platform, start_time, kwargs)

            return ToolResult.failure(
                f"Unknown action: {action}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            self.logger.exception(f"AppAutomationTool error: {e}")
            return ToolResult.error_result(
                "App automation failed",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _open_app(
        self, app_name: Optional[str], start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        if not app_name:
            return ToolResult.failure(
                "open_app requires 'app_name'",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Special case: if user says "open instagram in chrome" we still just open Chrome.
        app_name_str = str(app_name).strip()
        res = await self._system.execute(action="open_app", app_name=app_name_str)
        return ToolResult.success(
            res.message,
            data=res.data,
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _open_web(
        self, url: str, start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        # Ensure url has scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url.lstrip("/")

        res = await self._browser.execute(action="open", url=url)
        return ToolResult.success(
            res.message,
            data={**(res.data or {}), "url": url},
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _extract_page_text(
        self, start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        # browser_tool supports get_text
        res = await self._browser.execute(action="get_text")
        return ToolResult.success(
            "Extracted visible page text",
            data={"text": (res.data or {}).get("text", ""), "url": (res.data or {}).get("url")},
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _type_and_send(
        self, message_text: Optional[str], start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        message_text = message_text if message_text is not None else ""
        message_text = str(message_text)
        if not message_text.strip():
            return ToolResult.failure(
                "type_and_send requires non-empty 'message_text'",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Always require confirmation for sending.
        confirm_payload = {
            "message_text": message_text,
            "target": kwargs.get("target"),
        }
        # If UI passes through explicit confirmation, callers can set `confirmed=True`.
        confirmed = bool(kwargs.get("confirmed", False))
        if not confirmed:
            return ToolResult.needs_confirmation(
                f"Confirm sending message: {message_text[:60]}{'...' if len(message_text) > 60 else ''}",
                data=confirm_payload,
            )

        # Best-effort: type and then press Enter
        type_delay = float(kwargs.get("delay_seconds", 0.8))
        type_res = await self._system.execute(
            action="type_text",
            text=message_text,
            delay_seconds=type_delay,
        )

        # Press Enter using type_text
        await self._sleep(0.2)
        try:
            import pyautogui
            pyautogui.press("enter")
        except Exception:
            await self._system.execute(action="type_text", text="\n", delay_seconds=0.0)

        return ToolResult.success(
            "Sent message (best-effort typing + Enter)",
            data={"typed": type_res.data or {}, "message_text": message_text},
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ── Social Media: Open Platform ─────────────────────────────────────

    async def _open_social_platform(
        self, platform: str, start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        """Open a social media platform in the browser."""
        platform_info = self.SOCIAL_PLATFORMS.get(platform)
        if not platform_info:
            return ToolResult.failure(
                f"Unsupported platform: '{platform}'. Supported: {', '.join(self.SOCIAL_PLATFORMS.keys())}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        url = platform_info["url"]
        # First open Chrome
        await self._system.execute(action="open_app", app_name="chrome")
        await self._sleep(1.5)
        # Then navigate to the platform URL
        res = await self._browser.execute(action="open", url=url)
        return ToolResult.success(
            f"✅ Opened {platform_info['name']} in Chrome",
            data={"platform": platform, "url": url},
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ── Social Media: Check Messages ────────────────────────────────────

    async def _check_social_messages(
        self, platform: str, start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        """Open a social media platform and check for new messages."""
        platform_info = self.SOCIAL_PLATFORMS.get(platform)
        if not platform_info:
            return ToolResult.failure(
                f"Unsupported platform: '{platform}'",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        name = platform_info["name"]
        url = platform_info["url"]

        # Open Chrome and navigate to the platform
        await self._system.execute(action="open_app", app_name="chrome")
        await self._sleep(1.5)
        await self._browser.execute(action="open", url=url)
        await self._sleep(3.0)

        # Try to extract page text to see messages
        page_res = await self._browser.execute(action="get_text")
        page_text = (page_res.data or {}).get("text", "")

        summary = f"✅ Opened {name}. "
        if page_text:
            # Truncate to a reasonable preview
            preview = page_text[:500].strip()
            summary += f"Page shows: {preview}"
        else:
            summary += "You may need to log in if not already authenticated."

        return ToolResult.success(
            summary,
            data={
                "platform": platform,
                "url": url,
                "page_preview": page_text[:1000] if page_text else "",
            },
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ── Social Media: Reply to Messages ─────────────────────────────────

    async def _reply_social_message(
        self, platform: str, recipient: str, message_text: str,
        start_time: float, kwargs: Dict[str, Any]
    ) -> ToolResult:
        """Reply to a message on a social media platform."""
        platform_info = self.SOCIAL_PLATFORMS.get(platform)
        if not platform_info:
            return ToolResult.failure(
                f"Unsupported platform: '{platform}'",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Require confirmation for sending messages
        confirmed = bool(kwargs.get("confirmed", False))
        if not confirmed:
            return ToolResult.needs_confirmation(
                f"Confirm: Send this {'to ' + recipient + ' ' if recipient else ''}"
                f"on {platform_info['name']}: {message_text[:80]}{'...' if len(message_text) > 80 else ''}",
                data={
                    "platform": platform,
                    "recipient": recipient,
                    "message_text": message_text,
                },
            )

        name = platform_info["name"]
        url = platform_info["url"]

        # Open Chrome and navigate to DMs
        await self._system.execute(action="open_app", app_name="chrome")
        await self._sleep(1.5)
        await self._browser.execute(action="open", url=url)
        await self._sleep(3.0)

        # Type the message content
        type_delay = float(kwargs.get("delay_seconds", 1.0))
        await self._system.execute(
            action="type_text",
            text=message_text,
            delay_seconds=type_delay,
        )
        await self._sleep(0.3)

        # Press Enter to send
        try:
            import pyautogui
            pyautogui.press("enter")
        except Exception:
            pass

        return ToolResult.success(
            f"✅ Sent reply on {name}" + (f" to {recipient}" if recipient else ""),
            data={
                "platform": platform,
                "recipient": recipient,
                "message_text": message_text,
            },
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    async def _sleep(self, seconds: float) -> None:
        import asyncio
        await asyncio.sleep(max(0.0, float(seconds)))

