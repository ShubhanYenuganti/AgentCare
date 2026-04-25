"""Scheduling agent scaffold."""

from __future__ import annotations

from pathlib import Path

from uagents import Agent, Context

from agents.shared.config import SCHEDULING_AGENT_SEED, LocalFirstResolver
from agents.shared.constants import AGENT_PORTS
from agents.shared.models import MockDomainTask, MockSupervisorResult

agent = Agent(
    name="scheduling-agent",
    seed=SCHEDULING_AGENT_SEED,
    port=AGENT_PORTS["scheduling_agent"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)


@agent.on_message(MockDomainTask)
async def handle_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != "scheduling":
        ctx.logger.warning(
            "Ignoring MockDomainTask request_id=%s domain=%s expected=scheduling sender=%s",
            task.request_id,
            task.domain,
            sender,
        )
        return
    ctx.logger.info(
        "Received MockDomainTask request_id=%s domain=%s sender=%s",
        task.request_id,
        task.domain,
        sender,
    )
    response = MockSupervisorResult(
        request_id=task.request_id,
        domain="scheduling",
        supervisor="scheduling-agent",
        result=f"Scheduling mock complete: matched options for '{task.query}'",
    )
    ctx.logger.info(
        "Sending MockSupervisorResult request_id=%s back to sender=%s",
        task.request_id,
        sender,
    )
    await ctx.send(sender, response)


if __name__ == "__main__":
    agent.run()
