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
ArynoxTech AI Agent AI Agent - Logging Utility
=====================================
Provides structured logging with file rotation, console output, and
log level management throughout the application.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config.settings import LOGGING_CONFIG


class LoggerFactory:
    """Factory class to create and manage loggers for different modules."""

    _loggers: dict[str, logging.Logger] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize the root logger with file and console handlers."""
        if cls._initialized:
            return

        log_dir = Path(LOGGING_CONFIG["log_dir"])
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "localmind.log"
        log_level = getattr(logging, LOGGING_CONFIG["log_level"].upper(), logging.DEBUG)

        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # File handler with rotation
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=LOGGING_CONFIG["max_file_size_mb"] * 1024 * 1024,
            backupCount=LOGGING_CONFIG["backup_count"],
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-20s | %(filename)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Console handler
        if LOGGING_CONFIG["console_output"]:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance for the given module name.

        Args:
            name: Module name (typically __name__)

        Returns:
            Configured Logger instance
        """
        if not cls._initialized:
            cls.initialize()

        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = logger

        return cls._loggers[name]


# Convenience function
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for the calling module.

    Args:
        name: Logger name, defaults to root caller

    Returns:
        Configured Logger instance
    """
    if name is None:
        import inspect
        frame = inspect.currentframe()
        name = frame.f_back.f_globals["__name__"] if frame else "unknown"
    return LoggerFactory.get_logger(name)