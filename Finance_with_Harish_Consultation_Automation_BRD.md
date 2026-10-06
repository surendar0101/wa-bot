# Business Requirements Document (BRD)

## Finance Consultation Customer Journey Automation

**Client:** Finance with Harish  
**Document Type:** Business Requirements Document  
**Version:** 0.1 – Concept Validation  
**Purpose:** Initial business requirement and solution proposal for discussion

---

## 1. Executive Summary

Finance with Harish currently uses an online form-based approach for customers interested in financial consultations, followed by communication and coordination through WhatsApp.

As the number of consultation requests grows, activities such as customer information collection, requirement clarification, slot coordination, confirmations, reminders and follow-ups can create significant manual effort.

This proposal explores an **AI-assisted consultation automation platform** that can automate the operational activities surrounding the consultation while keeping the actual financial advisory interaction **human-led**.

The proposed solution would provide a continuous customer journey:

**Customer Enquiry → Information Collection → Qualification → Slot Selection → Payment → Confirmation → Reminder → Human Consultation → Follow-up**

The initial objective is not to replace the existing advisory process, but to reduce operational overhead and provide advisors with better-prepared customer information.

---

## 2. Business Problem

The current consultation journey may involve multiple manual touchpoints.

### Current-State Challenges

- Customers initially provide information through a form.
- Additional information may need to be collected through WhatsApp.
- Staff/advisors may need to manually respond to customer enquiries.
- Consultation slots may require manual coordination.
- Payment and booking confirmation may require manual intervention.
- Customers may require reminders before the consultation.
- The advisor may have limited structured information about the customer before the call.
- Post-consultation follow-up may also require manual effort.

### Business Impact

This can potentially result in:

- Increased operational workload
- Delayed customer responses
- Repetitive WhatsApp communication
- Manual scheduling effort
- Missed follow-ups
- Difficulty scaling consultation volume
- Limited visibility into the overall customer journey

> **Note:** These challenges are initial assumptions based on the externally observable workflow and should be validated with the Finance with Harish team.

---

## 3. Business Objectives

The primary objective is to create a **seamless and scalable consultation journey** with automation supporting the operational layer.

### Key Objectives

1. Reduce manual customer coordination.
2. Automate repetitive customer communication.
3. Simplify consultation booking.
4. Improve response time to customer enquiries.
5. Automatically remind customers about appointments.
6. Capture structured customer information.
7. Provide advisors with a concise customer brief before consultations.
8. Maintain customer interaction history.
9. Enable scalable handling of increasing consultation requests.
10. Keep personalized financial advice under human advisor control.

---

## 4. Proposed Solution

The proposed solution is an **AI-powered Consultation Automation Platform**.

### High-Level Workflow

```text
Customer
   │
   ▼
WhatsApp / Web
   │
   ▼
AI Customer Assistant
   │
   ▼
Requirement Collection
   │
   ▼
Customer Qualification
   │
   ├───────────────┐
   │               │
   ▼               ▼
General Query   Consultation
   │             Required
   │               │
   │               ▼
   │          Slot Selection
   │               │
   │               ▼
   │            Payment
   │               │
   │               ▼
   │          Appointment
   │               │
   │               ▼
   │          Confirmation
   │               │
   │               ▼
   │            Reminder
   │               │
   │               ▼
   │       Human Consultation
   │               │
   │               ▼
   │       AI Consultation Summary
   │               │
   │               ▼
   └────────► Follow-up / CRM
```

---

## 5. Scope

### 5.1 Phase 1 – Consultation Booking Automation

The first phase should focus on the highest-value operational workflow.

#### FR-01: Customer Enquiry

The system shall allow customers to initiate a consultation request through a supported channel.

**Preferred initial channel:** WhatsApp.

#### FR-02: Customer Information Collection

The system shall collect required information from customers.

Potential information includes:

- Name
- Contact information
- Consultation requirement
- Investment objective
- Approximate investment amount/range
- Existing investment status
- Preferred consultation type
- Preferred date/time

The exact fields should be finalized with the business.

#### FR-03: AI-Assisted Conversation

The AI assistant shall guide customers through the information collection process.

The assistant should:

- Ask questions sequentially.
- Understand natural-language responses.
- Handle common FAQs.
- Request missing information.
- Avoid unnecessarily repeating questions.
- Provide appropriate escalation when required.

#### FR-04: Customer Qualification

The system shall categorize the customer based on predefined business rules.

```text
Customer Request
       │
       ▼
Is consultation required?
       │
 ┌─────┴─────┐
 │           │
 No          Yes
 │           │
 ▼           ▼
FAQ       Booking Flow
```

Qualification rules will be finalized during requirement discovery.

#### FR-05: Slot Availability

The system shall retrieve available consultation slots.

Customers shall be able to select an available slot.

#### FR-06: Appointment Booking

Once the customer selects a slot, the system shall create the appointment.

The appointment should include:

