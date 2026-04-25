"""Executor orchestrator scaffold inspired by Fetch.ai quickstarter."""

from __future__ import annotations

import aiohttp
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents.shared.config import EXECUTOR_SEED, SUPERVISOR_ADDRESS_BY_DOMAIN, LocalFirstResolver
from agents.shared.constants import AGENT_PORTS, DOMAIN_KEYWORDS
from agents.shared.models import MockDomainTask, MockSupervisorResult
from agents.shared.state_service import PendingRequest, request_state

REQUEST_TIMEOUT_SECONDS = 45.0
HEARTBEAT_INTERVAL_SECONDS = 15.0
MAILBOX_INGRESS_SILENCE_WARNING_SECONDS = 120.0

executor = Agent(
    name="executor",
    seed=EXECUTOR_SEED,
    port=AGENT_PORTS["executor"],
    mailbox=True,                   # keeps ASI:One inbound channel
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),   # outbound: direct local, no Agentverse hop
)

chat_proto = Protocol(spec=chat_protocol_spec)
_started_at = datetime.now(tz=timezone.utc)
_last_chat_ingress_at: datetime | None = None


class HealthResponse(Model):
    status: str


class HttpMessagePost(Model):
    content: str


class HttpMessageResponse(Model):
    request_id: str
    routed_domain: str
    routed_address: str


def _classify_domain(query: str) -> str:
    lowered = query.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return domain
    return "health"


async def _send_terminal_chat_response(ctx: Context, recipient: str, text: str) -> None:
    try:
        await ctx.send(
            recipient,
            ChatMessage(
                timestamp=datetime.now(tz=timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=text),
                    EndSessionContent(type="end-session"),
                ],
            ),
        )
        ctx.logger.info("Sent ChatMessage reply to recipient=%s", recipient)
    except Exception as send_err:
        ctx.logger.error(
            "Failed to send ChatMessage reply to recipient=%s: %s",
            recipient,
            send_err,
        )


async def _route_query(
    ctx: Context, query: str, user_sender_address: str | None
) -> HttpMessageResponse:
    request_id = str(uuid4())
    domain = _classify_domain(query)
    routed_address = SUPERVISOR_ADDRESS_BY_DOMAIN[domain]
    ctx.logger.info(
        "Routing request_id=%s domain=%s routed_address=%s user_sender=%s",
        request_id,
        domain,
        routed_address,
        user_sender_address or "none",
    )
    request_state.set_request(
        PendingRequest(
            request_id=request_id,
            query=query,
            domain=domain,
            user_sender_address=user_sender_address,
            routed_address=routed_address,
            created_at=datetime.now(tz=timezone.utc),
        )
    )
    task = MockDomainTask(
        request_id=request_id,
        domain=domain,
        query=query,
        user_sender_address=user_sender_address,
        metadata={
            "orchestrator": "executor",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    try:
        await ctx.send(routed_address, task)
    except Exception as ex:
        request_state.remove_request(request_id)
        ctx.logger.exception(
            "Failed to dispatch request_id=%s domain=%s routed_address=%s: %s",
            request_id,
            domain,
            routed_address,
            ex,
        )
        if user_sender_address:
            await _send_terminal_chat_response(
                ctx,
                user_sender_address,
                "Sorry, I could not route your request right now. Please try again.",
            )
        raise
    return HttpMessageResponse(
        request_id=request_id,
        routed_domain=domain,
        routed_address=routed_address,
    )


@executor.on_rest_get("/health", HealthResponse)
async def health(_: Context) -> HealthResponse:
    return HealthResponse(status="ok healthy")


@executor.on_event("startup")
async def log_startup_health(ctx: Context) -> None:
    mailbox_client_present = executor.mailbox_client is not None
    agentverse_url = executor._agentverse.url if hasattr(executor, "_agentverse") else "unknown"
    mailbox_poll_url = (
        f"{executor._agentverse.agents_api}/{executor.address}/mailbox"
        if mailbox_client_present
        else "N/A"
    )
    ctx.logger.info(
        "Executor startup ready address=%s mailbox_client=%s agentverse=%s poll_url=%s",
        executor.address,
        "present" if mailbox_client_present else "MISSING",
        agentverse_url,
        mailbox_poll_url,
    )
    if not mailbox_client_present:
        ctx.logger.warning(
            "Mailbox client not initialized. ASI:One messages will not be received. "
            "Ensure the agent is registered on Agentverse and a mailbox is enabled via "
            "the Agent Inspector at https://agentverse.ai"
        )


@executor.on_rest_post("/message", HttpMessagePost, HttpMessageResponse)
async def post_message(ctx: Context, req: HttpMessagePost) -> HttpMessageResponse:
    ctx.logger.info("Received REST /message content=%r", req.content)
    return await _route_query(ctx, req.content, user_sender_address=None)


@chat_proto.on_message(ChatMessage, allow_unverified=True)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    global _last_chat_ingress_at
    _last_chat_ingress_at = datetime.now(tz=timezone.utc)
    ctx.logger.info(
        "Received ChatMessage sender=%s msg_id=%s session=%s",
        sender,
        msg.msg_id,
        ctx.session,
    )
    try:
        await ctx.send(
            sender,
            ChatAcknowledgement(timestamp=datetime.now(tz=timezone.utc), acknowledged_msg_id=msg.msg_id),
        )
    except Exception as ack_err:
        ctx.logger.warning(
            "ChatAcknowledgement to sender=%s failed (will still process): %s",
            sender,
            ack_err,
        )
    text_parts = [item.text for item in msg.content if isinstance(item, TextContent)]
    text = " ".join(text_parts).strip()
    ctx.logger.info("Parsed ChatMessage sender=%s text=%r", sender, text)
    if not text:
        ctx.logger.info("ChatMessage from sender=%s had no text content (session init?), skipping route", sender)
        return
    # Send immediate processing acknowledgement so ASI:One shows feedback
    # before the multi-hop pipeline completes (which may include LLM calls).
    try:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(tz=timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text="Processing your request…")],
            ),
        )
    except Exception:
        pass  # Non-fatal — still process the request
    await _route_query(ctx, text, user_sender_address=sender)


