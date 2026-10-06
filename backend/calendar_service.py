"""Google Calendar + Meet invites for confirmed bookings.

Demo mode (no credentials): generates Meet-style link + downloadable .ics
Live mode: GOOGLE_CALENDAR_CREDENTIALS_FILE + GOOGLE_CALENDAR_DELEGATE_EMAIL
"""

from __future__ import annotations

import logging
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

IST = "Asia/Kolkata"
CONSULTATION_MINUTES = 30


def _demo_meet_link() -> str:
    chars = string.ascii_lowercase
    a = "".join(secrets.choice(chars) for _ in range(3))
    b = "".join(secrets.choice(chars) for _ in range(4))
    c = "".join(secrets.choice(chars) for _ in range(3))
    return f"https://meet.google.com/{a}-{b}-{c}"


def _ics_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def generate_ics(
    *,
    uid: str,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    organizer_email: str,
    organizer_name: str,
    attendee_email: str,
    attendee_name: str,
    meet_link: str | None = None,
) -> str:
    desc = description
    if meet_link:
        desc = f"{description}\\n\\nJoin Google Meet: {meet_link}"

    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Finance with Harish//Consultation MVP//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_ics_dt(datetime.utcnow())}Z",
            f"DTSTART;TZID={IST}:{_ics_dt(start)}",
            f"DTEND;TZID={IST}:{_ics_dt(end)}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            f"ORGANIZER;CN={organizer_name}:MAILTO:{organizer_email}",
            f"ATTENDEE;CN={attendee_name};RSVP=TRUE:MAILTO:{attendee_email}",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def _create_google_event(
    *,
    customer_name: str,
    customer_email: str,
    slot_datetime: datetime,
    consultation_type: str,
    advisor_email: str,
    creds_path: str,
    calendar_id: str,
    delegate_email: str | None,
) -> dict[str, Any]:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    if delegate_email:
        creds = creds.with_subject(delegate_email)

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    end = slot_datetime + timedelta(minutes=CONSULTATION_MINUTES)
    request_id = uuid.uuid4().hex

    event_body = {
        "summary": f"Finance with Harish — {consultation_type}",
        "description": (
            f"Consultation with Harish\nCustomer: {customer_name}\nType: {consultation_type}"
        ),
        "start": {"dateTime": slot_datetime.isoformat(), "timeZone": IST},
        "end": {"dateTime": end.isoformat(), "timeZone": IST},
        "attendees": [
            {"email": customer_email, "displayName": customer_name},
            {"email": advisor_email, "displayName": "Harish"},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": request_id,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
    }

    created = (
        service.events()
        .insert(
            calendarId=calendar_id,
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates="all",
        )
        .execute()
    )

    meet_link = created.get("hangoutLink")
    if not meet_link:
        for ep in created.get("conferenceData", {}).get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri")
                break

    return {
        "mode": "google",
        "meet_link": meet_link or _demo_meet_link(),
        "calendar_event_id": created.get("id"),
        "html_link": created.get("htmlLink"),
        "ics_content": None,
        "invite_sent": True,
    }


def create_booking_calendar_event(
    *,
    customer_name: str,
    customer_email: str,
    slot_datetime: datetime,
    consultation_type: str,
) -> dict[str, Any]:
    advisor_email = os.getenv("ADVISOR_EMAIL", "varshnibabu@gmail.com")
    creds_path = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", "")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    delegate_email = os.getenv("GOOGLE_CALENDAR_DELEGATE_EMAIL")

    if creds_path and os.path.isfile(creds_path):
        try:
            return _create_google_event(
                customer_name=customer_name,
                customer_email=customer_email,
                slot_datetime=slot_datetime,
                consultation_type=consultation_type,
                advisor_email=advisor_email,
                creds_path=creds_path,
                calendar_id=calendar_id,
                delegate_email=delegate_email,
            )
        except Exception:
            logger.exception("Google Calendar API failed; using demo calendar invite")

    end = slot_datetime + timedelta(minutes=CONSULTATION_MINUTES)
    meet_link = _demo_meet_link()
    event_uid = f"consult-{uuid.uuid4().hex}@financewithharish.com"
    ics = generate_ics(
        uid=event_uid,
        summary=f"Finance with Harish — {consultation_type}",
        description=f"Consultation with Harish. Type: {consultation_type}",
        start=slot_datetime,
        end=end,
        organizer_email=advisor_email,
        organizer_name="Harish",
        attendee_email=customer_email,
        attendee_name=customer_name,
        meet_link=meet_link,
    )

    return {
        "mode": "demo",
        "meet_link": meet_link,
        "calendar_event_id": event_uid,
        "html_link": None,
        "ics_content": ics,
        "invite_sent": False,
    }
