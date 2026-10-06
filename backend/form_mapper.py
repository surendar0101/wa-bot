"""Map Google Form responses → conversation context."""

from __future__ import annotations

import re
from typing import Any

SERVICE_MAP = {
    "investment guidance": "Investment Planning",
    "insurance guidance": "General Guidance",
    "homeloan /debt guidance": "Homeloan / Debt Guidance",
    "homeloan/debt guidance": "Homeloan / Debt Guidance",
    "income tax guidance": "Tax Planning",
}

AMOUNT_MAP = {
    "₹5,000 - ₹10,000": "₹5L – ₹10L",
    "₹10,000 - ₹20,000": "₹5L – ₹10L",
    "₹20,000 - ₹40,000": "₹10L – ₹25L",
    "above 40,000": "Above ₹50L",
    "lumpsum amount": "Above ₹50L",
}

CALL_FORMAT_FEES = {
    ("regular", "audio"): 1500,
    ("regular", "video"): 2500,
    ("premium", "audio"): 2000,
    ("premium", "video"): 3000,
}


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if raw.strip().startswith("+"):
        return "+" + digits
    return f"+{digits}" if digits else raw.strip()


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def map_form_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Build conversation context from webhook / manual test payload."""
    name = (payload.get("name") or "").strip().title()
    service_raw = payload.get("service") or payload.get("requirement") or ""
    service_key = _norm(service_raw)
    consultation_type = SERVICE_MAP.get(service_key, service_raw or "General Guidance")

    amount_raw = payload.get("investment_amount") or ""
    investment_range = AMOUNT_MAP.get(_norm(amount_raw), amount_raw or "Not specified")

    tier_raw = _norm(payload.get("consultation_tier") or "regular consultation")
    tier = "premium" if "premium" in tier_raw else "regular"
    sla_days = 5 if tier == "premium" else 10

    call_raw = _norm(payload.get("call_format") or "")
    if "video" in call_raw:
        call_format = "video"
    elif "audio" in call_raw:
        call_format = "audio"
    else:
        call_format = "audio"

    fee_amount = payload.get("fee_amount") or CALL_FORMAT_FEES.get((tier, call_format), 1500)

    return {
        "name": name,
        "phone": normalize_phone(payload.get("phone") or ""),
        "requirement": service_raw or consultation_type,
        "investment_objective": service_raw or consultation_type,
        "consultation_type": consultation_type,
        "investment_range": investment_range,
        "form_service": service_raw,
        "form_investment_amount": amount_raw,
        "call_format": call_format,
        "consultation_tier": tier,
        "fee_amount": int(fee_amount),
        "sla_days": sla_days,
        "intake_source": "google_form",
        "form_id": payload.get("form_id"),
        "form_submitted_at": payload.get("submitted_at"),
    }


def form_outreach_message(ctx: dict[str, Any]) -> str:
    name = ctx.get("name", "there")
    service = ctx.get("form_service") or ctx.get("requirement", "consultation")
    tier = "Premium" if ctx.get("consultation_tier") == "premium" else "Regular"
    call_fmt = "Video" if ctx.get("call_format") == "video" else "Audio"
    fee = ctx.get("fee_amount", 1500)
    sla = ctx.get("sla_days", 10)
    return (
        f"Hi {name}! 👋 Thanks for submitting the *Financial Consultation Form*.\n\n"
        f"We received your request:\n"
        f"• Service: *{service}*\n"
        f"• Plan: *{tier}* ({call_fmt} call · ₹{fee:,})\n"
        f"• Timeline: within *{sla} business days*\n\n"
        f"Reply *BOOK* to continue here and pick your slot, or ask any question."
    )
