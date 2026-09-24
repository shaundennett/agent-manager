"""
ui/components/proforma_form.py
──────────────────────────────
Scrollable proforma editor for a single agent.md file.
Renders 10 collapsible accordion sections with inline AI-assist buttons.
"""

from __future__ import annotations

import logging
from typing import Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)

# ── Section definitions ───────────────────────────────────────────────────────
# Each section: (title, [(field_key, label, widget_type, required, ai_assist)])
# widget_type: "entry" | "textarea" | "dropdown:<opt1>,<opt2>" | "toggle"

SECTIONS: list[tuple[str, list[tuple]]] = [
    ("Identity & Purpose", [
        ("name",        "Name *",        "entry",    True,  False),
        ("version",     "Version *",     "entry",    True,  False),
        ("type",        "Type *",        "dropdown:orchestrator,worker,specialist,gateway,hybrid", True, True),
        ("role",        "Role *",        "entry",    True,  True),
        ("description", "Description *", "textarea", True,  True),
        ("goals",       "Goals *",       "textarea", True,  True),
        ("non_goals",   "Non-Goals",     "textarea", False, True),
    ]),
    ("Capabilities & Tools", [
        ("capabilities",     "Capabilities *",    "textarea", True,  True),
        ("tools",            "Tools *",           "textarea", True,  True),
        ("external_apis",    "External APIs",     "textarea", False, False),
        ("knowledge_sources","Knowledge Sources", "textarea", False, True),
    ]),
    ("Inputs & Outputs", [
        ("inputs",       "Inputs *",       "textarea",                        True,  True),
        ("outputs",      "Outputs *",      "textarea",                        True,  True),
        ("input_format", "Input Format *", "dropdown:JSON,text,structured,binary", True, False),
        ("output_format","Output Format *","dropdown:JSON,text,structured,binary", True, False),
    ]),
    ("Behaviour & Reasoning", [
        ("reasoning_strategy","Reasoning Strategy *","dropdown:ReAct,CoT,Plan-Execute,Reflexion,Custom", True, True),
        ("decision_logic",    "Decision Logic *",    "textarea", True,  True),
        ("fallback_behaviour","Fallback Behaviour *","textarea", True,  True),
        ("max_iterations",    "Max Iterations",      "entry",    False, False),
        ("timeout_seconds",   "Timeout (s)",         "entry",    False, False),
        ("retry_policy",      "Retry Policy",        "dropdown:none,fixed,exponential", False, False),
    ]),
    ("Communication & Orchestration", [
        ("trigger",               "Trigger *",              "dropdown:user,agent,schedule,event,webhook", True, False),
        ("communicates_with",     "Communicates With *",    "entry",   True,  True),
        ("communication_protocol","Protocol *",             "dropdown:direct-call,message-queue,REST,gRPC,event-bus", True, True),
        ("handoff_conditions",    "Handoff Conditions *",   "textarea",True,  True),
    ]),
    ("Memory & State", [
        ("memory_type",            "Memory Type *",            "dropdown:none,in-context,vector-store,database,hybrid", True, True),
        ("state_persistence",      "State Persistence *",      "dropdown:true,false", True, False),
        ("context_window_strategy","Context Window Strategy",  "dropdown:full,summarise,sliding,retrieval", False, True),
        ("memory_notes",           "Memory Notes",             "textarea", False, True),
    ]),
    ("Security & Compliance", [
        ("authentication",     "Authentication *",    "dropdown:none,API-key,OAuth2,OIDC,mTLS", True, False),
        ("authorisation_model","Authorisation *",     "dropdown:none,RBAC,ABAC,policy-engine",  True, False),
        ("data_sensitivity",   "Data Sensitivity *",  "dropdown:public,internal,confidential,restricted", True, False),
        ("pii_handling",       "PII Handling *",      "entry",  True,  True),
        ("audit_logging",      "Audit Logging *",     "dropdown:true,false", True, False),
        ("rate_limiting",      "Rate Limiting",       "entry",  False, False),
    ]),
    ("Observability", [
        ("logging_level",         "Logging Level *",    "dropdown:DEBUG,INFO,WARN,ERROR", True, False),
        ("metrics_exposed",       "Metrics Exposed",    "textarea", False, True),
        ("tracing_enabled",       "Tracing Enabled *",  "dropdown:true,false", True, False),
        ("health_check_endpoint", "Health Check",       "entry", False, False),
        ("alerting_thresholds",   "Alerting Thresholds","textarea", False, True),
    ]),
    ("Deployment", [
        ("runtime",               "Runtime *",           "entry",  True,  False),
        ("deployment_target",     "Deployment Target *", "dropdown:local,container,k8s,serverless,cloud", True, False),
        ("container_image",       "Container Image",     "entry",  False, False),
        ("environment_variables", "Env Variables *",     "textarea",True, True),
        ("resource_requirements", "Resource Requirements","textarea",False, False),
    ]),
    ("Testing & Evaluation", [
        ("test_strategy",     "Test Strategy *",     "textarea", True,  True),
        ("evaluation_metrics","Evaluation Metrics *","textarea", True,  True),
        ("test_cases",        "Test Cases",          "textarea", False, True),
        ("known_limitations", "Known Limitations *", "textarea", True,  True),
    ]),
]

