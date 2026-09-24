# Agent: Multi-Agent Builder (MAB)

## Overview

**Name:** Multi-Agent Builder (MAB)
**Version:** 1.0.0
**Type:** Developer Tooling Agent
**Runtime:** Python 3.11+
**Interface:** Desktop GUI (Tkinter + CustomTkinter) or Web UI (Streamlit)

Multi-Agent Builder is an AI-assisted developer tool that simplifies, accelerates, and manages the
creation of multi-agent application architectures. It provides a guided, visual workflow from an
initial natural-language prompt through to a fully structured, standards-compliant set of
`agent.md` definition files, with a live end-to-end agentic flow visualiser.

---

## Purpose and Goals

| Goal | Description |
|------|-------------|
| **Accelerate** | Reduce the time to scaffold a multi-agent system from hours to minutes |
| **Standardise** | Enforce industry-standard `agent.md` structure across every agent in the project |
| **Guide** | Walk developers through every required section with contextual help and AI suggestions |
| **Visualise** | Render a live, interactive flow diagram of the complete agentic system based on the authored definitions |

---

## Architecture

### High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Multi-Agent Builder (MAB)                      │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  1. AI Prompt    │   │  2. Agent Editor │   │  3. Flow View  │  │
│  │     Panel        │──▶│     Panel        │──▶│    Panel       │  │
│  │                  │   │                  │   │                │  │
│  │ Natural language │   │ Select agent +   │   │ Live directed  │  │
│  │ → project brief  │   │ fill proforma    │   │ graph of all   │  │
│  │ → file scaffold  │   │ template         │   │ agents & flows │  │
│  └──────────────────┘   └──────────────────┘   └────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
mab/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── .gitignore
│
├── core/
│   ├── __init__.py
│   ├── ai_client.py           # LLM API client (abstraction layer)
│   ├── scaffold_engine.py     # Project + file structure generator
│   ├── agent_parser.py        # agent.md reader/writer
│   └── flow_analyser.py       # Extracts graph nodes/edges from agent.md files
│
├── ui/
│   ├── __init__.py
│   ├── app.py                 # Root UI controller
│   ├── panels/
│   │   ├── prompt_panel.py    # Panel 1 — AI Prompt
│   │   ├── editor_panel.py    # Panel 2 — Agent Editor
│   │   └── flow_panel.py      # Panel 3 — Flow Visualiser
│   └── components/
│       ├── agent_list.py      # Sidebar agent selector
│       ├── proforma_form.py   # Structured agent.md form
│       └── flow_canvas.py     # Graph renderer
│
├── templates/
│   ├── agent_template.md      # Master proforma agent.md template
│   └── project_readme.md      # Auto-generated project README template
│
└── projects/                  # User-created project workspaces (runtime)
    └── <project-name>/
        ├── README.md
        └── agents/
            └── <agent-name>/
                └── agent.md
```

---

## Panel 1 — AI Prompt Panel

### Responsibility

Provide an initial full-screen prompt interface where the user describes the overall purpose of the
multi-agent application they intend to build. The AI analyses this description and generates:

1. A recommended set of agents with names, roles, and brief descriptions
2. The initial file and folder scaffold for the project
3. Pre-populated metadata in each generated `agent.md` template

### Inputs

| Field | Type | Description |
|-------|------|-------------|
| `project_name` | Text | Slug-safe project name |
| `project_description` | Textarea | Free-text natural language brief (required) |
| `output_directory` | Path picker | Where the project folder should be created |
| `llm_provider` | Dropdown | OpenAI / Anthropic / IBM watsonx / Ollama (local) |

### AI Behaviour

**Prompt sent to LLM:**
```
You are an expert multi-agent system architect. The user will describe a software application
they want to build using a multi-agent architecture.

Your task:
1. Identify all distinct agents required to fulfil this application's purpose.
2. For each agent provide: name (snake_case), role (one sentence), primary_responsibility,
   inputs, outputs, tools_required, and which other agents it communicates with.
3. Return ONLY valid JSON conforming to the schema below. No prose.

