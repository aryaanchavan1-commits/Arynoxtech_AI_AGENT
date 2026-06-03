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

"""Base test class and helpers for ArynoxTech AI Agent tests."""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.base_tool import ToolResult, ToolResultStatus


class AgentTestCase(unittest.TestCase):
    """Base test case for ArynoxTech tool tests with common helpers."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
            self.loop.close()

    @staticmethod
    def create_tool_result_success(message="Success", data=None):
        return ToolResult.success(message=message, data=data)

    @staticmethod
    def create_tool_result_failure(message="Failure"):
        return ToolResult.failure(message=message)

    @staticmethod
    def assert_tool_success(result):
        assert result.status == ToolResultStatus.SUCCESS, (
            f"Expected SUCCESS, got {result.status}: {result.message}"
        )

    @staticmethod
    def assert_tool_failure(result):
        assert result.status == ToolResultStatus.FAILURE, (
            f"Expected FAILURE, got {result.status}: {result.message}"
        )


class AsyncAgentTestCase(unittest.IsolatedAsyncioTestCase):
    """Base async test case with helpers for async tool tests."""

    @staticmethod
    def create_tool_result_success(message="Success", data=None):
        return ToolResult.success(message=message, data=data)

    @staticmethod
    def create_tool_result_failure(message="Failure"):
        return ToolResult.failure(message=message)

    @staticmethod
    def assert_tool_success(result):
        assert result.status == ToolResultStatus.SUCCESS, (
            f"Expected SUCCESS, got {result.status}: {result.message}"
        )

    @staticmethod
    def assert_tool_failure(result):
        assert result.status == ToolResultStatus.FAILURE, (
            f"Expected FAILURE, got {result.status}: {result.message}"
        )
