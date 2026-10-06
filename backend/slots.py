"""Available consultation slot generation."""

from datetime import datetime, timedelta
from typing import Any


def generate_available_slots(days_ahead: int = 7, slots_per_day: int = 4) -> list[dict[str, Any]]:
    """Generate demo slots Mon–Sat, 10 AM – 5 PM."""
    slots = []
    now = datetime.now()
    slot_hours = [10, 11, 14, 16, 17]

    for day_offset in range(1, days_ahead + 1):
        dt = now + timedelta(days=day_offset)
        if dt.weekday() == 6:  # Sunday
            continue
        for hour in slot_hours[:slots_per_day]:
            slot_dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
            if slot_dt <= now:
                continue
            slots.append(
                {
                    "id": slot_dt.strftime("%Y%m%d%H%M"),
                    "datetime": slot_dt.isoformat(),
                    "label": slot_dt.strftime("%a, %d %b · %I:%M %p"),
                    "available": True,
                }
            )
    return slots[:12]


def find_slot_by_id(slot_id: str, slots: list[dict]) -> dict | None:
    for s in slots:
        if s["id"] == slot_id:
            return s
    return None


def format_confirmation(
    name: str,
    slot_label: str,
    consultation_type: str,
    *,
    meet_link: str | None = None,
    email: str | None = None,
    calendar_mode: str = "demo",
) -> str:
    lines = [
        f"✅ *Booking Confirmed!*\n",
        f"Hi {name}, your consultation is scheduled:\n",
        f"📅 *{slot_label}*",
        f"📋 {consultation_type}",
        f"👤 Advisor: Harish",
    ]
    if email:
        lines.append(f"📧 Calendar invite sent to *{email}*")
    if meet_link:
        lines.append(f"🎥 Google Meet: {meet_link}")
    if calendar_mode == "demo" and email:
        lines.append("\n_Add the attached calendar file from your confirmation email, or download .ics from the dashboard._")
    lines.extend(
        [
            "\nYou'll receive reminders 24 hours and 1 hour before your session.",
            "\n_Note: Personalized financial advice will be provided during the consultation._",
        ]
    )
    return "\n".join(lines)
