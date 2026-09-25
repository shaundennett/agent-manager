"""
ui/app.py
─────────
Root UI controller.
Manages a three-tab layout: Prompt | Editor | Flow Visualiser.
Wires together the three panels and the top-level menu bar.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ui.panels.prompt_panel import PromptPanel
from ui.panels.editor_panel import EditorPanel
from ui.panels.flow_panel import FlowPanel

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class MABApp(ctk.CTk):
    """Multi-Agent Builder — root application window."""

    TITLE = "Multi-Agent Builder"
    MIN_W, MIN_H = 1100, 700

    def __init__(self) -> None:
        super().__init__()
        self.title(self.TITLE)
        self.minsize(self.MIN_W, self.MIN_H)
        self.geometry("1280x820")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._project_root: Path | None = None

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, height=46, corner_radius=0, fg_color="#1f2328")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="⬡  Multi-Agent Builder",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ffffff",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        # Menu bar (File actions)
        menu_frame = ctk.CTkFrame(header, fg_color="transparent")
        menu_frame.grid(row=0, column=1, sticky="e", padx=8)

        for label, cmd in [
            ("Open Project", self._open_project),
            ("New Project", self._go_to_prompt),
            ("About", self._show_about),
        ]:
            ctk.CTkButton(
                menu_frame, text=label, height=28, width=100,
                fg_color="transparent", hover_color="#374151",
                text_color="#d1d5db", font=ctk.CTkFont(size=12),
                command=cmd,
            ).pack(side="left", padx=2)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tabs(self) -> None:
        self._tab_bar = ctk.CTkFrame(self, height=38, corner_radius=0, fg_color="#e5e7eb")
        self._tab_bar.grid(row=1, column=0, sticky="new")

        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._content.grid(row=1, column=0, sticky="nsew", pady=(38, 0))
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Tab buttons
        self._tab_btns: dict[str, ctk.CTkButton] = {}
        tab_names = ["✨  Prompt", "✏️  Editor", "🔀  Flow"]
        for col, name in enumerate(tab_names):
            btn = ctk.CTkButton(
                self._tab_bar, text=name, height=34, corner_radius=0,
                fg_color="transparent", hover_color="#d1d5db",
                text_color="#1f2328", font=ctk.CTkFont(size=12),
                command=lambda n=name: self._switch_tab(n),
            )
            btn.grid(row=0, column=col, padx=0)
            self._tab_btns[name] = btn

        # Panels (all created once, shown/hidden by grid)
        self._prompt_panel = PromptPanel(
            self._content, on_project_created=self._on_project_created
        )
        self._editor_panel = EditorPanel(
            self._content, on_agent_saved=self._on_agent_saved
        )
        self._flow_panel = FlowPanel(self._content)

        self._panels = {
            "✨  Prompt": self._prompt_panel,
            "✏️  Editor": self._editor_panel,
            "🔀  Flow": self._flow_panel,
        }

        self._switch_tab("✨  Prompt")

    def _switch_tab(self, name: str) -> None:
        for n, panel in self._panels.items():
            panel.grid_remove()
        self._panels[name].grid(row=0, column=0, sticky="nsew")

        for n, btn in self._tab_btns.items():
            btn.configure(
                fg_color="#ffffff" if n == name else "transparent",
                font=ctk.CTkFont(size=12, weight="bold" if n == name else "normal"),
            )

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=24, corner_radius=0, fg_color="#f7f8fa")
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self._status_var = ctk.StringVar(value="Ready — open or create a project to begin")
        ctk.CTkLabel(
            bar, textvariable=self._status_var,
            font=ctk.CTkFont(size=11), text_color="#57606a", anchor="w",
        ).grid(row=0, column=0, padx=12, sticky="w")

        self._project_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            bar, textvariable=self._project_var,
            font=ctk.CTkFont(size=11), text_color="#57606a", anchor="e",
        ).grid(row=0, column=1, padx=12, sticky="e")

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_project_created(self, project_root: Path, meta: dict) -> None:
        # Augment meta with LLM settings from the just-written state file
        from core.project_state import load_state
        state = load_state(project_root)
        meta = {
            **meta,
            "llm_provider": state.get("llm_provider", ""),
            "llm_model":    state.get("llm_model", ""),
        }
        self._project_root = project_root
        self._project_var.set(str(project_root))
        self._status_var.set(f"Project created: {project_root.name}")
        self._editor_panel.load_project(project_root, meta)
        self._flow_panel.load_project(project_root)
        # State was just written by prompt_panel; restore it to keep prompt tab current
        self._prompt_panel.load_state(project_root)
        self._switch_tab("✏️  Editor")

    def _on_agent_saved(self) -> None:
        if self._project_root:
            self._flow_panel.load_project(self._project_root)
        self._status_var.set("Agent saved.")

    # ── Menu actions ──────────────────────────────────────────────────────────

    def _open_project(self) -> None:
        path = filedialog.askdirectory(title="Open project directory")
        if not path:
            return
        project_root = Path(path)
        agents_dir = project_root / "agents"
        if not agents_dir.exists():
            messagebox.showwarning(
                "Not a MAB Project",
                f"No 'agents/' directory found in {project_root}.\n"
                "Select the project root created by Multi-Agent Builder.",
            )
            return
        from core.project_state import load_state
        state = load_state(project_root)
        meta = {
            "summary":      state.get("project_summary", ""),
            "llm_provider": state.get("llm_provider", ""),
            "llm_model":    state.get("llm_model", ""),
        }

        self._project_root = project_root
        self._project_var.set(str(project_root))
        self._status_var.set(f"Opened: {project_root.name}")
        self._editor_panel.load_project(project_root, meta)
        self._flow_panel.load_project(project_root)
        self._prompt_panel.load_state(project_root)
        self._switch_tab("✏️  Editor")

    def _go_to_prompt(self) -> None:
        self._prompt_panel.reset_to_new()
        self._switch_tab("✨  Prompt")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About Multi-Agent Builder",
            "Multi-Agent Builder v1.0.0\n\n"
            "AI-assisted scaffolding and editing tool\n"
            "for multi-agent application architectures.\n\n"
            "All LLM credentials are sourced from\nenvironment variables only.",
        )
