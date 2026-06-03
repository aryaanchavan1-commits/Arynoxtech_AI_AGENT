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
ArynoxTech AI Agent AI Agent - System Tool
=================================
Tool for monitoring system resources, launching applications,
and gathering system information.
Uses psutil for system monitoring.
"""

import time
import subprocess
import platform
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult
from config.settings import SECURITY_CONFIG


class SystemTool(BaseTool):
    """
    Tool for system operations:
    - Monitor CPU usage
    - Monitor RAM usage
    - Get system information
    - Launch applications
    - Run safe system commands
    """

    name: str = "system_tool"
    description: str = "Open applications, monitor CPU/RAM, get system info, launch programs."
    version: str = "1.0.0"
    requires_confirmation: bool = False  # Allow system monitoring without confirmation

    def __init__(self) -> None:
        super().__init__()
        try:
            import psutil
            self.psutil = psutil
        except ImportError:
            self.psutil = None
            self.logger.warning("psutil not installed. System monitoring limited.")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute system tool operation.

        Args:
            action: 'cpu', 'memory', 'system_info', 'launch', 'disk', 'processes'
            command: Command to run (for 'launch')
            app_name: Application name to launch
            path: Specific path for operations

        Returns:
            ToolResult with system information
        """
        start_time = time.time()
        action = kwargs.get("action", "system_info")

        try:
            if action == "cpu":
                return await self._get_cpu_usage(kwargs, start_time)
            elif action == "memory":
                return await self._get_memory_usage(kwargs, start_time)
            elif action == "system_info":
                return await self._get_system_info(kwargs, start_time)
            elif action == "launch":
                return await self._launch_app(kwargs, start_time)
            elif action == "open_app":
                return await self._open_app(kwargs, start_time)
            elif action == "type_text":
                return await self._type_text(kwargs, start_time)
            elif action == "open_app_and_type":
                return await self._open_app_and_type(kwargs, start_time)
            elif action == "disk":
                return await self._get_disk_usage(kwargs, start_time)
            elif action == "processes":
                return await self._list_processes(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.logger.exception(f"System tool error: {e}")
            return ToolResult.error_result(
                f"System operation failed: {str(e)}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _get_cpu_usage(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get CPU usage information."""
        if self.psutil is None:
            return ToolResult.failure(
                "psutil not installed. Install with: pip install psutil",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            cpu_percent = self.psutil.cpu_percent(interval=0.5)
            cpu_count = self.psutil.cpu_count()
            cpu_freq = self.psutil.cpu_freq()

            data = {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "cpu_freq_mhz": cpu_freq.current if cpu_freq else 0,
                "cpu_freq_max_mhz": cpu_freq.max if cpu_freq else 0,
            }

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"CPU: {cpu_percent}% used ({cpu_count} cores)",
                data=data,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get CPU info: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _get_memory_usage(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get RAM usage information."""
        if self.psutil is None:
            return ToolResult.failure(
                "psutil not installed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            mem = self.psutil.virtual_memory()
            swap = self.psutil.swap_memory()

            data = {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent,
                "swap_total_gb": round(swap.total / (1024**3), 2),
                "swap_used_gb": round(swap.used / (1024**3), 2),
                "swap_percent": swap.percent,
            }

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"RAM: {data['used_gb']}GB / {data['total_gb']}GB ({data['percent']}%)",
                data=data,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get memory info: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _get_system_info(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get general system information."""
        try:
            uname = platform.uname()
            boot_time = self.psutil.boot_time() if self.psutil else None

            data = {
                "system": uname.system,
                "node_name": uname.node,
                "release": uname.release,
                "version": uname.version,
                "machine": uname.machine,
                "processor": uname.processor,
                "python_version": platform.python_version(),
                "boot_time": boot_time,
            }

            # Add CPU and memory if psutil available
            if self.psutil:
                data["cpu_count"] = self.psutil.cpu_count()
                mem = self.psutil.virtual_memory()
                data["ram_total_gb"] = round(mem.total / (1024**3), 2)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"System: {data['system']} {data['release']} ({data['machine']})",
                data=data,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get system info: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _launch_app(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Launch an application or run a command."""
        command = kwargs.get("command", "")
        app_name = kwargs.get("app_name", "")

        if not command and not app_name:
            return ToolResult.failure(
                "Provide either 'command' or 'app_name' to launch",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Build the command
        launch_cmd = command or self._get_app_command(app_name)

        if not launch_cmd:
            return ToolResult.failure(
                f"Unknown application: {app_name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Check if command involves blocked operations
        for blocked in SECURITY_CONFIG.get("require_confirmation_for", []):
            if blocked in launch_cmd.lower():
                return ToolResult.needs_confirmation(
                    f"Confirm running: {launch_cmd}",
                    data={"command": launch_cmd, "action": "run_command"},
                )

        try:
            # Use shell=False and split for security
            import shlex
            cmd_parts = shlex.split(launch_cmd) if platform.system() != "Windows" else [launch_cmd]
            
            if platform.system() == "Windows":
                subprocess.Popen(launch_cmd, shell=True)
            else:
                subprocess.Popen(cmd_parts)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Launched: {launch_cmd}",
                data={"command": launch_cmd, "app": app_name or command},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to launch: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _open_app(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Open an application by app_name."""
        app_name = (kwargs.get("app_name") or kwargs.get("app"))
        command = kwargs.get("command", "")
        if not app_name and not command:
            return ToolResult.failure(
                "Provide 'app_name' (e.g., notepad) or 'command' to open app",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        launch_cmd = command or self._get_app_command(str(app_name))
        if not launch_cmd:
            return ToolResult.failure(
                f"Unknown application: {app_name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        try:
            if platform.system() == "Windows":
                subprocess.Popen(launch_cmd, shell=True)
            else:
                import shlex
                cmd_parts = shlex.split(launch_cmd)
                subprocess.Popen(cmd_parts)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Opened: {app_name}",
                data={"command": launch_cmd, "app": app_name},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to open app: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _type_text(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Type text into the currently focused window."""
        text = kwargs.get("text", "")
        delay_seconds = float(kwargs.get("delay_seconds", 0.6))
        if text is None or str(text) == "":
            return ToolResult.failure(
                "Provide 'text' to type",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        try:
            if platform.system() != "Windows":
                return ToolResult.failure(
                    "type_text is currently implemented for Windows only",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            import pyautogui

            # Ensure a short delay to let the app become interactive.
            time.sleep(delay_seconds)

            # Attempt to type reliably: select all then replace.
            # (This avoids issues where focus isn't exactly where the cursor is.)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.write(str(text), interval=0.01)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Typed text ({len(str(text))} chars)",
                data={"text": str(text)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to type text: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _open_app_and_type(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Open an app and type text into it."""
        app_name = (kwargs.get("app_name") or kwargs.get("app"))
        text = kwargs.get("text", "")
        delay_seconds = float(kwargs.get("delay_seconds", 0.8))
        if not app_name:
            return ToolResult.failure(
                "Provide 'app_name' to open",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        try:
            open_result = await self._open_app(
                {"app_name": app_name, "command": kwargs.get("command", "")},
                start_time,
            )
            if open_result.status.value != "success":
                return open_result
            time.sleep(delay_seconds)
            return await self._type_text(
                {"text": text, "delay_seconds": 0.0},
                start_time,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed open_app_and_type: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _get_disk_usage(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Get disk usage information."""
        if self.psutil is None:
            return ToolResult.failure(
                "psutil not installed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            path = kwargs.get("path", "/")
            disk = self.psutil.disk_usage(path)
            partitions = self.psutil.disk_partitions()

            data = {
                "path": path,
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent,
                "partitions": [
                    {
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                    }
                    for p in partitions[:5]  # Limit to 5 partitions
                ],
            }

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Disk: {data['used_gb']}GB / {data['total_gb']}GB ({data['percent']}%)",
                data=data,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to get disk info: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _list_processes(self, kwargs: Dict, start_time: float) -> ToolResult:
        """List top processes by CPU/memory usage."""
        if self.psutil is None:
            return ToolResult.failure(
                "psutil not installed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            limit = kwargs.get("limit", 10)
            sort_by = kwargs.get("sort_by", "cpu")  # cpu or memory

            processes = []
            for proc in self.psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    pinfo = proc.info
                    processes.append(pinfo)
                except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                    continue

            if sort_by == "cpu":
                processes.sort(key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)
            else:
                processes.sort(key=lambda p: p.get("memory_percent", 0) or 0, reverse=True)

            top_processes = processes[:limit]
            data = {
                "sort_by": sort_by,
                "total_processes": len(processes),
                "processes": [
                    {
                        "pid": p["pid"],
                        "name": p["name"],
                        "cpu": p.get("cpu_percent", 0),
                        "memory": round(p.get("memory_percent", 0), 1),
                    }
                    for p in top_processes
                ],
            }

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Top {limit} processes by {sort_by} usage",
                data=data,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to list processes: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _get_app_command(self, app_name: str) -> str:
        """Get launch command for ANY application on Windows by name.
        Uses the Windows 'start' command which can launch any installed app,
        or searches common install paths."""
        import re
        system = platform.system()
        name = app_name.lower().strip()

        # Strip common filler words
        name = re.sub(r'\b(app|application|program|software)\b', '', name).strip()

        # Quick known apps dictionary (expanded)
        known_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "browser": "chrome.exe",
            "internet": "chrome.exe",
            "firefox": "firefox.exe",
            "mozilla firefox": "firefox.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "terminal": "cmd.exe",
            "powershell": "powershell.exe",
            "vscode": "code",
            "visual studio code": "code",
            "paint": "mspaint.exe",
            "microsoft paint": "mspaint.exe",
            "word": "WINWORD.EXE",
            "microsoft word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
            "microsoft excel": "EXCEL.EXE",
            "powerpoint": "POWERPNT.EXE",
            "outlook": "OUTLOOK.EXE",
            "teams": "Teams.exe",
            "microsoft teams": "Teams.exe",
            "notepad++": "notepad++.exe",
            "spotify": "Spotify.exe",
            "discord": "Discord.exe",
            "slack": "slack.exe",
            "zoom": "Zoom.exe",
            "whatsapp": "WhatsApp.exe",
            "telegram": "Telegram.exe",
            "vlc": "vlc.exe",
            "vlc media player": "vlc.exe",
            "snipping tool": "SnippingTool.exe",
            "control panel": "control",
            "settings": "ms-settings:",
            "task manager": "taskmgr.exe",
            "file manager": "explorer.exe",
            "calculator": "calc.exe",
            "calendar": "outlookcal:",
            "camera": "camera:",
            "clock": "ms-clock:",
            "music": "groove music:",
            "photos": "ms-photos:",
            "store": "ms-windows-store:",
            "paint": "mspaint.exe",
            "wordpad": "wordpad.exe",
            "sticky notes": "StickyNotes.exe",
            # Social media & messaging apps
            "instagram": "instagram.exe",
            "whatsapp": "WhatsApp.exe",
            "messenger": "Messenger.exe",
            "snapchat": "Snapchat.exe",
            "facebook": "facebook.exe",
            "twitter": "twitter.exe",
            "x": "twitter.exe",
            "linkedin": "LinkedIn.exe",
            "youtube": "chrome.exe",
            "gmail": "chrome.exe",
            "google maps": "chrome.exe",
            "maps": "chrome.exe",
            "chatgpt": "chrome.exe",
            "gpt": "chrome.exe",
            # Creative & productivity
            "bluestacks": "BlueStacks.exe",
            "android emulator": "BlueStacks.exe",
            "photoshop": "Photoshop.exe",
            "adobe photoshop": "Photoshop.exe",
            "adobe reader": "AcroRd32.exe",
            "acrobat": "AcroRd32.exe",
            # System utilities
            "device manager": "devmgmt.msc",
            "disk management": "diskmgmt.msc",
            "services": "services.msc",
            "registry": "regedit.exe",
            "regedit": "regedit.exe",
            "gpedit": "gpedit.msc",
            "group policy": "gpedit.msc",
        }

        if name in known_apps:
            cmd = known_apps[name]
            if system == "Windows":
                return f"start \"\" \"{cmd}\"" if not cmd.startswith("start") and not cmd.startswith("ms-") else cmd
            elif system == "Darwin":
                return f"open -a \"{cmd}\""
            else:
                return cmd

        if system == "Windows":
            return f"start \"\" \"{name}\""
        elif system == "Darwin":
            return f"open -a \"{name}\""
        else:
            return f"xdg-open {name} 2>/dev/null || {name}"
