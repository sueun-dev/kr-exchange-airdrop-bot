"""Logging configuration helpers for the application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


def default_log_file() -> Path:
    """Returns the default log file path for this repo layout."""
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "logs" / "airdrop_event.log"


def configure_logging(
    *, log_file: Optional[Path] = None, level: int = logging.INFO
) -> None:
    """Configures application logging.

    Args:
        log_file: Optional file path to write logs to.
        level: Root logger level.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

