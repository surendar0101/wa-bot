"""Finance with Harish — Consultation Automation MVP API."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from conversation_engine import ConversationEngine, generate_consultation_brief
from calendar_service import create_booking_calendar_event
from database import get_db, init_db
from llm import is_ollama_available, llm_mode
from form_intake import process_form_intake
from form_mapper import form_outreach_message
from models import Appointment, Conversation, Customer, FormSubmission, Message
from schemas import (
    AppointmentOut,
    ChatRequest,
    ChatResponse,
    DashboardStats,
    FormIntakePayload,
    FormIntakeResponse,
    FormSubmissionOut,
    PaymentRequest,
    SlotSelectRequest,
    StartConversationRequest,
)
from slots import find_slot_by_id, format_confirmation, generate_available_slots

load_dotenv()

DEMO_SAMPLES = [
    {
        "name": "Raj Kumar",
        "phone": "+919811122233",
        "consultation_type": "Portfolio Review",
        "investment_range": "₹10L – ₹25L",
        "existing_investor": True,
        "existing_investment_types": "Mutual Funds",
        "requirement": "Portfolio review and diversification strategy",
        "key_questions": "Am I over-exposed to mid-cap? Should I rebalance?",
        "day_offset": 0,
        "hour": 10,
        "minute": 0,
    },
    {
        "name": "Priya Sharma",
        "phone": "+919822233344",
        "consultation_type": "Investment Planning",
        "investment_range": "₹5L – ₹10L",
        "existing_investor": False,
        "existing_investment_types": "None",
        "requirement": "Starting SIPs for long-term wealth creation",
        "key_questions": "Best funds for a 10-year horizon? How much to invest monthly?",
        "day_offset": 0,
        "hour": 11,
        "minute": 30,
    },
    {
        "name": "Arun Patel",
        "phone": "+919833344455",
        "consultation_type": "Retirement Planning",
        "investment_range": "₹25L – ₹50L",
        "existing_investor": True,
        "existing_investment_types": "PPF / NPS",
        "requirement": "Retirement corpus planning — target age 55",
        "key_questions": "Is my NPS allocation sufficient? Need help with post-retirement income.",
        "day_offset": 0,
        "hour": 14,
        "minute": 0,
    },
]

app = FastAPI(
    title="Finance with Harish — Consultation Automation",
    description="MVP demo for AI-assisted consultation booking",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ConversationEngine()

TERMINAL_STATES = frozenset({"confirmed", "escalated"})

CALENDAR_INVITES_DIR = os.path.join(os.path.dirname(__file__), "calendar_invites")
os.makedirs(CALENDAR_INVITES_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


def _get_or_create_conversation(db: Session, phone: str) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(Conversation.phone == phone)
        .order_by(Conversation.updated_at.desc())
        .first()
    )
    if conv and conv.state not in {"confirmed", "escalated"}:
        return conv
    conv = Conversation(phone=phone, state="greeting", context={})
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _save_message(db: Session, conv_id: int, role: str, content: str):
    db.add(Message(conversation_id=conv_id, role=role, content=content))
    db.commit()


def _conversation_messages(db: Session, conv_id: int) -> list[dict[str, str]]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in rows]


def _build_resume_response(db: Session, conv: Conversation) -> ChatResponse:
    ctx = conv.context or {}
    state = conv.state
    history = _conversation_messages(db, conv.id)
    ui = engine.resume_ui(state, ctx)

    show_slots = state == "await_slot_selection"
    slots = ctx.get("available_slots") if show_slots else None
    appt_id = ctx.get("appointment_id")
    fee = int(ctx.get("fee_amount") or 999)
    show_payment = state == "payment" and bool(appt_id)
    booking_confirmed = state == "confirmed"

    last_reply = history[-1]["content"] if history else engine.GREETING
    meet_link = None
    calendar_url = None
    if booking_confirmed and appt_id:
        appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
        if appt:
            meet_link = appt.meet_link
            calendar_url = f"/api/appointments/{appt.id}/calendar.ics"

    return ChatResponse(
        conversation_id=conv.id,
        reply=last_reply,
        state=state,
        messages=history,
        options=ui.options,
        option_style=ui.option_style,
        show_slots=show_slots,
        slots=slots,
        show_payment=show_payment,
        show_upload=ui.show_upload or state == "await_investment_upload",
        upload_accept=ui.upload_accept,
        booking_confirmed=booking_confirmed,
        appointment_id=appt_id if (show_payment or booking_confirmed) else None,
        payment_fee=fee if show_payment else None,
        meet_link=meet_link,
        calendar_download_url=calendar_url,
    )


def _maybe_restore_form_lead(db: Session, phone: str) -> Conversation | None:
    """If a form lead exists but chat was reset to greeting, restore outreach."""
    sub = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.phone == phone,
            FormSubmission.status.in_(["awaiting_whatsapp", "in_progress"]),
        )
        .order_by(FormSubmission.processed_at.desc())
        .first()
    )
    if not sub:
        return None

    conv = (
        db.query(Conversation)
        .filter(Conversation.phone == phone)
        .order_by(Conversation.updated_at.desc())
        .first()
    )
    ctx = sub.context_snapshot or {}
    if not ctx.get("intake_source"):
        ctx["intake_source"] = "google_form"

    needs_restore = (
        not conv
        or conv.state == "greeting"
        or (
            conv.state == "post_form_followup"
            and (conv.context or {}).get("intake_source") != "google_form"
        )
    )
    if not needs_restore:
        return conv

    outreach = form_outreach_message(ctx)
    if conv:
        conv.state = "post_form_followup"
        conv.context = ctx
        conv.qualified_for_booking = False
        conv.updated_at = datetime.utcnow()
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
    else:
        customer = db.query(Customer).filter(Customer.phone == phone).first()
        conv = Conversation(
            phone=phone,
            customer_id=customer.id if customer else None,
            state="post_form_followup",
            context=ctx,
            qualified_for_booking=False,
        )
        db.add(conv)
        db.flush()

    last = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .first()
    )
    if not last or "Financial Consultation Form" not in (last.content or ""):
        db.add(Message(conversation_id=conv.id, role="assistant", content=outreach))
    db.commit()
    db.refresh(conv)
    return conv


def _upsert_customer(db: Session, phone: str, ctx: dict) -> Customer:
    customer = db.query(Customer).filter(Customer.phone == phone).first()
    if not customer:
        customer = Customer(phone=phone)
        db.add(customer)
    if ctx.get("name"):
        customer.name = ctx["name"]
    if ctx.get("email"):
        customer.email = ctx["email"]
    if ctx.get("consultation_type"):
        customer.consultation_type = ctx["consultation_type"]
    if ctx.get("investment_objective"):
        customer.investment_objective = ctx["investment_objective"]
    if ctx.get("investment_range"):
        customer.investment_range = ctx["investment_range"]
    if ctx.get("existing_investor") is not None:
        customer.existing_investor = ctx["existing_investor"]
    if ctx.get("existing_investment_types"):
        customer.existing_investment_types = ctx["existing_investment_types"]
    if ctx.get("investment_details_summary"):
        customer.investment_details = ctx["investment_details_summary"]
    elif ctx.get("investment_details_text") or ctx.get("investment_detail_files"):
        from conversation_engine import _format_investment_details
        customer.investment_details = _format_investment_details(ctx)
    if ctx.get("key_questions"):
        customer.key_questions = ctx["key_questions"]
    if ctx.get("requirement"):
        customer.investment_objective = ctx.get("investment_objective") or ctx["requirement"]
    if ctx.get("intake_source"):
        customer.intake_source = ctx["intake_source"]
    db.commit()
    db.refresh(customer)
    return customer


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "finance-consultation-mvp",
        "stack": "open-source",
        "ai_mode": llm_mode(),
        "ollama_available": is_ollama_available(),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.2") if is_ollama_available() else None,
    }


@app.post("/api/chat/start", response_model=ChatResponse)
def start_conversation(req: StartConversationRequest, db: Session = Depends(get_db)):
    restored = _maybe_restore_form_lead(db, req.phone)

    conv = restored or (
        db.query(Conversation)
        .filter(Conversation.phone == req.phone)
        .order_by(Conversation.updated_at.desc())
        .first()
    )

    if conv and conv.state not in TERMINAL_STATES:
        return _build_resume_response(db, conv)

    if conv and conv.state in TERMINAL_STATES:
        return _build_resume_response(db, conv)

    conv = Conversation(phone=req.phone, state="greeting", context={})
    db.add(conv)
    db.commit()
    db.refresh(conv)

    greeting = engine.GREETING
    _save_message(db, conv.id, "assistant", greeting)

    return ChatResponse(
        conversation_id=conv.id,
        reply=greeting,
        state="greeting",
        messages=[{"role": "assistant", "content": greeting}],
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    conv = _get_or_create_conversation(db, req.phone)
    ctx = conv.context or {}
    prev_state = conv.state

    _save_message(db, conv.id, "user", req.message)

    if req.message.lower().strip() == "help":
        reply = (
            "I can help you book a consultation or answer general questions.\n"
            "Type *book* to start booking, or ask about *fees*, *services*, or *hours*."
        )
        _save_message(db, conv.id, "assistant", reply)
        return ChatResponse(conversation_id=conv.id, reply=reply, state=conv.state)

    if req.message.lower().strip() == "reset":
        conv.state = "greeting"
        conv.context = {}
        db.commit()
        reply = engine.GREETING
        _save_message(db, conv.id, "assistant", reply)
        return ChatResponse(conversation_id=conv.id, reply=reply, state="greeting")

    bot = engine.process(conv.state, req.message, ctx)
    conv.state = bot.state
    conv.context = ctx
    conv.qualified_for_booking = bot.qualified_for_booking
    conv.updated_at = datetime.utcnow()

    if prev_state == "post_form_followup" and bot.state != "post_form_followup":
        sub = (
            db.query(FormSubmission)
            .filter(FormSubmission.phone == req.phone, FormSubmission.status == "awaiting_whatsapp")
            .order_by(FormSubmission.processed_at.desc())
            .first()
        )
        if sub:
            sub.status = "in_progress"

    if bot.qualified_for_booking and bot.state == "show_slots":
        customer = _upsert_customer(db, req.phone, ctx)
        conv.customer_id = customer.id
        db.commit()

        slots = generate_available_slots()
        ctx["available_slots"] = slots
        conv.context = ctx
        conv.state = "await_slot_selection"
        db.commit()

        slot_lines = "\n".join(f"{i+1}. {s['label']}" for i, s in enumerate(slots))
        intro = bot.message.strip() if bot.message else "Here are available slots:"
        reply = f"{intro}\n\n{slot_lines}\n\nTap a slot below to book."
        _save_message(db, conv.id, "assistant", reply)
        return ChatResponse(
            conversation_id=conv.id,
            reply=reply,
            state="await_slot_selection",
            show_slots=True,
            slots=slots,
        )

    reply = bot.message
    if reply:
        _save_message(db, conv.id, "assistant", reply)

    db.commit()

    appt_id = (conv.context or {}).get("appointment_id")
    return ChatResponse(
        conversation_id=conv.id,
        reply=reply,
        state=conv.state,
        options=bot.options,
        option_style=bot.option_style,
        show_upload=bot.show_upload,
        upload_accept=bot.upload_accept,
        show_payment=conv.state == "payment" and bool(appt_id),
        appointment_id=appt_id if conv.state == "payment" else None,
    )


UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")


@app.post("/api/chat/upload-investment", response_model=ChatResponse)
async def upload_investment_doc(
    phone: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Receive PDF/screenshot of customer holdings for pre-call brief."""
    conv = _get_or_create_conversation(db, phone)
    ctx = conv.context or {}

    if conv.state != "await_investment_upload":
        raise HTTPException(400, "Not awaiting investment document upload")

    ext = os.path.splitext(file.filename or "upload")[1].lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    if ext not in allowed:
        raise HTTPException(400, f"File type not allowed. Use: {', '.join(allowed)}")

    safe_phone = phone.replace("+", "").replace(" ", "")
    dest_dir = os.path.join(UPLOAD_DIR, safe_phone)
    os.makedirs(dest_dir, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{ts}_{(file.filename or 'upload').replace(' ', '_')}"
    dest_path = os.path.join(dest_dir, safe_name)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10MB)")
    with open(dest_path, "wb") as f:
        f.write(content)

    file_type = "PDF" if ext == ".pdf" else "Screenshot"
    bot = engine.record_upload(ctx, file.filename or safe_name, file_type, dest_path)

    conv.context = ctx
    conv.state = bot.state
    conv.updated_at = datetime.utcnow()
    db.commit()

    _save_message(db, conv.id, "user", f"[Uploaded {file.filename}]")
    _save_message(db, conv.id, "assistant", bot.message)

    return ChatResponse(
        conversation_id=conv.id,
        reply=bot.message,
        state=bot.state,
        options=bot.options,
        option_style=bot.option_style,
        show_upload=bot.show_upload,
        upload_accept=bot.upload_accept,
    )


