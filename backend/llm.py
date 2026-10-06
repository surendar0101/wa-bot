"""Open-source LLM integration via Ollama (local models).

Models: llama3.2, mistral, phi3, gemma2, qwen2.5
Install: https://ollama.com → `ollama pull llama3.2`

Set OLLAMA_ENABLED=auto (default) to use LLM when Ollama is running.
Falls back to rule-based flow when unavailable.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = (
    "You are a customer service assistant for Finance with Harish, a financial consultancy in India. "
    "NEVER give personalized financial advice, investment recommendations, or stock/fund picks. "
    "Only help with: booking consultations, general FAQs about services/fees/hours, and intake questions. "
    "If asked for financial advice, say it will be covered during the consultation with Harish. "
    "Keep responses concise, warm, and WhatsApp-friendly. Use plain text."
)

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "90"))
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "auto").lower()

_cache: dict[str, Any] = {"available": None, "checked_at": 0.0}
CACHE_TTL = 30.0


def _ollama_configured() -> bool:
    return OLLAMA_ENABLED not in {"false", "0", "no"}


def is_ollama_available() -> bool:
    if not _ollama_configured():
        return False
    now = time.time()
    if _cache["available"] is not None and now - _cache["checked_at"] < CACHE_TTL:
        return _cache["available"]
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=1.5)
        ok = r.status_code == 200
    except Exception:
        ok = False
    _cache["available"] = ok
    _cache["checked_at"] = now
    return ok


def llm_mode() -> str:
    return "ollama" if is_ollama_available() else "rule-based"


def _chat(prompt: str, system: str | None = None) -> str | None:
    if not is_ollama_available():
        return None
    messages = [{"role": "system", "content": system or SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    try:
        r = httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content")
    except Exception:
        return None


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def analyze_message(state: str, message: str, ctx: dict, options: list[str] | None = None) -> dict | None:
    if not is_ollama_available():
        return None

    options_hint = f"\nValid options: {options}" if options else ""
    prompt = f"""Analyze customer message in consultation booking.

Step: {state}
Context: {json.dumps(ctx, default=str)}
Message: "{message}"{options_hint}

Return ONLY JSON:
{{
  "intent": "booking|faq_fee|faq_services|faq_hours|advice_request|provide_info|yes|no|other",
  "name": "full name or null",
  "requirement": "consultation need summary or null",
  "consultation_type": "Portfolio Review|Investment Planning|Retirement Planning|Tax Planning|General Guidance|null",
  "investment_range": "Below ₹5L|₹5L – ₹10L|₹10L – ₹25L|₹25L – ₹50L|Above ₹50L|null",
  "existing_investor": true|false|null,
  "investment_types": "Mutual Funds|Stocks / Equity|FD / RD|PPF / NPS|Real Estate|Gold / Bonds|Multiple types|null",
  "key_questions": "string or null",
  "matched_option": "best option match or null"
}}"""

    return _parse_json(_chat(prompt) or "")


def classify_intent(user_message: str) -> str | None:
    if not is_ollama_available():
        return None
    prompt = f'Classify: booking, faq_fee, faq_services, faq_hours, advice_request, other.\nMessage: "{user_message}"\nLabel only:'
    result = _chat(prompt)
    if not result:
        return None
    label = result.strip().lower().replace(" ", "_")
    mapping = {"fee": "faq_fee", "services": "faq_services", "hours": "faq_hours", "advice": "advice_request"}
    if label in mapping:
        return mapping[label]
    return label if label.startswith("faq_") or label in {"booking", "advice_request", "other"} else "other"


def polish_response(user_message: str, base_response: str) -> str:
    if not is_ollama_available() or not base_response:
        return base_response
    prompt = f'Customer: "{user_message}"\nRephrase for WhatsApp (keep facts identical):\n{base_response}'
    enhanced = _chat(prompt)
    return enhanced.strip() if enhanced and len(enhanced) < 800 else base_response


def smart_faq_answer(faq_key: str, user_message: str, base_answer: str) -> str:
    """FAQ replies are always template-based — no LLM."""
    return base_answer


def enhance_consultation_brief(ctx: dict, template_brief: str) -> str:
    if not is_ollama_available():
        return template_brief
    prompt = f"""Intake: {json.dumps(ctx, default=str)}

Write brief advisor prep notes for Harish (under 150 words):
- 2-line customer summary
- Topics to cover
- 3 questions to ask
NO fund/stock recommendations."""

    summary = _chat(prompt)
    if not summary:
        return template_brief
    return f"{template_brief}\n\n--- AI PREP NOTES ---\n{summary.strip()}"
