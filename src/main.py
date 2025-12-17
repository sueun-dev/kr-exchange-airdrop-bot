"""Backwards-compatible entrypoint.

Prefer running `python -m exchange_event` or `uv run python -m exchange_event`.
"""

from __future__ import annotations

from exchange_event.cli import main


if __name__ == "__main__":
    main()
