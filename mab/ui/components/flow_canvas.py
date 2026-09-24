"""
ui/components/flow_canvas.py
─────────────────────────────
Mermaid-based flow visualiser.

Behaviour
---------
* Converts the FlowGraph to a Mermaid ``flowchart TD`` diagram via
  ``core.flow_analyser.generate_mermaid``.
* Writes the diagram to ``<project_root>/flow.mmd`` on every render so the
  file is always available in the workspace.
* Displays the raw Mermaid source in a read-only, syntax-highlighted
  (monospace) scrollable text widget inside the UI — no external browser or
  extra dependencies required.
* Toolbar buttons: Copy to clipboard · Save .mmd · Save .html (standalone
  Mermaid HTML page that can be opened in any browser for a rendered view).
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

logger = logging.getLogger(__name__)

# Mermaid CDN used only when exporting the standalone HTML file
_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"

_PLACEHOLDER = "# No project loaded — open a project to generate the diagram."

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Agent Flow</title>
  <script src="{cdn}"></script>
  <style>
    body {{ margin: 0; background: #ffffff; display: flex;
           justify-content: center; padding: 2rem; font-family: sans-serif; }}
    .mermaid {{ max-width: 100%; }}
  </style>
</head>
<body>
  <div class="mermaid">
{diagram}
  </div>
  <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>
"""


class FlowCanvas(ctk.CTkFrame):
    """Displays a Mermaid flowchart source with toolbar controls."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._graph_data: Any = None
        self._mermaid_src: str = _PLACEHOLDER
        self._project_root: Path | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color="#f7f8fa")
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(4, weight=1)

        for col, (label, cmd, tip) in enumerate([
            ("⧉ Copy",      self._copy_to_clipboard, "Copy Mermaid source"),
            ("💾 Save .mmd", self._save_mmd,          "Save .mmd file"),
            ("🌐 Save .html", self._save_html,         "Export standalone HTML"),
        ]):
            ctk.CTkButton(
                toolbar, text=label, width=110, height=26,
                fg_color="transparent", hover_color="#e5e7eb",
                text_color="#1f2328", font=ctk.CTkFont(size=12),
                command=cmd,
            ).grid(row=0, column=col, padx=2, pady=4)

        self._status_var = ctk.StringVar(value="No project loaded")
        ctk.CTkLabel(
            toolbar, textvariable=self._status_var,
            font=ctk.CTkFont(size=11), text_color="#57606a",
        ).grid(row=0, column=5, padx=8, sticky="e")

        # Scrollable text area for Mermaid source
        text_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1e1e2e")
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self._text = tk.Text(
            text_frame,
            wrap="none",
            font=("Consolas", 12),
            bg="#1e1e2e",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            selectbackground="#45475a",
            relief="flat",
            borderwidth=0,
            state="disabled",
        )
        self._text.grid(row=0, column=0, sticky="nsew", padx=8, pady=6)

        vsb = ctk.CTkScrollbar(text_frame, command=self._text.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ctk.CTkScrollbar(text_frame, orientation="horizontal",
                                command=self._text.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self._text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._set_text(_PLACEHOLDER)

    # ── Public API ────────────────────────────────────────────────────────────

    def render(self, graph_data: Any, project_root: Path | None = None) -> None:
        """Generate and display the Mermaid diagram for *graph_data*."""
        from core.flow_analyser import generate_mermaid

        self._graph_data = graph_data
        if project_root:
            self._project_root = project_root

        # Determine output path — write alongside project if root is known
        out_path: Path | None = None
        if self._project_root:
            out_path = self._project_root / "flow.mmd"

        self._mermaid_src = generate_mermaid(graph_data, output_path=out_path)
        self._set_text(self._mermaid_src)

        n_nodes = len(graph_data.nodes)
        n_edges = len(graph_data.edges)
        file_note = f"  ·  saved → {out_path.name}" if out_path else ""
        self._status_var.set(
            f"{n_nodes} agent(s)  ·  {n_edges} connection(s){file_note}"
        )

    def clear(self) -> None:
        self._graph_data = None
        self._mermaid_src = _PLACEHOLDER
        self._set_text(_PLACEHOLDER)
        self._status_var.set("No project loaded")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _set_text(self, content: str) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", content)
        self._text.configure(state="disabled")

    def _copy_to_clipboard(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self._mermaid_src)
        self._status_var.set("Copied to clipboard ✓")
        self.after(2000, lambda: self._status_var.set(""))

    def _save_mmd(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".mmd",
            filetypes=[("Mermaid diagram", "*.mmd"), ("All files", "*.*")],
            title="Save Mermaid diagram",
        )
        if path:
            Path(path).write_text(self._mermaid_src, encoding="utf-8")
            self._status_var.set(f"Saved → {Path(path).name}")

    def _save_html(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML file", "*.html"), ("All files", "*.*")],
            title="Export standalone HTML",
        )
        if path:
            html = _HTML_TEMPLATE.format(
                cdn=_MERMAID_CDN,
                diagram=self._mermaid_src,
            )
            Path(path).write_text(html, encoding="utf-8")
            self._status_var.set(f"Exported → {Path(path).name}")