Schema:
{
  "project_name": "string",
  "project_summary": "string",
  "agents": [
    {
      "name": "string",
      "role": "string",
      "primary_responsibility": "string",
      "inputs": ["string"],
      "outputs": ["string"],
      "tools": ["string"],
      "communicates_with": ["string"],
      "trigger": "user | agent | schedule | event",
      "position_hint": "orchestrator | worker | specialist | gateway"
    }
  ]
}
```

**On receipt of LLM response:**
- Parse and validate JSON
- Display a proposed agent list with checkboxes (user may add/remove agents before confirming)
- On confirmation, call `scaffold_engine.create_project()` to write the file structure
- Transition to Panel 2 with the first agent pre-selected

### Scaffold Engine Specification

`scaffold_engine.create_project(project_name, output_dir, agents: list[AgentSpec])`:

1. Creates `<output_dir>/<project_name>/` directory
2. Writes `README.md` from `templates/project_readme.md` with project metadata substituted
3. For each agent in `agents`:
   - Creates `agents/<agent.name>/agent.md` from `templates/agent_template.md`
   - Pre-populates all fields derivable from the LLM response (name, role, inputs, outputs, etc.)
   - Marks all remaining required fields with the placeholder `<!-- TODO: complete this section -->`
4. Logs scaffolding summary to the UI status bar

---

## Panel 2 — Agent Editor Panel

### Responsibility

Allow the user to select any agent from the project and complete its `agent.md` file using a
structured proforma form. The form reflects every section of the industry-standard `agent.md`
specification. Each field carries inline guidance text. The AI can be invoked per-field to suggest
content based on the agent's context.

### Layout

```
┌────────────────┬────────────────────────────────────────────────────┐
│ Agent Sidebar  │  Proforma Editor                                   │
│                │                                                    │
│ [+] New Agent  │  ┌──────────────────────────────────────────────┐  │
│                │  │ Section: Identity & Purpose                  │  │
│ ○ orchestrator │  │  • Name          [________________]          │  │
│ ○ data_agent   │  │  • Version       [________________]          │  │
│ ● planner      │  │  • Role          [________________]          │  │
│ ○ reviewer     │  │  • Description   [__________________]        │  │
│ ○ executor     │  │                  [__________________]        │  │
│                │  ├──────────────────────────────────────────────┤  │
│ Completion:    │  │ Section: Capabilities & Tools                │  │
│ [████░░] 67%   │  │  ...                                         │  │
│                │  └──────────────────────────────────────────────┘  │
│ [Export All]   │                                    [✨ AI Assist]  │
└────────────────┴────────────────────────────────────────────────────┘
```

### Agent Sidebar

- Lists all agents in the current project
- Visual completion indicator per agent (% of required fields filled)
- "New Agent" button — opens a mini-dialog to name and add an agent manually
- "Export All" — writes all in-memory form state back to `agent.md` files on disk

### Proforma Form Sections

The proforma mirrors the full `agent.md` standard. Each section is a collapsible accordion panel.
Required fields are marked `*`. Fields with AI-assist get a ✨ button.

#### Section 1 — Identity & Purpose
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `name` | Text | ✅ | ❌ |
| `version` | Text (semver) | ✅ | ❌ |
| `type` | Dropdown (orchestrator/worker/specialist/gateway/hybrid) | ✅ | ✅ |
| `role` | Short text (≤ 100 chars) | ✅ | ✅ |
| `description` | Textarea | ✅ | ✅ |
| `goals` | Bullet list editor | ✅ | ✅ |
| `non_goals` | Bullet list editor | ❌ | ✅ |

#### Section 2 — Capabilities & Tools
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `capabilities` | Multi-line bullet list | ✅ | ✅ |
| `tools` | Tag editor (with tool name + description) | ✅ | ✅ |
| `external_apis` | Key-value list (name, endpoint, auth_type) | ❌ | ❌ |
| `knowledge_sources` | Bullet list | ❌ | ✅ |

#### Section 3 — Inputs & Outputs
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `inputs` | Structured list (name, type, description, required) | ✅ | ✅ |
| `outputs` | Structured list (name, type, description) | ✅ | ✅ |
| `input_format` | Dropdown (JSON/text/structured/binary) | ✅ | ❌ |
| `output_format` | Dropdown | ✅ | ❌ |

#### Section 4 — Behaviour & Reasoning
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `reasoning_strategy` | Dropdown (ReAct/CoT/Plan-Execute/Reflexion/Custom) | ✅ | ✅ |
| `decision_logic` | Textarea | ✅ | ✅ |
| `fallback_behaviour` | Textarea | ✅ | ✅ |
| `max_iterations` | Number | ❌ | ❌ |
| `timeout_seconds` | Number | ❌ | ❌ |
| `retry_policy` | Dropdown (none/fixed/exponential) | ❌ | ❌ |

#### Section 5 — Communication & Orchestration
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `trigger` | Dropdown (user/agent/schedule/event/webhook) | ✅ | ❌ |
| `communicates_with` | Multi-select (from project agent list) | ✅ | ✅ |
| `communication_protocol` | Dropdown (direct-call/message-queue/REST/gRPC/event-bus) | ✅ | ✅ |
| `upstream_agents` | Auto-derived (read-only, from `communicates_with` graph) | — | — |
| `downstream_agents` | Auto-derived | — | — |
| `handoff_conditions` | Key-value list (condition → target_agent) | ✅ | ✅ |

#### Section 6 — Memory & State
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `memory_type` | Dropdown (none/in-context/vector-store/database/hybrid) | ✅ | ✅ |
| `state_persistence` | Toggle | ✅ | ❌ |
| `context_window_strategy` | Dropdown (full/summarise/sliding/retrieval) | ❌ | ✅ |
| `memory_notes` | Textarea | ❌ | ✅ |

#### Section 7 — Security & Compliance
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `authentication` | Dropdown (none/API-key/OAuth2/OIDC/mTLS) | ✅ | ❌ |
| `authorisation_model` | Dropdown (none/RBAC/ABAC/policy-engine) | ✅ | ❌ |
| `data_sensitivity` | Dropdown (public/internal/confidential/restricted) | ✅ | ❌ |
| `pii_handling` | Toggle + description | ✅ | ✅ |
| `audit_logging` | Toggle | ✅ | ❌ |
| `rate_limiting` | Text (e.g., "100 req/min") | ❌ | ❌ |

#### Section 8 — Observability
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `logging_level` | Dropdown (DEBUG/INFO/WARN/ERROR) | ✅ | ❌ |
| `metrics_exposed` | Bullet list | ❌ | ✅ |
| `tracing_enabled` | Toggle | ✅ | ❌ |
| `health_check_endpoint` | Text | ❌ | ❌ |
| `alerting_thresholds` | Key-value list | ❌ | ✅ |

#### Section 9 — Deployment
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `runtime` | Text (e.g., Python 3.11) | ✅ | ❌ |
| `deployment_target` | Dropdown (local/container/k8s/serverless/cloud) | ✅ | ❌ |
| `container_image` | Text | ❌ | ❌ |
| `environment_variables` | Key-value list (name, description, secret: bool) | ✅ | ✅ |
| `resource_requirements` | Key-value (cpu, memory, gpu) | ❌ | ❌ |

#### Section 10 — Testing & Evaluation
| Field | Type | Required | AI-assist |
|-------|------|----------|-----------|
| `test_strategy` | Textarea | ✅ | ✅ |
| `evaluation_metrics` | Bullet list | ✅ | ✅ |
| `test_cases` | Structured list (scenario, input, expected_output) | ❌ | ✅ |
| `known_limitations` | Textarea | ✅ | ✅ |

### AI Assist Behaviour (per field)

When the user clicks ✨ on a field:
1. Collect all already-completed fields for the current agent as context
2. Collect the project description and other agents' names/roles for wider context
3. Call LLM with a focused prompt: "Suggest a value for the `{field_name}` field of agent `{agent_name}` given the following context: ..."
4. Display suggestion in a popover — user accepts (inserts into field), edits, or dismisses
5. Never overwrite field content without explicit user acceptance

---

## Panel 3 — Flow Visualiser

### Responsibility

Render a live, read-only directed graph of the entire multi-agent system, derived purely from the
information already captured in the `agent.md` files. The graph auto-updates whenever an agent
definition is saved.

### Graph Construction (`flow_analyser.py`)

1. Load all `agent.md` files from the current project's `agents/` directory
2. For each agent, extract:
   - Node: `name`, `role`, `type`, `trigger`, `completion_pct`
   - Edges: `communicates_with` → directed edges with `handoff_conditions` as edge labels
3. Build a `networkx.DiGraph` (or equivalent) in memory
4. Classify node shapes by `position_hint`:
   - `orchestrator` → rounded rectangle (blue)
   - `worker` → rectangle (grey)
   - `specialist` → diamond (purple)
   - `gateway` → hexagon (green — entry/exit points)
5. Colour edges by communication protocol type

### Rendering

- **Library:** `matplotlib` + `networkx` (embedded in Tkinter canvas) **or** `pyvis` / `streamlit-agraph` (for Streamlit variant)
- **Layout algorithm:** Hierarchical (top-down) using `graphviz` `dot` layout, falling back to `spring_layout`
- Node tooltip on hover: name, role, trigger, completion %
- Edge tooltip on hover: protocol, handoff conditions
- Controls: zoom in/out, pan, reset, PNG export, toggle edge labels

### Visual Legend

```
  ╔══════════╗   Orchestrator     ──────▶  Direct call
  ║          ║
  ╚══════════╝

  ┌──────────┐   Worker          - - - -▶  Message queue
  │          │
  └──────────┘

  ◇──────────◇   Specialist      ════════▶  Event bus
  
  ⬡──────────⬡   Gateway
