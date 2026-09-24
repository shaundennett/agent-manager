"""
ui/panels/flow_panel.py
───────────────────────
Panel 3 — Flow Visualiser Panel.
Wraps the FlowCanvas and adds a refresh control + legend.
Auto-refreshes when the project changes.
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
            text="Agent Flow Visualiser",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        ctk.CTkButton(
            header, text="⟳ Refresh", width=90, height=28,
            fg_color="transparent", border_width=1,
            text_color="#1f2328", hover_color="#e5e7eb",
            command=self.refresh,
        ).grid(row=0, column=2, padx=8, pady=8)

        # Legend panel
        legend = ctk.CTkFrame(header, fg_color="transparent")
        legend.grid(row=0, column=1, padx=4, sticky="e")

        legend_items = [
            ("#3b82d4", "Orchestrator"),
            ("#6b7280", "Worker"),
            ("#7c5cd8", "Specialist"),
            ("#22c55e", "Gateway"),
        ]
        for col, (colour, label) in enumerate(legend_items):
            dot = ctk.CTkLabel(
                legend, text="●", font=ctk.CTkFont(size=16),
                text_color=colour, width=18,
            )
            dot.grid(row=0, column=col * 2, padx=(8, 0))
            ctk.CTkLabel(
                legend, text=label, font=ctk.CTkFont(size=11),
                text_color="#57606a",
            ).grid(row=0, column=col * 2 + 1, padx=(2, 4))

        # Canvas
        self._canvas = FlowCanvas(self, fg_color="#ffffff")
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
            self._canvas.render(graph)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Flow refresh error: %s", exc)
            self._canvas.clear()
