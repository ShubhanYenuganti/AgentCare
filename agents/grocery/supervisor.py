"""Grocery supervisor scaffold."""

from __future__ import annotations

from pathlib import Path

from uagents import Agent, Context

from agents.shared.config import (
    GROCERY_SUPERVISOR_SEED,
    GROCERY_WORKER_ADDRESS,
    LocalFirstResolver,
)
from agents.shared.constants import AGENT_PORTS
from agents.shared.models import MockDomainTask, MockSupervisorResult, MockWorkerResult

supervisor = Agent(
    name="grocery-supervisor",
    seed=GROCERY_SUPERVISOR_SEED,
    port=AGENT_PORTS["grocery_supervisor"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)

_pending_executor_by_request_id: dict[str, str] = {}


@supervisor.on_message(MockDomainTask)
async def handle_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != "grocery":
        ctx.logger.warning(
            "Ignoring MockDomainTask request_id=%s domain=%s expected=grocery sender=%s",
            task.request_id,
            task.domain,
            sender,
        )
        return
    ctx.logger.info(
        "Received MockDomainTask request_id=%s domain=%s sender=%s worker_target=%s",
        task.request_id,
        task.domain,
        sender,
        GROCERY_WORKER_ADDRESS,
    )
    _pending_executor_by_request_id[task.request_id] = sender
    forwarded = task.copy(
        update={
            "metadata": {**(task.metadata or {}), "grocery_supervisor": "forwarded"}
        }
    )
    ctx.logger.info(
        "Dispatching request_id=%s from grocery-supervisor to grocery-worker",
        task.request_id,
    )
    await ctx.send(GROCERY_WORKER_ADDRESS, forwarded)


@supervisor.on_message(MockWorkerResult)
async def handle_worker_result(
    ctx: Context, worker_sender: str, result: MockWorkerResult
) -> None:
    if result.domain != "grocery":
        ctx.logger.warning(
            "Ignoring MockWorkerResult request_id=%s domain=%s expected=grocery sender=%s",
            result.request_id,
            result.domain,
            worker_sender,
        )
        return
    ctx.logger.info(
        "Received MockWorkerResult request_id=%s sender=%s worker=%s",
        result.request_id,
        worker_sender,
        result.worker,
    )
    executor_address = _pending_executor_by_request_id.pop(result.request_id, None)
    if executor_address is None:
        ctx.logger.warning(
            "Missing upstream sender for request_id=%s; dropping result",
            result.request_id,
        )
        return
    response = MockSupervisorResult(
        request_id=result.request_id,
        domain=result.domain,
        supervisor="grocery-supervisor",
        result=f"Grocery mock complete via {result.worker}: {result.result}",
    )
    ctx.logger.info(
        "Forwarding MockSupervisorResult request_id=%s to executor=%s",
        result.request_id,
        executor_address,
    )
    await ctx.send(executor_address, response)


if __name__ == "__main__":
    supervisor.run()