```

---

## Agent Template (`templates/agent_template.md`)

```markdown
# Agent: <!-- name -->

## Overview

**Name:** <!-- name -->
**Version:** <!-- version -->
**Type:** <!-- type: orchestrator | worker | specialist | gateway | hybrid -->
**Role:** <!-- role: one-sentence summary -->
**Runtime:** <!-- runtime -->

## Description

<!-- description: detailed purpose of this agent -->

## Goals

<!-- goals: bullet list of what this agent must achieve -->

## Non-Goals

<!-- non_goals: bullet list of what this agent explicitly does not do -->

---

## Capabilities & Tools

### Capabilities
<!-- capabilities: bullet list -->

### Tools
<!-- tools: list of tool name + description pairs -->

### External APIs
<!-- external_apis: list of name, endpoint, auth_type -->

---

## Inputs & Outputs

### Inputs
<!-- inputs: structured list — name, type, description, required -->

### Outputs
<!-- outputs: structured list — name, type, description -->

**Input Format:** <!-- input_format -->
**Output Format:** <!-- output_format -->

---

## Behaviour & Reasoning

**Reasoning Strategy:** <!-- reasoning_strategy -->

### Decision Logic
<!-- decision_logic -->

### Fallback Behaviour
<!-- fallback_behaviour -->

