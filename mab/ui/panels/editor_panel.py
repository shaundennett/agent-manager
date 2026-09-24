"""
ui/panels/editor_panel.py
─────────────────────────
Panel 2 — Agent Editor Panel.
Splits into an AgentList sidebar (left) and ProformaForm (right).
Handles AI-assist popovers and save/export logic.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from ui.components.agent_list import AgentListPanel
from ui.components.proforma_form import ProformaForm

logger = logging.getLogger(__name__)


class EditorPanel(ctk.CTkFrame):
    """Two-pane agent editor: sidebar list + proforma form."""

    def __init__(
        self,
        master,
        on_agent_saved: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, corner_radius=0, **kwargs)
        self.on_agent_saved = on_agent_saved

        self._project_root: Path | None = None
        self._project_summary: str = ""
        self._llm_provider: str = ""
        self._llm_model: str = ""
        self._current_agent_name: str | None = None
        self._agent_data_cache: dict[str, object] = {}   # name → AgentData
        self._dirty = False

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Sidebar
        self._agent_list = AgentListPanel(
            self,
            on_select=self._on_agent_selected,
            on_new_agent=self._on_new_agent,
            on_export_all=self._on_export_all,
            fg_color="#f7f8fa",
        )
        self._agent_list.grid(row=0, column=0, sticky="nsew")

        # Right pane
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Right toolbar
        toolbar = ctk.CTkFrame(right, height=40, corner_radius=0, fg_color="#f7f8fa")
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)

        self._agent_title_var = ctk.StringVar(value="Select an agent →")
        ctk.CTkLabel(
            toolbar, textvariable=self._agent_title_var,
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
        ).grid(row=0, column=0, padx=16, pady=8, sticky="w")

        self._completion_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            toolbar, textvariable=self._completion_var,
            font=ctk.CTkFont(size=12), text_color="#57606a",
        ).grid(row=0, column=1, padx=8, sticky="e")

        # "Fill All with AI" button
        self._fill_all_btn = ctk.CTkButton(
            toolbar, text="✨ Fill All with AI", width=140, height=28,
            fg_color="#7c5cd8", hover_color="#6d28d9",
            command=self._on_fill_all,
            state="disabled",
        )
        self._fill_all_btn.grid(row=0, column=2, padx=(0, 4), pady=6)

        self._save_btn = ctk.CTkButton(
            toolbar, text="Save", width=80, height=28,
            fg_color="#3b82d4", hover_color="#2563eb",
            command=self._on_save,
            state="disabled",
        )
        self._save_btn.grid(row=0, column=3, padx=(0, 8), pady=6)

        # Proforma form
        self._form = ProformaForm(
            right,
            on_change=self._on_field_change,
            on_ai_assist=self._on_ai_assist,
            on_fill_section=self._on_fill_section,
        )
        self._form.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_project(self, project_root: Path, meta: dict) -> None:
        """Load a project directory and populate the sidebar."""
        self._project_root = project_root
        self._project_summary = meta.get("summary", "")
        self._llm_provider = meta.get("llm_provider", "")
        self._llm_model = meta.get("llm_model", "")
        self._agent_data_cache.clear()
        self._current_agent_name = None
        self._refresh_sidebar(reload_from_disk=True)

    def _refresh_sidebar(self, reload_from_disk: bool = False) -> None:
        """
        Rebuild the sidebar agent list.

        reload_from_disk=True  → re-read every agent.md from disk into cache
                                 (used on initial load and after explicit saves).
        reload_from_disk=False → just refresh sidebar badges from the existing
                                 in-memory cache (used after field edits).
        """
        if not self._project_root:
            return
        agents_dir = self._project_root / "agents"
        if not agents_dir.exists():
            return

        from core.agent_parser import load as parse_agent

        items = []

        if reload_from_disk:
            for agent_md in sorted(agents_dir.rglob("agent.md")):
                try:
                    ad = parse_agent(agent_md)
                    # Preserve in-memory edits: only overwrite if not cached
                    if ad.name not in self._agent_data_cache:
                        self._agent_data_cache[ad.name] = ad
                    else:
                        # Refresh path reference in case it changed
                        self._agent_data_cache[ad.name].path = ad.path
                    items.append({
                        "name": ad.name,
                        "completion_pct": self._agent_data_cache[ad.name].completion_pct,
                        "error": False,
                    })
                except Exception as exc:  # noqa: BLE001
                    name = agent_md.parent.name
                    items.append({"name": name, "completion_pct": 0, "error": True})
                    logger.warning("Parse error for %s: %s", agent_md, exc)
        else:
            # Build items purely from existing cache
            for name, ad in self._agent_data_cache.items():
                items.append({
                    "name": name,
                    "completion_pct": ad.completion_pct,
                    "error": False,
                })
            items.sort(key=lambda x: x["name"])

        self._agent_list.refresh(items)

        # Auto-select first agent on initial load only
        if items and not self._current_agent_name:
            self._on_agent_selected(items[0]["name"])
            self._agent_list.select(items[0]["name"])

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_agent_selected(self, name: str) -> None:
        if self._dirty:
            if messagebox.askyesno("Unsaved Changes", "Save current agent before switching?"):
                self._on_save()

        self._current_agent_name = name
        ad = self._agent_data_cache.get(name)
        if ad is None:
            return

        self._agent_title_var.set(f"Editing: {name}")
        self._completion_var.set(f"Completion: {ad.completion_pct}%")
        self._form.load_fields(ad.fields)
        self._save_btn.configure(state="normal")
        self._fill_all_btn.configure(state="normal")
        self._dirty = False

    def _on_field_change(self, key: str, value: str) -> None:
        self._dirty = True
        name = self._current_agent_name
        if name and name in self._agent_data_cache:
            self._agent_data_cache[name].fields[key] = value
            pct = self._agent_data_cache[name].completion_pct
            self._completion_var.set(f"Completion: {pct}%")

    def _on_save(self) -> None:
        name = self._current_agent_name
        if not name or not self._project_root:
            return
        ad = self._agent_data_cache.get(name)
        if ad is None:
            return

        # Merge form values back
        ad.fields.update(self._form.get_fields())

        from core.agent_parser import save as save_agent
        try:
            save_agent(ad)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save Error", str(exc))
            return

        self._dirty = False
        self._completion_var.set(f"Completion: {ad.completion_pct}%")
        # Sidebar badges only — cache already has the updated AgentData
        self._refresh_sidebar(reload_from_disk=False)
        self.on_agent_saved()

    def _on_export_all(self) -> None:
        if not self._project_root:
            return
        from core.agent_parser import save as save_agent
        errors = []
        for name, ad in self._agent_data_cache.items():
            try:
                save_agent(ad)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
        if errors:
            messagebox.showerror("Export Errors", "\n".join(errors))
        else:
            messagebox.showinfo("Export Complete", f"All agents exported to {self._project_root}")
        self._refresh_sidebar(reload_from_disk=False)
        self.on_agent_saved()

    def _on_new_agent(self) -> None:
        if not self._project_root:
            messagebox.showwarning("No Project", "Open or create a project first.")
            return

        dialog = ctk.CTkInputDialog(
            text="Enter a name for the new agent (snake_case):",
            title="New Agent",
        )
        name = dialog.get_input()
        if not name:
            return

        from core.scaffold_engine import AgentSpec, add_agent, _slugify
        safe_name = _slugify(name)
        spec = AgentSpec(name=safe_name, role="", position_hint="worker")
        try:
            path = add_agent(self._project_root, spec, self._project_summary)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", str(exc))
            return

        self._refresh_sidebar(reload_from_disk=True)
        self._on_agent_selected(safe_name)
        self._agent_list.select(safe_name)

    def _apply_project_llm_env(self) -> None:
        """Set env vars from stored project state so AIClient picks the right provider/model."""
        import os
        if self._llm_provider:
            os.environ["MAB_LLM_PROVIDER"] = self._llm_provider
        if self._llm_model:
            os.environ["MAB_LLM_MODEL"] = self._llm_model

    def _on_fill_all(self) -> None:
        """
        Generate AI suggestions for every ai_assist=True field in the form,
        then show a single batch-review dialog for the user to accept/skip each.
        """
        name = self._current_agent_name
        if not name:
            return
        ad = self._agent_data_cache.get(name)
        if ad is None:
            return

        from ui.components.proforma_form import SECTIONS
        ai_fields = [
            key
            for _section, fields in SECTIONS
            for key, _label, _wtype, _req, ai in fields
            if ai
        ]

        self._fill_all_btn.configure(state="disabled", text="⏳ Generating…")
        self._completion_var.set("Calling AI for all fields…")

        context = self._form.get_fields()
        other_agents = [
            {"name": n, "role": a.role}
            for n, a in self._agent_data_cache.items()
            if n != name
        ]

        def _run() -> None:
            try:
                self._apply_project_llm_env()
                from core.ai_client import AIClient
                client = AIClient()
                results: list[tuple[str, str]] = []
                for field_key in ai_fields:
                    # Skip fields already filled
                    existing = context.get(field_key, "").strip()
                    if existing and "TODO" not in existing:
                        continue
                    try:
                        suggestion = client.assist_field(
                            field_key,
                            agent_context=context,
                            project_summary=self._project_summary,
                            other_agents=other_agents,
                        )
                        if suggestion.strip():
                            results.append((field_key, suggestion.strip()))
                            # Feed each accepted value back as context for next call
                            context[field_key] = suggestion.strip()
                    except Exception:  # noqa: BLE001
                        pass  # skip fields that error; don't abort the batch

                self.after(0, lambda r=results: self._show_batch_review(r))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda m=msg: self._on_fill_all_error(m))

        threading.Thread(target=_run, daemon=True).start()

    def _on_fill_all_error(self, message: str) -> None:
        self._fill_all_btn.configure(state="normal", text="✨ Fill All with AI")
        self._completion_var.set("")
        messagebox.showerror("AI Fill Error", message)

    def _on_fill_section(self, section_title: str, field_keys: list[str]) -> None:
        """
        Generate AI suggestions for a specific section's ai_assist fields only,
        then show the same batch-review dialog used by Fill All.
        """
        name = self._current_agent_name
        if not name:
            return

        # Only suggest for empty/TODO fields
        context = self._form.get_fields()
        unfilled = [
            k for k in field_keys
            if not context.get(k, "").strip() or "TODO" in context.get(k, "")
        ]
        if not unfilled:
            messagebox.showinfo(
                "Fill Section",
                f"All fields in '{section_title}' already have content.",
            )
            return

        other_agents = [
            {"name": n, "role": a.role}
            for n, a in self._agent_data_cache.items()
            if n != name
        ]

        self._completion_var.set(f"Calling AI for {section_title}…")

        def _run() -> None:
            try:
                self._apply_project_llm_env()
                from core.ai_client import AIClient
                client = AIClient()
                results: list[tuple[str, str]] = []
                for field_key in unfilled:
                    try:
                        suggestion = client.assist_field(
                            field_key,
                            agent_context=context,
                            project_summary=self._project_summary,
                            other_agents=other_agents,
                        )
                        if suggestion.strip():
                            results.append((field_key, suggestion.strip()))
                            context[field_key] = suggestion.strip()
                    except Exception:  # noqa: BLE001
                        pass

                self.after(0, lambda r=results: self._show_batch_review(r))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda m=msg: (
                    self._completion_var.set(""),
                    messagebox.showerror("AI Fill Error", m),
                ))

        threading.Thread(target=_run, daemon=True).start()

    def _show_batch_review(self, results: list[tuple[str, str]]) -> None:
        """
        Show a scrollable dialog listing every AI suggestion.
        Each row has Accept / Skip controls. Apply All / Cancel at the bottom.
        """
        self._fill_all_btn.configure(state="normal", text="✨ Fill All with AI")

        if not results:
            self._completion_var.set("")
            messagebox.showinfo(
                "Fill All with AI",
                "All AI-assist fields already have content — nothing to fill.",
            )
            return

        popup = ctk.CTkToplevel(self)
        popup.title("AI Suggestions — Review All")
        popup.geometry("700x560")
        popup.grab_set()
        popup.grid_rowconfigure(1, weight=1)
        popup.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(popup, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=f"AI generated {len(results)} suggestion(s) for unfilled fields",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Review each suggestion then click Apply Selected.",
            font=ctk.CTkFont(size=11),
            text_color="#57606a",
        ).grid(row=1, column=0, sticky="w")

        # Scrollable suggestion list
        scroll = ctk.CTkScrollableFrame(popup, label_text="")
        scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)
        scroll.grid_columnconfigure(1, weight=1)

        row_vars: list[tuple[str, ctk.BooleanVar, ctk.CTkTextbox]] = []

        for idx, (field_key, suggestion) in enumerate(results):
            # Separator between rows
            if idx > 0:
                ctk.CTkFrame(scroll, height=1, fg_color="#e5e7eb").grid(
                    row=idx * 3 - 1, column=0, columnspan=3,
                    sticky="ew", padx=4, pady=2,
                )

            base_row = idx * 3

            # Checkbox + field label
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(
                scroll, text="", variable=var, width=24,
            ).grid(row=base_row, column=0, padx=(4, 0), pady=(8, 2), sticky="nw")

            ctk.CTkLabel(
                scroll,
                text=field_key.replace("_", " ").title(),
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=base_row, column=1, padx=6, pady=(8, 2), sticky="w")

            # Editable suggestion textbox
            tb = ctk.CTkTextbox(scroll, height=70, wrap="word", font=ctk.CTkFont(size=11))
            tb.insert("1.0", suggestion)
            tb.grid(row=base_row + 1, column=1, columnspan=2,
                    padx=6, pady=(0, 4), sticky="ew")

            row_vars.append((field_key, var, tb))

        # Bottom action bar
        btn_bar = ctk.CTkFrame(popup, fg_color="transparent")
        btn_bar.grid(row=2, column=0, padx=16, pady=(8, 14), sticky="e")

        def _select_all() -> None:
            for _, v, _ in row_vars:
                v.set(True)

        def _deselect_all() -> None:
            for _, v, _ in row_vars:
                v.set(False)

        def _apply() -> None:
            applied = 0
            for field_key, var, tb in row_vars:
                if var.get():
                    value = tb.get("1.0", "end-1c").strip()
                    if value:
                        self._form.set_field(field_key, value)
                        applied += 1
            popup.destroy()
            self._completion_var.set(f"Applied {applied} AI suggestion(s).")

        ctk.CTkButton(
            btn_bar, text="Select All", width=90, height=30,
            fg_color="transparent", border_width=1, text_color="#1f2328",
            command=_select_all,
        ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(
            btn_bar, text="Deselect All", width=100, height=30,
            fg_color="transparent", border_width=1, text_color="#1f2328",
            command=_deselect_all,
        ).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(
            btn_bar, text="Cancel", width=80, height=30,
            fg_color="transparent", border_width=1, text_color="#1f2328",
            command=popup.destroy,
        ).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(
            btn_bar, text="Apply Selected", width=120, height=30,
            fg_color="#7c5cd8", hover_color="#6d28d9",
            command=_apply,
        ).grid(row=0, column=3)

    def _on_ai_assist(self, field_key: str) -> None:
        name = self._current_agent_name
        if not name:
            return
        ad = self._agent_data_cache.get(name)
        if ad is None:
            return

        context = self._form.get_fields()
        other_agents = [
            {"name": n, "role": a.role}
            for n, a in self._agent_data_cache.items()
            if n != name
        ]

        def _run() -> None:
            try:
                self._apply_project_llm_env()
                from core.ai_client import AIClient
                client = AIClient()
                suggestion = client.assist_field(
                    field_key,
                    agent_context=context,
                    project_summary=self._project_summary,
                    other_agents=other_agents,
                )
                self.after(0, lambda: self._show_assist_popover(field_key, suggestion))
            except Exception as exc:  # noqa: BLE001
                logger.exception("AI assist failed: %s", exc)
                msg = str(exc)
                self.after(0, lambda m=msg: messagebox.showerror("AI Assist Error", m))

        threading.Thread(target=_run, daemon=True).start()

    def _show_assist_popover(self, field_key: str, suggestion: str) -> None:
        """Show a topLevel popover with the AI suggestion."""
        popup = ctk.CTkToplevel(self)
        popup.title(f"AI Suggestion — {field_key}")
        popup.geometry("520x280")
        popup.grab_set()
        popup.grid_columnconfigure(0, weight=1)
        popup.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            popup,
            text=f"Suggested value for: {field_key}",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="w")

        text = ctk.CTkTextbox(popup, wrap="word", font=ctk.CTkFont(size=12))
        text.insert("1.0", suggestion)
        text.grid(row=1, column=0, columnspan=2, padx=16, pady=4, sticky="nsew")

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, padx=16, pady=12, sticky="e")

        def _accept() -> None:
            value = text.get("1.0", "end-1c").strip()
            self._form.set_field(field_key, value)
            popup.destroy()

        ctk.CTkButton(
            btn_frame, text="Accept", fg_color="#3b82d4",
            command=_accept, width=90,
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            btn_frame, text="Dismiss", fg_color="transparent",
            border_width=1, text_color="#1f2328",
            command=popup.destroy, width=90,
        ).grid(row=0, column=1)
