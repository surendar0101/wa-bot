# Finance with Harish — Consultation Automation MVP

Working demo for the BRD: AI-assisted WhatsApp-style intake → qualification → slot booking → payment → confirmation → advisor brief.

## Quick Start

```bash
# Terminal 1 — Backend
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

Or use the one-liner:

```bash
./start.sh
```

## Demo Flow

1. **Customer WhatsApp tab** — Chat with the AI assistant
   - Try quick actions: "Book consultation", "What are your fees?"
   - Complete intake: name → requirement → qualification → consultation type → investment range → existing investor → key questions
   - Pick a slot → Pay (demo) → Get confirmation

2. **Advisor Dashboard** — Live stats + upcoming consultations
   - Click "Load Sample Data" for pre-seeded appointments
   - Click **Simulate Form Submit** to demo Google Form → WhatsApp outreach
   - Click any row to view the **AI-generated consultation brief**

## Google Form Integration (MVP)

Form: [Financial Consultation Form](https://docs.google.com/forms/d/e/1FAIpQLSfQ7V70Sf-KszsDymyD3KBZ57nNJksavCfiEb75C9U4N0Bffg/viewform)

**Demo without Apps Script:**

1. Advisor Dashboard → **Simulate Form Submit**
2. Customer WhatsApp tab (phone `+919876543210`) — outreach message appears
3. Reply **BOOK** → skips name/service/plan → existing investor → holdings → key questions → slots → pay (fee from form tier)

**Production hookup:**

1. Set `FORM_WEBHOOK_SECRET` in `backend/.env`
2. Expose backend (ngrok / deploy): `https://YOUR-HOST/api/webhooks/form-intake`
3. Form → Responses → link to Sheet → **Extensions → Apps Script**
4. Paste `backend/google_form_apps_script.js`, set Script properties:
   - `WEBHOOK_URL` = your webhook URL
   - `WEBHOOK_SECRET` = same as `FORM_WEBHOOK_SECRET`
5. Add trigger: `onFormSubmit` → `onFormSubmit`

Phone number from the form is the key that links the submission to the WhatsApp conversation.

## Architecture

```
WhatsApp UI (React)  →  FastAPI  →  Conversation Engine (state machine)
                              ↓
                         SQLite DB
                              ↓
                    Advisor Dashboard + Briefs
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/chat/start` | Start new conversation |
| `POST /api/chat` | Send message |
| `POST /api/chat/select-slot` | Book slot |
| `POST /api/chat/pay` | Confirm payment (demo) |
| `GET /api/dashboard/stats` | Dashboard metrics |
| `GET /api/dashboard/appointments` | All appointments |
| `GET /api/dashboard/form-submissions` | Pending Google Form leads |
| `POST /api/webhooks/form-intake` | Google Form webhook (Apps Script) |
| `POST /api/demo/simulate-form` | Simulate form submit locally |
| `POST /api/demo/seed` | Seed sample data |

API docs: **http://localhost:8000/docs**

## Stack (100% Open Source)

| Layer | Library / Model |
|-------|-----------------|
| Backend | [FastAPI](https://github.com/tiangolo/fastapi), [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy), [Uvicorn](https://github.com/encode/uvicorn) |
| Frontend | [React](https://github.com/facebook/react), [Vite](https://github.com/vitejs/vite) |
| Database | SQLite (built-in) |
| AI (default) | Rule-based state machine — no LLM required, runs offline |
| AI (optional) | [Ollama](https://ollama.com) + open-weight models (`llama3.2`, `mistral`, `phi3`, etc.) |

## AI — Open Source LLM (Ollama)

**Default: `auto`** — uses LLM if Ollama is running, otherwise rule-based.

```bash
# Install Ollama + model
curl -fsSL https://ollama.com/install.sh | sh   # or https://ollama.com
ollama pull llama3.2

# Optional backend/.env
OLLAMA_ENABLED=auto
OLLAMA_MODEL=llama3.2
```

When active, the assistant:
- Understands natural language ("I'm looking to retire in 10 years" → Retirement Planning)
- Extracts name, investment range, etc. from free-form text
- Gives natural FAQ replies (still no financial advice)
- Generates richer consultation briefs for the advisor dashboard

Verify: `curl http://localhost:8000/api/health` → `"ai_mode":"ollama"`

Recommended models: `llama3.2`, `mistral`, `phi3`, `qwen2.5`

## MVP Scope (from BRD)

- [x] FR-01 Customer enquiry (WhatsApp UI)
- [x] FR-02 Information collection
- [x] FR-03 AI-assisted conversation (rule-based + optional Ollama OSS models)
- [x] FR-04 Customer qualification (FAQ vs booking)
- [x] FR-05 Slot availability
- [x] FR-06 Appointment booking
- [x] FR-07 Payment (demo/mock)
- [x] FR-08 Confirmation
- [x] FR-09 Reminder logic (API simulation)
- [x] FR-10/11 Customer profile + consultation brief
- [x] AI guardrails (no financial advice, escalation path)

## Production Next Steps

- WhatsApp Business API (Twilio/Meta)
- Razorpay live payments
- Google Calendar sync
- n8n for reminder automation
- LangGraph (open-source) for complex agent flows
- PostgreSQL + auth for advisor dashboard