**Max Iterations:** <!-- max_iterations -->
**Timeout (s):** <!-- timeout_seconds -->
**Retry Policy:** <!-- retry_policy -->

---

## Communication & Orchestration

**Trigger:** <!-- trigger -->
**Communicates With:** <!-- communicates_with: comma-separated agent names -->
**Communication Protocol:** <!-- communication_protocol -->

### Handoff Conditions
<!-- handoff_conditions: condition → target_agent pairs -->

---

## Memory & State

**Memory Type:** <!-- memory_type -->
**State Persistence:** <!-- state_persistence: true | false -->
**Context Window Strategy:** <!-- context_window_strategy -->

<!-- memory_notes -->

---

## Security & Compliance

**Authentication:** <!-- authentication -->
**Authorisation Model:** <!-- authorisation_model -->
**Data Sensitivity:** <!-- data_sensitivity -->
**PII Handling:** <!-- pii_handling: true | false — description -->
**Audit Logging:** <!-- audit_logging: true | false -->
**Rate Limiting:** <!-- rate_limiting -->

---

## Observability

**Logging Level:** <!-- logging_level -->
**Tracing Enabled:** <!-- tracing_enabled: true | false -->
**Health Check Endpoint:** <!-- health_check_endpoint -->

### Metrics Exposed
<!-- metrics_exposed: bullet list -->

