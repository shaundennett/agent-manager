# BOB.md Compliance Plan

## Overview

A review of the Multi-Agent Builder (MAB) codebase against the requirements in `BOB.md`
found ten issues across five categories: Python version standards, missing tests, security
(error disclosure and dependency versions), engineering principles (duplicate code, missing
type hint), and documentation accuracy.

Each sub-task below is scoped to be implemented, reviewed, and merged independently.

---

## Sub-Task 1 — Upgrade Python version references from 3.11 to 3.12

**Status:** [ ] pending

**Intent**
BOB.md mandates Python 3.12+. Two source files and the README still default to "Python 3.11",
which means every scaffolded agent.md will record an incorrect runtime and the README
misrepresents the minimum requirement.

**Expected Outcomes**
- `mab/core/scaffold_engine.py` defaults `runtime` to `"Python 3.12"`.
- `mab/core/agent_parser.py` falls back to `"Python 3.12"` when no runtime is set.
- `mab/README.md` minimum Python row reads `3.12`.

**Todo List**
1. In `mab/core/scaffold_engine.py`, change the `"runtime": "Python 3.11"` substitution
   value to `"Python 3.12"`.
2. In `mab/core/agent_parser.py` `_build_content`, change the fallback
   `or "Python 3.11"` to `or "Python 3.12"`.
3. In `mab/README.md`, update the Requirements table Python minimum from `3.11` to `3.12`.

**Relevant Context**
- `mab/core/scaffold_engine.py:146` — `"runtime": "Python 3.11"`
- `mab/core/agent_parser.py:264` — `or "Python 3.11"`
- `mab/README.md` Requirements table

---

## Sub-Task 2 — Pin dependencies to latest secure versions

**Status:** [ ] pending

**Intent**
BOB.md requires the latest stable versions of all packages and explicitly prohibits EOL or
vulnerable packages. The current `requirements.txt` has `anthropic==0.28.0` (very outdated,
large security surface), `Pillow==10.3.0` (has known CVEs patched in 10.4+),
`networkx==3.3` and `matplotlib==3.9.0` (minor drift behind latest stable).

**Expected Outcomes**
- `requirements.txt` pins all four packages to their current latest stable versions.
- No installed package has a known unpatched CVE at the time of update.

**Todo List**
1. Check the current latest stable release of each affected package:
   `anthropic`, `Pillow`, `networkx`, `matplotlib`.
2. Update `mab/requirements.txt` with the new pinned versions.
3. Verify the application still starts and the existing manual smoke-test (open project,
   generate scaffold) passes after the upgrade.

**Relevant Context**
- `mab/requirements.txt`
- Affected packages: `anthropic==0.28.0`, `Pillow==10.3.0`, `networkx==3.3`,
  `matplotlib==3.9.0`

---

## Sub-Task 3 — Remove duplicate `load_dotenv()` call

**Status:** [ ] pending

**Intent**
BOB.md principle: "Do not duplicate logic." `main.py` already calls `load_dotenv` with the
correct path before anything else runs. The second bare `load_dotenv()` call at the top of
`ai_client.py` is redundant and can cause ordering ambiguity.

**Expected Outcomes**
- `load_dotenv()` is called exactly once, in `main.py`.
- `ai_client.py` no longer imports or calls `load_dotenv`.
- Behaviour is identical: env vars are available when `AIClient` is constructed.

**Todo List**
1. In `mab/core/ai_client.py`, remove the `from dotenv import load_dotenv` import and the
   `load_dotenv()` call on the lines immediately following it.

**Relevant Context**
- `mab/core/ai_client.py:15-17`
- `mab/main.py:26-28`

---

## Sub-Task 4 — Add type annotation to `_build_from_agent_data`

**Status:** [ ] pending

**Intent**
BOB.md requires type hints for all functions and methods. The `_build_from_agent_data`
function in `flow_analyser.py` suppresses mypy with a `# type: ignore` comment instead of
providing the correct annotation.

**Expected Outcomes**
- `_build_from_agent_data` has a properly typed parameter `agent_data_list: list[AgentData]`.
- The `# type: ignore[no-untyped-def]` comment is removed.

**Todo List**
1. Import `AgentData` from `core.agent_parser` inside the function (or at module top if no
   circular-import risk).
2. Change the signature to `def _build_from_agent_data(agent_data_list: list) -> FlowGraph:`
   using a quoted forward reference or a local import to avoid the circular dependency
   (`flow_analyser` -> `agent_parser`). A `TYPE_CHECKING` guard is the cleanest approach.
3. Remove the `# type: ignore[no-untyped-def]` comment.

**Relevant Context**
- `mab/core/flow_analyser.py:107`
- `mab/core/agent_parser.py` — `AgentData` class

---

## Sub-Task 5 — Harden error messages shown to the user

**Status:** [ ] pending

**Intent**
BOB.md security requirement: "Return generic error messages to clients; log details
server-side only." Currently, raw `str(exc)` values from LLM API errors and scaffold
failures are shown directly in `messagebox.showerror` dialogs and status labels, which can
leak internal paths, API response payloads, or provider error details.

**Expected Outcomes**
- All `messagebox.showerror` / status label calls triggered by caught exceptions show a
  short, generic message (e.g. "Generation failed — check the application log for details").
