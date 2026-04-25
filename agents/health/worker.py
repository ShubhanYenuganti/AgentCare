"""Health worker scaffold."""

from __future__ import annotations

from pathlib import Path

from uagents import Agent, Context

from agents.shared.config import HEALTH_WORKER_SEED, LocalFirstResolver
from agents.shared.constants import AGENT_PORTS
from agents.shared.models import MockDomainTask, MockWorkerResult

worker = Agent(
    name="health-worker",
    seed=HEALTH_WORKER_SEED,
    port=AGENT_PORTS["health_worker"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)


@worker.on_message(MockDomainTask)
async def handle_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != "health":
        return
    result = MockWorkerResult(
        request_id=task.request_id,
        domain=task.domain,
        worker="health-worker",
        result=f"processed '{task.query}'",
    )
    await ctx.send(sender, result)


if __name__ == "__main__":
    worker.run()
