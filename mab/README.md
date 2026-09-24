# Multi-Agent Builder (MAB)

> AI-assisted scaffolding and editing tool for multi-agent application architectures.

MAB gives you a three-panel GUI to go from a plain-English description of your application to a
fully structured, standards-compliant set of `agent.md` definition files — complete with an
interactive flow diagram of the entire agent network.

---

## Requirements

| Requirement | Minimum version |
|-------------|----------------|
| Python | 3.11 |
| pip | 23+ |
| OS | Windows 10 · macOS 12 · Ubuntu 22.04 |
| LLM API key | OpenAI **or** Anthropic **or** IBM watsonx.ai **or** Ollama (local, no key needed) |

---

## Quick start

### 1 — Clone / download

```bash
git clone <repo-url>
cd mab
```

### 2 — Create a virtual environment (recommended)

```bash
# Windows
py -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure your LLM credentials

Copy the example environment file and fill in the key for whichever provider you want to use:

```bash
cp .env.example .env
```

Open `.env` in any text editor:

```env
# Pick ONE provider and fill in its credentials

# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# IBM watsonx.ai
WATSONX_API_KEY=...
WATSONX_PROJECT_ID=...
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# Ollama (local — no key needed, just make sure Ollama is running)
# MAB_OLLAMA_BASE_URL=http://127.0.0.1:11434

# Which provider to use
MAB_LLM_PROVIDER=openai          # openai | anthropic | watsonx | ollama
MAB_LLM_MODEL=gpt-4o             # model id for the chosen provider
```

> ⚠️ Never commit `.env` to version control — it is already listed in `.gitignore`.

### 5 — Run

```bash
# Windows
py main.py

# macOS / Linux
python main.py
```

---

## Using the application

The interface is divided into three tabs across the top of the window.

---

### Tab 1 — ✨ Prompt

This is where every project starts.

1. **Project Name** — give your project a short slug-safe name (e.g. `customer_support_bot`).
2. **Output Directory** — where the project folder will be created (defaults to `./projects`).
3. **LLM Provider** — select the provider matching your `.env` credentials.
4. **Application Brief** — describe the application you want to build in plain English.
   The more detail you provide, the better the generated architecture will be.

   Example brief:
   > *"A customer support automation system that receives incoming tickets, classifies them
   > by urgency and topic, routes them to the appropriate specialist agent, drafts a response,
   > and logs the interaction for audit purposes."*

5. Click **✨ Generate Agent Architecture**.

The LLM will return a proposed list of agents — each with a name, role, type, inputs, outputs,
and communication relationships. Review the list, uncheck any agents you don't want, then click
**Create Project →**.

MAB writes the full folder structure to disk:

```
<output_dir>/<project_name>/
├── README.md
└── agents/
    ├── orchestrator/
    │   └── agent.md          ← pre-populated from your brief
    ├── classifier/
    │   └── agent.md
    └── ...
```

---

### Tab 2 — ✏️ Editor

The editor panel opens automatically after project creation.

**Left sidebar** — lists every agent in the project with a colour-coded completion percentage:
- 🔴 Red bar — < 30 % complete
- 🟡 Amber bar — 30–70 % complete
- 🟢 Green bar — > 70 % complete

Click any agent name to open it in the editor.

**Proforma form** — 10 collapsible sections covering every field in the industry-standard
`agent.md` specification:

| # | Section |
|---|---------|
| 1 | Identity & Purpose |
| 2 | Capabilities & Tools |
| 3 | Inputs & Outputs |
| 4 | Behaviour & Reasoning |
| 5 | Communication & Orchestration |
| 6 | Memory & State |
| 7 | Security & Compliance |
| 8 | Observability |
| 9 | Deployment |
| 10 | Testing & Evaluation |

Fields marked **\*** are required. Fields with a **✨** button support AI-assist — click it to
get a context-aware suggestion from your LLM. Suggestions appear in a popover and are never
applied without your explicit acceptance.

**Saving**
- Click **Save** in the toolbar to write the current agent back to its `agent.md` file.
- Click **Export All** in the sidebar to save every agent at once.

**Adding agents manually**
- Click **+ New Agent** in the sidebar, enter a `snake_case` name, and a blank template is
  created ready to fill in.

---

### Tab 3 — 🔀 Flow

The flow visualiser renders a live directed graph of the entire multi-agent system derived from
the `communicates_with` and `handoff_conditions` fields in every `agent.md` file.

**Node colours by agent type:**

| Colour | Type |
|--------|------|
| 🔵 Blue | Orchestrator |
| ⚫ Grey | Worker |
| 🟣 Purple | Specialist |
| 🟢 Green | Gateway |

**Toolbar controls:**

| Button | Action |
|--------|--------|
| ＋ | Zoom in |
| － | Zoom out |
| ⟳ | Reset zoom and pan |
| ⊞ | Toggle edge / node labels |
| 💾 | Export diagram as PNG |

Click and drag to pan. Use the mouse wheel to zoom.

The graph updates automatically when you save an agent. You can also click **⟳ Refresh**
manually.

---

## Opening an existing project

Use **File → Open Project** in the header menu bar and select the project root directory (the
folder that contains the `agents/` subdirectory). MAB will load all agents and open the editor.

---

## Project layout reference

```
<project_name>/
├── README.md                   ← auto-generated project overview
└── agents/
    └── <agent_name>/
        └── agent.md            ← full agent definition
```

Each `agent.md` follows the 10-section MAB standard. All sections use comment-tag placeholders
(`<!-- field_name -->`) in their initial state; the editor replaces these with your values.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `OPENAI_API_KEY is not set` | Make sure `.env` exists and is in the `mab/` directory |
| `LLM returned invalid JSON` | Try rephrasing the brief to be more specific; MAB retries twice automatically |
| `No 'agents/' directory found` | When opening a project, select the project **root** folder, not a subfolder |
| Graph not updating | Click **⟳ Refresh** on the Flow tab, or save an agent from the Editor tab |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside your active virtual environment |
| Ollama connection refused | Start Ollama with `ollama serve` and confirm `MAB_OLLAMA_BASE_URL` in `.env` |

---

## Security notes

- LLM API keys are loaded **only** from environment variables via `.env` — never hardcoded.
- `.env` is listed in `.gitignore` and will not be committed to version control.
- All generated project files remain local on your machine.
- No project content is sent to any external service beyond your configured LLM provider.