- Full exception detail is logged via `logger.exception(...)` only (server-side).
- User-visible error text contains no raw exception strings.

**Todo List**
1. In `mab/ui/panels/prompt_panel.py` `_run_generation`, replace `msg = str(exc)` passed to
   `_on_error` with a fixed generic string; ensure `logger.exception` is called in the
   except block.
2. In `mab/ui/panels/prompt_panel.py` `_on_confirm`, replace `messagebox.showerror("Scaffold Error", str(exc))`
   with a generic message; log the exception.
3. In `mab/ui/panels/prompt_panel.py` `_fetch_ollama_models`, replace `str(exc)` in the UI
   label with a fixed message like "Cannot reach Ollama — check MAB_OLLAMA_BASE_URL".
4. Review `mab/ui/panels/editor_panel.py` for any similar patterns and apply the same fix.

**Relevant Context**
- `mab/ui/panels/prompt_panel.py:261-269` — `_run_generation` / `_on_error`
- `mab/ui/panels/prompt_panel.py:394-396` — `_on_confirm` scaffold error
- `mab/ui/panels/prompt_panel.py:206-210` — `_fetch_ollama_models` error label

---

## Sub-Task 6 — Fix README Flow tab documentation

**Status:** [ ] pending

**Intent**
The README documents zoom, pan, label-toggle, and PNG-export controls for the Flow tab that
do not exist in the actual `FlowCanvas` implementation. Inaccurate documentation misleads
users and violates the "explicit behaviour" principle.

**Expected Outcomes**
- The "Tab 3 — Flow" section in `mab/README.md` accurately describes the real toolbar:
  Copy to clipboard, Save .mmd, Save .html.
- All references to zoom, pan, PNG export, and non-existent toolbar buttons are removed.

**Todo List**
1. In `mab/README.md`, rewrite the Tab 3 "Toolbar controls" table to list only the three
   real buttons: Copy (`⧉ Copy`), Save `.mmd` (`💾 Save .mmd`), Export HTML (`🌐 Save .html`).
2. Remove the paragraph about click-to-pan and mouse-wheel zoom (the canvas is a static
   text widget, not an interactive graph).
3. Keep the node colour legend — it is accurate.

**Relevant Context**
- `mab/README.md:179-202`
- `mab/ui/components/flow_canvas.py` — actual toolbar implementation

---

## Sub-Task 7 — Write pytest unit tests for all core modules

**Status:** [ ] pending

**Intent**
BOB.md: "All new logic must have unit tests (pytest)… Coverage of edge cases: empty input,
None, non-string types, malformed data." There are currently zero test files. The four core
modules contain pure-Python logic with no UI or LLM dependency and are directly testable.

**Expected Outcomes**
- A `mab/tests/` package is created with four test modules.
- `pytest` run from the `mab/` directory exits 0 with all tests passing.
- Each test module covers the happy path, edge cases (empty string, None-equivalent inputs,
  malformed/corrupt data), and adversarial inputs for security-sensitive parsing.

**Todo List**
1. Create `mab/tests/__init__.py`.
2. Create `mab/tests/test_agent_parser.py`:
   - `_parse_fields`: inline comment tags, block tags, bold-key lines, section bodies,
     TODO markers ignored, empty string, whitespace-only content.
   - `_build_content`: known fields produce expected markdown output; missing fields
     render `_Not yet defined._`.
   - `load` / `save` round-trip: save then reload produces identical fields.
   - `AgentData.completion_pct`: 0 fields → 0%, all fields set → 100%.
3. Create `mab/tests/test_scaffold_engine.py`:
   - `_slugify`: spaces, hyphens, special chars, empty string, uppercase.
   - `_populate_template`: all placeholders replaced; unknown keys left as TODO.
   - `create_project`: creates correct directory structure with tmp path (use `tmp_path`
     pytest fixture); README and agent.md files written.
   - `add_agent`: adds agent dir and file to existing project.
4. Create `mab/tests/test_flow_analyser.py`:
   - `_build_from_agent_data`: empty list → empty graph; single agent → 1 node, 0 edges;
     two communicating agents → 1 edge; unknown target → stub node created.
   - `generate_mermaid`: output starts with `flowchart TD`; node IDs are safe (no spaces);
     writes file when `output_path` is given.
5. Create `mab/tests/test_project_state.py`:
   - `save_state` writes valid JSON with `updated_at` timestamp.
   - `load_state` returns the saved dict.
   - `load_state` on missing file returns `{}`.
   - `load_state` on corrupt JSON returns `{}` without raising.
6. Add `pytest` to `mab/requirements.txt` (or a separate `requirements-dev.txt`).

**Relevant Context**
- `mab/core/agent_parser.py` — `_parse_fields`, `_build_content`, `load`, `save`, `AgentData`
- `mab/core/scaffold_engine.py` — `_slugify`, `_populate_template`, `create_project`, `add_agent`
- `mab/core/flow_analyser.py` — `_build_from_agent_data`, `generate_mermaid`
- `mab/core/project_state.py` — `save_state`, `load_state`
- `mab/templates/agent_template.md` — used by scaffold engine tests
