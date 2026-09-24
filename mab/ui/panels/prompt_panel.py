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

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_prompt_screen()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_prompt_screen(self) -> None:
        """Initial input screen."""
        self._screen = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._screen.grid(row=0, column=0, sticky="nsew")
        self._screen.grid_columnconfigure(0, weight=1)
        self._screen.grid_rowconfigure(3, weight=1)

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
        self._project_name_entry.grid(row=0, column=1, padx=(0, 16), pady=(16, 4), sticky="ew")

        # Output directory
        ctk.CTkLabel(card, text="Output Directory *", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=1, column=0, padx=16, pady=4, sticky="w")
        dir_frame = ctk.CTkFrame(card, fg_color="transparent")
        dir_frame.grid(row=1, column=1, padx=(0, 16), pady=4, sticky="ew")
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
        ).grid(row=2, column=1, padx=(0, 16), pady=4, sticky="w")

        # Model name (dynamic for Ollama, editable for all)
        ctk.CTkLabel(card, text="Model", anchor="w",
                      font=ctk.CTkFont(size=13)).grid(row=3, column=0, padx=16, pady=4, sticky="w")
        model_frame = ctk.CTkFrame(card, fg_color="transparent")
        model_frame.grid(row=3, column=1, padx=(0, 16), pady=4, sticky="ew")
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
        self._description_box.grid(row=4, column=1, padx=(0, 16), pady=4, sticky="ew")
        self._description_box.insert(
            "1.0",
            "Describe the application you want to build. For example:\n\n"
            "\"A customer support automation system that receives incoming tickets, "
            "classifies them by urgency and topic, routes them to the appropriate "
            "specialist agent, drafts a response, and logs the interaction.\"",
        )
        self._description_box.bind("<FocusIn>", self._clear_placeholder)

        # Generate button
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
            row=5, column=0, columnspan=2, padx=16, pady=(12, 16), sticky="ew"
        )

        # Status
        self._status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self._screen, textvariable=self._status_var,
            font=ctk.CTkFont(size=12), text_color="#57606a",
        ).grid(row=3, column=0, pady=(8, 0))

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
            msg = str(exc)
            self.after(0, lambda m=msg: self._model_status.configure(
                text=f"Cannot reach Ollama: {m}"
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
            msg = str(exc)
            self.after(0, lambda m=msg: self._on_error(m))

    def _on_error(self, message: str) -> None:
        self._generate_btn.configure(state="normal", text="✨  Generate Agent Architecture")
        self._status_var.set(f"Error: {message}")
        messagebox.showerror("Generation Error", message)

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
            messagebox.showerror("Scaffold Error", str(exc))
            return

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
        })

        review_frame.destroy()
        self.on_project_created(project_root, {"summary": project_summary})

    # ── State restore (called when an existing project is opened) ─────────────

    def load_state(self, project_root: Path) -> None:
        """
        Restore the prompt-page fields from a project's mab_project.json.
        Called by app.py when the user opens an existing project.
        Shows the prompt tab pre-filled with the original inputs.
        """
        from core.project_state import load_state
        state = load_state(project_root)
        if not state:
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
