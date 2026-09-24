"""
core/agent_parser.py
────────────────────
Reads and writes agent.md files.

Strategy
────────
* On first scaffold, files contain <!-- field --> comment-tag placeholders.
  `load()` extracts whatever values are already substituted (bold lines,
  section bodies) and returns them alongside the raw content.

* On every `save()` after that, the file is FULLY REGENERATED from the
  stored field values using `_build_content()`.  This avoids the
  round-trip fragility of trying to patch comment tags in-place.

* `load()` reads both the comment-tag format AND the generated format,
  so files saved by the tool, files edited by hand, and freshly scaffolded
  files all parse correctly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# ── Field sets ────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "name", "version", "type", "role", "description", "goals",
    "capabilities", "tools", "inputs", "outputs", "input_format",
    "output_format", "reasoning_strategy", "decision_logic",
    "fallback_behaviour", "trigger", "communicates_with",
    "communication_protocol", "handoff_conditions", "memory_type",
    "state_persistence", "authentication", "authorisation_model",
    "data_sensitivity", "pii_handling", "audit_logging",
    "logging_level", "tracing_enabled", "runtime",
    "deployment_target", "environment_variables",
    "test_strategy", "evaluation_metrics", "known_limitations",
}

_TODO_MARKER = "<!-- TODO: complete this section -->"

# Bold inline header → field key
_BOLD_KEY_MAP: dict[str, str] = {
    "Name":                    "name",
    "Version":                 "version",
    "Type":                    "type",
    "Role":                    "role",
    "Runtime":                 "runtime",
    "Input Format":            "input_format",
    "Output Format":           "output_format",
    "Reasoning Strategy":      "reasoning_strategy",
    "Max Iterations":          "max_iterations",
    "Timeout (s)":             "timeout_seconds",
    "Retry Policy":            "retry_policy",
    "Trigger":                 "trigger",
    "Communicates With":       "communicates_with",
    "Communication Protocol":  "communication_protocol",
    "Memory Type":             "memory_type",
    "State Persistence":       "state_persistence",
    "Context Window Strategy": "context_window_strategy",
    "Authentication":          "authentication",
    "Authorisation Model":     "authorisation_model",
    "Data Sensitivity":        "data_sensitivity",
    "PII Handling":            "pii_handling",
    "Audit Logging":           "audit_logging",
    "Rate Limiting":           "rate_limiting",
    "Logging Level":           "logging_level",
    "Tracing Enabled":         "tracing_enabled",
    "Health Check Endpoint":   "health_check_endpoint",
    "Deployment Target":       "deployment_target",
    "Container Image":         "container_image",
    "Test Strategy":           "test_strategy",
}

# Markdown section heading → field key (for multi-line body blocks)
_SECTION_MAP: dict[str, str] = {
    "description":             "description",
    "goals":                   "goals",
    "non-goals":               "non_goals",
    "capabilities":            "capabilities",
    "tools":                   "tools",
    "external apis":           "external_apis",
    "knowledge sources":       "knowledge_sources",
    "inputs":                  "inputs",
    "outputs":                 "outputs",
    "decision logic":          "decision_logic",
    "fallback behaviour":      "fallback_behaviour",
    "handoff conditions":      "handoff_conditions",
    "memory notes":            "memory_notes",
    "environment variables":   "environment_variables",
    "resource requirements":   "resource_requirements",
    "evaluation metrics":      "evaluation_metrics",
    "test cases":              "test_cases",
    "known limitations":       "known_limitations",
    "metrics exposed":         "metrics_exposed",
    "alerting thresholds":     "alerting_thresholds",
}


class AgentData:
    """Container for a single agent's field values."""

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path | None = path
        self.fields: dict[str, str] = {}
        # raw_content is kept only so callers can inspect the original text;
        # save() no longer uses it for rendering.
        self.raw_content: str = ""

    @property
    def name(self) -> str:
        return self.fields.get("name", "")

    @property
    def role(self) -> str:
        return self.fields.get("role", "")

    @property
    def agent_type(self) -> str:
        return self.fields.get("type", "worker")

    @property
    def trigger(self) -> str:
        return self.fields.get("trigger", "")

    @property
    def communicates_with(self) -> list[str]:
        raw = self.fields.get("communicates_with", "")
        return [s.strip() for s in raw.split(",") if s.strip()]

    @property
    def communication_protocol(self) -> str:
        return self.fields.get("communication_protocol", "")

    @property
    def handoff_conditions(self) -> str:
        return self.fields.get("handoff_conditions", "")

    @property
    def completion_pct(self) -> int:
        filled = sum(
            1
            for f in REQUIRED_FIELDS
            if self.fields.get(f, "").strip()
            and _TODO_MARKER not in self.fields.get(f, "")
        )
        return round(filled / len(REQUIRED_FIELDS) * 100)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.fields)


