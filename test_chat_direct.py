"""
Direct ChatMessage injection test — bypasses ASI:One entirely.

Sends a signed ChatMessage envelope directly to the executor's Agentverse mailbox
using a fresh test-agent identity. Run while the executor is running:

    python3 test_chat_direct.py

Then watch the executor logs for:
    Received ChatMessage sender=...

If the log appears  → executor CAN receive ChatMessages via mailbox → problem is ASI:One not submitting
If the log is absent → something rejects the envelope before the executor sees it
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import aiohttp
from uagents import Model
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.envelope import Envelope
from uagents_core.identity import Identity

# ── config ────────────────────────────────────────────────────────────────────
EXECUTOR_ADDRESS = "agent1qgs7zw0ce49c5k626tf8cag5wcjan7hhrpeguwlg836kkyjr69ypuwhms84"
MAILBOX_SUBMIT   = "https://agentverse.ai/v2/agents/mailbox/submit"

# ── build the ChatMessage ─────────────────────────────────────────────────────
chat_msg = ChatMessage(
    timestamp=datetime.now(tz=timezone.utc),
    msg_id=uuid4(),
    content=[TextContent(type="text", text="direct test: health medication refill")],
)
chat_msg_json = chat_msg.model_dump_json()
chat_digest   = Model.build_schema_digest(ChatMessage)
proto_digest  = chat_protocol_spec.digest          # proto:30a801ed...

print(f"ChatMessage digest : {chat_digest}")
print(f"Protocol digest    : {proto_digest}")
print(f"Target address     : {EXECUTOR_ADDRESS}")
print()

# ── create a sender identity using the health-supervisor seed so it IS in almanac ──
# Using a registered agent seed means the executor can resolve and reply back.
import os, dotenv
dotenv.load_dotenv(dotenv.find_dotenv())
_sender_seed = os.getenv("HEALTH_SUPERVISOR_SEED_PHRASE", "12wUl9HA7wPxHTtist2fDf7mKm1z59vFpfqlwBTC-IM")
sender_identity = Identity.from_seed(seed=_sender_seed, index=0)
sender_address  = sender_identity.address
print(f"Sender address     : {sender_address}  (health-supervisor — registered in almanac)")
print()

# ── build and sign the envelope ───────────────────────────────────────────────
session = uuid4()
env = Envelope(
    version=1,
    sender=sender_address,
    target=EXECUTOR_ADDRESS,
    session=session,
    schema_digest=chat_digest,
    protocol_digest=proto_digest,
)
env.encode_payload(chat_msg_json)
env.sign(sender_identity)

payload = {
    "version": env.version,
    "sender": env.sender,
    "target": env.target,
    "session": str(env.session),
    "schema_digest": env.schema_digest,
    "protocol_digest": env.protocol_digest,
    "payload": env.payload,
    "expires": env.expires,
    "nonce": env.nonce,
    "signature": env.signature,
}

# ── submit ────────────────────────────────────────────────────────────────────
async def main() -> None:
    print(f"Submitting to: {MAILBOX_SUBMIT}")
    async with aiohttp.ClientSession() as session_http:
        async with session_http.post(
            MAILBOX_SUBMIT,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            status = resp.status
            body   = await resp.text()
            print(f"HTTP {status}: {body}")

    if status == 200:
        print()
        print("✓ Submission accepted. Watch executor logs for:")
        print("  Received ChatMessage sender=...")
        print()
        print("If nothing appears in ~5 seconds, the executor is NOT polling this mailbox,")
        print("or the envelope was accepted but silently dropped by Agentverse.")
    else:
        print()
        print("✗ Submission rejected. This means there is a mailbox submission issue.")

asyncio.run(main())
