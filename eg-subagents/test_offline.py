"""Offline integration tests: drive real smolagents agents with a scripted fake model.

These verify the wiring (tool resolution, agent construction, step callbacks, threading,
and the manager -> spawn_subagent path) without needing a live LLM or network. Run:

    uv run python test_offline.py
"""

import threading
import time

from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
)
from smolagents.monitoring import TokenUsage

from async_subagent import AsyncSubAgentManager, make_async_subagent_tools
from subagent import SubAgentManager
from tools_registry import UnknownToolError, resolve

_USAGE = TokenUsage(input_tokens=1, output_tokens=1)


def _messages_text(messages) -> str:
    """Flatten message content (ChatMessage or dict) into a searchable string."""
    parts = []
    for m in messages:
        content = (
            getattr(m, "content", None) if not isinstance(m, dict) else m.get("content")
        )
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def _final_answer_tool_call(answer: str) -> ChatMessage:
    return ChatMessage(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=[
            ChatMessageToolCall(
                id="call_1",
                type="function",
                function=ChatMessageToolCallFunction(
                    name="final_answer", arguments={"answer": answer}
                ),
            )
        ],
        token_usage=_USAGE,
    )


def _code_final_answer(answer: str) -> ChatMessage:
    return ChatMessage(
        role=MessageRole.ASSISTANT,
        content=f'Thought: done.\n<code>\nfinal_answer("{answer}")\n</code>',
        token_usage=_USAGE,
    )


class WorkerFinalAnswerModel:
    """Fake model: any worker immediately returns a final answer."""

    model_id = "fake/worker"

    def generate(
        self,
        messages,
        stop_sequences=None,
        response_format=None,
        tools_to_call_from=None,
        **kwargs,
    ):
        if tools_to_call_from is not None:
            return _final_answer_tool_call("WEB_DONE")
        return _code_final_answer("CODE_DONE")

    __call__ = generate


class ManagerScriptModel:
    """Fake model driving a CodeAgent manager that spawns one web worker, then answers.

    The single web worker (ToolCallingAgent) is distinguished from the manager
    (CodeAgent) by whether tools_to_call_from is passed.
    """

    model_id = "fake/manager"

    def generate(
        self,
        messages,
        stop_sequences=None,
        response_format=None,
        tools_to_call_from=None,
        **kwargs,
    ):
        if tools_to_call_from is not None:
            return _final_answer_tool_call("WORKER_DONE: summary text")

        text = _messages_text(messages)
        if "WORKER_DONE" in text:
            return _code_final_answer("Report complete with citation")
        code = (
            "Thought: delegate to a web sub-agent.\n"
            "<code>\n"
            'result = spawn_subagent(task="Summarize MARKER", tools=["web_search", "visit_webpage"])\n'
            "print(result)\n"
            "</code>"
        )
        return ChatMessage(role=MessageRole.ASSISTANT, content=code, token_usage=_USAGE)

    __call__ = generate


def test_sync_worker_code():
    mgr = SubAgentManager(model=WorkerFinalAnswerModel(), max_workers=6)
    out = mgr.run("Compute something", ["code"])
    assert "CODE_DONE" in out, out
    assert mgr.subagent_count == 1
    print("PASS test_sync_worker_code")


def test_sync_worker_web():
    mgr = SubAgentManager(model=WorkerFinalAnswerModel(), max_workers=6)
    out = mgr.run("Summarize a page", ["web_search", "visit_webpage"])
    assert "WEB_DONE" in out, out
    print("PASS test_sync_worker_web")


def test_sync_guards():
    mgr = SubAgentManager(model=WorkerFinalAnswerModel(), max_workers=1)
    mgr.run("one", ["code"])
    capped = mgr.run("two", ["code"])
    assert "Worker limit reached" in capped, capped

    bad = mgr.run("x", ["spawn_subagent"])
    assert "cannot spawn children" in bad, bad
    print("PASS test_sync_guards")


