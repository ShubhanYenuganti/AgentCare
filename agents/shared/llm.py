"""LLM wrappers for Claude API interactions."""

from __future__ import annotations

import json
import os

import anthropic


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is required for Claude API calls")
    return anthropic.Anthropic()


def _extract_text(content: list[object]) -> str:
    if not content:
        return ""
    block = content[0]
    return getattr(block, "text", "") or ""


def call_claude(system: str, user: str, max_tokens: int = 1000) -> str:
    response = _client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return _extract_text(response.content)


def call_claude_json(system: str, user: str, max_tokens: int = 1000) -> dict:
    text = call_claude(system, user, max_tokens).strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def call_claude_vision(b64_image: str, media_type: str, prompt: str) -> dict:
    response = _client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = _extract_text(response.content).strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def build_system_prompt(base_prompt: str, org_context: dict, domain: str) -> str:
    org_section = f"""Organisation context:
- Care philosophy: {org_context.get('care_philosophy', 'Not specified')}
- {domain.capitalize()} protocol: {org_context.get(f'{domain}_protocol', 'Standard protocol')}
- Escalation chain: {org_context.get('escalation_chain', 'Caregiver -> Admin')}
- Escalation lead: {org_context.get('escalation_lead', 'Admin')}

Apply this context when drafting emails, assessing risk, and framing actions.
"""
    return f"{org_section}\n{base_prompt}"