@chat_proto.on_message(ChatAcknowledgement, allow_unverified=True)
async def handle_chat_ack(_: Context, __: str, ___: ChatAcknowledgement) -> None:
    return


@executor.on_interval(period=HEARTBEAT_INTERVAL_SECONDS)
async def heartbeat_and_timeout_sweep(ctx: Context) -> None:
    stale_requests = request_state.remove_stale_requests(REQUEST_TIMEOUT_SECONDS)
    for pending in stale_requests:
        age_seconds = (datetime.now(tz=timezone.utc) - pending.created_at).total_seconds()
        ctx.logger.warning(
            "Request timeout request_id=%s domain=%s routed_address=%s age_sec=%.1f",
            pending.request_id,
            pending.domain,
            pending.routed_address,
            age_seconds,
        )
        if pending.user_sender_address:
            await _send_terminal_chat_response(
                ctx,
                pending.user_sender_address,
                "Sorry, your request timed out while waiting for downstream agents. Please try again.",
            )

    pending_snapshot = request_state.all_requests()
    pending_count = len(pending_snapshot)
    oldest_pending_age_seconds = 0.0
    if pending_count:
        oldest_created_at = min(
            pending.created_at for pending in pending_snapshot.values()
        )
        oldest_pending_age_seconds = (
            datetime.now(tz=timezone.utc) - oldest_created_at
        ).total_seconds()
    chat_ingress_age_seconds = (
        (datetime.now(tz=timezone.utc) - _last_chat_ingress_at).total_seconds()
        if _last_chat_ingress_at
        else (datetime.now(tz=timezone.utc) - _started_at).total_seconds()
    )
    ctx.logger.info(
        "Heartbeat pending_requests=%s oldest_pending_age_sec=%.1f chat_ingress_age_sec=%.1f",
        pending_count,
        oldest_pending_age_seconds,
        chat_ingress_age_seconds,
    )
    if (
        pending_count > 0
        and chat_ingress_age_seconds >= MAILBOX_INGRESS_SILENCE_WARNING_SECONDS
    ):
        ctx.logger.warning(
            "Potential mailbox ingress stall: pending_requests=%s oldest_pending_age_sec=%.1f no_chat_ingress_sec=%.1f",
            pending_count,
            oldest_pending_age_seconds,
            chat_ingress_age_seconds,
        )


