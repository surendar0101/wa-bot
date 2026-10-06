"""Workflow orchestrator — rule-based state machine + Ollama NLU when available."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from llm import analyze_message, enhance_consultation_brief, smart_faq_answer

FAQ_RESPONSES = {
    "fee": (
        "Consultation fees start at ₹999 for a 30-minute session. "
        "Portfolio review and investment planning sessions are priced based on complexity."
    ),
    "services": (
        "Finance with Harish offers Portfolio Review, Investment Planning, "
        "Retirement Planning, Tax-efficient Investing, and General Financial Guidance."
    ),
    "hours": "Consultations are available Monday–Saturday, 10 AM to 7 PM IST.",
    "advice": (
        "Personalized financial advice is provided by Harish during your consultation — "
        "I'm here to help with booking and general information."
    ),
}

ADVICE_MARKERS = (
    "rebalance", "over-exposed", "over exposed", "overexposed",
    "mid-cap", "mid cap", "large-cap", "small-cap",
    "should i sell", "should i buy", "should i rebalance", "should i invest",
    "which fund", "which stock", "stock tip", "recommend",
    "too much", "too exposed", "am i over", "allocation",
    "advice on", "advise me", "your opinion", "hold or sell",
    "good time to", "better option", "where should i put",
)

CONSULTATION_TYPES = [
    "Portfolio Review",
    "Investment Planning",
    "Retirement Planning",
    "Tax Planning",
    "General Guidance",
]

SERVICE_OPTIONS = [
    "Portfolio Review",
    "Investment Planning",
    "Retirement Planning",
    "Tax-efficient Investing",
    "General Financial Guidance",
]

SERVICE_TO_CONSULTATION = {
    "Portfolio Review": "Portfolio Review",
    "Investment Planning": "Investment Planning",
    "Retirement Planning": "Retirement Planning",
    "Tax-efficient Investing": "Tax Planning",
    "General Financial Guidance": "General Guidance",
}

INVESTMENT_RANGES = [
    "Below ₹5L",
    "₹5L – ₹10L",
    "₹10L – ₹25L",
    "₹25L – ₹50L",
    "Above ₹50L",
]

EXISTING_INVESTMENT_TYPES = [
    "Mutual Funds",
    "Stocks / Equity",
    "FD / RD",
    "PPF / NPS",
    "Real Estate",
    "Gold / Bonds",
    "Multiple types",
]

INVESTMENT_DETAIL_OPTIONS = [
    "Plain text message",
    "Upload PDF",
    "Upload screenshot",
    "Skip for now",
]

FAQ_INTERRUPT_STATES = {
    "greeting", "collect_name", "collect_requirement", "qualification",
    "collect_consultation_type", "collect_investment_range", "collect_existing_investor",
    "collect_investment_types", "collect_investment_details_method",
    "collect_investment_details_text", "await_investment_upload", "faq_mode",
}

# FAQ + general Q&A — rule/templates only, no Ollama.
BOOKING_INTAKE_STATES = frozenset({
    "collect_name",
    "collect_email",
    "collect_requirement",
    "collect_consultation_type",
    "collect_investment_range",
    "collect_existing_investor",
    "collect_investment_types",
    "collect_investment_details_method",
    "collect_investment_details_text",
    "await_investment_upload",
})

NO_LLM_STATES = BOOKING_INTAKE_STATES | frozenset({
    "greeting",
    "faq_mode",
    "qualification",
    "collect_key_questions",
    "show_slots",
    "await_slot_selection",
    "payment",
    "confirmed",
})

RESUME_PROMPTS = {
    "collect_name": "May I have your *full name*?",
    "collect_email": "What's your *email address*? (for Meet invite & calendar)",
    "collect_requirement": "What would you like to discuss? Pick a service or type your own.",
    "collect_consultation_type": "Which type of consultation would you like?",
    "collect_investment_range": "What's your approximate investment range?",
    "collect_existing_investor": "Do you currently have existing investments?",
    "collect_investment_types": "What do you currently invest in?",
    "collect_investment_details_method": "How would you like to share your investment details?",
    "collect_investment_details_text": "Describe your current holdings (funds, amounts, platforms…)",
    "await_investment_upload": "Please upload your file using the button below.",
    "collect_key_questions": "Any specific questions for Harish? (or tap Skip)",
    "await_slot_selection": "Please tap a slot below to book.",
    "payment": "Tap *Pay Now* below to confirm (demo — no real charge).",
}

STATE_OPTIONS = {
    "qualification": (["Yes, book consultation", "No, just a general query"], "yes_no"),
    "collect_consultation_type": (CONSULTATION_TYPES, "list"),
    "collect_investment_range": (INVESTMENT_RANGES, "list"),
    "collect_existing_investor": (["Yes, I have investments", "No, I'm just starting"], "yes_no"),
    "collect_investment_types": (EXISTING_INVESTMENT_TYPES, "list"),
    "collect_investment_details_method": (INVESTMENT_DETAIL_OPTIONS, "list"),
    "collect_key_questions": (["Skip for now"], "chips"),
    "collect_requirement": (SERVICE_OPTIONS, "list"),
}


@dataclass
class BotResponse:
    message: str
    state: str
    options: list[str] | None = None
    option_style: str = "list"
    qualified_for_booking: bool = False
    escalate: bool = False
    show_upload: bool = False
    upload_accept: str = ".pdf,.png,.jpg,.jpeg,.webp"


def _detect_faq_intent(text: str) -> str | None:
    t = text.lower()
    if any(w in t for w in ["fee", "cost", "price", "charge", "how much"]):
        return "fee"
    if any(w in t for w in ["service", "offer", "what do you", "help with"]):
        return "services"
    if any(w in t for w in ["hour", "time", "when open", "available day"]):
        return "hours"
    if _is_advice_request(text):
        return "advice"
    return None


def _is_advice_request(text: str) -> bool:
    t = text.lower()
    if any(m in t for m in ADVICE_MARKERS):
        return True
    if any(w in t for w in ["recommend", "should i invest", "which fund", "stock tip", "advice on"]):
        return True
    return False


def _wants_booking(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in ["book", "consult", "appointment", "schedule", "slot", "meeting", "call with harish"])


def _match_option(text: str, options: list[str]) -> str | None:
    t = text.strip().lower()
    for i, opt in enumerate(options):
        if opt.lower() in t or t == str(i + 1):
            return opt
    return None


def _yes_no(text: str) -> bool | None:
    t = text.lower().strip()
    if t in {"yes", "y", "yeah", "sure", "ok", "okay", "haan", "ha", "correct"} or "book" in t:
        return True
    if t in {"no", "n", "nope", "nah", "nahi"} or "general query" in t:
        return False
    return None


def _has_investment_details(ctx: dict) -> bool:
    if ctx.get("investment_details_text") or ctx.get("investment_detail_files"):
        return True
    method = ctx.get("investment_details_method", "")
    return method not in ("", "Not provided", "Skipped", "Plain text (empty)")


def _needs_holdings_to_answer(msg: str) -> bool:
    t = msg.lower()
    if _is_advice_request(msg):
        return True
    markers = (
        "diversif", "correct", "portfolio", "holdings", "allocation",
        "my investment", "investments is", "investments are", "investment is",
        "review my", "check my", "on track", "properly invested",
    )
    return any(m in t for m in markers)


def _validate_email(text: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", text.strip()))


def _resolve_faq(msg: str) -> str | None:
    return _detect_faq_intent(msg)


def _apply_llm_fields(ctx: dict, analysis: dict) -> None:
    if analysis.get("name"):
        ctx["name"] = str(analysis["name"]).title()
    if analysis.get("requirement"):
        ctx["requirement"] = analysis["requirement"]
        ctx["investment_objective"] = analysis["requirement"]
    if analysis.get("consultation_type") in CONSULTATION_TYPES:
        ctx["consultation_type"] = analysis["consultation_type"]
    if analysis.get("investment_range") in INVESTMENT_RANGES:
        ctx["investment_range"] = analysis["investment_range"]
    if analysis.get("existing_investor") is not None:
        ctx["existing_investor"] = bool(analysis["existing_investor"])
    if analysis.get("investment_types"):
        ctx["existing_investment_types"] = analysis["investment_types"]
    if analysis.get("key_questions"):
        ctx["key_questions"] = analysis["key_questions"]
    if analysis.get("email") and _validate_email(str(analysis["email"])):
        ctx["email"] = str(analysis["email"]).strip().lower()


def _format_investment_details(ctx: dict) -> str:
    method = ctx.get("investment_details_method", "Not provided")
    text = ctx.get("investment_details_text", "")
    files = ctx.get("investment_detail_files") or []
    parts = [f"Method: {method}"]
    if text:
        parts.append(f"Customer notes:\n{text}")
    if files:
        parts.append("Uploaded files:")
        for f in files:
            parts.append(f"  • {f.get('name')} ({f.get('type', 'file')})")
    if method == "Not provided" or (not text and not files):
        return "Not provided"
    return "\n".join(parts)


def generate_consultation_brief(ctx: dict[str, Any]) -> str:
    name = ctx.get("name", "Customer")
    ctype = ctx.get("consultation_type", "General")
    inv_range = ctx.get("investment_range", "Not specified")
    existing = "Yes" if ctx.get("existing_investor") else "No"
    inv_types = ctx.get("existing_investment_types", "N/A" if ctx.get("existing_investor") else "None")
    objective = ctx.get("investment_objective") or ctx.get("requirement", "Not specified")
    questions = ctx.get("key_questions", "None specified")
    inv_details = _format_investment_details(ctx)

    template = f"""CONSULTATION BRIEF
