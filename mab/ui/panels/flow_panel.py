"""
ui/panels/flow_panel.py
───────────────────────
Panel 3 — Flow Visualiser Panel.
Wraps the FlowCanvas (Mermaid-based) and adds a refresh control.
Auto-refreshes when the project changes.
Writes flow.mmd to the project root on every refresh.
"""

from __future__ import annotations

import logging
from pathlib import Path

import customtkinter as ctk

from ui.components.flow_canvas import FlowCanvas

logger = logging.getLogger(__name__)


class FlowPanel(ctk.CTkFrame):
    """Hosts the flow visualiser with a header and refresh button."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, corner_radius=0, **kwargs)
        self._project_root: Path | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Header bar
        header = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color="#f7f8fa")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="Agent Flow — Mermaid",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        ctk.CTkLabel(
            header,
            text="Renders flowchart TD  ·  flow.mmd saved to project root",
            font=ctk.CTkFont(size=11),
            text_color="#57606a",
            anchor="w",
        ).grid(row=0, column=1, padx=4, pady=10, sticky="w")

        ctk.CTkButton(
            header, text="⟳ Refresh", width=90, height=28,
            fg_color="transparent", border_width=1,
            text_color="#1f2328", hover_color="#e5e7eb",
            command=self.refresh,
        ).grid(row=0, column=2, padx=8, pady=8)

        # Canvas
        self._canvas = FlowCanvas(self, fg_color="#1e1e2e")
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_project(self, project_root: Path) -> None:
        self._project_root = project_root
        self.refresh()

    def refresh(self) -> None:
        if not self._project_root:
            return
        try:
            from core.flow_analyser import build_graph
            graph = build_graph(self._project_root)
            self._canvas.render(graph, project_root=self._project_root)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Flow refresh error: %s", exc)
            self._canvas.clear()
