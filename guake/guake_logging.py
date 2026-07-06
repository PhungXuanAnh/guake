# -*- coding: utf-8; -*-
"""
Copyright (C) 2007-2013 Guake authors

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
Boston, MA 02110-1301 USA
"""

import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from colorlog import ColoredFormatter
except ImportError:
    ColoredFormatter = None

log = logging.getLogger(__name__)


def _get_log_file_path():
    """Return a log file path under XDG cache (or $GUAKE_LOG_FILE override)."""
    override = os.environ.get("GUAKE_LOG_FILE")
    if override:
        return Path(override)
    cache_home = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    log_dir = Path(cache_home) / "guake"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path("/tmp")
    return log_dir / "guake.log"


def setupLogging(debug_mode):
    # Always log DEBUG to file (so we can investigate issues across restarts);
    # console level still respects --verbose.
    console_level = logging.DEBUG if debug_mode else logging.INFO
    file_level = logging.DEBUG

    log_file = _get_log_file_path()

    formatters = {
        "plain": {
            "format": "%(asctime)s %(levelname)-8s %(name)s [%(process)d] %(message)s",
        },
    }
    if ColoredFormatter:
        formatters["console"] = {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(levelname)-8s%(reset)s %(message)s",
            "log_colors": {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        }
        console_formatter = "console"
    else:
        formatters["console"] = {"format": "%(message)s"}
        console_formatter = "console"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "loggers": {
                "": {
                    "handlers": ["default", "file"],
                    "level": "DEBUG",
                    "propagate": True,
                },
            },
            "handlers": {
                "default": {
                    "level": logging.getLevelName(console_level),
                    "class": "logging.StreamHandler",
                    "formatter": console_formatter,
                },
                "file": {
                    "level": logging.getLevelName(file_level),
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "plain",
                    "filename": str(log_file),
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 3,
                    "encoding": "utf-8",
                },
            },
            "formatters": formatters,
        }
    )
    log.setLevel(logging.DEBUG)
    log.info("Logging configured. File: %s (console=%s, file=%s)",
             log_file, logging.getLevelName(console_level),
             logging.getLevelName(file_level))