class MailboxDebugResponse(Model):
    address: str
    poll_url: str
    http_status: int
    item_count: int
    items_preview: list[str]
    error: str | None


async def _raw_mailbox_poll(ctx: Context) -> MailboxDebugResponse:
    """Direct Agentverse mailbox HTTP poll — bypasses the uagents loop for diagnostics."""
    if executor.mailbox_client is None:
        return MailboxDebugResponse(
            address=executor.address,
            poll_url="N/A",
            http_status=-1,
            item_count=0,
            items_preview=[],
            error="mailbox_client is None",
        )
    agents_url = executor._agentverse.agents_api
    poll_url = f"{agents_url}/{executor.address}/mailbox"
    try:
        attestation = executor.mailbox_client.attestation
        async with aiohttp.ClientSession() as session:
            async with session.get(
                poll_url,
                headers={"Authorization": f"Agent {attestation}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                status = resp.status
                if status == 200:
                    items = await resp.json()
                    previews = [str(it)[:120] for it in items[:5]]
                    return MailboxDebugResponse(
                        address=executor.address,
                        poll_url=poll_url,
                        http_status=status,
                        item_count=len(items),
                        items_preview=previews,
                        error=None,
                    )
                else:
                    body = await resp.text()
                    return MailboxDebugResponse(
                        address=executor.address,
                        poll_url=poll_url,
                        http_status=status,
                        item_count=0,
                        items_preview=[],
                        error=body[:300],
                    )
    except Exception as exc:
        return MailboxDebugResponse(
            address=executor.address,
            poll_url=poll_url,
            http_status=-1,
            item_count=0,
            items_preview=[],
            error=str(exc)[:300],
        )


@executor.on_rest_get("/mailbox-debug", MailboxDebugResponse)
async def mailbox_debug(ctx: Context) -> MailboxDebugResponse:
    """Call this to see what is currently in the Agentverse mailbox queue."""
    result = await _raw_mailbox_poll(ctx)
    ctx.logger.info(
        "MAILBOX-DEBUG poll: status=%s items=%s error=%s",
        result.http_status,
        result.item_count,
        result.error,
    )
    return result


@executor.on_interval(period=20.0)
async def mailbox_diagnostic_poll(ctx: Context) -> None:
    """Periodic raw mailbox poll — surfaces Agentverse queue state in logs."""
    result = await _raw_mailbox_poll(ctx)
    ctx.logger.info(
        "MAILBOX-DIAG poll_url=%s status=%s items=%s error=%s",
        result.poll_url,
        result.http_status,
        result.item_count,
        result.error,
    )
    if result.item_count > 0:
        for i, preview in enumerate(result.items_preview):
            ctx.logger.info("MAILBOX-DIAG item[%d]: %s", i, preview)


# Include the chat protocol only after message handlers are registered.
# Publish manifest for Agentverse interoperability (quickstarter parity).
executor.include(chat_proto, publish_manifest=True)


@executor.on_message(MockSupervisorResult)
async def handle_supervisor_result(
    ctx: Context, sender: str, result: MockSupervisorResult
) -> None:
    pending = request_state.remove_request(result.request_id)
    final_text = f"[{result.domain}] {result.result}"
    ctx.logger.info(
        "Received MockSupervisorResult sender=%s request_id=%s domain=%s result=%s",
        sender,
        result.request_id,
        result.domain,
        result.result,
    )
    if pending is None:
        ctx.logger.warning(
            "No pending request state found for request_id=%s; cannot correlate sender",
            result.request_id,
        )
        return
    if pending and pending.user_sender_address:
        ctx.logger.info(
            "Sending final ChatMessage request_id=%s to user_sender=%s",
            result.request_id,
            pending.user_sender_address,
        )
        await _send_terminal_chat_response(
            ctx,
            pending.user_sender_address,
            final_text,
        )
        return
    ctx.logger.info(
        "Completed request_id=%s for non-chat flow (no user sender address)",
        result.request_id,
    )


if __name__ == "__main__":
    executor.run()