@app.post("/api/chat/select-slot", response_model=ChatResponse)
def select_slot(req: SlotSelectRequest, db: Session = Depends(get_db)):
    conv = _get_or_create_conversation(db, req.phone)
    if conv.state != "await_slot_selection":
        raise HTTPException(400, "Not awaiting slot selection")

    ctx = conv.context or {}
    slots = ctx.get("available_slots") or generate_available_slots()

    slot = find_slot_by_id(req.slot_id, slots)
    if not slot:
        try:
            idx = int(req.slot_id) - 1
            if 0 <= idx < len(slots):
                slot = slots[idx]
        except ValueError:
            pass

    if not slot:
        raise HTTPException(400, "Invalid slot selection")

    ctx["selected_slot"] = slot
    conv.context = ctx
    conv.state = "payment"
    db.commit()

    customer = _upsert_customer(db, req.phone, ctx)
    slot_dt = datetime.fromisoformat(slot["datetime"])
    fee = int(ctx.get("fee_amount") or 999)

    appt = Appointment(
        customer_id=customer.id,
        consultation_type=ctx.get("consultation_type", "General Guidance"),
        slot_datetime=slot_dt,
        status="pending_payment",
        payment_status="pending",
        payment_amount=fee,
        consultation_brief=generate_consultation_brief(ctx),
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    ctx["appointment_id"] = appt.id
    conv.context = ctx
    db.commit()

    reply = (
        f"Slot selected: *{slot['label']}*\n\n"
        f"Consultation fee: *₹{fee:,}* (demo)\n\n"
        "Tap *Pay Now* below — mock payment, no real charge."
    )
    _save_message(db, conv.id, "user", f"Selected slot: {slot['label']}")
    _save_message(db, conv.id, "assistant", reply)

    return ChatResponse(
        conversation_id=conv.id,
        reply=reply,
        state="payment",
        show_payment=True,
        appointment_id=appt.id,
        payment_fee=fee,
    )


@app.post("/api/chat/pay", response_model=ChatResponse)
def confirm_payment(req: PaymentRequest, db: Session = Depends(get_db)):
    conv = _get_or_create_conversation(db, req.phone)
    appt = db.query(Appointment).filter(Appointment.id == req.appointment_id).first()
    if not appt:
        raise HTTPException(404, "Appointment not found")

    ctx = conv.context or {}
    slot = ctx.get("selected_slot", {})
    name = ctx.get("name", "there")
    email = ctx.get("email")
    customer = db.query(Customer).filter(Customer.id == appt.customer_id).first()
    if customer and customer.email:
        email = email or customer.email
    if not email:
        conv.state = "collect_email"
        ctx["pending_slot_message"] = "Payment received — please confirm your email for the calendar invite."
        ctx["awaiting_email_for_payment"] = True
        conv.context = ctx
        db.commit()
        reply = "What's your *email address*? We'll send the Google Meet link and calendar invite."
        _save_message(db, conv.id, "assistant", reply)
        return ChatResponse(conversation_id=conv.id, reply=reply, state="collect_email")

    mock_payment_id = f"mock_pay_{uuid.uuid4().hex[:12]}"

    cal = create_booking_calendar_event(
        customer_name=name,
        customer_email=email,
        slot_datetime=appt.slot_datetime,
        consultation_type=appt.consultation_type,
    )

    appt.payment_status = "paid"
    appt.status = "confirmed"
    appt.meet_link = cal.get("meet_link")
    appt.calendar_event_id = cal.get("calendar_event_id")
    appt.calendar_html_link = cal.get("html_link")
    fee = appt.payment_amount or int(ctx.get("fee_amount") or 999)

    if customer:
        customer.email = email
        if ctx.get("name"):
            customer.name = ctx["name"]

    calendar_url = None
    if cal.get("ics_content"):
        ics_path = os.path.join(CALENDAR_INVITES_DIR, f"{appt.id}.ics")
        with open(ics_path, "w", encoding="utf-8") as f:
            f.write(cal["ics_content"])
        calendar_url = f"/api/appointments/{appt.id}/calendar.ics"

    db.commit()

    conv.state = "confirmed"
    sub = (
        db.query(FormSubmission)
        .filter(FormSubmission.phone == req.phone)
        .order_by(FormSubmission.processed_at.desc())
        .first()
    )
    if sub:
        sub.status = "booked"
    db.commit()

    reply = (
        f"💳 *Payment successful* (demo)\n"
        f"Ref: `{mock_payment_id}` · ₹{fee:,}\n\n"
        + format_confirmation(
            name,
            slot.get("label", appt.slot_datetime.strftime("%a, %d %b · %I:%M %p")),
            appt.consultation_type,
            meet_link=cal.get("meet_link"),
            email=email,
            calendar_mode=cal.get("mode", "demo"),
        )
    )
    if calendar_url and cal.get("mode") == "demo":
        reply += f"\n\n📎 Add to calendar: {calendar_url}"

    _save_message(db, conv.id, "user", "Payment confirmed")
    _save_message(db, conv.id, "assistant", reply)

    return ChatResponse(
        conversation_id=conv.id,
        reply=reply,
        state="confirmed",
        booking_confirmed=True,
        appointment_id=appt.id,
        meet_link=cal.get("meet_link"),
        calendar_download_url=calendar_url,
    )


def _dashboard_appointments_query(db: Session):
    """Upcoming confirmed only — one row per customer (latest booking)."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    appts = (
        db.query(Appointment)
        .filter(Appointment.status == "confirmed", Appointment.slot_datetime >= start_of_day)
        .order_by(Appointment.slot_datetime.desc())
        .all()
    )

    by_phone: dict[str, tuple] = {}
    for a in appts:
        customer = db.query(Customer).filter(Customer.id == a.customer_id).first()
        phone = customer.phone if customer else f"unknown-{a.id}"
        if phone not in by_phone:
            by_phone[phone] = (a, customer)

    return sorted(by_phone.values(), key=lambda row: row[0].slot_datetime)


@app.get("/api/slots")
def list_slots():
    return {"slots": generate_available_slots()}


@app.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    rows = _dashboard_appointments_query(db)
    appointments = [r[0] for r in rows]
    conversations = db.query(Conversation).all()

    todays = [a for a in appointments if a.slot_datetime.date() == today]

    pending = [c for c in conversations if c.state not in {"confirmed", "escalated", "greeting"}]

    form_leads = (
        db.query(FormSubmission)
        .filter(FormSubmission.status.in_(["awaiting_whatsapp", "in_progress"]))
        .count()
    )

    return DashboardStats(
        todays_consultations=len(todays),
        pending_requests=len(pending),
        confirmed=len(appointments),
        follow_ups=0,
        form_leads=form_leads,
    )


@app.get("/api/dashboard/appointments", response_model=list[AppointmentOut])
def dashboard_appointments(db: Session = Depends(get_db)):
    result = []
    for a, customer in _dashboard_appointments_query(db):
        result.append(
            AppointmentOut(
                id=a.id,
                customer_name=customer.name if customer else "Unknown",
                phone=customer.phone if customer else "",
                email=customer.email if customer else None,
                consultation_type=a.consultation_type,
                slot_datetime=a.slot_datetime,
                status=a.status,
                payment_status=a.payment_status,
                consultation_brief=a.consultation_brief,
                meet_link=a.meet_link,
                intake_source=customer.intake_source if customer else None,
            )
        )
    return result


@app.get("/api/dashboard/conversations")
def dashboard_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(20).all()
    out = []
    for c in convs:
        msgs = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at).all()
        out.append(
            {
                "id": c.id,
                "phone": c.phone,
                "state": c.state,
                "qualified": c.qualified_for_booking,
                "updated_at": c.updated_at.isoformat(),
                "messages": [{"role": m.role, "content": m.content, "at": m.created_at.isoformat()} for m in msgs],
            }
        )
    return out


@app.get("/api/dashboard/form-submissions", response_model=list[FormSubmissionOut])
def dashboard_form_submissions(db: Session = Depends(get_db)):
    rows = (
        db.query(FormSubmission)
        .filter(FormSubmission.status.in_(["awaiting_whatsapp", "in_progress"]))
        .order_by(FormSubmission.processed_at.desc())
        .limit(20)
        .all()
    )
    out = []
    for row in rows:
        snap = row.context_snapshot or {}
        out.append(
            FormSubmissionOut(
                id=row.id,
                phone=row.phone,
                name=row.name,
                service=snap.get("form_service") or snap.get("requirement"),
                consultation_tier=snap.get("consultation_tier"),
                call_format=snap.get("call_format"),
                fee_amount=snap.get("fee_amount"),
                status=row.status,
                submitted_at=row.submitted_at,
                processed_at=row.processed_at,
            )
        )
    return out


def _verify_form_webhook_secret(x_webhook_secret: str | None) -> None:
    expected = os.getenv("FORM_WEBHOOK_SECRET", "dev-form-secret")
    if x_webhook_secret != expected:
        raise HTTPException(401, "Invalid webhook secret")


@app.post("/api/webhooks/form-intake", response_model=FormIntakeResponse)
def google_form_webhook(
    payload: FormIntakePayload,
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    _verify_form_webhook_secret(x_webhook_secret)
    try:
        result = process_form_intake(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return FormIntakeResponse(
        ok=True,
        phone=result["phone"],
        conversation_id=result["conversation_id"],
        form_submission_id=result["form_submission_id"],
        outreach_message=result["outreach_message"],
        state=result["state"],
    )


@app.post("/api/demo/simulate-form", response_model=FormIntakeResponse)
def simulate_form_intake(payload: FormIntakePayload, db: Session = Depends(get_db)):
    """Local demo — simulates Google Form submit without Apps Script."""
    try:
        result = process_form_intake(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return FormIntakeResponse(
        ok=True,
        phone=result["phone"],
        conversation_id=result["conversation_id"],
        form_submission_id=result["form_submission_id"],
        outreach_message=result["outreach_message"],
        state=result["state"],
    )


@app.get("/api/appointments/{appointment_id}/brief")
def get_brief(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(404, "Not found")
    return {"brief": appt.consultation_brief}


@app.get("/api/appointments/{appointment_id}/calendar.ics")
def download_calendar_invite(appointment_id: int):
    path = os.path.join(CALENDAR_INVITES_DIR, f"{appointment_id}.ics")
    if not os.path.isfile(path):
        raise HTTPException(404, "Calendar invite not found")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="consultation-{appointment_id}.ics"'},
    )


def _seed_demo_samples(db: Session) -> int:
    created = 0
    now = datetime.now()

    for sample in DEMO_SAMPLES:
        if db.query(Customer).filter(Customer.phone == sample["phone"]).first():
            continue

        customer = Customer(
            name=sample["name"],
            phone=sample["phone"],
            consultation_type=sample["consultation_type"],
            investment_range=sample["investment_range"],
            existing_investor=sample["existing_investor"],
            existing_investment_types=sample["existing_investment_types"],
            investment_objective=sample["requirement"],
            key_questions=sample["key_questions"],
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        slot_dt = (
            now.replace(hour=sample["hour"], minute=sample["minute"], second=0, microsecond=0)
            + timedelta(days=sample["day_offset"])
        )
        ctx = {
            "name": sample["name"],
            "consultation_type": sample["consultation_type"],
            "investment_range": sample["investment_range"],
            "existing_investor": sample["existing_investor"],
            "existing_investment_types": sample["existing_investment_types"],
            "key_questions": sample["key_questions"],
            "requirement": sample["requirement"],
            "investment_objective": sample["requirement"],
        }
        appt = Appointment(
            customer_id=customer.id,
            consultation_type=sample["consultation_type"],
            slot_datetime=slot_dt,
            status="confirmed",
            payment_status="paid",
            consultation_brief=generate_consultation_brief(ctx),
        )
        db.add(appt)
        created += 1

    db.commit()
    return created


@app.post("/api/demo/reset")
def reset_demo_data(db: Session = Depends(get_db)):
    """Clear all records and load fresh 3 demo appointments."""
    db.query(Message).delete()
    db.query(Conversation).delete()
    db.query(FormSubmission).delete()
    db.query(Appointment).delete()
    db.query(Customer).delete()
    db.commit()
    created = _seed_demo_samples(db)
    return {"message": f"Dashboard reset — {created} demo records", "total": created}


@app.post("/api/demo/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    """Add demo records if missing (use /demo/reset for a clean slate)."""
    created = _seed_demo_samples(db)
    total = len(_dashboard_appointments_query(db))
    return {"message": f"Added {created} demo records", "created": created, "total": total}


@app.get("/api/demo/reminders")
def simulate_reminders(db: Session = Depends(get_db)):
    """Simulate reminder logic — shows what would be sent."""
    now = datetime.now()
    appts = db.query(Appointment).filter(Appointment.status == "confirmed").all()
    reminders = []

    for a in appts:
        customer = db.query(Customer).filter(Customer.id == a.customer_id).first()
        delta = a.slot_datetime - now
        hours = delta.total_seconds() / 3600

        if 23 <= hours <= 25 and not a.reminder_24h_sent:
            reminders.append(
                {
                    "appointment_id": a.id,
                    "type": "24h",
                    "message": f"Reminder: Hi {customer.name}, your consultation with Harish is tomorrow at {a.slot_datetime.strftime('%I:%M %p')}.",
                }
            )
        elif 1 <= hours <= 2 and not a.reminder_1h_sent:
            reminders.append(
                {
                    "appointment_id": a.id,
                    "type": "1h",
                    "message": f"Reminder: Hi {customer.name}, your consultation starts in 1 hour ({a.slot_datetime.strftime('%I:%M %p')}).",
                }
            )

    return {"pending_reminders": reminders, "checked_at": now.isoformat()}
