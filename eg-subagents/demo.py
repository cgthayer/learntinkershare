"""Runnable demo: a lean manager delegates web research and math to sub-agents.

Run: make demo  (after setting ANTHROPIC_API_KEY in .env)
"""

import logging
import os

from dotenv import load_dotenv
from smolagents import CodeAgent, LiteLLMModel

from subagent import SubAgentManager, make_subagent_tool

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_ID = "anthropic/claude-haiku-4-5"

COMPOSITE_TASK = """Answer both of these using sub-agents, then give me one short combined answer:
1. Compute the 118th number in the Fibonacci sequence exactly (treat 1, 1, 2, 3 as the start).
2. Who first popularized the Fibonacci sequence in Western Europe, and roughly when? Cite one source URL.

Delegate part 1 to a sub-agent with the "code" tool, and part 2 to a sub-agent with
web tools. Do not do the work yourself."""


def build_model():
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env (see env.example).")
    return LiteLLMModel(model_id=MODEL_ID, temperature=0.0, api_key=api_key)


def build_manager(model, max_workers: int = 6):
    """A manager whose only tool is spawn_subagent, so all real work is delegated."""
    subagent_manager = SubAgentManager(model=model, max_workers=max_workers)
    manager = CodeAgent(
        tools=[make_subagent_tool(subagent_manager)],
        model=model,
        add_base_tools=False,
    )
    return manager, subagent_manager


def main():
    model = build_model()
    manager, subagent_manager = build_manager(model)
    result = manager.run(COMPOSITE_TASK)
    logger.info("sub-agents created: %d", subagent_manager.subagent_count)
    print("\n=== FINAL ANSWER ===")
    print(result)


if __name__ == "__main__":
    main()
