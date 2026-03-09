"""Backwards-compatible entrypoint.

Prefer running `python -m bithumb_airdrop_bot` or `uv run bithumb-airdrop-bot`.
"""

from __future__ import annotations

from bithumb_airdrop_bot.cli import main


if __name__ == "__main__":
    main()
