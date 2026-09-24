"""
ui/components/agent_list.py
───────────────────────────
Left sidebar listing all agents in the current project, with per-agent
completion progress bars and New Agent / Export All actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk


class AgentListPanel(ctk.CTkFrame):
    """Sidebar showing the agent list with completion indicators."""

    ITEM_HEIGHT = 54
    SIDEBAR_WIDTH = 210

    def __init__(
        self,
        master,
        on_select: Callable[[str], None],
        on_new_agent: Callable[[], None],
        on_export_all: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, width=self.SIDEBAR_WIDTH, corner_radius=0, **kwargs)
        self.on_select = on_select
        self.on_new_agent = on_new_agent
        self.on_export_all = on_export_all

        self._agents: list[dict] = []       # [{name, completion_pct, error}]
        self._selected: str | None = None
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._progress_bars: dict[str, ctk.CTkProgressBar] = {}

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkLabel(
            self, text="Agents", font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        header.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")

        # Scrollable list
        self._scroll_frame = ctk.CTkScrollableFrame(
            self, label_text="", corner_radius=0
        )
        self._scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._scroll_frame.grid_columnconfigure(0, weight=1)

        # Bottom actions
        actions = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions, text="+ New Agent", height=28,
            command=self.on_new_agent, font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            actions, text="Export All", height=28,
            command=self.on_export_all, font=ctk.CTkFont(size=12),
            fg_color="#22c55e", hover_color="#16a34a", text_color="#ffffff",
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self, agents: list[dict]) -> None:
        """
        Rebuild the list. Each dict: {name, completion_pct, error (bool)}.
        """
        self._agents = agents
        for widget in self._scroll_frame.winfo_children():
            widget.destroy()
        self._buttons.clear()
        self._progress_bars.clear()

        for idx, agent in enumerate(agents):
            self._add_item(idx, agent)

        # Re-highlight selection
        if self._selected and self._selected in self._buttons:
            self._highlight(self._selected)

    def select(self, name: str) -> None:
        """Programmatically select an agent."""
        self._selected = name
        if name in self._buttons:
            self._highlight(name)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _add_item(self, idx: int, agent: dict) -> None:
        name = agent["name"]
        pct = agent.get("completion_pct", 0)
        has_error = agent.get("error", False)

        row_frame = ctk.CTkFrame(
            self._scroll_frame, corner_radius=6, fg_color="transparent"
        )
        row_frame.grid(row=idx, column=0, padx=6, pady=(2, 2), sticky="ew")
        row_frame.grid_columnconfigure(0, weight=1)

        btn_colour = "#ef4444" if has_error else "transparent"
        btn = ctk.CTkButton(
            row_frame,
            text=name,
            anchor="w",
            height=30,
            corner_radius=4,
            fg_color=btn_colour,
            hover_color="#e5e7eb",
            text_color="#1f2328",
            font=ctk.CTkFont(size=12),
            command=lambda n=name: self._on_click(n),
        )
        btn.grid(row=0, column=0, sticky="ew", padx=2)
        self._buttons[name] = btn

        pct_label = ctk.CTkLabel(
            row_frame,
            text=f"{pct}%",
            font=ctk.CTkFont(size=10),
            text_color="#57606a",
            anchor="w",
        )
        pct_label.grid(row=1, column=0, padx=6, sticky="w")

        pbar = ctk.CTkProgressBar(row_frame, height=4, corner_radius=2)
        pbar.set(pct / 100)
        progress_colour = (
            "#ef4444" if pct < 30
            else "#f59e0b" if pct < 70
            else "#22c55e"
        )
        pbar.configure(progress_color=progress_colour)
        pbar.grid(row=2, column=0, padx=6, pady=(0, 4), sticky="ew")
        self._progress_bars[name] = pbar

    def _on_click(self, name: str) -> None:
        self._selected = name
        self._highlight(name)
        self.on_select(name)

    def _highlight(self, name: str) -> None:
        for n, btn in self._buttons.items():
            btn.configure(fg_color="#dbeafe" if n == name else "transparent")
