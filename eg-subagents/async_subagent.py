"""Async sub-agents: launch workers in background threads and poll for progress.

Separate from subagent.py (sync, blocking spawn). The manager can start several
workers, check status, read incremental output, and kill stragglers without waiting
for each one to finish before starting the next.
"""

import logging
import threading
from dataclasses import dataclass, field

from smolagents import CodeAgent, tool

from tools_registry import UnknownToolError, resolve

logger = logging.getLogger(__name__)

MAX_STEPS_BY_KIND = {"code": 8, "web": 10}


@dataclass
class AsyncJob:
    """State for one background sub-agent."""

    agent_name: str
    task: str
    tools: list[str]
    status: str = "running"
    output_lines: list[str] = field(default_factory=list)
    last_checked: int = 0
    result: str | None = None
    error: str | None = None
    kill_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


class AsyncSubAgentManager:
    """Runs sub-agents in background threads with pollable output."""

    def __init__(self, model, max_workers: int = 6):
        self.model = model
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._jobs: dict[str, AsyncJob] = {}
        self._name_counter = 0

    def _next_name(self) -> str:
        self._name_counter += 1
        return f"agent-{self._name_counter}"

    def _active_count(self) -> int:
        return sum(1 for job in self._jobs.values() if job.status == "running")

    def _append(self, job: AsyncJob, line: str) -> None:
        with self._lock:
            job.output_lines.append(line)

    def _make_step_callback(self, job: AsyncJob):
        def on_step(step, agent=None):
            if job.kill_event.is_set():
                return
            parts = []
            if step.observations:
                parts.append(f"observed {len(str(step.observations))} chars")
            if step.action_output is not None:
                parts.append(f"tool output type={type(step.action_output).__name__}")
            if step.model_output and not parts:
                parts.append(f"model output {len(str(step.model_output))} chars")
            if parts:
                self._append(job, f"[step {step.step_number}] " + " | ".join(parts))

        return on_step

    def _run_worker(self, job: AsyncJob) -> None:
        self._append(job, f"[started] {job.task[:200]}")
        try:
            if job.kill_event.is_set():
                job.status = "killed"
                self._append(job, "[killed] before start")
                return

            agent_class, tool_objects, extra_imports = resolve(job.tools)
            kind = "code" if agent_class is CodeAgent else "web"
            kwargs = {
                "tools": tool_objects,
                "model": self.model,
                "add_base_tools": False,
                "max_steps": MAX_STEPS_BY_KIND[kind],
                "step_callbacks": [self._make_step_callback(job)],
            }
            if agent_class is CodeAgent:
                kwargs["additional_authorized_imports"] = extra_imports

            agent = agent_class(**kwargs)
            result = agent.run(job.task)

            with self._lock:
                if job.kill_event.is_set():
                    job.status = "killed"
                    job.output_lines.append("[killed] finished in background")
                else:
                    job.status = "completed"
                    job.result = str(result)
                    job.output_lines.append(f"[final] {job.result}")
        except Exception as e:  # noqa: BLE001 - surface worker failure to manager
            logger.exception("async worker %s failed", job.agent_name)
            with self._lock:
                job.status = "error"
                job.error = str(e)
                job.output_lines.append(f"[error] {e}")

    def launch(self, task: str, tools: list[str], agent_name: str | None = None) -> str:
        try:
            resolve(tools)
        except UnknownToolError as e:
            return f"Could not launch sub-agent: {e}"

        with self._lock:
            if self._active_count() >= self.max_workers:
                return (
                    f"Worker limit reached ({self.max_workers} running). "
                    "Wait for some to finish or kill one before launching more."
                )
            name = agent_name or self._next_name()
            if name in self._jobs and self._jobs[name].status == "running":
                return f"Agent name '{name}' is already running. Pick another name."

            job = AsyncJob(agent_name=name, task=task, tools=tools)
            self._jobs[name] = job
            thread = threading.Thread(
                target=self._run_worker,
                args=(job,),
                name=f"async-subagent-{name}",
                daemon=True,
            )
            job.thread = thread
            thread.start()

        logger.info("launched async subagent %s tools=%s", name, tools)
        return name

    def _get_job(self, agent_name: str) -> AsyncJob | None:
        with self._lock:
            return self._jobs.get(agent_name)

    def status(self, agent_name: str) -> str:
        job = self._get_job(agent_name)
        if job is None:
            return f"Unknown agent '{agent_name}'."
        still_running = job.status == "running"
        return (
            f"agent_name={job.agent_name} status={job.status} "
            f"still_running={still_running} lines={len(job.output_lines)}"
        )

    def all_output(self, agent_name: str) -> str:
        job = self._get_job(agent_name)
        if job is None:
            return f"Unknown agent '{agent_name}'."
        with self._lock:
            if not job.output_lines:
                return f"[{agent_name}] (no output yet)"
            return "\n".join(job.output_lines)

    def output_since_last_checked(self, agent_name: str) -> str:
        job = self._get_job(agent_name)
        if job is None:
            return f"Unknown agent '{agent_name}'."
        with self._lock:
            new_lines = job.output_lines[job.last_checked :]
            job.last_checked = len(job.output_lines)
            if not new_lines:
                return f"[{agent_name}] (no new output since last check)"
            return "\n".join(new_lines)

    def kill(self, agent_name: str) -> str:
        job = self._get_job(agent_name)
        if job is None:
            return f"Unknown agent '{agent_name}'."
        job.kill_event.set()
        with self._lock:
            if job.status == "running":
                job.output_lines.append("[kill requested]")
            elif job.status in ("completed", "error"):
                return f"Agent '{agent_name}' already finished ({job.status})."
            job.status = "killed"
        return f"Kill signalled for '{agent_name}'. Thread may still wind down."

    @property
    def job_count(self) -> int:
        with self._lock:
            return len(self._jobs)


