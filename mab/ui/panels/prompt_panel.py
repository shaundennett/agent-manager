"""
ui/panels/prompt_panel.py
─────────────────────────
Panel 1 — AI Prompt Panel.
Accepts a natural-language project brief, calls the LLM to generate an
agent scaffold, shows a reviewable agent list, and triggers project creation.

State persistence
─────────────────
On project creation all prompt-page values are written to mab_project.json
in the project root.  Call load_state(project_root) to restore them.
The Project Rules field is also written to / read from BOB.md in the
project root so it is available to every tool that consults that file.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)

_BOB_MD_FILENAME = "BOB.md"

_RULES_PLACEHOLDER = (
    "Enter rules and conditions that apply to all components — "
    "coding standards, security requirements, testing policy, architecture principles, etc.\n\n"
    "You can type freely here or use ✨ Generate Rules to have the LLM draft this for you."
)


class PromptPanel(ctk.CTkFrame):
    """Full-screen AI prompt entry and scaffold confirmation screen."""

    LLM_PROVIDERS = ["openai", "anthropic", "watsonx", "ollama"]

    def __init__(
        self,
        master,
        on_project_created: Callable[[Path, dict], None],
        **kwargs,
    ) -> None:
        super().__init__(master, corner_radius=0, **kwargs)
        self.on_project_created = on_project_created
        self._proposed_agents: list[dict] = []
        self._agent_check_vars: dict[str, ctk.BooleanVar] = {}
        # Set when an existing project is loaded; None when creating a new one.
        self._project_root: Path | None = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_prompt_screen()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_prompt_screen(self) -> None:
        """Initial input screen."""
        self._screen = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self._screen.grid(row=0, column=0, sticky="nsew")
        self._screen.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            self._screen,
            text="Multi-Agent Builder",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#1f2328",
        ).grid(row=0, column=0, pady=(40, 4))

        ctk.CTkLabel(
            self._screen,
            text="Describe your application and we'll design the agent architecture for you.",
            font=ctk.CTkFont(size=14),
            text_color="#57606a",
        ).grid(row=1, column=0, pady=(0, 24))

        # Form card
        card = ctk.CTkFrame(self._screen, corner_radius=12, border_width=1,
                             border_color="#e5e7eb")
        card.grid(row=2, column=0, padx=80, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # Project name
        ctk.CTkLabel(card, text="Project Name *", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        self._project_name_entry = ctk.CTkEntry(
            card, placeholder_text="e.g. customer_support_system", height=32
        )
        self._project_name_entry.grid(row=0, column=1, columnspan=2, padx=(0, 16), pady=(16, 4), sticky="ew")

        # Output directory
        ctk.CTkLabel(card, text="Output Directory *", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=1, column=0, padx=16, pady=4, sticky="w")
        dir_frame = ctk.CTkFrame(card, fg_color="transparent")
        dir_frame.grid(row=1, column=1, columnspan=2, padx=(0, 16), pady=4, sticky="ew")
        dir_frame.grid_columnconfigure(0, weight=1)

        self._output_dir_entry = ctk.CTkEntry(dir_frame, placeholder_text="./projects", height=32)
        self._output_dir_entry.grid(row=0, column=0, sticky="ew")
        self._output_dir_entry.insert(0, "./projects")

        ctk.CTkButton(
            dir_frame, text="Browse", width=70, height=32,
            command=self._browse_dir,
        ).grid(row=0, column=1, padx=(6, 0))

        # LLM provider
        ctk.CTkLabel(card, text="LLM Provider", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=2, column=0, padx=16, pady=4, sticky="w")
        self._provider_var = ctk.StringVar(value=self.LLM_PROVIDERS[0])
        ctk.CTkOptionMenu(
            card, variable=self._provider_var, values=self.LLM_PROVIDERS, height=32,
            command=self._on_provider_changed,
        ).grid(row=2, column=1, columnspan=2, padx=(0, 16), pady=4, sticky="w")

        # Model name (dynamic for Ollama, editable for all)
        ctk.CTkLabel(card, text="Model", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=3, column=0, padx=16, pady=4, sticky="w")
        model_frame = ctk.CTkFrame(card, fg_color="transparent")
        model_frame.grid(row=3, column=1, columnspan=2, padx=(0, 16), pady=4, sticky="ew")
        model_frame.grid_columnconfigure(0, weight=1)

        default_model = os.environ.get("MAB_LLM_MODEL", "gpt-4o")
        self._model_var = ctk.StringVar(value=default_model)
        self._model_entry = ctk.CTkEntry(
            model_frame, textvariable=self._model_var, height=32,
            placeholder_text="model name"
        )
        self._model_entry.grid(row=0, column=0, sticky="ew")

        self._model_status = ctk.CTkLabel(
            model_frame, text="", font=ctk.CTkFont(size=11),
            text_color="#57606a", anchor="w",
        )
        self._model_status.grid(row=1, column=0, sticky="w", pady=(0, 2))

        # Description
        ctk.CTkLabel(card, text="Application Brief *", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=4, column=0, padx=16, pady=4, sticky="nw")
        self._description_box = ctk.CTkTextbox(
            card, height=160, wrap="word", font=ctk.CTkFont(size=13)
        )
        self._description_box.grid(row=4, column=1, columnspan=2, padx=(0, 16), pady=4, sticky="ew")
        self._description_box.insert(
            "1.0",
            "Describe the application you want to build. For example:\n\n"
            "\"A customer support automation system that receives incoming tickets, "
            "classifies them by urgency and topic, routes them to the appropriate "
            "specialist agent, drafts a response, and logs the interaction.\"",
        )
        self._description_box.bind("<FocusIn>", self._clear_placeholder)

        # ── Project Rules (BOB.md) ────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color="#e5e7eb").grid(
            row=5, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="ew"
        )

        rules_header = ctk.CTkFrame(card, fg_color="transparent")
        rules_header.grid(row=6, column=0, columnspan=3, padx=16, pady=(0, 4), sticky="ew")
        rules_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            rules_header,
            text="Project Rules (BOB.md)",
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#1f2328",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            rules_header,
            text="Rules and conditions that apply to all components — written to BOB.md in the project root.",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color="#57606a",
        ).grid(row=0, column=1, padx=(10, 0), sticky="w")

        ctk.CTkButton(
            rules_header,
            text="✨ Generate Rules",
            width=130, height=28,
            fg_color="transparent",
            border_width=1,
            border_color="#c4b5fd",
            hover_color="#ede9fe",
            text_color="#7c5cd8",
            font=ctk.CTkFont(size=12),
            command=self._open_generate_rules_dialog,
        ).grid(row=0, column=2, padx=(8, 0))

        self._rules_box = ctk.CTkTextbox(
            card, height=200, wrap="word", font=ctk.CTkFont(size=12)
        )
        self._rules_box.grid(row=7, column=0, columnspan=3, padx=16, pady=(0, 4), sticky="ew")
        self._rules_box.insert("1.0", _RULES_PLACEHOLDER)
        self._rules_box.bind("<FocusIn>", self._clear_rules_placeholder)

        # ── Generate button ───────────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color="#e5e7eb").grid(
            row=8, column=0, columnspan=3, padx=16, pady=(8, 0), sticky="ew"
        )

        self._generate_btn = ctk.CTkButton(
            card,
            text="✨  Generate Agent Architecture",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#3b82d4",
            hover_color="#2563eb",
            command=self._on_generate,
        )
        self._generate_btn.grid(
            row=9, column=0, columnspan=3, padx=16, pady=(12, 16), sticky="ew"
        )
        # Keep a reference to the card so mode-switching can reach the button's parent
        self._form_card = card

        # Status
        self._status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self._screen, textvariable=self._status_var,
            font=ctk.CTkFont(size=12), text_color="#57606a",
        ).grid(row=3, column=0, pady=(8, 0))

    # ── Rules helpers ─────────────────────────────────────────────────────────

    def _clear_rules_placeholder(self, _event) -> None:
        content = self._rules_box.get("1.0", "end-1c")
        if content.startswith("Enter rules and conditions"):
            self._rules_box.delete("1.0", "end")

    def _get_rules(self) -> str:
        """Return the current rules text, or empty string if still placeholder."""
        content = self._rules_box.get("1.0", "end-1c").strip()
        if content.startswith("Enter rules and conditions"):
            return ""
        return content

    def _set_rules(self, text: str) -> None:
        """Populate the rules box with text."""
        self._rules_box.delete("1.0", "end")
        if text:
            self._rules_box.insert("1.0", text)

    # ── Generate Rules dialog ─────────────────────────────────────────────────

    def _open_generate_rules_dialog(self) -> None:
        """Open a top-level dialog that lets the user describe the project to
        the LLM and receive a draft BOB.md in return."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Generate Project Rules")
        dialog.geometry("700x520")
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.grid_rowconfigure(2, weight=1)
        dialog.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            dialog,
            text="Generate Project Rules (BOB.md)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#1f2328",
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            dialog,
            text=(
                "Describe your project — its language, framework, security requirements, "
                "team conventions, or any specific rules you want enforced. "
                "The LLM will draft a BOB.md rules file you can review and edit before accepting."
            ),
            font=ctk.CTkFont(size=12),
            text_color="#57606a",
            wraplength=660,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        # ── Input ─────────────────────────────────────────────────────────────
        input_frame = ctk.CTkFrame(dialog, corner_radius=8, border_width=1, border_color="#e5e7eb")
        input_frame.grid(row=2, column=0, padx=20, pady=(0, 8), sticky="nsew")
        input_frame.grid_rowconfigure(1, weight=1)
        input_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            input_frame, text="Project description for rules generation:",
            font=ctk.CTkFont(size=12), text_color="#57606a", anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        # Pre-fill from the existing application brief if available
        prefill = self._description_box.get("1.0", "end-1c").strip()
        if prefill.startswith("Describe the application"):
            prefill = ""

        desc_box = ctk.CTkTextbox(input_frame, wrap="word", font=ctk.CTkFont(size=12))
        desc_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        if prefill:
            desc_box.insert("1.0", prefill)

        # ── Preview area (populated after generation) ─────────────────────────
        preview_frame = ctk.CTkFrame(dialog, corner_radius=8, border_width=1, border_color="#e5e7eb")
        preview_frame.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="nsew")
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(3, weight=2)

        preview_label = ctk.CTkLabel(
            preview_frame, text="Generated rules will appear here for review:",
            font=ctk.CTkFont(size=12), text_color="#57606a", anchor="w",
        )
        preview_label.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        preview_box = ctk.CTkTextbox(
            preview_frame, wrap="word", font=ctk.CTkFont(size=12),
            state="disabled",
        )
        preview_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=20, pady=(0, 16), sticky="ew")
        btn_frame.grid_columnconfigure(2, weight=1)

        status_lbl = ctk.CTkLabel(
            btn_frame, text="", font=ctk.CTkFont(size=11), text_color="#57606a", anchor="w"
        )
        status_lbl.grid(row=0, column=0, sticky="w")

        gen_btn = ctk.CTkButton(
            btn_frame,
            text="✨ Generate",
            width=110, height=34,
            fg_color="#7c5cd8",
            hover_color="#6d28d9",
            command=lambda: self._run_generate_rules(
                desc_box.get("1.0", "end-1c").strip(),
                preview_box,
                gen_btn,
                accept_btn,
                status_lbl,
            ),
        )
        gen_btn.grid(row=0, column=1, padx=(0, 8))

        accept_btn = ctk.CTkButton(
            btn_frame,
            text="Accept →",
            width=90, height=34,
            fg_color="#3b82d4",
            hover_color="#2563eb",
            state="disabled",
            command=lambda: self._accept_generated_rules(
                preview_box.get("1.0", "end-1c"), dialog
            ),
        )
        accept_btn.grid(row=0, column=2, sticky="w")

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80, height=34,
            fg_color="transparent", border_width=1, text_color="#1f2328",
            command=dialog.destroy,
        ).grid(row=0, column=3, padx=(8, 0))

    def _run_generate_rules(
        self,
        description: str,
        preview_box: ctk.CTkTextbox,
        gen_btn: ctk.CTkButton,
        accept_btn: ctk.CTkButton,
        status_lbl: ctk.CTkLabel,
    ) -> None:
        if not description:
            messagebox.showwarning(
                "Missing Description",
                "Please enter a project description to generate rules from.",
                parent=self.winfo_toplevel(),
            )
            return

        gen_btn.configure(state="disabled", text="⏳ Generating…")
        status_lbl.configure(text="Calling LLM…")

        # Apply the provider/model selected on the form before constructing AIClient
        os.environ["MAB_LLM_PROVIDER"] = self._provider_var.get()
        os.environ["MAB_LLM_MODEL"] = self._model_var.get().strip()

        def _run() -> None:
            try:
                from core.ai_client import AIClient
                client = AIClient()
                rules_md = client.generate_project_rules(description)
                self.after(0, lambda: _on_done(rules_md))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Rules generation failed: %s", exc)
                self.after(0, lambda: _on_error())

        def _on_done(rules_md: str) -> None:
            gen_btn.configure(state="normal", text="✨ Generate")
            status_lbl.configure(text="Review the generated rules below.")
            preview_box.configure(state="normal")
            preview_box.delete("1.0", "end")
            preview_box.insert("1.0", rules_md)
            preview_box.configure(state="normal")  # keep editable for user tweaks
            accept_btn.configure(state="normal")

        def _on_error() -> None:
            gen_btn.configure(state="normal", text="✨ Generate")
            status_lbl.configure(text="Generation failed — check the log for details.")

        threading.Thread(target=_run, daemon=True).start()

    def _accept_generated_rules(self, rules_md: str, dialog: ctk.CTkToplevel) -> None:
        """Copy the generated rules into the main rules box and close the dialog."""
        self._set_rules(rules_md.strip())
        dialog.destroy()

    # ── Actions ───────────────────────────────────────────────────────────────

    # Default model names per provider
    _PROVIDER_DEFAULTS = {
        "openai":    "gpt-4o",
        "anthropic": "claude-3-5-sonnet-20241022",
        "watsonx":   "ibm/granite-3-8b-instruct",
        "ollama":    "",
    }

    def _on_provider_changed(self, provider: str) -> None:
        """Update the model field when the provider dropdown changes."""
        if provider == "ollama":
            self._model_var.set("")
            self._model_status.configure(text="Fetching local models…")
            threading.Thread(target=self._fetch_ollama_models, daemon=True).start()
        else:
            default = self._PROVIDER_DEFAULTS.get(provider, "")
            self._model_var.set(default)
            self._model_status.configure(text="")

    def _fetch_ollama_models(self) -> None:
        """Query the Ollama API for available models and populate the model field."""
        base_url = os.environ.get("MAB_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        try:
            req = urllib.request.urlopen(f"{base_url}/api/tags", timeout=5)
            data = json.loads(req.read())
            models = [m["name"] for m in data.get("models", [])]
            if models:
                self.after(0, lambda m=models: self._set_ollama_models(m))
            else:
                self.after(0, lambda: self._model_status.configure(
                    text="No models found — run: ollama pull <model>"
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot reach Ollama: %s", exc)
            self.after(0, lambda: self._model_status.configure(
                text="Cannot reach Ollama — check MAB_OLLAMA_BASE_URL"
            ))

    def _set_ollama_models(self, models: list[str]) -> None:
        """Populate model entry with first Ollama model; show all as hint."""
        self._model_var.set(models[0])
        hint = "Available: " + ", ".join(models)
        self._model_status.configure(text=hint)

    def _clear_placeholder(self, _event) -> None:
        content = self._description_box.get("1.0", "end-1c")
        if content.startswith("Describe the application"):
            self._description_box.delete("1.0", "end")

    def _browse_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self._output_dir_entry.delete(0, "end")
            self._output_dir_entry.insert(0, path)

    # ── Mode switching (new project vs existing project) ──────────────────────

    def reset_to_new(self) -> None:
        """Switch the panel back to new-project mode (called by app.py on New Project)."""
        self._project_root = None
        self._set_new_mode()

    def _set_new_mode(self) -> None:
        """Show the Generate Architecture button."""
        self._generate_btn.configure(
            text="✨  Generate Agent Architecture",
            fg_color="#3b82d4",
            hover_color="#2563eb",
            command=self._on_generate,
            state="normal",
        )

    def _set_existing_mode(self) -> None:
        """Replace the Generate button with Apply Changes for an existing project."""
        self._generate_btn.configure(
            text="💾  Apply Changes",
            fg_color="#22c55e",
            hover_color="#16a34a",
            command=self._on_apply_changes,
            state="normal",
        )

    def _on_generate(self) -> None:
        project_name = self._project_name_entry.get().strip()
        description = self._description_box.get("1.0", "end-1c").strip()
        output_dir = self._output_dir_entry.get().strip() or "./projects"

        if not project_name:
            messagebox.showwarning("Missing Field", "Please enter a project name.")
            return
        if not description or description.startswith("Describe the application"):
            messagebox.showwarning("Missing Field", "Please enter an application description.")
            return

        self._generate_btn.configure(state="disabled", text="⏳  Generating…")
        self._status_var.set("Calling LLM — this may take a few seconds…")

        os.environ["MAB_LLM_PROVIDER"] = self._provider_var.get()
        os.environ["MAB_LLM_MODEL"] = self._model_var.get().strip()

        threading.Thread(
            target=self._run_generation,
            args=(project_name, description, output_dir),
            daemon=True,
        ).start()

    def _run_generation(
        self, project_name: str, description: str, output_dir: str
    ) -> None:
        try:
            from core.ai_client import AIClient
            client = AIClient()
            result = client.generate_scaffold(description)
            self.after(0, lambda: self._show_review(result, project_name, output_dir))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scaffold generation failed: %s", exc)
            self.after(0, self._on_error)

    def _on_error(self) -> None:
        self._generate_btn.configure(state="normal", text="✨  Generate Agent Architecture",
                                     fg_color="#3b82d4", hover_color="#2563eb")
        self._status_var.set("Generation failed — check the application log for details.")
        messagebox.showerror(
            "Generation Error",
            "Architecture generation failed.\nSee the application log for details.",
        )

    def _on_apply_changes(self) -> None:
        """
        Existing-project mode: persist any changes made on the Prompt page
        (project name, description, LLM settings, rules) back to
        mab_project.json and rewrite BOB.md.  No LLM call is made.
        """
        if not self._project_root:
            return

        rules = self._get_rules()
        description = self._description_box.get("1.0", "end-1c").strip()
        project_name = self._project_name_entry.get().strip()

        # Write BOB.md if rules are present
        if rules:
            _write_bob_md(self._project_root, rules)

        # Update mab_project.json — merge over the existing state so we don't
        # lose fields we don't own (e.g. agents list)
        from core.project_state import load_state, save_state
        state = load_state(self._project_root)
        state.update({
            "project_name":  project_name,
            "description":   description,
            "llm_provider":  self._provider_var.get(),
            "llm_model":     self._model_var.get().strip(),
            "project_rules": rules,
        })
        save_state(self._project_root, state)

        self._status_var.set("Changes saved.")
        messagebox.showinfo(
            "Changes Applied",
            "Project settings and rules have been saved.\n"
            + (f"BOB.md written to {self._project_root / _BOB_MD_FILENAME}" if rules else ""),
        )

    def _show_review(
        self, result: dict, project_name: str, output_dir: str
    ) -> None:
        """Show the agent review screen after LLM response."""
        self._generate_btn.configure(state="normal", text="✨  Generate Agent Architecture")
        self._status_var.set("")
        self._proposed_agents = result.get("agents", [])
        project_summary = result.get("project_summary", "")

        if not self._proposed_agents:
            messagebox.showerror("No Agents", "The LLM returned no agents. Try rephrasing the description.")
            return

        # Switch to review screen
        self._screen.grid_remove()
        self._build_review_screen(project_name, project_summary, output_dir)

    def _build_review_screen(
        self, project_name: str, project_summary: str, output_dir: str
    ) -> None:
        review = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        review.grid(row=0, column=0, sticky="nsew")
        review.grid_columnconfigure(0, weight=1)
        review.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            review,
            text=f"Proposed Architecture for: {project_name}",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, pady=(32, 4), padx=40, sticky="w")

        ctk.CTkLabel(
            review,
            text=project_summary,
            font=ctk.CTkFont(size=13),
            text_color="#57606a",
            wraplength=700,
            justify="left",
        ).grid(row=1, column=0, pady=(0, 16), padx=40, sticky="w")

        # Agent checklist
        scroll = ctk.CTkScrollableFrame(review, label_text="Select agents to include:")
        scroll.grid(row=2, column=0, padx=40, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._agent_check_vars = {}
        for idx, agent in enumerate(self._proposed_agents):
            var = ctk.BooleanVar(value=True)
            self._agent_check_vars[agent["name"]] = var

            row_frame = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#f7f8fa")
            row_frame.grid(row=idx, column=0, padx=4, pady=3, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkCheckBox(row_frame, text="", variable=var, width=20).grid(
                row=0, column=0, padx=(8, 4), pady=8
            )
            ctk.CTkLabel(
                row_frame,
                text=f"{agent['name']}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(
                row_frame,
                text=f"{agent.get('position_hint', 'worker')} · {agent.get('role', '')}",
                font=ctk.CTkFont(size=11),
                text_color="#57606a",
                anchor="w",
            ).grid(row=1, column=1, sticky="w", pady=(0, 6))

        # Action buttons
        btn_frame = ctk.CTkFrame(review, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=16, padx=40, sticky="w")

        ctk.CTkButton(
            btn_frame, text="← Back", width=90, height=36,
            fg_color="transparent", border_width=1, text_color="#1f2328",
            command=lambda: (review.destroy(), self._screen.grid()),
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Create Project →",
            height=36,
            fg_color="#3b82d4",
            hover_color="#2563eb",
            command=lambda: self._on_confirm(
                project_name, project_summary, output_dir, review
            ),
        ).grid(row=0, column=1)

    def _on_confirm(
        self,
        project_name: str,
        project_summary: str,
        output_dir: str,
        review_frame: ctk.CTkFrame,
    ) -> None:
        from core.scaffold_engine import AgentSpec, ProjectSpec, create_project

        selected = [
            a for a in self._proposed_agents
            if self._agent_check_vars.get(a["name"], ctk.BooleanVar(value=True)).get()
        ]
        if not selected:
            messagebox.showwarning("No Agents", "Select at least one agent.")
            return

        agents = [AgentSpec.from_dict(a) for a in selected]
        spec = ProjectSpec(
            project_name=project_name,
            project_summary=project_summary,
            agents=agents,
        )

        messages: list[str] = []
        try:
            project_root = create_project(
                spec,
                Path(output_dir),
                progress_cb=lambda m: messages.append(m),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Project scaffold failed: %s", exc)
            messagebox.showerror(
                "Scaffold Error",
                "Project creation failed.\nSee the application log for details.",
            )
            return

        # ── Write BOB.md to the project root ──────────────────────────────────
        rules = self._get_rules()
        if rules:
            _write_bob_md(project_root, rules)

        # ── Persist all prompt-page inputs alongside the project ──────────────
        from core.project_state import save_state
        save_state(project_root, {
            "project_name":    project_name,
            "project_summary": project_summary,
            "description":     self._description_box.get("1.0", "end-1c").strip(),
            "output_dir":      str(Path(output_dir).resolve()),
            "llm_provider":    self._provider_var.get(),
            "llm_model":       self._model_var.get().strip(),
            "agents":          self._proposed_agents,
            "project_rules":   rules,
        })

        review_frame.destroy()
        self.on_project_created(project_root, {"summary": project_summary})

    # ── State restore (called when an existing project is opened) ─────────────

    def load_state(self, project_root: Path) -> None:
        """
        Restore the prompt-page fields from a project's mab_project.json.
        Called by app.py when the user opens an existing project.
        Shows the prompt tab pre-filled with the original inputs.
        Also loads BOB.md from the project root if it exists.
        """
        self._project_root = project_root
        self._set_existing_mode()

        from core.project_state import load_state
        state = load_state(project_root)
        if not state:
            # Still try to load BOB.md even if no state file
            _load_bob_md_into(project_root, self._set_rules)
            return

        # Project name
        self._project_name_entry.delete(0, "end")
        self._project_name_entry.insert(0, state.get("project_name", ""))

        # Output directory
        out_dir = state.get("output_dir", "")
        if out_dir:
            self._output_dir_entry.delete(0, "end")
            self._output_dir_entry.insert(0, out_dir)

        # LLM provider + model
        provider = state.get("llm_provider", "")
        if provider and provider in self.LLM_PROVIDERS:
            self._provider_var.set(provider)
        model = state.get("llm_model", "")
        if model:
            self._model_var.set(model)
            self._model_status.configure(text="")

        # Application brief
        description = state.get("description", "")
        if description:
            self._description_box.delete("1.0", "end")
            self._description_box.insert("1.0", description)

        # Project rules — prefer BOB.md on disk over cached state value
        bob_md_text = _read_bob_md(project_root)
        if bob_md_text:
            self._set_rules(bob_md_text)
        else:
            rules = state.get("project_rules", "")
            if rules:
                self._set_rules(rules)

        # Restore proposed agents and show summary banner (no LLM call needed)
        agents = state.get("agents", [])
        project_summary = state.get("project_summary", "")
        if agents:
            self._proposed_agents = agents
            self._show_restore_banner(
                state.get("project_name", project_root.name),
                project_summary,
                agents,
            )

    def _show_restore_banner(
        self, project_name: str, project_summary: str, agents: list[dict]
    ) -> None:
        """
        Show a compact read-only summary of the last LLM output beneath the
        form so the user can see what was previously generated without re-running.
        Replaces any existing banner.
        """
        # Remove old banner if present
        if hasattr(self, "_restore_banner") and self._restore_banner.winfo_exists():
            self._restore_banner.destroy()

        banner = ctk.CTkFrame(
            self._screen, corner_radius=8,
            border_width=1, border_color="#bfdbfe",
            fg_color="#eff6ff",
        )
        banner.grid(row=4, column=0, padx=80, pady=(8, 0), sticky="ew")
        banner.grid_columnconfigure(0, weight=1)
        self._restore_banner = banner

        header = ctk.CTkFrame(banner, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=f"Last generated architecture for: {project_name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1e40af",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="✕", width=24, height=24,
            fg_color="transparent", hover_color="#dbeafe",
            text_color="#1e40af",
            command=banner.destroy,
        ).grid(row=0, column=1)

        if project_summary:
            ctk.CTkLabel(
                banner,
                text=project_summary,
                font=ctk.CTkFont(size=11),
                text_color="#374151",
                wraplength=700,
                justify="left",
                anchor="w",
            ).grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

        agent_text = "  ·  ".join(
            f"{a.get('name', '?')} ({a.get('position_hint', 'worker')})"
            for a in agents
        )
        ctk.CTkLabel(
            banner,
            text=f"Agents: {agent_text}",
            font=ctk.CTkFont(size=11),
            text_color="#57606a",
            wraplength=700,
            justify="left",
            anchor="w",
        ).grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")


# ── BOB.md file helpers ───────────────────────────────────────────────────────

def _write_bob_md(project_root: Path, content: str) -> None:
    """Write the rules content to BOB.md in the project root."""
    target = project_root / _BOB_MD_FILENAME
    try:
        target.write_text(content, encoding="utf-8")
        logger.info("BOB.md written to %s", target)
    except OSError as exc:
        logger.warning("Could not write BOB.md: %s", exc)


def _read_bob_md(project_root: Path) -> str:
    """Read BOB.md from the project root. Returns empty string if absent."""
    target = project_root / _BOB_MD_FILENAME
    if not target.exists():
        return ""
    try:
        return target.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Could not read BOB.md: %s", exc)
        return ""


def _load_bob_md_into(project_root: Path, set_fn: Callable[[str], None]) -> None:
    """Read BOB.md and call set_fn if content is found."""
    text = _read_bob_md(project_root)
    if text:
        set_fn(text)
