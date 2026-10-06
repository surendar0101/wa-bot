from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    phone = Column(String(20), unique=True, index=True)
    email = Column(String(200), nullable=True)
    consultation_type = Column(String(100), nullable=True)
    investment_objective = Column(Text, nullable=True)
    investment_range = Column(String(50), nullable=True)
    existing_investor = Column(Boolean, nullable=True)
    existing_investment_types = Column(String(200), nullable=True)
    investment_details = Column(Text, nullable=True)
    risk_preference = Column(String(50), nullable=True)
    key_questions = Column(Text, nullable=True)
    intake_source = Column(String(50), nullable=True)  # google_form | whatsapp
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="customer")
    appointments = relationship("Appointment", back_populates="customer")
    form_submissions = relationship("FormSubmission", back_populates="customer")


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    phone = Column(String(20), index=True)
    name = Column(String(200))
    raw_payload = Column(JSON, default=dict)
    context_snapshot = Column(JSON, default=dict)
    whatsapp_outreach_sent = Column(Boolean, default=True)
    status = Column(String(30), default="awaiting_whatsapp")  # awaiting_whatsapp | in_progress | booked
    submitted_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="form_submissions")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    phone = Column(String(20), index=True)
    state = Column(String(50), default="greeting")
    context = Column(JSON, default=dict)
    qualified_for_booking = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String(20))  # user | assistant | system
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    consultation_type = Column(String(100))
    slot_datetime = Column(DateTime)
    status = Column(String(30), default="confirmed")  # pending_payment | confirmed | cancelled | completed
    payment_status = Column(String(30), default="pending")  # pending | paid | waived
    payment_amount = Column(Integer, default=999)
    consultation_brief = Column(Text, nullable=True)
    meet_link = Column(String(500), nullable=True)
    calendar_event_id = Column(String(200), nullable=True)
    calendar_html_link = Column(String(500), nullable=True)
    reminder_24h_sent = Column(Boolean, default=False)
    reminder_1h_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="appointments")