def test_async_flow():
    mgr = AsyncSubAgentManager(model=WorkerFinalAnswerModel(), max_workers=6)
    names = [
        mgr.launch(f"summarize url {i}", ["web_search", "visit_webpage"], f"url-{i}")
        for i in range(3)
    ]

    deadline = time.time() + 15
    while time.time() < deadline:
        if all("still_running=False" in mgr.status(n) for n in names):
            break
        time.sleep(0.1)

    for n in names:
        assert "still_running=False" in mgr.status(n), mgr.status(n)
        assert "WEB_DONE" in mgr.all_output(n), mgr.all_output(n)
    print("PASS test_async_flow")


def test_async_incremental_and_unknown():
    mgr = AsyncSubAgentManager(model=WorkerFinalAnswerModel(), max_workers=6)
    name = mgr.launch("task", ["visit_webpage"], "solo")
    time.sleep(0.5)
    first = mgr.output_since_last_checked(name)
    assert "started" in first or "final" in first, first
    second = mgr.output_since_last_checked(name)
    assert "no new output" in second, second
    assert "Unknown agent" in mgr.status("nope")
    print("PASS test_async_incremental_and_unknown")


def test_async_cap_and_kill():
    slow = _SlowModel()
    mgr = AsyncSubAgentManager(model=slow, max_workers=2)
    mgr.launch("a", ["visit_webpage"], "a")
    mgr.launch("b", ["visit_webpage"], "b")
    capped = mgr.launch("c", ["visit_webpage"], "c")
    assert "Worker limit reached" in capped, capped

    killed = mgr.kill("a")
    assert "Kill signalled" in killed, killed
    slow.release.set()
    print("PASS test_async_cap_and_kill")


def test_manager_spawns_subagent():
    mgr = SubAgentManager  # noqa: F841 - referenced for clarity in failures
    from demo import build_manager

    manager, sub = build_manager(ManagerScriptModel(), max_workers=6)
    result = manager.run(
        "Write a cited report using sub-agents. Do not do the work yourself."
    )
    assert sub.subagent_count == 1, sub.subagent_count
    assert "Report complete" in str(result), result
    print("PASS test_manager_spawns_subagent")


class _SlowModel:
    """Worker model that blocks until released, to test the concurrent cap."""

    model_id = "fake/slow"

    def __init__(self):
        self.release = threading.Event()

    def generate(
        self,
        messages,
        stop_sequences=None,
        response_format=None,
        tools_to_call_from=None,
        **kwargs,
    ):
        self.release.wait(timeout=10)
        return _final_answer_tool_call("SLOW_DONE")

    __call__ = generate


def test_registry_resolve():
    agent_cls, tools, imports = resolve(["code"])
    assert agent_cls.__name__ == "CodeAgent"
    assert imports
    agent_cls, tools, imports = resolve(["web_search", "visit_webpage"])
    assert agent_cls.__name__ == "ToolCallingAgent"
    for bad in (["kill_async_subagent"], ["launch_async_subagent"], []):
        try:
            resolve(bad)
            raise AssertionError(f"expected failure for {bad}")
        except UnknownToolError:
            pass
    print("PASS test_registry_resolve")


def test_async_tool_factory():
    tools = make_async_subagent_tools(
        AsyncSubAgentManager(model=WorkerFinalAnswerModel())
    )
    tool_names = [tool.name for tool in tools]
    assert tool_names == [
        "launch_async_subagent",
        "async_subagent_status",
        "async_subagent_all_output",
        "async_subagent_output_since_last_checked",
        "kill_async_subagent",
    ]
    print("PASS test_async_tool_factory")


def main():
    test_registry_resolve()
    test_async_tool_factory()
    test_sync_worker_code()
    test_sync_worker_web()
    test_sync_guards()
    test_async_flow()
    test_async_incremental_and_unknown()
    test_async_cap_and_kill()
    test_manager_spawns_subagent()
    print("\nALL OFFLINE TESTS PASSED")


if __name__ == "__main__":
    main()
