"""The sub-agent tool: the manager's only way to delegate work.

Each call builds a fresh, short-lived agent with its own memory and only the
requested tools. The manager receives just the worker's final answer, so page
content and intermediate reasoning stay out of the manager's context.
"""

import logging

from smolagents import CodeAgent, tool

from tools_registry import UnknownToolError, resolve

logger = logging.getLogger(__name__)

# Sub-agents get more steps than a trivial task needs; web research in particular
# may take several fetches before it can answer.
MAX_STEPS_BY_KIND = {"code": 8, "web": 10}


class SubAgentManager:
    """Creates sub-agents on demand under a per-run worker cap."""

    def __init__(self, model, max_workers: int = 6):
        self.model = model
        self.max_workers = max_workers
        self.subagent_count = 0

    def run(self, task: str, tools: list[str]) -> str:
        if self.subagent_count >= self.max_workers:
            logger.warning("worker limit hit at %d", self.max_workers)
            return (
                f"Worker limit reached ({self.max_workers} sub-agents already created). "
                "Finish the task with the results you already have."
            )

        try:
            agent_class, tool_objects, extra_imports = resolve(tools)
        except UnknownToolError as e:
            return f"Could not create sub-agent: {e}"

        kind = "code" if agent_class is CodeAgent else "web"
        kwargs = {
            "tools": tool_objects,
            "model": self.model,
            "add_base_tools": False,
            "max_steps": MAX_STEPS_BY_KIND[kind],
        }
        if agent_class is CodeAgent:
            kwargs["additional_authorized_imports"] = extra_imports

        self.subagent_count += 1
        logger.info("subagent #%d kind=%s tools=%s", self.subagent_count, kind, tools)
        agent = agent_class(**kwargs)
        return str(agent.run(task))


def make_subagent_tool(subagent_manager: SubAgentManager):
    """Return a @tool bound to the given manager for use by a manager agent."""

    @tool
    def spawn_subagent(task: str, tools: list[str]) -> str:
        """Delegate a self-contained task to a short-lived sub-agent.

        The sub-agent has its own isolated context and returns only its final
        answer, so use this to keep bulky work (web pages, long computations) out
        of your own context. Available tool names: web_search, visit_webpage,
        html_to_markdown, code. Use "code" for math or analytical work; use
        web_search and visit_webpage together for research. Sub-agents cannot
        spawn their own sub-agents.

        Args:
            task: A complete, self-contained description of what the sub-agent
                should do and what to return.
            tools: Names of the capabilities to grant the sub-agent.

        Returns:
            The sub-agent's final answer, or an error string if it could not run.
        """
        return subagent_manager.run(task, tools)

    return spawn_subagent
