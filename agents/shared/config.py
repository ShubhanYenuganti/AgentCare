"""Environment and address configuration for mock agents."""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv
from uagents.resolver import GlobalResolver, Resolver
from uagents_core.identity import Identity

load_dotenv(find_dotenv())


def _seed(name: str, fallback: str) -> str:
    return os.getenv(name, fallback)


def _address_from_seed(seed: str) -> str:
    return Identity.from_seed(seed=seed, index=0).address


EXECUTOR_SEED = _seed("EXECUTOR_SEED_PHRASE", "macos-executor-seed-phrase")
HEALTH_SUPERVISOR_SEED = _seed(
    "HEALTH_SUPERVISOR_SEED_PHRASE", "macos-health-supervisor-seed-phrase"
)
HEALTH_WORKER_SEED = _seed("HEALTH_WORKER_SEED_PHRASE", "macos-health-worker-seed-phrase")
APPOINTMENT_SUPERVISOR_SEED = _seed(
    "APPT_SUPERVISOR_SEED_PHRASE", "macos-appointment-supervisor-seed-phrase"
)
APPOINTMENT_WORKER_SEED = _seed(
    "APPT_WORKER_SEED_PHRASE", "macos-appointment-worker-seed-phrase"
)
GROCERY_SUPERVISOR_SEED = _seed(
    "GROCERY_SUPERVISOR_SEED_PHRASE", "macos-grocery-supervisor-seed-phrase"
)
GROCERY_WORKER_SEED = _seed(
    "GROCERY_WORKER_SEED_PHRASE", "macos-grocery-worker-seed-phrase"
)
FINANCIAL_SUPERVISOR_SEED = _seed(
    "FINANCIAL_SUPERVISOR_SEED_PHRASE", "macos-financial-supervisor-seed-phrase"
)
FINANCIAL_WORKER_SEED = _seed(
    "FINANCIAL_WORKER_SEED_PHRASE", "macos-financial-worker-seed-phrase"
)
SCHEDULING_AGENT_SEED = _seed(
    "SCHEDULING_AGENT_SEED_PHRASE", "macos-scheduling-agent-seed-phrase"
)


EXECUTOR_ADDRESS = os.getenv("EXECUTOR_AGENT_ADDRESS") or _address_from_seed(EXECUTOR_SEED)
HEALTH_SUPERVISOR_ADDRESS = os.getenv("HEALTH_SUPERVISOR_ADDRESS") or _address_from_seed(
    HEALTH_SUPERVISOR_SEED
)
HEALTH_WORKER_ADDRESS = os.getenv("HEALTH_WORKER_ADDRESS") or _address_from_seed(
    HEALTH_WORKER_SEED
)
APPOINTMENT_SUPERVISOR_ADDRESS = os.getenv("APPT_SUPERVISOR_ADDRESS") or _address_from_seed(
    APPOINTMENT_SUPERVISOR_SEED
)
APPOINTMENT_WORKER_ADDRESS = os.getenv("APPT_WORKER_ADDRESS") or _address_from_seed(
    APPOINTMENT_WORKER_SEED
)
GROCERY_SUPERVISOR_ADDRESS = os.getenv("GROCERY_SUPERVISOR_ADDRESS") or _address_from_seed(
    GROCERY_SUPERVISOR_SEED
)
GROCERY_WORKER_ADDRESS = os.getenv("GROCERY_WORKER_ADDRESS") or _address_from_seed(
    GROCERY_WORKER_SEED
)
FINANCIAL_SUPERVISOR_ADDRESS = os.getenv("FINANCIAL_SUPERVISOR_ADDRESS") or _address_from_seed(
    FINANCIAL_SUPERVISOR_SEED
)
FINANCIAL_WORKER_ADDRESS = os.getenv("FINANCIAL_WORKER_ADDRESS") or _address_from_seed(
    FINANCIAL_WORKER_SEED
)
SCHEDULING_AGENT_ADDRESS = os.getenv("SCHEDULING_AGENT_ADDRESS") or _address_from_seed(
    SCHEDULING_AGENT_SEED
)

