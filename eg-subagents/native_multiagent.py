"""Comparison: smolagents' built-in managed_agents pattern.

This is the "official" way to build a hierarchy: specialists are wired up at
init time as fixed roles. Contrast with demo.py, where the manager creates workers
dynamically at runtime with an arbitrary tool list and a worker cap.

Run: make native  (after setting ANTHROPIC_API_KEY in .env)
"""

import logging

from smolagents import CodeAgent, ToolCallingAgent, WebSearchTool

from demo import build_model
from web_tools import visit_webpage

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(name)s:%(lineno)d - %(message)s"
)

TASK = "Who is the current CEO of Hugging Face? Cite one source URL."


def main():
    model = build_model()

    web_agent = ToolCallingAgent(
        tools=[WebSearchTool(), visit_webpage],
        model=model,
        max_steps=10,
        name="web_search_agent",
        description="Runs web searches and reads pages for you. Give it your query as the task.",
    )
    manager = CodeAgent(tools=[], model=model, managed_agents=[web_agent])
    result = manager.run(TASK)
    print("\n=== FINAL ANSWER ===")
    print(result)


if __name__ == "__main__":
    main()
