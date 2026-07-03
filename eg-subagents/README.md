# eg-subagents

A small, runnable example for developers learning how to build **dynamic sub-agents**
with [smolagents](https://github.com/huggingface/smolagents). Read this if you want to
see how a manager agent can delegate work to short-lived workers so that bulky context
(web pages, long computations) never bloats the manager.

## The idea

A **manager** agent holds exactly one tool: `spawn_subagent(task, tools)`. When it needs
web research or heavy math, it creates a worker, hands it a task and a list of tool names,
and gets back only the worker's final answer. Two guardrails keep this from running away:

- **No recursion** — `spawn_subagent` is never in the tool registry, so a worker cannot
  create its own children.
- **Worker cap** — a configurable limit (default 6) on how many workers a single manager
  run may create.

```
        Manager (CodeAgent)
        tool: spawn_subagent
                 |
     spawn_subagent(task, tools=[...])
                 |
     +-----------+-----------+
     |                       |
 code worker            web worker
 (CodeAgent)         (ToolCallingAgent)
 math/analysis       web_search + visit_webpage
```

## Setup

Requires Python 3.11+ and an Anthropic API key. Uses [uv](https://docs.astral.sh/uv/)
for dependencies (same toolchain pattern as [zenkai](https://github.com/) backend).

```bash
cd eg-subagents
cp env.example .env   # then edit .env and set ANTHROPIC_API_KEY
make setup            # uv sync
```

## Run

```bash
make demo     # dynamic sub-agent demo (Fibonacci + web research)
make native   # smolagents' built-in managed_agents, for contrast
make lint     # ruff format + check
```

## How it works

| File | Role |
|------|------|
| [`tools_registry.py`](tools_registry.py) | The catalog of capabilities workers can be granted, keyed by string name. `resolve()` validates requested names, rejects `spawn_subagent`, and picks the worker's agent class. |
| [`web_tools.py`](web_tools.py) | `visit_webpage` and `html_to_markdown`, with page-length truncation so a worker's context stays bounded. |
| [`subagent.py`](subagent.py) | `SubAgentManager` (holds the model and the worker counter) and `make_subagent_tool()` (the `@tool` the manager calls). |
| [`demo.py`](demo.py) | Builds the manager and runs a composite task that needs both a code worker and a web worker. |
| [`native_multiagent.py`](native_multiagent.py) | The static `managed_agents` pattern, for comparison. |

Requesting the `code` capability gives a worker a `CodeAgent` that can run Python
(analytical imports only); any other request gives a `ToolCallingAgent`.

Dependencies and dev tooling live in [`pyproject.toml`](pyproject.toml); the lockfile is
[`uv.lock`](uv.lock).

## Dynamic sub-agents vs. native managed_agents

smolagents' native pattern wires specialists up at init time as fixed roles — simpler and
a good fit when you know your team in advance. The dynamic `spawn_subagent` tool here is
better for tinkering: the manager decides at runtime what mix of tools each worker gets,
under a cap.

## Tinker knobs

- `max_workers` in [`demo.py`](demo.py) `build_manager()` — the worker cap.
- `MAX_STEPS_BY_KIND` in [`subagent.py`](subagent.py) — how many steps each worker type gets.
- `MAX_PAGE_CHARS` in [`web_tools.py`](web_tools.py) — page truncation limit.
- `WEB_TOOLS` / `CODE_IMPORTS` in [`tools_registry.py`](tools_registry.py) — add capabilities.

For production, run `CodeAgent` execution in a sandbox (smolagents supports E2B, Modal,
Docker). This demo executes locally for simplicity.