- Customer name
- Contact information
- Consultation type
- Appointment date/time
- Relevant customer information

#### FR-07: Payment

Where applicable, the system shall integrate with the selected payment provider.

```text
Select Slot
    ↓
Payment
    ↓
Payment Verification
    ↓
Appointment Confirmation
```

Payment rules and provider need to be confirmed.

#### FR-08: Confirmation

After successful booking/payment, the customer shall receive an automated confirmation.

Example:

> Your consultation has been successfully scheduled for Thursday at 5:00 PM.

#### FR-09: Appointment Reminder

The system shall automatically send reminders before the consultation.

Potential reminder schedule:

- 24 hours before
- 1–2 hours before

Final reminder schedule to be confirmed.

---

## 6. Phase 2 – Advisor Copilot

Once the booking automation is validated, the platform can be extended to support the advisor.

### FR-10: Customer Profile

The system shall maintain structured customer information.

Example:

```text
Customer Profile

Name: Raj
Consultation: Portfolio Review
Investment Range: ₹10L–₹25L
Existing Investor: Yes
Risk Preference: Moderate
Previous Consultation: Yes
```

### FR-11: Consultation Brief

Before the consultation, the system shall generate a concise advisor brief.

Example:

```text
CONSULTATION BRIEF

Customer:
Raj

Objective:
Portfolio Review

Investment Range:
₹10L – ₹25L

Existing Investments:
Yes

Key Questions:
• Portfolio diversification
• Long-term allocation
• Risk management

Previous Interaction:
Available
```

The objective is to reduce the time required for the advisor to understand the customer's context.

---

## 7. Phase 3 – Post-Consultation Automation

Future functionality can include:

### FR-12: Consultation Summary

Where permitted and technically feasible, the system may generate a structured summary from consultation notes/transcripts.

### FR-13: Action Items

The system may identify:

- Customer action items
- Advisor action items
- Follow-up requirements
- Next consultation date

### FR-14: Follow-up

Automated follow-up communication can be triggered based on predefined rules.

---

## 8. AI Guardrails

This is a **critical requirement**.

The AI system should primarily act as a:

> **Customer Service + Consultation Orchestration Assistant**

It should **not independently provide personalized financial recommendations** unless the business has explicitly designed, approved and governed such functionality.

### AI Should Handle

- Information collection
- FAQs from approved knowledge
- Qualification
- Booking
- Reminders
- Customer history
- Administrative communication
- Advisor briefing

### Human Advisor Should Handle

- Personalized financial advice
- Investment recommendations
- Portfolio decisions
- Complex financial questions
- Exceptions
- Sensitive customer situations

### Escalation

The AI should provide a clear path to human intervention whenever it cannot safely or confidently handle a request.

---

## 9. Proposed System Architecture

```text
                         CUSTOMER
                            │
                            ▼
                    WhatsApp / Web
                            │
                            ▼
                  ┌──────────────────┐
                  │ AI Conversation  │
                  │     Layer        │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Workflow / Agent │
                  │    Orchestrator  │
                  └────────┬─────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
         Customer       Calendar       Payment
          Profile
             │
             ▼
          Database
             │
             ▼
       Advisor Dashboard
             │
             ▼
      Consultation Brief
             │
             ▼
       Human Consultation
```

---

## 10. Proposed Technology Stack

The exact technology stack should be finalized after understanding the existing systems.

| Component | Proposed Technology |
|---|---|
| Customer channel | WhatsApp Business API |
| Backend | Python / FastAPI |
| AI | LLM API |
| Agent orchestration | LangGraph / workflow engine |
| Database | PostgreSQL |
| Automation | n8n |
| Calendar | Google Calendar |
| Payment | Razorpay / existing payment provider |
| CRM | Existing CRM / custom CRM |
| Notifications | WhatsApp |
| Dashboard | React |
| Hosting | Cloud platform |

The architecture should remain **modular**, so individual integrations can be replaced without redesigning the complete system.

---

## 11. Non-Functional Requirements

### Performance

- Customer messages should receive responses within an acceptable conversational response time.
- Booking operations should provide near-real-time slot availability.

### Reliability

- Failed messages should be retried.
- Failed payments should not create confirmed appointments.
- Booking conflicts should be prevented.

### Security

- Customer financial information must be protected.
- Access should be role-based.
- Sensitive information should not be unnecessarily exposed to AI systems.
- Data retention policies should be defined.

### Auditability

The system should maintain appropriate logs for:

- Customer interactions
- Booking events
- Payment status
- AI decisions/actions
- Human escalation
- Appointment changes

---

## 12. Admin / Advisor Dashboard

A future dashboard could provide:

