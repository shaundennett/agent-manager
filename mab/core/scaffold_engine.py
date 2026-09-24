"""
core/scaffold_engine.py
───────────────────────
Creates the project folder structure and pre-populates agent.md template files
from the LLM scaffold response.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_TODO = "<!-- TODO: complete this section -->"


@dataclass
class AgentSpec:
    name: str
    role: str
    primary_responsibility: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    communicates_with: list[str] = field(default_factory=list)
    trigger: str = "agent"
    position_hint: str = "worker"

    @classmethod
    def from_dict(cls, data: dict) -> "AgentSpec":
        return cls(
            name=_slugify(data.get("name", "unnamed_agent")),
            role=data.get("role", ""),
            primary_responsibility=data.get("primary_responsibility", ""),
            inputs=data.get("inputs", []),
            outputs=data.get("outputs", []),
            tools=data.get("tools", []),
            communicates_with=data.get("communicates_with", []),
            trigger=data.get("trigger", "agent"),
            position_hint=data.get("position_hint", "worker"),
        )


@dataclass
class ProjectSpec:
    project_name: str
    project_summary: str
    agents: list[AgentSpec]


def create_project(
    spec: ProjectSpec,
    output_dir: Path,
    progress_cb: Callable[[str], None] | None = None,
) -> Path:
    """
    Scaffold the full project directory structure.
    Returns the path to the created project root.
    """
    def notify(msg: str) -> None:
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    project_root = output_dir / _slugify(spec.project_name)
    project_root.mkdir(parents=True, exist_ok=True)
    notify(f"Created project root: {project_root}")

    # Project README
    readme_template = (_TEMPLATE_DIR / "project_readme.md").read_text(encoding="utf-8")
    agent_table_rows = "\n".join(
        f"| `{a.name}` | {a.position_hint} | {a.role} |"
        for a in spec.agents
    )
    readme = (
        readme_template
        .replace("{{project_name}}", spec.project_name)
        .replace("{{project_summary}}", spec.project_summary)
        .replace("{{agent_table}}", agent_table_rows)
        .replace("{{agent_count}}", str(len(spec.agents)))
    )
    (project_root / "README.md").write_text(readme, encoding="utf-8")
    notify("Written README.md")

    # Per-agent scaffolds
    agent_template = (_TEMPLATE_DIR / "agent_template.md").read_text(encoding="utf-8")

    for agent_spec in spec.agents:
        agent_dir = project_root / "agents" / agent_spec.name
        agent_dir.mkdir(parents=True, exist_ok=True)
        content = _populate_template(agent_template, agent_spec, spec)
        (agent_dir / "agent.md").write_text(content, encoding="utf-8")
        notify(f"  Scaffolded agent: {agent_spec.name}")

    notify(f"Scaffold complete — {len(spec.agents)} agent(s) created.")
    return project_root


def add_agent(
    project_root: Path,
    agent_spec: AgentSpec,
    project_summary: str = "",
) -> Path:
    """Add a single new agent to an existing project."""
    agent_template = (_TEMPLATE_DIR / "agent_template.md").read_text(encoding="utf-8")
    dummy_spec = ProjectSpec(
        project_name=project_root.name,
        project_summary=project_summary,
        agents=[agent_spec],
    )
    content = _populate_template(agent_template, agent_spec, dummy_spec)
    agent_dir = project_root / "agents" / agent_spec.name
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_path = agent_dir / "agent.md"
    agent_path.write_text(content, encoding="utf-8")
    logger.info("Added agent: %s", agent_spec.name)
    return agent_path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _populate_template(
    template: str,
    agent: AgentSpec,
    project: ProjectSpec,
) -> str:
    """
    Replace comment-tag placeholders in the template with values from AgentSpec.
    Any placeholder that cannot be derived is replaced with _TODO.
    """
    inputs_md = "\n".join(f"- {i}" for i in agent.inputs) if agent.inputs else _TODO
    outputs_md = "\n".join(f"- {o}" for o in agent.outputs) if agent.outputs else _TODO
    tools_md = "\n".join(f"- {t}" for t in agent.tools) if agent.tools else _TODO
    comms = ", ".join(agent.communicates_with) if agent.communicates_with else _TODO

    subs = {
        "name": agent.name,
        "version": "1.0.0",
        "type": agent.position_hint,
        "role": agent.role,
        "runtime": "Python 3.11",
        "description": agent.primary_responsibility or _TODO,
        "goals": _TODO,
        "non_goals": _TODO,
        "capabilities": _TODO,
        "tools": tools_md,
        "external_apis": _TODO,
        "knowledge_sources": _TODO,
        "inputs": inputs_md,
        "outputs": outputs_md,
        "input_format": _TODO,
        "output_format": _TODO,
        "reasoning_strategy": _TODO,
        "decision_logic": _TODO,
        "fallback_behaviour": _TODO,
        "max_iterations": _TODO,
        "timeout_seconds": _TODO,
        "retry_policy": _TODO,
        "trigger": agent.trigger,
        "communicates_with": comms,
        "communication_protocol": _TODO,
        "handoff_conditions": _TODO,
        "memory_type": _TODO,
        "state_persistence": _TODO,
        "context_window_strategy": _TODO,
        "memory_notes": _TODO,
        "authentication": _TODO,
        "authorisation_model": _TODO,
        "data_sensitivity": _TODO,
        "pii_handling": _TODO,
        "audit_logging": _TODO,
        "rate_limiting": _TODO,
        "logging_level": "INFO",
        "metrics_exposed": _TODO,
        "tracing_enabled": "false",
        "health_check_endpoint": _TODO,
        "alerting_thresholds": _TODO,
        "deployment_target": _TODO,
        "container_image": _TODO,
        "environment_variables": _TODO,
        "resource_requirements": _TODO,
        "test_strategy": _TODO,
        "evaluation_metrics": _TODO,
        "test_cases": _TODO,
        "known_limitations": _TODO,
    }

    result = template
    for key, value in subs.items():
        # Replace ALL occurrences (the name tag appears in the title AND in **Name:**)
        pattern = re.compile(r"<!--\s*" + re.escape(key) + r"(?:\s*:[^>]*)?\s*-->")
        result = pattern.sub(value, result)

    return result


def _slugify(text: str) -> str:
    """Convert text to a safe directory/file slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text