_TODO = "<!-- TODO: complete this section -->"


class ProformaForm(ctk.CTkScrollableFrame):
    """Scrollable accordion form for all 10 agent.md sections."""

    def __init__(
        self,
        master,
        on_change: Callable[[str, str], None],
        on_ai_assist: Callable[[str], None],
        on_fill_section: Callable[[str, list[str]], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.on_change = on_change        # (field_key, new_value)
        self.on_ai_assist = on_ai_assist  # (field_key)
        self.on_fill_section = on_fill_section  # (section_title, [field_keys])

        self._widgets: dict[str, ctk.CTkBaseClass] = {}
        self._section_frames: dict[str, ctk.CTkFrame] = {}
        self._section_open: dict[str, bool] = {}

        self.grid_columnconfigure(0, weight=1)
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        for row_idx, (section_title, fields) in enumerate(SECTIONS):
            self._add_section(row_idx, section_title, fields)

    def _add_section(
        self, row_idx: int, title: str, fields: list[tuple]
    ) -> None:
        container = ctk.CTkFrame(self, corner_radius=8, border_width=1,
                                  border_color="#e5e7eb")
        container.grid(row=row_idx, column=0, sticky="ew", padx=8, pady=4)
        container.grid_columnconfigure(0, weight=1)

        # Accordion header row
        header_row = ctk.CTkFrame(container, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=4, pady=2)
        header_row.grid_columnconfigure(0, weight=1)

        open_state = ctk.BooleanVar(value=(row_idx == 0))
        self._section_open[title] = row_idx == 0

        def toggle(t=title, ov=open_state):
            ov.set(not ov.get())
            self._section_open[t] = ov.get()
            body = self._section_frames.get(t)
            if body:
                if ov.get():
                    body.grid()
                else:
                    body.grid_remove()

        header_btn = ctk.CTkButton(
            header_row,
            text=f"▸  {title}",
            anchor="w",
            fg_color="transparent",
            hover_color="#f0f4ff",
            text_color="#1f2328",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=toggle,
            height=32,
        )
        header_btn.grid(row=0, column=0, sticky="ew")

        # Section-level AI fill button (only if section has ai_assist fields)
        section_ai_fields = [k for k, _l, _w, _r, ai in fields if ai]
        if section_ai_fields and self.on_fill_section:
            fill_btn = ctk.CTkButton(
                header_row,
                text="✨ Fill section",
                width=100, height=26,
                fg_color="transparent",
                hover_color="#ede9fe",
                text_color="#7c5cd8",
                border_width=1,
                border_color="#c4b5fd",
                font=ctk.CTkFont(size=11),
                command=lambda t=title, fk=section_ai_fields: self.on_fill_section(t, fk),
            )
            fill_btn.grid(row=0, column=1, padx=(4, 6))

        # Section body
        body = ctk.CTkFrame(container, corner_radius=0, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        body.grid_columnconfigure(1, weight=1)
        self._section_frames[title] = body

        if row_idx != 0:
            body.grid_remove()

        for field_row, (key, label, widget_type, required, ai_assist) in enumerate(fields):
            self._add_field(body, field_row, key, label, widget_type, required, ai_assist)

    def _add_field(
        self,
        parent: ctk.CTkFrame,
        row: int,
        key: str,
        label: str,
        widget_type: str,
        required: bool,
        ai_assist: bool,
    ) -> None:
        lbl = ctk.CTkLabel(
            parent, text=label, anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="#1f2328" if required else "#57606a",
            width=160,
        )
        lbl.grid(row=row, column=0, padx=(0, 8), pady=4, sticky="nw")

        if widget_type.startswith("dropdown:"):
            options = widget_type.split(":")[1].split(",")
            var = ctk.StringVar(value=options[0])
            widget = ctk.CTkOptionMenu(
                parent, variable=var, values=options,
                width=220, height=28,
                command=lambda v, k=key: self.on_change(k, v),
            )
            self._widgets[key] = widget
        elif widget_type == "textarea":
            widget = ctk.CTkTextbox(parent, height=80, wrap="word", font=ctk.CTkFont(size=12))
            widget.bind("<KeyRelease>", lambda e, k=key: self._text_changed(k))
            self._widgets[key] = widget
        else:  # entry
            widget = ctk.CTkEntry(parent, height=28, font=ctk.CTkFont(size=12))
            widget.bind("<KeyRelease>", lambda e, k=key: self._entry_changed(k))
            self._widgets[key] = widget

        widget.grid(row=row, column=1, padx=(0, 4), pady=4, sticky="ew")

        if ai_assist:
            assist_btn = ctk.CTkButton(
                parent, text="✨", width=28, height=28,
                fg_color="transparent", hover_color="#e5e7eb",
                text_color="#7c5cd8", font=ctk.CTkFont(size=14),
                command=lambda k=key: self.on_ai_assist(k),
            )
            assist_btn.grid(row=row, column=2, padx=(2, 0), pady=4)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_fields(self, fields: dict[str, str]) -> None:
        """Populate the form with values from a parsed agent.md."""
        for key, widget in self._widgets.items():
            value = fields.get(key, "")
            if value == _TODO:
                value = ""
            self._set_widget_value(widget, value)

    def get_fields(self) -> dict[str, str]:
        """Read all current form values into a dict."""
        result: dict[str, str] = {}
        for key, widget in self._widgets.items():
            result[key] = self._get_widget_value(widget)
        return result

    def set_field(self, key: str, value: str) -> None:
        """Set a single field value (used by AI-assist acceptance)."""
        widget = self._widgets.get(key)
        if widget:
            self._set_widget_value(widget, value)
            self.on_change(key, value)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _text_changed(self, key: str) -> None:
        widget = self._widgets.get(key)
        if isinstance(widget, ctk.CTkTextbox):
            value = widget.get("1.0", "end-1c")
            self.on_change(key, value)

    def _entry_changed(self, key: str) -> None:
        widget = self._widgets.get(key)
        if isinstance(widget, ctk.CTkEntry):
            self.on_change(key, widget.get())

    @staticmethod
    def _set_widget_value(widget: ctk.CTkBaseClass, value: str) -> None:
        if isinstance(widget, ctk.CTkTextbox):
            widget.delete("1.0", "end")
            if value:
                widget.insert("1.0", value)
        elif isinstance(widget, ctk.CTkEntry):
            widget.delete(0, "end")
            if value:
                widget.insert(0, value)
        elif isinstance(widget, ctk.CTkOptionMenu):
            widget.set(value or widget.cget("values")[0])

    @staticmethod
    def _get_widget_value(widget: ctk.CTkBaseClass) -> str:
        if isinstance(widget, ctk.CTkTextbox):
            return widget.get("1.0", "end-1c").strip()
        if isinstance(widget, ctk.CTkEntry):
            return widget.get().strip()
        if isinstance(widget, ctk.CTkOptionMenu):
            return widget.get()
        return ""