def make_async_subagent_tools(manager: AsyncSubAgentManager) -> list:
    """Return the five async sub-agent tools for a manager agent."""

    @tool
    def launch_async_subagent(task: str, tools: list[str], agent_name: str = "") -> str:
        """Start a sub-agent in the background and return its agent_name immediately.

        Use this to fan out parallel work: launch several agents, then poll status and
        output while they run. Available tool names for workers: web_search,
        visit_webpage, html_to_markdown, code. Workers cannot launch or monitor other
        agents.

        Args:
            task: Self-contained description of what the sub-agent should do.
            tools: Capability names to grant the sub-agent.
            agent_name: Optional name; auto-generated if empty.

        Returns:
            The agent_name to use with status/output/kill tools.
        """
        name = agent_name if agent_name else None
        return manager.launch(task=task, tools=tools, agent_name=name)

    @tool
    def async_subagent_status(agent_name: str) -> str:
        """Check whether a background sub-agent is still running.

        Args:
            agent_name: Name returned by launch_async_subagent.

        Returns:
            Status string with still_running true/false.
        """
        return manager.status(agent_name=agent_name)

    @tool
    def async_subagent_all_output(agent_name: str) -> str:
        """Return all logged output from a background sub-agent.

        Args:
            agent_name: Name returned by launch_async_subagent.

        Returns:
            Full output log for the agent.
        """
        return manager.all_output(agent_name=agent_name)

    @tool
    def async_subagent_output_since_last_checked(agent_name: str) -> str:
        """Return only new output since the last time you checked this agent.

        Args:
            agent_name: Name returned by launch_async_subagent.

        Returns:
            New log lines since the previous call to this tool for this agent.
        """
        return manager.output_since_last_checked(agent_name=agent_name)

    @tool
    def kill_async_subagent(agent_name: str) -> str:
        """Request that a background sub-agent stop. Best-effort; may not halt instantly.

        Args:
            agent_name: Name returned by launch_async_subagent.

        Returns:
            Confirmation that the kill was signalled.
        """
        return manager.kill(agent_name=agent_name)

    return [
        launch_async_subagent,
        async_subagent_status,
        async_subagent_all_output,
        async_subagent_output_since_last_checked,
        kill_async_subagent,
    ]