# Optional: if set, the executor sends overdue-action alerts to this Agentverse address.
# Typically the address of the care coordinator's agent on app.agentverse.ai.
ASI_ONE_AGENT_ADDRESS: str | None = os.getenv("ASI_ONE_AGENT_ADDRESS") or None

SUPERVISOR_ADDRESS_BY_DOMAIN = {
    "health": HEALTH_SUPERVISOR_ADDRESS,
    "appointment": APPOINTMENT_SUPERVISOR_ADDRESS,
    "grocery": GROCERY_SUPERVISOR_ADDRESS,
    "financial": FINANCIAL_SUPERVISOR_ADDRESS,
    "scheduling": SCHEDULING_AGENT_ADDRESS,
}


def validate_startup_config() -> list[str]:
    """Return missing required runtime env variable names."""

    required = [
        "SQLITE_DB_PATH",
        "EXECUTOR_INTERNAL_URL",
        "MOCK_API_BASE",
    ]
    missing = [key for key in required if not os.getenv(key)]
    return missing


# ── LocalFirstResolver ────────────────────────────────────────────────────────
# Maps every known local agent address → its direct localhost submit endpoint.
# This makes all intra-stack agent-to-agent messages bypass the Agentverse
# mailbox and communicate directly (sub-millisecond vs. up to 30 s per hop).
# The executor's inbound channel still uses the Agentverse mailbox (mailbox=True)
# so ASI:One can reach it, but replies and all internal routing are direct.

def _local_submit(port: int) -> str:
    return f"http://localhost:{port}/submit"

# Import AGENT_PORTS lazily to avoid circular imports
def _build_local_endpoints() -> dict[str, str]:
    from agents.shared.constants import AGENT_PORTS
    return {
        EXECUTOR_ADDRESS:               _local_submit(AGENT_PORTS["executor"]),
        HEALTH_SUPERVISOR_ADDRESS:      _local_submit(AGENT_PORTS["health_supervisor"]),
        HEALTH_WORKER_ADDRESS:          _local_submit(AGENT_PORTS["health_worker"]),
        APPOINTMENT_SUPERVISOR_ADDRESS: _local_submit(AGENT_PORTS["appointment_supervisor"]),
        APPOINTMENT_WORKER_ADDRESS:     _local_submit(AGENT_PORTS["appointment_worker"]),
        GROCERY_SUPERVISOR_ADDRESS:     _local_submit(AGENT_PORTS["grocery_supervisor"]),
        GROCERY_WORKER_ADDRESS:         _local_submit(AGENT_PORTS["grocery_worker"]),
        FINANCIAL_SUPERVISOR_ADDRESS:   _local_submit(AGENT_PORTS["financial_supervisor"]),
        FINANCIAL_WORKER_ADDRESS:       _local_submit(AGENT_PORTS["financial_worker"]),
        SCHEDULING_AGENT_ADDRESS:       _local_submit(AGENT_PORTS["scheduling_agent"]),
    }


class LocalFirstResolver(Resolver):
    """
    Resolves known stack agents to their direct localhost endpoints, bypassing
    the Agentverse almanac round-trip entirely.  Falls through to GlobalResolver
    for any external address (e.g. the ASI:One platform agent).

    Latency impact:
      Before: each intra-stack hop  ≈ 1–30 s  (Agentverse mailbox poll cycle)
      After:  each intra-stack hop  < 5 ms    (direct localhost HTTP)
    """

    def __init__(self) -> None:
        self._local: dict[str, str] = _build_local_endpoints()
        self._global = GlobalResolver()

    async def resolve(self, destination: str) -> tuple[str | None, list[str]]:
        endpoint = self._local.get(destination)
        if endpoint:
            return destination, [endpoint]
        return await self._global.resolve(destination)
