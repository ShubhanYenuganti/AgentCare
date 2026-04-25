"""Sprint 1 architecture invariant regression tests.

These tests lock the structural properties of the executor and agent stack that
must not regress across sprints.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGENTS_DIR = pathlib.Path(__file__).parent.parent / "agents"
_EXECUTOR_SRC = _AGENTS_DIR / "executor" / "agent.py"
_SUPERVISOR_PATHS = {
    "health": _AGENTS_DIR / "health" / "supervisor.py",
    "appointment": _AGENTS_DIR / "appointment" / "supervisor.py",
    "grocery": _AGENTS_DIR / "grocery" / "supervisor.py",
    "financial": _AGENTS_DIR / "financial" / "supervisor.py",
}


# ---------------------------------------------------------------------------
# Test 1: Executor mailbox ingress invariant
# ---------------------------------------------------------------------------

def test_executor_mailbox_is_true() -> None:
    """Executor agent must be created with mailbox=True.

    The uagents library stores the mailbox flag as _use_mailbox internally.
    We verify via the source that mailbox=True is passed at construction AND
    that the runtime attribute reflects it.
    """
    # Source-level check: the Agent(...) call must include mailbox=True
    source = _EXECUTOR_SRC.read_text(encoding="utf-8")
    assert "mailbox=True" in source, (
        "executor Agent() constructor in agent.py must pass mailbox=True"
    )

    # Runtime check: the uagents library exposes _use_mailbox
    from agents.executor.agent import executor

    mailbox_flag = getattr(executor, "_use_mailbox", None)
    assert mailbox_flag is True, (
        f"executor._use_mailbox must be True (got {mailbox_flag!r}). "
        "ASI:One messages won't be received without a mailbox."
    )


# ---------------------------------------------------------------------------
# Test 2: LocalFirstResolver is used
# ---------------------------------------------------------------------------

def test_executor_uses_local_first_resolver() -> None:
    """Executor must use LocalFirstResolver, not GlobalResolver."""
    from agents.executor.agent import executor
    from agents.shared.config import LocalFirstResolver

    assert isinstance(executor._resolver, LocalFirstResolver), (
        f"executor._resolver should be LocalFirstResolver, got {type(executor._resolver)}"
    )


# ---------------------------------------------------------------------------
# Test 3: No on_interval handlers on domain supervisors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain,path", list(_SUPERVISOR_PATHS.items()))
def test_supervisor_has_no_on_interval(domain: str, path: pathlib.Path) -> None:
    """Domain supervisors should NOT have @supervisor.on_interval decorators.

    Only the executor has a heartbeat interval loop; supervisors are purely
    event-driven (OnDemandDetectionRequest, ModificationRequest, etc.).
    """
    source = path.read_text(encoding="utf-8")
    assert "@supervisor.on_interval" not in source, (
        f"{domain} supervisor at {path} has an unexpected on_interval handler. "
        "Domain supervisors must be event-driven only."
    )


# ---------------------------------------------------------------------------
# Test 4: ChatAcknowledgement preserved in executor chat handler
# ---------------------------------------------------------------------------

def test_executor_chat_handler_sends_acknowledgement() -> None:
    """The executor chat handler must import and send ChatAcknowledgement."""
    source = _EXECUTOR_SRC.read_text(encoding="utf-8")

    assert "ChatAcknowledgement" in source, (
        "ChatAcknowledgement must be imported in executor/agent.py"
    )
    # Verify it's actually sent (not just imported)
    assert "await ctx.send(\n            sender,\n            ChatAcknowledgement(" in source or (
        "ChatAcknowledgement(" in source and "await ctx.send" in source
    ), "executor chat handler must send a ChatAcknowledgement before routing"


# ---------------------------------------------------------------------------
# Test 5: LocalFirstResolver covers all stack agents
# ---------------------------------------------------------------------------

def test_local_first_resolver_covers_all_agents() -> None:
    """LocalFirstResolver must resolve every known agent address to a localhost endpoint."""
    from agents.shared.config import (
        LocalFirstResolver,
        EXECUTOR_ADDRESS,
        HEALTH_SUPERVISOR_ADDRESS,
        HEALTH_WORKER_ADDRESS,
        APPOINTMENT_SUPERVISOR_ADDRESS,
        APPOINTMENT_WORKER_ADDRESS,
        GROCERY_SUPERVISOR_ADDRESS,
        GROCERY_WORKER_ADDRESS,
        FINANCIAL_SUPERVISOR_ADDRESS,
        FINANCIAL_WORKER_ADDRESS,
        SCHEDULING_AGENT_ADDRESS,
    )

    resolver = LocalFirstResolver()
    known_addresses = [
        EXECUTOR_ADDRESS,
        HEALTH_SUPERVISOR_ADDRESS,
        HEALTH_WORKER_ADDRESS,
        APPOINTMENT_SUPERVISOR_ADDRESS,
        APPOINTMENT_WORKER_ADDRESS,
        GROCERY_SUPERVISOR_ADDRESS,
        GROCERY_WORKER_ADDRESS,
        FINANCIAL_SUPERVISOR_ADDRESS,
        FINANCIAL_WORKER_ADDRESS,
        SCHEDULING_AGENT_ADDRESS,
    ]

    async def _resolve_all() -> list[tuple[str, list[str]]]:
        results = []
        for addr in known_addresses:
            resolved = await resolver.resolve(addr)
            results.append((addr, resolved[1]))
        return results

    results = asyncio.run(_resolve_all())
    for addr, endpoints in results:
        assert endpoints, f"No endpoints resolved for address {addr}"
        assert any(ep.startswith("http://localhost:") for ep in endpoints), (
            f"Address {addr} did not resolve to a localhost endpoint; got {endpoints}"
        )


# ---------------------------------------------------------------------------
# Test 6: Executor port
# ---------------------------------------------------------------------------

def test_executor_port() -> None:
    """AGENT_PORTS['executor'] must be 8001."""
    from agents.shared.constants import AGENT_PORTS

    assert AGENT_PORTS["executor"] == 8001, (
        f"Expected executor port 8001, got {AGENT_PORTS['executor']}"
    )


# ---------------------------------------------------------------------------
# Test 7: SUPERVISOR_ADDRESS_BY_DOMAIN has all expected domains
# ---------------------------------------------------------------------------

def test_supervisor_address_by_domain_has_all_domains() -> None:
    """SUPERVISOR_ADDRESS_BY_DOMAIN must contain all four care domains."""
    from agents.shared.config import SUPERVISOR_ADDRESS_BY_DOMAIN

    expected = {"health", "appointment", "grocery", "financial"}
    missing = expected - set(SUPERVISOR_ADDRESS_BY_DOMAIN.keys())
    assert not missing, (
        f"SUPERVISOR_ADDRESS_BY_DOMAIN is missing domains: {missing}"
    )


# ---------------------------------------------------------------------------
# Test 8: Intent classification basics
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query,expected_intent", [
    ("what medication should I check?", "question"),
    ("schedule a caregiver slot", "scheduling"),
    ("update the grocery order", "modification"),
    ("check health status", "detection"),
])
def test_classify_intent(query: str, expected_intent: str) -> None:
    """_classify_intent must correctly classify basic query patterns.

    We run classification in a subprocess so we avoid importing agent.py in the
    test process (agent.py creates an Agent with side-effecting asyncio setup at
    module scope which interferes with the pytest event loop).
    """
    import subprocess
    script = (
        "import sys; sys.path.insert(0, '.'); "
        "from agents.executor.agent import _classify_intent; "
        f"r = _classify_intent({query!r}); "
        "print(r.intent)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(_AGENTS_DIR.parent),
    )
    assert result.returncode == 0, (
        f"Subprocess failed for query={query!r}:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    actual_intent = result.stdout.strip()
    assert actual_intent == expected_intent, (
        f"Query {query!r}: expected intent={expected_intent!r}, got {actual_intent!r}"
    )