# ── Public API ────────────────────────────────────────────────────────────────

def load(path: Path) -> AgentData:
    """Parse an agent.md file and return an AgentData instance."""
    data = AgentData(path=path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot read {path}: {exc}") from exc

    data.raw_content = raw
    data.fields = _parse_fields(raw)

    # Fall back: infer name from parent directory if not parsed
    if not data.fields.get("name") and path.parent.name:
        data.fields["name"] = path.parent.name

    return data


def save(data: AgentData, path: Path | None = None) -> None:
    """
    Write an AgentData instance to disk as a clean structured markdown file.
    Every save fully regenerates the file from the in-memory field dict,
    so there is no fragile comment-tag round-trip.
    """
    target = path or data.path
    if target is None:
        raise ValueError("No target path for save()")

    content = _build_content(data.fields)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    # Update raw_content so subsequent loads from the cache stay consistent
    data.raw_content = content


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_fields(content: str) -> dict[str, str]:
    """
    Extract field values from agent.md content.
    Handles both the initial scaffold format (comment tags) and the
    saved format (bold lines + section headers).
    """
    fields: dict[str, str] = {}

    # 1. Inline comment tags:  <!-- key: value -->
    for m in re.finditer(r"<!--\s*(\w+)\s*:\s*([^->][^>]*?)\s*-->", content):
        key, value = m.group(1), m.group(2).strip()
        if value and "TODO" not in value and "complete this" not in value:
            fields[key] = value

    # 2. Standalone block tags:  <!-- key -->\ntext\n...
    for m in re.finditer(
        r"<!--\s*(\w+)\s*-->\s*\n(.*?)(?=\n<!--|\n---|\Z)", content, re.DOTALL
    ):
        key, value = m.group(1), m.group(2).strip()
        if value and _TODO_MARKER not in value and "TODO" not in value:
            fields.setdefault(key, value)

    # 3. Bold inline fields:  **Key:** value
    for m in re.finditer(r"^\*\*([^*:]+):?\*\*\s*:?\s*(.+)$", content, re.MULTILINE):
        raw_key = m.group(1).strip().rstrip(":")
        value = m.group(2).strip()
        field_name = _BOLD_KEY_MAP.get(raw_key)
        if field_name and value and "TODO" not in value and "<!--" not in value:
            fields.setdefault(field_name, value)

    # 4. Section body blocks (between ## / ### headers)
    headers = list(re.finditer(r"^#{2,3}\s+(.+)$", content, re.MULTILINE))
    for i, hm in enumerate(headers):
        header_text = hm.group(1).strip().lower()
        field_name = _SECTION_MAP.get(header_text)
        if not field_name:
            continue
        start = hm.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        block = content[start:end].strip()
        # Remove bold key lines and HR rules that live inside the section
        block = re.sub(r"^\*\*[^*]+\*\*\s*:.*$", "", block, flags=re.MULTILINE)
        block = re.sub(r"^---\s*$", "", block, flags=re.MULTILINE)
        block = block.strip()
        if block and _TODO_MARKER not in block and "<!--" not in block:
            fields.setdefault(field_name, block)

    return fields


# ── Serialisation ─────────────────────────────────────────────────────────────

def _v(fields: dict, key: str) -> str:
    """Return field value or empty string, never the TODO marker."""
    val = fields.get(key, "")
    if _TODO_MARKER in val:
        return ""
    return val.strip()


def _build_content(fields: dict[str, str]) -> str:
    """
    Generate a clean, fully human-readable agent.md from a field dict.
    This is the canonical on-disk format after the first save.
    """
    name    = _v(fields, "name")    or "unnamed"
    version = _v(fields, "version") or "1.0.0"
    atype   = _v(fields, "type")    or "worker"
    role    = _v(fields, "role")
    runtime = _v(fields, "runtime") or "Python 3.11"

    def section(heading: str, body: str, level: int = 2) -> str:
        hdr = "#" * level + " " + heading
        if not body:
            return f"{hdr}\n\n_Not yet defined._\n"
        return f"{hdr}\n\n{body}\n"

    def kv(label: str, value: str) -> str:
        return f"**{label}:** {value or '_Not set_'}"

    lines: list[str] = []

    # Title
    lines.append(f"# Agent: {name}\n")

    # Overview
    lines.append("## Overview\n")
    lines.append(kv("Name",    name))
    lines.append(kv("Version", version))
    lines.append(kv("Type",    atype))
    lines.append(kv("Role",    role))
    lines.append(kv("Runtime", runtime))
    lines.append("")
    lines.append("---\n")

    # Identity sections
    lines.append(section("Description",  _v(fields, "description")))
    lines.append(section("Goals",        _v(fields, "goals")))
    lines.append(section("Non-Goals",    _v(fields, "non_goals")))
    lines.append("---\n")

    # Capabilities & Tools
    lines.append("## Capabilities & Tools\n")
    lines.append(section("Capabilities",    _v(fields, "capabilities"),    3))
    lines.append(section("Tools",           _v(fields, "tools"),           3))
    lines.append(section("External APIs",   _v(fields, "external_apis"),   3))
    lines.append(section("Knowledge Sources", _v(fields, "knowledge_sources"), 3))
    lines.append("---\n")

    # Inputs & Outputs
    lines.append("## Inputs & Outputs\n")
    lines.append(section("Inputs",  _v(fields, "inputs"),  3))
    lines.append(section("Outputs", _v(fields, "outputs"), 3))
    lines.append(kv("Input Format",  _v(fields, "input_format")))
    lines.append(kv("Output Format", _v(fields, "output_format")))
    lines.append("")
    lines.append("---\n")

    # Behaviour & Reasoning
    lines.append("## Behaviour & Reasoning\n")
    lines.append(kv("Reasoning Strategy", _v(fields, "reasoning_strategy")))
    lines.append(kv("Max Iterations",     _v(fields, "max_iterations")))
    lines.append(kv("Timeout (s)",        _v(fields, "timeout_seconds")))
    lines.append(kv("Retry Policy",       _v(fields, "retry_policy")))
    lines.append("")
    lines.append(section("Decision Logic",    _v(fields, "decision_logic"),    3))
    lines.append(section("Fallback Behaviour", _v(fields, "fallback_behaviour"), 3))
    lines.append("---\n")

    # Communication & Orchestration
    lines.append("## Communication & Orchestration\n")
    lines.append(kv("Trigger",               _v(fields, "trigger")))
    lines.append(kv("Communicates With",     _v(fields, "communicates_with")))
    lines.append(kv("Communication Protocol", _v(fields, "communication_protocol")))
    lines.append("")
    lines.append(section("Handoff Conditions", _v(fields, "handoff_conditions"), 3))
    lines.append("---\n")

    # Memory & State
    lines.append("## Memory & State\n")
    lines.append(kv("Memory Type",             _v(fields, "memory_type")))
    lines.append(kv("State Persistence",       _v(fields, "state_persistence")))
    lines.append(kv("Context Window Strategy", _v(fields, "context_window_strategy")))
    lines.append("")
    lines.append(section("Memory Notes", _v(fields, "memory_notes"), 3))
    lines.append("---\n")

    # Security & Compliance
    lines.append("## Security & Compliance\n")
    lines.append(kv("Authentication",    _v(fields, "authentication")))
    lines.append(kv("Authorisation Model", _v(fields, "authorisation_model")))
    lines.append(kv("Data Sensitivity", _v(fields, "data_sensitivity")))
    lines.append(kv("PII Handling",     _v(fields, "pii_handling")))
    lines.append(kv("Audit Logging",    _v(fields, "audit_logging")))
    lines.append(kv("Rate Limiting",    _v(fields, "rate_limiting")))
    lines.append("")
    lines.append("---\n")

    # Observability
    lines.append("## Observability\n")
    lines.append(kv("Logging Level",         _v(fields, "logging_level")))
    lines.append(kv("Tracing Enabled",       _v(fields, "tracing_enabled")))
    lines.append(kv("Health Check Endpoint", _v(fields, "health_check_endpoint")))
    lines.append("")
    lines.append(section("Metrics Exposed",    _v(fields, "metrics_exposed"),    3))
    lines.append(section("Alerting Thresholds", _v(fields, "alerting_thresholds"), 3))
    lines.append("---\n")

    # Deployment
    lines.append("## Deployment\n")
    lines.append(kv("Deployment Target", _v(fields, "deployment_target")))
    lines.append(kv("Container Image",   _v(fields, "container_image")))
    lines.append(kv("Runtime",           runtime))
    lines.append("")
    lines.append(section("Environment Variables", _v(fields, "environment_variables"), 3))
    lines.append(section("Resource Requirements", _v(fields, "resource_requirements"), 3))
    lines.append("---\n")

    # Testing & Evaluation
    lines.append("## Testing & Evaluation\n")
    lines.append(kv("Test Strategy", _v(fields, "test_strategy")))
    lines.append("")
    lines.append(section("Evaluation Metrics", _v(fields, "evaluation_metrics"), 3))
    lines.append(section("Test Cases",         _v(fields, "test_cases"),          3))
    lines.append(section("Known Limitations",  _v(fields, "known_limitations"),   3))

    return "\n".join(lines)
