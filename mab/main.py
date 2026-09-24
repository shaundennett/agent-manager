"""
main.py
───────
Multi-Agent Builder — application entry point.

Usage:
    python main.py

Environment:
    Copy .env.example to .env and populate your LLM credentials before running.
    See README.md for full setup instructions.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# ── Ensure the mab/ package root is on sys.path when run directly ─────────────
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from dotenv import load_dotenv

load_dotenv(dotenv_path=_HERE / ".env", override=False)

# ── Logging setup ─────────────────────────────────────────────────────────────
_LOG_LEVEL = os.environ.get("MAB_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mab")


def main() -> None:
    logger.info("Starting Multi-Agent Builder")
    from ui.app import MABApp
    app = MABApp()
    app.mainloop()
    logger.info("Multi-Agent Builder closed")


if __name__ == "__main__":
    main()
