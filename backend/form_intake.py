"""Process Google Form webhook → customer, conversation, simulated WhatsApp outreach."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from form_mapper import form_outreach_message, map_form_payload, normalize_phone
from models import Conversation, Customer, FormSubmission, Message


def process_form_intake(db: Session, payload: dict) -> dict:
    ctx = map_form_payload(payload)
    phone = ctx["phone"]
    if not phone or len(phone) < 10:
        raise ValueError("Invalid phone number")

    # Dedupe: same phone within last hour
    recent = (
        db.query(FormSubmission)
        .filter(FormSubmission.phone == phone)
        .order_by(FormSubmission.processed_at.desc())
        .first()
    )
    if recent and recent.raw_payload == payload:
        conv = (
            db.query(Conversation)
            .filter(Conversation.phone == phone)
            .order_by(Conversation.updated_at.desc())
            .first()
        )
        ctx = recent.context_snapshot or ctx
        outreach = form_outreach_message(ctx)
        if conv and conv.state in {"greeting", "post_form_followup"}:
            conv.state = "post_form_followup"
            conv.context = ctx
            conv.qualified_for_booking = False
            conv.updated_at = datetime.utcnow()
            db.query(Message).filter(Message.conversation_id == conv.id).delete()
            db.add(Message(conversation_id=conv.id, role="assistant", content=outreach))
            db.commit()
        return {
            "duplicate": True,
            "phone": phone,
            "conversation_id": conv.id if conv else None,
            "form_submission_id": recent.id,
            "outreach_message": form_outreach_message(recent.context_snapshot or ctx),
            "state": conv.state if conv else "post_form_followup",
        }

    customer = db.query(Customer).filter(Customer.phone == phone).first()
    if not customer:
        customer = Customer(phone=phone)
        db.add(customer)
    customer.name = ctx.get("name") or customer.name
    customer.consultation_type = ctx.get("consultation_type")
    customer.investment_objective = ctx.get("investment_objective")
    customer.investment_range = ctx.get("investment_range")
    customer.intake_source = "google_form"
    db.flush()

    submitted_at = None
    if payload.get("submitted_at"):
        try:
            submitted_at = datetime.fromisoformat(str(payload["submitted_at"]).replace("Z", "+00:00"))
        except ValueError:
            submitted_at = datetime.utcnow()

    submission = FormSubmission(
        customer_id=customer.id,
        phone=phone,
        name=ctx.get("name", ""),
        raw_payload=payload,
        context_snapshot=ctx,
        whatsapp_outreach_sent=True,
        status="awaiting_whatsapp",
        submitted_at=submitted_at,
    )
    db.add(submission)

    outreach = form_outreach_message(ctx)
    conv = (
        db.query(Conversation)
        .filter(Conversation.phone == phone)
        .order_by(Conversation.updated_at.desc())
        .first()
    )
    if conv and conv.state not in {"confirmed", "escalated"}:
        conv.state = "post_form_followup"
        conv.context = ctx
        conv.customer_id = customer.id
        conv.qualified_for_booking = False
        conv.updated_at = datetime.utcnow()
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
    else:
        conv = Conversation(
            phone=phone,
            customer_id=customer.id,
            state="post_form_followup",
            context=ctx,
            qualified_for_booking=False,
        )
        db.add(conv)
    db.flush()

    db.add(Message(conversation_id=conv.id, role="assistant", content=outreach))
    db.commit()
    db.refresh(submission)
    db.refresh(conv)

    return {
        "duplicate": False,
        "phone": phone,
        "conversation_id": conv.id,
        "form_submission_id": submission.id,
        "outreach_message": outreach,
        "state": "post_form_followup",
    }