```text
┌──────────────────────────────────────────┐
│             CONSULTATION DASHBOARD       │
├──────────────────────────────────────────┤
│                                          │
│ Today's Consultations          12        │
│ Pending Requests                18       │
│ Confirmed                        9       │
│ Follow-ups                       7       │
│                                          │
├──────────────────────────────────────────┤
│ Upcoming Consultations                  │
│                                          │
│ 10:00 AM  Raj      Portfolio Review     │
│ 11:30 AM  Priya    Investment Planning  │
│ 02:00 PM  Arun     Retirement Planning  │
│                                          │
└──────────────────────────────────────────┘
```

---

## 13. Success Metrics

The pilot should be evaluated using measurable business outcomes.

### Operational Metrics

- Reduction in manual WhatsApp interactions
- Reduction in manual booking effort
- Average customer response time
- Percentage of automated interactions
- Number of consultations processed

### Conversion Metrics

- Enquiry → consultation conversion
- Booking → payment conversion
- Appointment completion rate
- Cancellation/no-show rate

### Customer Experience

- Customer response time
- Booking completion time
- Customer satisfaction
- Number of escalations

### Advisor Productivity

- Time spent on administrative coordination
- Time required to prepare for consultation
- Number of consultations handled per advisor

---

## 14. MVP Scope

For initial validation, the complete platform should not be built immediately.

### MVP Workflow

```text
WhatsApp
    ↓
AI Intake
    ↓
Requirement Collection
    ↓
Basic Qualification
    ↓
Available Slots
    ↓
Booking
    ↓
Confirmation
    ↓
Reminder
```

### Optional MVP Enhancement

```text
Customer Information
       ↓
AI-generated
Consultation Brief
       ↓
Harish
```

This gives enough functionality to demonstrate the business value without spending significant time on advanced CRM, analytics and post-consultation automation.

---

## 15. Future Roadmap

### Phase 1 – Consultation Booking Automation

- WhatsApp
- AI intake
- Qualification
- Slot booking
- Payment
- Confirmation
- Reminders

### Phase 2 – Advisor Copilot

- Customer profile
- Consultation brief
- Customer history
- AI-assisted preparation

### Phase 3 – Customer Lifecycle Automation

- Consultation summaries
- Follow-ups
- Action items
- Re-engagement
- Customer history

### Phase 4 – Business Intelligence

- Lead funnel
- Conversion analytics
- Consultation analytics
- Customer segmentation
- Operational dashboards

---

## 16. Key Assumptions to Validate with Finance with Harish

Before development begins, the following should be confirmed:

1. Current customer acquisition channels.
2. Current Google Form workflow.
3. Number of consultation requests per month.
4. Number of people handling WhatsApp communication.
5. Current slot management process.
6. Current payment process.
7. Existing calendar/CRM systems.
8. Current reminder process.
9. Current cancellation/no-show process.
10. Customer information required before consultation.
11. Consultation types offered.
12. Current FAQs.
13. Current post-consultation workflow.
14. Data privacy/compliance requirements.
15. Which parts of the process they actually want automated.

---

## 17. Proposed Pilot

### Pilot Objective

Validate whether automation can reduce manual operational effort while improving the customer booking experience.

### Suggested Pilot Workflow

**Customer → WhatsApp → AI Intake → Qualification → Slot → Payment → Confirmation → Reminder**

### Pilot Outcome

At the end of the pilot, measure:

> **How much manual effort was eliminated and whether customers completed the consultation journey more efficiently.**

If successful, expand into the **Advisor Copilot and Customer Lifecycle Automation** phases.

---

## 18. Business Value Proposition

### For Customers

- Faster response
- Easier consultation booking
- Less back-and-forth communication
- Automated reminders
- Consistent experience

### For Harish / Team

- Reduced manual coordination
- Fewer repetitive conversations
- Better visibility into consultations
- Better customer preparation
- Ability to handle higher consultation volume

### Strategic Benefit

> **Transform consultation management from a manually coordinated process into a scalable, intelligent customer journey — without removing the human element from financial advice.**

---

## 19. Final Proposal Statement

The proposed solution is **not intended to replace the advisor**.

It is intended to create an intelligent operational layer around the advisor:

```text
              CUSTOMER
                  │
                  ▼
        ┌───────────────────┐
        │ AI + AUTOMATION   │
        │                   │
        │ Intake            │
        │ Qualification     │
        │ Booking           │
        │ Payment           │
        │ Reminders         │
        │ Follow-up         │
        └─────────┬─────────┘
                  │
                  ▼
           HUMAN ADVISOR
                  │
                  ▼
        Personalized Advice
```

**Core Principle:**

> **Automate the coordination. Augment the advisor. Preserve the human advisory relationship.**

---

## 20. First-Call Validation Strategy

For the first meeting, the full BRD should be kept as a backup document. The presentation should focus on:

1. Current customer journey
2. Identified operational opportunity
3. Proposed automated journey
4. Customer WhatsApp experience
5. Advisor consultation brief
6. MVP scope
7. Pilot approach

The purpose of the first call is **validation rather than selling a finished product**.

Suggested closing question:

> **“Does this resemble the challenges you're currently seeing, and if so, which part of the process would you most want to automate first?”**