━━━━━━━━━━━━━━━━━━

Customer: {name}
Consultation: {ctype}

Objective:
{objective}

Investment Range: {inv_range}
Existing Investor: {existing}
Current Investments: {inv_types}

Investment Details (pre-call):
{inv_details}

Key Questions:
{questions}

⚠️ Advisory Note: Provide personalized advice during the call only."""

    return enhance_consultation_brief(ctx, template)


class ConversationEngine:
    GREETING = (
        "Hello! 👋 Welcome to *Finance with Harish*.\n\n"
        "I'm your consultation assistant — I can help you book a session with Harish "
        "or answer questions about our services.\n\n"
        "How may I help you today?"
    )

    def _options_for(self, state: str) -> BotResponse | None:
        if state not in STATE_OPTIONS:
            return None
        opts, style = STATE_OPTIONS[state]
        return BotResponse("", state, options=opts, option_style=style)

    def resume_ui(self, state: str, ctx: dict) -> BotResponse:
        """UI hints when reopening chat mid-flow (no state transition)."""
        if state == "post_form_followup":
            return BotResponse("", state, options=["BOOK"], option_style="chips")
        if state == "faq_mode":
            return BotResponse("", state, options=["Book consultation"], option_style="chips")
        if state == "await_investment_upload":
            return BotResponse(
                "",
                state,
                options=["Skip for now"],
                option_style="chips",
                show_upload=True,
            )
        if state == "collect_investment_details_text":
            return BotResponse("", state, options=["Continue", "Skip for now"], option_style="chips")
        if state == "collect_investment_details_method":
            return BotResponse("", state, options=INVESTMENT_DETAIL_OPTIONS, option_style="list")
        opt = self._options_for(state)
        if opt:
            return opt
        return BotResponse("", state)

    def _advice_intake_response(self, msg: str, ctx: dict) -> BotResponse:
        ctx["key_questions"] = msg
        ctx.setdefault("requirement", "Portfolio / investment guidance")
        ctx.setdefault("investment_objective", msg)
        ctx.setdefault("consultation_type", "Portfolio Review")
        ctx["existing_investor"] = True
        return BotResponse(
            "That's a great question for Harish — I can't give personalised advice here, "
            "but if you share your *current holdings* I'll forward them along with your question "
            "so he can review everything before advising you.\n\n"
            "How would you like to share your investment details?",
            "collect_investment_details_method",
            options=INVESTMENT_DETAIL_OPTIONS,
            option_style="list",
        )

    def _faq_interrupt(self, msg: str, state: str, ctx: dict) -> BotResponse | None:
        # User is answering the optional pre-call questions step — never treat as FAQ/advice.
        if state == "collect_key_questions":
            return None
        faq = _resolve_faq(msg)
        if not faq:
            return None

        if faq == "advice":
            return self._advice_intake_response(msg, ctx)

        answer = smart_faq_answer(faq, msg, FAQ_RESPONSES[faq])

        if faq == "services":
            target = "collect_requirement" if ctx.get("name") else "greeting"
            prefix = f"Thanks, {ctx['name']}! " if ctx.get("name") else ""
            return BotResponse(f"{prefix}Which area interests you?", target, options=SERVICE_OPTIONS, option_style="list")

        if state == "greeting":
            return BotResponse(
                f"{answer}\n\nWould you like to book a consultation?",
                "qualification",
                options=["Yes, book consultation", "No, just a general query"],
                option_style="yes_no",
            )

        if state == "faq_mode":
            return BotResponse(
                f"{answer}\n\nAnything else I can help with?",
                "faq_mode",
                options=["Book consultation"],
                option_style="chips",
            )

        resume = RESUME_PROMPTS.get(state, "How would you like to continue?")
        name = ctx.get("name", "")
        prefix = f"{answer}\n\nThanks, {name}! " if name else f"{answer}\n\n"
        opts = SERVICE_OPTIONS if state == "collect_requirement" else None
        style = "list" if opts else "chips" if state in STATE_OPTIONS else "list"
        state_opts = STATE_OPTIONS.get(state)
        if state_opts and not opts:
            opts, style = state_opts
        return BotResponse(f"{prefix}{resume}", state, options=opts, option_style=style)

    def _llm_deviation_fallback(self, state: str, msg: str, ctx: dict) -> BotResponse | None:
        """Ollama only when user deviates from predefined options (free-text, typos, etc.)."""
        opts = STATE_OPTIONS.get(state, (None,))[0]
        analysis = analyze_message(state, msg, ctx, opts)
        if not analysis:
            return None

        _apply_llm_fields(ctx, analysis)

        matched = analysis.get("matched_option")
        if matched and opts and matched in opts:
            handler = getattr(self, f"_handle_{state}", None)
            if handler:
                return handler(matched, ctx)

        if state == "collect_name" and ctx.get("name"):
            return self._after_name(ctx)

        if state == "collect_requirement":
            matched = analysis.get("matched_option") or _match_option(msg, SERVICE_OPTIONS)
            if matched:
                ctx["consultation_type"] = SERVICE_TO_CONSULTATION.get(matched, matched)
                ctx["requirement"] = matched
                ctx["investment_objective"] = matched
                return self._start_plan_intake(ctx, matched)

        if state == "collect_consultation_type" and ctx.get("consultation_type"):
            return self._handle_collect_consultation_type(ctx["consultation_type"], ctx)

        if state == "collect_investment_range" and ctx.get("investment_range"):
            return self._handle_collect_investment_range(ctx["investment_range"], ctx)

        if state == "collect_existing_investor" and ctx.get("existing_investor") is not None:
            yn = "Yes, I have investments" if ctx["existing_investor"] else "No, I'm just starting"
            return self._handle_collect_existing_investor(yn, ctx)

        if state == "collect_investment_types" and ctx.get("existing_investment_types"):
            return self._handle_collect_investment_types(ctx["existing_investment_types"], ctx)

        return None

    def _start_plan_intake(self, ctx: dict, plan_label: str | None = None) -> BotResponse:
        """Predefined intake steps after plan is known — same default flow for all plans."""
        label = plan_label or ctx.get("requirement") or ctx.get("consultation_type") or "your consultation"
        return BotResponse(
            f"Got it — *{label}*.\n\nWhat's your approximate investment range?",
            "collect_investment_range",
            options=INVESTMENT_RANGES,
            option_style="list",
        )

    def _go_to_booking_slots(self, ctx: dict, ack_message: str) -> BotResponse:
        if not ctx.get("name"):
            ctx["pending_slot_message"] = ack_message
            return BotResponse("May I have your *full name*?", "collect_name")
        if not ctx.get("email"):
            ctx["pending_slot_message"] = ack_message
            return BotResponse(
                "What's your *email address*? We'll send a Google Meet link and calendar invite.",
                "collect_email",
            )
        return BotResponse(ack_message, "show_slots", qualified_for_booking=True)

    def _after_name(self, ctx: dict) -> BotResponse:
        name = ctx["name"]
        if ctx.get("consultation_type") or ctx.get("requirement"):
            label = ctx.get("requirement") or ctx.get("consultation_type")
            return BotResponse(
                f"Thanks, {name}! 🙏 You're booking *{label}*.\n\nWhat's your approximate investment range?",
                "collect_investment_range",
                options=INVESTMENT_RANGES,
                option_style="list",
            )
        return BotResponse(
            f"Thanks, {name}! 🙏 What would you like to discuss?",
            "collect_requirement",
            options=SERVICE_OPTIONS,
            option_style="list",
        )

    def process(self, state: str, user_message: str, context: dict[str, Any]) -> BotResponse:
        msg = user_message.strip()
        if not msg:
            return BotResponse("Please send a message so I can assist you.", state)

        faq_response = self._faq_interrupt(msg, state, context)
        if faq_response:
            return faq_response

        if _wants_booking(msg) and state == "greeting":
            return BotResponse("Great! May I have your *full name*?", "collect_name")

        handler = getattr(self, f"_handle_{state}", None)
        if handler:
            result = handler(msg, context)
            if result.state == state and state in BOOKING_INTAKE_STATES:
                llm_result = self._llm_deviation_fallback(state, msg, context)
                if llm_result and llm_result.state != state:
                    return llm_result
            return result
        return BotResponse(self.GREETING, "greeting")

    def _handle_post_form_followup(self, msg: str, ctx: dict) -> BotResponse:
        t = msg.lower().strip()
        if t in {"book", "yes", "continue", "ok", "okay", "start"} or _wants_booking(msg):
            ctx["form_followup_started"] = True
            return BotResponse(
                f"Great, {ctx.get('name', 'there')}! Your form details are already on file.\n\n"
                "Do you currently have any existing investments?",
                "collect_existing_investor",
                options=["Yes, I have investments", "No, I'm just starting"],
                option_style="yes_no",
            )
        if _is_advice_request(msg):
            return self._advice_intake_response(msg, ctx)
        faq = _resolve_faq(msg)
        if faq and faq != "advice":
            answer = smart_faq_answer(faq, msg, FAQ_RESPONSES[faq])
            return BotResponse(
                f"{answer}\n\nReply *BOOK* when you're ready to schedule.",
                "post_form_followup",
                options=["BOOK"],
                option_style="chips",
            )
        return BotResponse(
            "Reply *BOOK* to continue scheduling, or ask about fees/services.",
            "post_form_followup",
            options=["BOOK"],
            option_style="chips",
        )

    def _handle_greeting(self, msg: str, ctx: dict) -> BotResponse:
        chosen = _match_option(msg, SERVICE_OPTIONS)
        if not chosen:
            for svc in SERVICE_OPTIONS:
                if svc.lower() in msg.lower():
                    chosen = svc
                    break
        if chosen:
            ctx.update(requirement=chosen, investment_objective=chosen, consultation_type=SERVICE_TO_CONSULTATION.get(chosen, chosen))
            return BotResponse(f"Great choice — *{chosen}*! May I have your *full name*?", "collect_name")
        if _wants_booking(msg) or any(w in msg.lower() for w in ["retire", "portfolio", "invest", "tax", "sip", "mutual", "planning"]):
            return BotResponse("Let's get you scheduled! May I have your *full name*?", "collect_name")
        if _is_advice_request(msg):
            return self._advice_intake_response(msg, ctx)
        return BotResponse(self.GREETING, "greeting")

    def _handle_collect_name(self, msg: str, ctx: dict) -> BotResponse:
        if len(msg) < 2:
            return BotResponse("Please enter your full name.", "collect_name")
        ctx["name"] = msg.title()
        if pending := ctx.pop("pending_slot_message", None):
            ctx["pending_slot_message"] = pending
        return BotResponse(
            f"Thanks, {ctx['name']}! What's your *email address*? (for Meet invite & calendar)",
            "collect_email",
        )

    def _handle_collect_email(self, msg: str, ctx: dict) -> BotResponse:
        email = msg.strip().lower()
        if not _validate_email(email):
            return BotResponse("Please enter a valid email address (e.g. you@gmail.com).", "collect_email")
        ctx["email"] = email
        if ctx.pop("awaiting_email_for_payment", False) and ctx.get("appointment_id"):
            return BotResponse(
                "Email saved ✓ Tap *Pay Now* below to complete booking and receive your Meet + calendar invite.",
                "payment",
            )
        if pending := ctx.pop("pending_slot_message", None):
            return BotResponse(pending, "show_slots", qualified_for_booking=True)
        return self._after_name(ctx)

    def _handle_collect_requirement(self, msg: str, ctx: dict) -> BotResponse:
        chosen = _match_option(msg, SERVICE_OPTIONS) or _match_option(msg, CONSULTATION_TYPES)
        if not chosen:
            for svc in SERVICE_OPTIONS:
                if svc.lower() in msg.lower():
                    chosen = svc
                    break
        if not chosen:
            return BotResponse(
                "Please pick a service or type what you'd like to discuss:",
                "collect_requirement",
                options=SERVICE_OPTIONS,
                option_style="list",
            )
        ctx["requirement"] = chosen
        ctx["investment_objective"] = chosen
        ctx["consultation_type"] = SERVICE_TO_CONSULTATION.get(chosen, chosen)
        return self._start_plan_intake(ctx, chosen)

    def _handle_qualification(self, msg: str, ctx: dict) -> BotResponse:
        yn = _yes_no(msg)
        if yn is False:
            return BotResponse(
                "No problem! Ask me anything about services, fees, or hours.",
                "faq_mode",
                options=["Book consultation"],
                option_style="chips",
            )
        if yn is True:
            if not ctx.get("name"):
                return BotResponse("Great! May I have your *full name*?", "collect_name")
            if ctx.get("consultation_type") or ctx.get("requirement"):
                return self._start_plan_intake(ctx)
            return BotResponse(
                "Which type of consultation?",
                "collect_consultation_type",
                options=CONSULTATION_TYPES,
                option_style="list",
            )
        return BotResponse(
            "Would you like to book?",
            "qualification",
            options=["Yes, book consultation", "No, just a general query"],
            option_style="yes_no",
        )

    def _handle_collect_consultation_type(self, msg: str, ctx: dict) -> BotResponse:
        chosen = _match_option(msg, CONSULTATION_TYPES)
        if not chosen:
            return BotResponse("Please select a consultation type:", "collect_consultation_type", options=CONSULTATION_TYPES, option_style="list")
        ctx["consultation_type"] = chosen
        return BotResponse("What's your approximate investment range?", "collect_investment_range", options=INVESTMENT_RANGES, option_style="list")

    def _handle_collect_investment_range(self, msg: str, ctx: dict) -> BotResponse:
        chosen = _match_option(msg, INVESTMENT_RANGES)
        if not chosen:
            return BotResponse("Please pick an investment range:", "collect_investment_range", options=INVESTMENT_RANGES, option_style="list")
        ctx["investment_range"] = chosen
        return BotResponse(
            "Do you currently have any existing investments?",
            "collect_existing_investor",
            options=["Yes, I have investments", "No, I'm just starting"],
            option_style="yes_no",
        )

    def _handle_collect_existing_investor(self, msg: str, ctx: dict) -> BotResponse:
        t = msg.lower()
        if t.startswith("yes") or "have investment" in t:
            ctx["existing_investor"] = True
            return BotResponse("What do you currently invest in?", "collect_investment_types", options=EXISTING_INVESTMENT_TYPES, option_style="list")
        if t.startswith("no") or "just starting" in t:
            ctx["existing_investor"] = False
            ctx["existing_investment_types"] = "None"
            return BotResponse(
                "Got it — you're just getting started!\n\n"
                "If you have any current holdings (even a small SIP), sharing them helps Harish prepare. "
                "How would you like to share your investment details?",
                "collect_investment_details_method",
                options=INVESTMENT_DETAIL_OPTIONS,
                option_style="list",
            )
        return BotResponse("Do you have existing investments?", "collect_existing_investor", options=["Yes, I have investments", "No, I'm just starting"], option_style="yes_no")

    def _handle_collect_investment_types(self, msg: str, ctx: dict) -> BotResponse:
        chosen = _match_option(msg, EXISTING_INVESTMENT_TYPES)
        if not chosen:
            for opt in EXISTING_INVESTMENT_TYPES:
                if opt.lower() in msg.lower():
                    chosen = opt
                    break
        if not chosen:
            return BotResponse("Please select:", "collect_investment_types", options=EXISTING_INVESTMENT_TYPES, option_style="list")
        ctx["existing_investment_types"] = chosen
        return BotResponse(
            f"Noted — you invest in *{chosen}*.\n\n"
            "To help Harish prepare, you can share your current holdings now. How would you like to provide them?",
            "collect_investment_details_method",
            options=INVESTMENT_DETAIL_OPTIONS,
            option_style="list",
        )

    def _handle_collect_investment_details_method(self, msg: str, ctx: dict) -> BotResponse:
        t = msg.lower()
        if "plain text" in t or t == "plain text message":
            ctx["investment_details_method"] = "Plain text"
            return BotResponse(
                "Please describe your current investments — fund names, approximate amounts, platforms, etc.\n\n"
                "You can send multiple messages.",
                "collect_investment_details_text",
            )
        if "pdf" in t:
            ctx["investment_details_method"] = "PDF upload"
            ctx.setdefault("investment_detail_files", [])
            return BotResponse(
                "Please upload your portfolio statement or CAS PDF using the button below.\n\n"
                "You can add a short note in chat after uploading (optional).",
                "await_investment_upload",
                show_upload=True,
                upload_accept=".pdf",
            )
        if "screenshot" in t:
            ctx["investment_details_method"] = "Screenshot upload"
            ctx.setdefault("investment_detail_files", [])
            return BotResponse(
                "Please upload a screenshot of your holdings (broker app, MF statement, etc.).",
                "await_investment_upload",
                show_upload=True,
                upload_accept=".png,.jpg,.jpeg,.webp",
            )
        if "skip" in t:
            ctx["investment_details_method"] = "Skipped"
            return BotResponse(
                "No problem — you can discuss holdings directly with Harish on the call.\n\n"
                "Any specific questions to address? (Optional)",
                "collect_key_questions",
                options=["Skip for now"],
                option_style="chips",
            )
        return BotResponse(
            "How would you like to share your investment details?",
            "collect_investment_details_method",
            options=INVESTMENT_DETAIL_OPTIONS,
            option_style="list",
        )

    def _handle_collect_investment_details_text(self, msg: str, ctx: dict) -> BotResponse:
        if msg.lower() in {"done", "that's all", "thats all", "next", "continue"}:
            if not ctx.get("investment_details_text"):
                ctx["investment_details_method"] = "Plain text (empty)"
            return self._after_investment_details(ctx)
        existing = ctx.get("investment_details_text", "")
        ctx["investment_details_text"] = f"{existing}\n{msg}".strip() if existing else msg
        ctx["investment_details_method"] = "Plain text"
        return BotResponse(
            "Thanks — noted. Send more details or tap *Continue* when done.",
            "collect_investment_details_text",
            options=["Continue"],
            option_style="chips",
        )

    def _handle_await_investment_upload(self, msg: str, ctx: dict) -> BotResponse:
        t = msg.lower()
        if t in {"done", "continue", "next", "skip"} or "continue" in t:
            if ctx.get("investment_detail_files"):
                return self._after_investment_details(ctx)
            return BotResponse(
                "Please upload a file first, or tap Skip for now.",
                "await_investment_upload",
                show_upload=True,
                options=["Skip for now"],
                option_style="chips",
            )
        # Optional caption/note with upload
        note = ctx.get("investment_details_text", "")
        ctx["investment_details_text"] = f"{note}\n{msg}".strip() if note else msg
        return BotResponse(
            "Got your note. Upload another file or tap *Continue*.",
            "await_investment_upload",
            show_upload=True,
            options=["Continue", "Skip for now"],
            option_style="chips",
        )

    def record_upload(self, ctx: dict, filename: str, file_type: str, saved_path: str) -> BotResponse:
        ctx.setdefault("investment_detail_files", [])
        ctx["investment_detail_files"].append(
            {"name": filename, "type": file_type, "path": saved_path}
        )
        return BotResponse(
            f"Thanks for sharing *{filename}*! 🙏\n\n"
            f"We've received your input and will share these details with Harish's team before your consultation.\n\n"
            f"Upload another file or tap *Continue* when done.",
            "await_investment_upload",
            show_upload=True,
            options=["Continue", "Skip for now"],
            option_style="chips",
        )

    def _after_investment_details(self, ctx: dict) -> BotResponse:
        summary = _format_investment_details(ctx)
        ctx["investment_details_summary"] = summary
        existing_q = ctx.get("key_questions")
        if existing_q and existing_q != "None specified":
            return self._go_to_booking_slots(
                ctx,
                f"Investment details saved ✓\n\n"
                f"I've noted your question for Harish:\n*\"{existing_q}\"*\n\n"
                f"He'll review your holdings and advise you on the call.\n\n"
                f"Let's pick a time for your consultation.",
            )
        return BotResponse(
            "Investment details saved — Harish will review these before your call.\n\n"
            "Any specific questions for him? (Optional)",
            "collect_key_questions",
            options=["Skip for now"],
            option_style="chips",
        )

    def _handle_collect_key_questions(self, msg: str, ctx: dict) -> BotResponse:
        if msg.lower() in {"skip", "skip for now"}:
            ctx["key_questions"] = "None specified"
            return self._go_to_booking_slots(
                ctx, "No problem! Let's find a convenient time for your consultation."
            )

        ctx["key_questions"] = msg

        if _needs_holdings_to_answer(msg) and not _has_investment_details(ctx):
            if any(w in msg.lower() for w in ("my investment", "diversif", "portfolio", "holdings", "allocation")):
                ctx["existing_investor"] = True
            return BotResponse(
                f"Noted — I'll share this with Harish:\n*\"{msg}\"*\n\n"
                "To review this properly, please share your current holdings. "
                "How would you like to provide them?",
                "collect_investment_details_method",
                options=INVESTMENT_DETAIL_OPTIONS,
                option_style="list",
            )

        return self._go_to_booking_slots(
            ctx,
            f"Thanks — I've noted this for Harish:\n\n*\"{msg}\"*\n\n"
            "He'll review it before your call.\n\n"
            "Now let's pick a time that works for you.",
        )

    def _handle_show_slots(self, msg: str, ctx: dict) -> BotResponse:
        return BotResponse("", "await_slot_selection", qualified_for_booking=True)

    def _handle_await_slot_selection(self, msg: str, ctx: dict) -> BotResponse:
        return BotResponse("Please select a slot from the options shown.", "await_slot_selection")

    def _handle_payment(self, msg: str, ctx: dict) -> BotResponse:
        return BotResponse("Tap *Pay Now* below to confirm (demo — no real charge).", "payment")

    def _handle_confirmed(self, msg: str, ctx: dict) -> BotResponse:
        return BotResponse("Your consultation is confirmed! Reminders will be sent before your session.", "confirmed")

    def _handle_faq_mode(self, msg: str, ctx: dict) -> BotResponse:
        if _wants_booking(msg) or msg.lower() in {"book consultation", "book", "yes"}:
            return BotResponse("Let's book! May I have your *full name*?", "collect_name")
        if _is_advice_request(msg):
            return self._advice_intake_response(msg, ctx)
        faq = _resolve_faq(msg)
        if faq == "services":
            return BotResponse("Which area interests you?", "collect_requirement", options=SERVICE_OPTIONS, option_style="list")
        if faq:
            return BotResponse(smart_faq_answer(faq, msg, FAQ_RESPONSES[faq]), "faq_mode", options=["Book consultation"], option_style="chips")
        return BotResponse(
            "I can help with services, fees, and booking — or share your investment question "
            "and I'll forward it to Harish with your holdings.",
            "faq_mode",
            options=["Book consultation"],
            option_style="chips",
        )

    def _handle_escalated(self, msg: str, ctx: dict) -> BotResponse:
        return BotResponse("Escalated to our team — someone will reach out shortly.", "escalated", escalate=True)
