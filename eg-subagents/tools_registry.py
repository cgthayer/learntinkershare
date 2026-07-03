"""The catalog of capabilities a manager may hand to a spawned sub-agent.

Sub-agents are assembled from string names so the manager can request tools in a
task without holding tool objects. spawn_subagent is never listed here, which is
what stops a worker from creating its own children.
"""

from smolagents import CodeAgent, ToolCallingAgent, WebSearchTool

from web_tools import html_to_markdown, visit_webpage

# Names the manager may request. "code" is a pseudo-capability: it carries no tool
# object but flips the worker to a CodeAgent that can execute Python.
WEB_TOOLS = {
    "web_search": WebSearchTool(),
    "visit_webpage": visit_webpage,
    "html_to_markdown": html_to_markdown,
}
CODE_CAPABILITY = "code"

SPAWNABLE_NAMES = sorted([*WEB_TOOLS.keys(), CODE_CAPABILITY])

# Never resolvable, even if a worker's task tries to request it.
FORBIDDEN_TOOL_NAMES = {"spawn_subagent"}

# Imports a code worker is allowed to use. Intentionally analytical, not I/O.
CODE_IMPORTS = ["math", "statistics", "numpy", "fractions", "itertools"]


class UnknownToolError(ValueError):
    """Raised when a requested tool name is not in the registry."""


def resolve(tool_names):
    """Turn a list of requested tool names into a sub-agent recipe.

    Returns a tuple of (agent_class, tool_objects, extra_imports). Requesting the
    "code" capability selects a CodeAgent; anything else builds a ToolCallingAgent.

    Raises UnknownToolError for unknown or forbidden names, or if the list is empty.
    """
    if not tool_names:
        raise UnknownToolError(
            "No tools requested; give the sub-agent at least one capability."
        )

    forbidden = [n for n in tool_names if n in FORBIDDEN_TOOL_NAMES]
    if forbidden:
        raise UnknownToolError(
            f"Refusing to grant {forbidden}: sub-agents cannot spawn children."
        )

    unknown = [n for n in tool_names if n not in WEB_TOOLS and n != CODE_CAPABILITY]
    if unknown:
        raise UnknownToolError(
            f"Unknown tool(s) {unknown}. Available: {SPAWNABLE_NAMES}."
        )

    wants_code = CODE_CAPABILITY in tool_names
    tools = [WEB_TOOLS[n] for n in tool_names if n in WEB_TOOLS]

    if wants_code:
        return CodeAgent, tools, CODE_IMPORTS
    return ToolCallingAgent, tools, []
