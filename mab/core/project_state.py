"""
core/project_state.py
─────────────────────
Reads and writes the per-project persistent state file: mab_project.json

This file lives at <project_root>/mab_project.json and records everything
the user entered on the Prompt page so it can be restored when the project
is reopened.

Schema
──────
{
  "project_name":   "my_project",
  "project_summary": "One-paragraph summary from the LLM",
  "description":    "The original free-text application brief",
  "output_dir":     "/path/to/projects",
  "llm_provider":   "openai",
  "llm_model":      "gpt-4o",
  "created_at":     "2025-01-01T12:00:00",
  "agents":         [ ... full LLM agent list ... ]
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FILENAME = "mab_project.json"


def save_state(project_root: Path, state: dict[str, Any]) -> None:
    """Write project state to <project_root>/mab_project.json."""
    target = project_root / _FILENAME
    # Always stamp the write time
    state = {**state, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        target.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug("Project state saved to %s", target)
    except OSError as exc:
        logger.warning("Could not save project state: %s", exc)


def load_state(project_root: Path) -> dict[str, Any]:
    """
    Read <project_root>/mab_project.json.
    Returns an empty dict if the file does not exist or is unreadable.
    """
    target = project_root / _FILENAME
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load project state from %s: %s", target, exc)
        return {}
