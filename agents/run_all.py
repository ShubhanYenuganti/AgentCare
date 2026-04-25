"""Run all scaffold agents and the FastAPI server as separate subprocesses."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Final

from agents.shared.config import validate_startup_config

AGENT_MODULES: Final[list[str]] = [
    "agents.executor.agent",
    "agents.health.supervisor",
    "agents.health.worker",
    "agents.appointment.supervisor",
    "agents.appointment.worker",
    "agents.grocery.supervisor",
    "agents.grocery.worker",
    "agents.financial.supervisor",
    "agents.financial.worker",
    "agents.scheduling.agent",
]

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = os.getenv("API_PORT", "8000")


def _spawn_all() -> list[subprocess.Popen]:
    processes: list[subprocess.Popen] = []

    # FastAPI server — must be first so agents that call it on startup find it ready
    api_cmd = [
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--host", API_HOST,
        "--port", API_PORT,
    ]
    processes.append(subprocess.Popen(api_cmd))
    print(f"[run_all] API server started on http://{API_HOST}:{API_PORT}", flush=True)

    # Agent processes
    for module in AGENT_MODULES:
        processes.append(subprocess.Popen([sys.executable, "-m", module]))

    return processes


def _shutdown(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    missing = validate_startup_config()
    if missing:
        print("Missing required env vars:", ", ".join(missing))
        return 1

    processes = _spawn_all()
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        _shutdown(processes)
        return 130
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    raise SystemExit(main())