### Alerting Thresholds
<!-- alerting_thresholds: key-value pairs -->

---

## Deployment

**Deployment Target:** <!-- deployment_target -->
**Container Image:** <!-- container_image -->

### Environment Variables
<!-- environment_variables: name, description, secret: true|false -->

### Resource Requirements
<!-- resource_requirements: cpu, memory, gpu -->

---

## Testing & Evaluation

**Test Strategy:** <!-- test_strategy -->

### Evaluation Metrics
<!-- evaluation_metrics: bullet list -->

### Test Cases
<!-- test_cases: scenario, input, expected_output -->

### Known Limitations
<!-- known_limitations -->
```

---

## Dependencies

```
# requirements.txt
customtkinter>=5.2.2         # Modern Tkinter UI widgets
openai>=1.30.0               # OpenAI API client
anthropic>=0.25.0            # Anthropic Claude client
ibm-watsonx-ai>=1.0.10       # IBM watsonx.ai client
networkx>=3.3                # Graph construction
matplotlib>=3.9.0            # Graph rendering (embedded canvas)
pyvis>=0.3.2                 # Interactive HTML graph export
python-dotenv>=1.0.1         # Environment variable management
pyyaml>=6.0.1                # YAML config handling
Pillow>=10.3.0               # Image handling for canvas export
```

---

## Configuration

All configuration is managed via environment variables. No secrets are ever hardcoded.

```env
# .env  (not committed — listed in .gitignore)

# LLM Provider (choose one)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_URL=

# Application
MAB_DEFAULT_OUTPUT_DIR=./projects
MAB_LLM_PROVIDER=openai           # openai | anthropic | watsonx | ollama
MAB_LLM_MODEL=gpt-4o              # model identifier for chosen provider
MAB_LOG_LEVEL=INFO
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| API key exposure | Loaded exclusively from environment variables via `python-dotenv`; never logged or displayed |
| Generated file paths | All paths sanitised with `pathlib.Path` and restricted to the configured output directory |
| LLM response injection | JSON schema validation applied to all LLM responses before use; raw LLM output never executed |
| Dependency vulnerabilities | `requirements.txt` pinned to latest stable versions; Mend scanning recommended in CI |
| Sensitive project content | All project files remain local; no content is sent to external services beyond the configured LLM provider |

---

## Error Handling

| Error Scenario | Behaviour |
|----------------|-----------|
| LLM API unreachable | Display user-friendly error in prompt panel; offer retry or offline mode |
| LLM returns malformed JSON | Re-prompt with explicit schema reminder (up to 2 retries); show raw response for manual review on final failure |
| File system permission denied | Surface error with the exact path and suggested fix; do not crash |
| Invalid `agent.md` on parse | Skip and log; mark agent as "parse error" in sidebar with red indicator |
| Missing required fields on export | Highlight incomplete fields; warn user but allow forced export |

---

## Development Roadmap

| Phase | Feature | Priority |
|-------|---------|----------|
| v1.0 | AI prompt → scaffold, proforma editor, static flow graph | P0 |
| v1.1 | Per-field AI assist, agent completion tracking | P0 |
| v1.2 | Interactive flow graph (click-to-edit from graph) | P1 |
| v1.3 | Export to LangGraph / AutoGen / CrewAI boilerplate code | P1 |
| v2.0 | Collaborative multi-user editing, Git integration | P2 |
| v2.1 | Agent simulation / dry-run mode | P2 |

---

## Acceptance Criteria

- [ ] User can describe an application in natural language and receive a proposed agent list within 10 seconds
- [ ] Scaffold generates a valid, navigable folder structure with one `agent.md` per agent
- [ ] All 10 proforma sections are accessible in the editor for any selected agent
- [ ] AI-assist suggestions are contextually relevant and can be accepted/rejected per field
- [ ] Completion percentage updates in real time as fields are filled
- [ ] Flow visualiser renders a directed graph with correct edges within 2 seconds of saving an agent
- [ ] All API keys are sourced from environment variables and never persisted to disk by the application
- [ ] Application runs on Windows 10+, macOS 12+, and Ubuntu 22.04+ with Python 3.11+
