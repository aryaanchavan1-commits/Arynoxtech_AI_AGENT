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
ArynoxTech AI Agent AI Agent - Browser Tool
==================================
Tool for opening websites and performing browser automation
using Selenium WebDriver.
"""

import time
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


class BrowserTool(BaseTool):
    """
    Tool for browser operations:
    - Open websites in a browser
    - Basic browser automation (click, fill forms, extract text)
    - Take screenshots
    """

    name: str = "browser_tool"
    description: str = "Open websites if requested, perform basic browser automation."
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG["browser"]
        self._driver = None

    @property
    def driver(self):
        """Lazy import and initialize Selenium WebDriver."""
        if self._driver is None:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.chrome.service import Service

                options = Options()
                if self.config.get("headless", False):
                    options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1280,720")

                self._driver = webdriver.Chrome(options=options)
                self._driver.implicitly_wait(self.config.get("timeout_seconds", 30))
                self.logger.info("Browser driver initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize browser driver: {e}")
                raise RuntimeError(
                    "Browser automation requires Chrome and chromedriver installed. "
                    f"Error: {e}"
                )
        return self._driver

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute browser tool operation.

        Args:
            action: 'open', 'get_text', 'screenshot', 'click', 'fill_form', 'search'
            url: URL to navigate to
            selector: CSS selector (for click/fill)
            text: Text to type (for fill_form)
            query: Search query (for search)

        Returns:
            ToolResult with operation outcome
        """
        start_time = time.time()
        action = kwargs.get("action", "open")

        try:
            if action == "open":
                return await self._open_url(kwargs, start_time)
            elif action == "get_text":
                return await self._get_text(kwargs, start_time)
            elif action == "screenshot":
                return await self._screenshot(kwargs, start_time)
            elif action == "click":
                return await self._click(kwargs, start_time)
            elif action == "fill_form":
                return await self._fill_form(kwargs, start_time)
            elif action == "search":
                return await self._search(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except RuntimeError as e:
            # Browser not available - provide graceful message
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Browser automation not available: {e}. "
                "Please install Chrome and chromedriver for browser features.",
                execution_time_ms=elapsed,
            )
        except Exception as e:
            self.logger.exception(f"Browser tool error: {e}")
            return ToolResult.error_result(
                f"Browser operation failed: {str(e)}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _open_url(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Open a URL in the browser."""
        url = kwargs.get("url", "https://www.google.com")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self.driver.get(url)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Opened: {url}",
            data={
                "url": url,
                "title": self._driver.title,
                "page_source_length": len(self._driver.page_source),
            },
            execution_time_ms=elapsed,
        )

    async def _get_text(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Extract visible text from the current page."""
        body = self.driver.find_element("tag name", "body")
        text = body.text
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Extracted {len(text)} chars from page",
            data={
                "url": self.driver.current_url,
                "title": self.driver.title,
                "text": text[:5000],  # Limit to 5000 chars
                "full_length": len(text),
            },
            execution_time_ms=elapsed,
        )

    async def _screenshot(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Take a screenshot of the current page."""
        from pathlib import Path
        output_path = kwargs.get("output_path", "screenshot.png")
        
        self.driver.save_screenshot(output_path)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Screenshot saved to: {output_path}",
            data={"path": str(Path(output_path).resolve())},
            execution_time_ms=elapsed,
        )

    async def _click(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Click an element on the page."""
        selector = kwargs.get("selector", "")
        by = kwargs.get("by", "css selector")

        element = self.driver.find_element(by, selector)
        element.click()
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Clicked element: {selector}",
            data={"url": self.driver.current_url, "selector": selector},
            execution_time_ms=elapsed,
        )

    async def _fill_form(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Fill a form field with text."""
        selector = kwargs.get("selector", "")
        text = kwargs.get("text", "")
        by = kwargs.get("by", "css selector")

        element = self.driver.find_element(by, selector)
        element.clear()
        element.send_keys(text)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Filled '{selector}' with text ({len(text)} chars)",
            data={"selector": selector, "text_length": len(text)},
            execution_time_ms=elapsed,
        )

    async def _search(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Perform a web search (uses Google by default)."""
        query = kwargs.get("query", "")

        if not query:
            return ToolResult.failure(
                "No search query provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        self.driver.get(search_url)
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Searched: {query}",
            data={"query": query, "url": search_url, "title": self.driver.title},
            execution_time_ms=elapsed,
        )

    def cleanup(self) -> None:
        """Close the browser driver."""
        if self._driver:
            try:
                self._driver.quit()
                self.logger.info("Browser driver closed")
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}")