"""
core/ai_client.py
─────────────────
LLM abstraction layer supporting OpenAI, Anthropic, IBM watsonx.ai, and Ollama.
All credentials are sourced exclusively from environment variables.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Provider constants ────────────────────────────────────────────────────────
OPENAI = "openai"
ANTHROPIC = "anthropic"
WATSONX = "watsonx"
OLLAMA = "ollama"

SYSTEM_ARCHITECT_PROMPT = (
    "You are an expert multi-agent system architect. "
    "Return ONLY valid JSON — no markdown fences, no prose."
)

SCAFFOLD_SCHEMA = {
    "project_name": "string",
    "project_summary": "string",
    "agents": [
        {
            "name": "string (snake_case)",
            "role": "string (one sentence)",
            "primary_responsibility": "string",
            "inputs": ["string"],
            "outputs": ["string"],
            "tools": ["string"],
            "communicates_with": ["string"],
            "trigger": "user | agent | schedule | event",
            "position_hint": "orchestrator | worker | specialist | gateway",
        }
    ],
}

FIELD_ASSIST_SYSTEM = (
    "You are an expert multi-agent system architect helping a developer fill in "
    "agent definition fields. Return ONLY the requested field value as plain text "
    "— no JSON wrapper, no markdown fences, no explanation."
)

RULES_SYSTEM = (
    "You are an expert software engineering lead. "
    "Generate a concise, structured BOB.md / CLAUDE.md style rules file for the "
    "project described by the user. "
    "The file must cover: coding standards, security requirements, testing requirements, "
    "architecture principles, and any domain-specific constraints implied by the description. "
    "Return ONLY plain markdown — no prose introduction, no code fences wrapping the whole output."
)


class AIClient:
    """Unified LLM client. Provider is resolved at construction time."""

    def __init__(self) -> None:
        self.provider: str = os.environ.get("MAB_LLM_PROVIDER", OPENAI).lower()
        self.model: str = os.environ.get("MAB_LLM_MODEL", "gpt-4o")
        self._client: Any = None
        self._init_client()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_client(self) -> None:
        if self.provider == OPENAI:
            from openai import OpenAI  # type: ignore[import-untyped]
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY is not set.")
            self._client = OpenAI(api_key=api_key)

        elif self.provider == ANTHROPIC:
            from anthropic import Anthropic  # type: ignore[import-untyped]
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
            self._client = Anthropic(api_key=api_key)

        elif self.provider == WATSONX:
            from ibm_watsonx_ai import APIClient, Credentials  # type: ignore[import-untyped]
            api_key = os.environ.get("WATSONX_API_KEY", "")
            url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
            if not api_key:
                raise EnvironmentError("WATSONX_API_KEY is not set.")
            credentials = Credentials(url=url, api_key=api_key)
            self._client = APIClient(credentials)
            self._wx_project_id = os.environ.get("WATSONX_PROJECT_ID", "")

        elif self.provider == OLLAMA:
            # Uses the OpenAI-compatible local endpoint
            from openai import OpenAI  # type: ignore[import-untyped]
            base_url = os.environ.get("MAB_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            self._client = OpenAI(
                base_url=f"{base_url}/v1",
                api_key="ollama",  # Ollama ignores the key value
            )
        else:
            raise ValueError(f"Unknown LLM provider: '{self.provider}'")

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_scaffold(self, project_description: str) -> dict:
        """
        Send the project description to the LLM and parse the returned JSON
        scaffold definition. Retries up to 2 times on malformed JSON.
        """
        user_prompt = (
            f"The user wants to build the following application:\n\n"
            f"{project_description}\n\n"
            f"Return a JSON object that strictly conforms to this schema:\n"
            f"{json.dumps(SCAFFOLD_SCHEMA, indent=2)}\n\n"
            f"Identify every distinct agent needed. Use snake_case names."
        )
        raw = self._chat(SYSTEM_ARCHITECT_PROMPT, user_prompt, retries=2)
        return self._parse_json(raw)

    def generate_project_rules(self, project_description: str) -> str:
        """
        Ask the LLM to produce a BOB.md-style rules file for the project.
        Returns the raw markdown string.
        """
        user_prompt = (
            f"Project description:\n\n{project_description}\n\n"
            "Write a complete BOB.md rules file for this project. "
            "Be specific and actionable. Use markdown headings and bullet lists."
        )
        return self._chat(RULES_SYSTEM, user_prompt, retries=1).strip()

    def assist_field(
        self,
        field_name: str,
        agent_context: dict,
        project_summary: str,
        other_agents: list[dict],
    ) -> str:
        """
        Suggest a value for a single agent.md field based on surrounding context.
        Returns the suggestion as a plain string.
        """
        context_str = json.dumps(agent_context, indent=2)
        peers_str = json.dumps(
            [{"name": a.get("name"), "role": a.get("role")} for a in other_agents],
            indent=2,
        )
        user_prompt = (
            f"Project summary: {project_summary}\n\n"
            f"Current agent context:\n{context_str}\n\n"
            f"Other agents in the project:\n{peers_str}\n\n"
            f"Suggest a concise, appropriate value for the field: `{field_name}`.\n"
            f"Return ONLY the value — no labels, no JSON, no markdown."
        )
        return self._chat(FIELD_ASSIST_SYSTEM, user_prompt, retries=1).strip()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _chat(self, system: str, user: str, retries: int = 1) -> str:
        """Send a chat completion and return the raw text response."""
        for attempt in range(retries + 1):
            try:
                if self.provider in (OPENAI, OLLAMA):
                    response = self._client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=0.3,
                    )
                    return response.choices[0].message.content or ""

                elif self.provider == ANTHROPIC:
                    response = self._client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        system=system,
                        messages=[{"role": "user", "content": user}],
                    )
                    return response.content[0].text or ""

                elif self.provider == WATSONX:
                    from ibm_watsonx_ai.foundation_models import ModelInference  # type: ignore[import-untyped]
                    model = ModelInference(
                        model_id=self.model,
                        api_client=self._client,
                        project_id=self._wx_project_id,
                    )
                    prompt = f"{system}\n\n{user}"
                    result = model.generate_text(prompt=prompt)
                    return result or ""

            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM attempt %d/%d failed: %s", attempt + 1, retries + 1, exc)
                if attempt == retries:
                    raise
        return ""

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Strip optional markdown fences and parse JSON. Raises ValueError on failure."""
        text = raw.strip()
        # Strip ```json ... ``` fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                line for line in lines if not line.startswith("```")
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}\n\nRaw:\n{raw}") from exc
