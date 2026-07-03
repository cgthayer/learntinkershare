"""Async sub-agent demo: web search, parallel URL summarizers, combined report.

The manager searches for articles, launches one background sub-agent per URL to
summarize it, polls until all finish, then writes a cited synthesis.

Run: make demo-async  (after setting ANTHROPIC_API_KEY in .env)
"""

import logging

from smolagents import CodeAgent, WebSearchTool

from async_subagent import AsyncSubAgentManager, make_async_subagent_tools
from demo import build_model

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)

ASYNC_TASK = """Research how major cloud providers power AI or large language model
infrastructure with renewable or low-carbon energy.

Workflow — follow these steps in order:
1. Use web_search once to find 3 relevant article or report URLs (diverse sources).
2. For EACH of those 3 URLs, call launch_async_subagent with tools=["visit_webpage"] and a task
   like: "Visit <URL> and write a 3-5 sentence summary focused on renewable energy
   and LLM/cloud training. Include the URL at the top."
   Give each worker a distinct agent_name (e.g. url-1, url-2, ...).
3. Poll async_subagent_status and async_subagent_output_since_last_checked until
   every worker has still_running=false. You may check workers in any order.
4. When all are done, read any missing detail with async_subagent_all_output.
5. Write a final combined report: one section per source with bullet summary and
   the citation URL. If a worker reports a fetch failure, include that as a failed
   source instead of launching replacement workers. Do not visit pages yourself —
   only the sub-agents do that."""


def build_async_manager(model, max_workers: int = 4):
    """Manager with web search plus async launch/monitor/kill tools."""
    async_manager = AsyncSubAgentManager(model=model, max_workers=max_workers)
    manager = CodeAgent(
        tools=[WebSearchTool(), *make_async_subagent_tools(async_manager)],
        model=model,
        add_base_tools=False,
        max_steps=20,
    )
    return manager, async_manager


def main():
    model = build_model()
    manager, async_manager = build_async_manager(model)
    result = manager.run(ASYNC_TASK)
    logger.info("async jobs tracked: %d", async_manager.job_count)
    print("\n=== FINAL REPORT ===")
    print(result)


if __name__ == "__main__":
    main()
