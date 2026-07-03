# eg-subagents

A small, runnable example for developers learning how to build **dynamic sub-agents**
with [smolagents](https://github.com/huggingface/smolagents). Read this if you want to
see how a manager agent can delegate work to short-lived workers so that bulky context
(web pages, long computations) never bloats the manager.

Two patterns live side by side for learning:

| Pattern | Module | Demo | Behavior |
|---------|--------|------|----------|
| **Sync** | [`subagent.py`](subagent.py) | `make demo` | `spawn_subagent` blocks until the worker finishes |
| **Async** | [`async_subagent.py`](async_subagent.py) | `make demo-async` | Launch workers in background threads; poll status and output |

## Sync sub-agents

A **manager** agent holds exactly one tool: `spawn_subagent(task, tools)`. When it needs
web research or heavy math, it creates a worker, hands it a task and a list of tool names,
and gets back only the worker's final answer. Two guardrails keep this from running away:

- **No recursion** — manager-only tools are never in the worker tool registry.
- **Worker cap** — a configurable limit (default 6) on how many workers a single manager
  run may create.

```
        Manager (CodeAgent)
        tool: spawn_subagent
                 |
     spawn_subagent(task, tools=[...])   ← blocks until done
                 |
     +-----------+-----------+
     |                       |
 code worker            web worker
```

Sync workers run **sequentially** — each call blocks. smolagents does not parallelize tool
calls within a step either.

## Async sub-agents

The async pattern adds **background workers** the manager can fan out and monitor:

```
Manager
  ├─ launch_async_subagent(task, tools) → agent_name  (returns immediately)
  ├─ async_subagent_status(agent_name)                still_running?
  ├─ async_subagent_output_since_last_checked(...)    incremental log
  ├─ async_subagent_all_output(agent_name)            full log
  └─ kill_async_subagent(agent_name)                  best-effort stop
```

Workers run in **daemon threads** — launching several summarizers means several agents can
work at the same time while the manager polls and eventually synthesizes a report.

The async demo (`demo_async.py`) searches for articles on AI/cloud infrastructure and
renewable or low-carbon energy, launches one background sub-agent per URL to summarize
it, polls until all complete, then writes a combined report with citations. If a page is
blocked (for example a 403), the worker reports that failed source instead of the manager
spawning replacement workers.

Kill is best-effort: the manager sets a flag; the thread may still finish its current step.

## Testing status

| What | Status |
|------|--------|
| Imports, ruff lint | Verified |
| Forbidden-tool guard (workers cannot get manager tools) | Verified (unit-style, no API) |
| Sync worker cap | Verified (unit-style, no API) |
| Async launch / status / incremental output / kill (no API) | Verified (unit-style) |
| End-to-end `uv run python demo.py` with a live LLM | Verified with Anthropic Claude Haiku |
| End-to-end `uv run python demo_async.py` with a live LLM | Verified with Anthropic Claude Haiku; one source returned 403 and was reported cleanly |

## Setup

Requires Python 3.11+ and an Anthropic API key. Uses [uv](https://docs.astral.sh/uv/)
for dependencies (same toolchain pattern as zenkai backend).

```bash
cd eg-subagents
cp env.example .env   # then edit .env and set ANTHROPIC_API_KEY
make setup            # uv sync
```

If `make` is not installed, use `uv sync` and `uv run python demo.py` directly.

## Run

```bash
make demo        # sync: Fibonacci + web research via spawn_subagent
make demo-async  # async: web search + parallel URL summarizers + cited report
make native      # smolagents' built-in managed_agents, for contrast
make lint        # ruff format + check
make test        # offline integration tests with a scripted fake model
```

## How it works

| File | Role |
|------|------|
| [`tools_registry.py`](tools_registry.py) | Tool catalog keyed by name; `resolve()` validates and picks agent class; blocks manager-only tools. |
| [`web_tools.py`](web_tools.py) | `visit_webpage` and `html_to_markdown`, with page truncation. |
| [`subagent.py`](subagent.py) | Sync: `SubAgentManager` + `make_subagent_tool()`. |
| [`async_subagent.py`](async_subagent.py) | Async: `AsyncSubAgentManager` + launch/status/output/kill tools. |
| [`demo.py`](demo.py) | Sync composite task (Fibonacci + web research). |
| [`demo_async.py`](demo_async.py) | Async fan-out demo (search → parallel summaries → report). |
| [`native_multiagent.py`](native_multiagent.py) | Static `managed_agents` pattern for comparison. |

Requesting the `code` capability gives a worker a `CodeAgent` (analytical Python imports);
any other request gives a `ToolCallingAgent`.

Dependencies and dev tooling live in [`pyproject.toml`](pyproject.toml); the lockfile is
[`uv.lock`](uv.lock).

## Dynamic sub-agents vs. native managed_agents

smolagents' native pattern wires specialists up at init time as fixed roles — simpler and
a good fit when you know your team in advance. The dynamic tools here are better for
tinkering: the manager decides at runtime what each worker gets, under a cap.

## Tinker knobs

- `max_workers` in `build_manager()` / `build_async_manager()` — concurrent worker cap.
- `MAX_STEPS_BY_KIND` in [`subagent.py`](subagent.py) and [`async_subagent.py`](async_subagent.py).
- `MAX_PAGE_CHARS` in [`web_tools.py`](web_tools.py).
- `WEB_TOOLS` / `CODE_IMPORTS` in [`tools_registry.py`](tools_registry.py).

For production, run `CodeAgent` execution in a sandbox (smolagents supports E2B, Modal,
Docker). This demo executes locally for simplicity.
