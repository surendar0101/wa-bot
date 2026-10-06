from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    phone: str = Field(default="+919876543210", description="Customer phone (demo)")
    message: str


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    state: str
    messages: list[dict[str, str]] | None = None
    options: list[str] | None = None
    option_style: str = "list"
    show_slots: bool = False
    slots: list[dict[str, Any]] | None = None
    show_payment: bool = False
    show_upload: bool = False
    upload_accept: str = ".pdf,.png,.jpg,.jpeg,.webp"
    booking_confirmed: bool = False
    appointment_id: int | None = None
    meet_link: str | None = None
    payment_fee: int | None = None
    calendar_download_url: str | None = None


class SlotSelectRequest(BaseModel):
    phone: str
    slot_id: str


class PaymentRequest(BaseModel):
    phone: str
    appointment_id: int


class StartConversationRequest(BaseModel):
    phone: str = "+919876543210"


class DashboardStats(BaseModel):
    todays_consultations: int
    pending_requests: int
    confirmed: int
    follow_ups: int
    form_leads: int = 0


class FormIntakePayload(BaseModel):
    name: str
    phone: str
    service: str | None = None
    call_format: str | None = None
    investment_amount: str | None = None
    consultation_tier: str | None = None
    submitted_at: str | None = None
    form_id: str | None = None
    fee_amount: int | None = None


class FormSubmissionOut(BaseModel):
    id: int
    phone: str
    name: str
    service: str | None
    consultation_tier: str | None
    call_format: str | None
    fee_amount: int | None
    status: str
    submitted_at: datetime | None
    processed_at: datetime

    class Config:
        from_attributes = True


class FormIntakeResponse(BaseModel):
    ok: bool
    phone: str
    conversation_id: int
    form_submission_id: int
    outreach_message: str
    state: str


class AppointmentOut(BaseModel):
    id: int
    customer_name: str
    phone: str
    consultation_type: str
    slot_datetime: datetime
    status: str
    payment_status: str
    consultation_brief: str | None
    email: str | None = None
    meet_link: str | None = None
    intake_source: str | None = None

    class Config:
        from_attributes = True
