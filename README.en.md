# Django Study Hub — AI-Powered Educational SaaS

> **Note:** This is a sanitized version of a production codebase. Client-specific configurations and production credentials have been removed. The full development history (Issues and commits) is maintained in a private repository; commits here represent milestone syncs of working features.

## Problem & Context

I work at a small tutoring operation in Japan. We set up an official LINE channel so students could ask questions — but it didn't work.

The failure wasn't technical. It was structural: no dedicated responder, weak per-answer incentives, and a complete blind spot for late-night questions. Forcing a solution with more people wasn't viable at our scale.

The answer wasn't "hire someone." It was "build a system that doesn't require a human to be awake."

---

## From Chatbot to Platform: The Differentiation Problem

Once I built the AI Q&A integration, I faced an honest question: *Isn't this just a ChatGPT app?*

By 2024, GPT-4 was already good enough to answer most student questions directly. Generic features were commoditizing fast. So I made a deliberate choice: don't compete in the space big companies will dominate. Instead, build the unglamorous, hyper-local things they'll never bother with:

- A vocabulary database aligned to specific Japanese school textbooks (no commercial app does this at this granularity)
- Question history shared between students and their specific teachers
- Learning history accumulated per student, per organization

The moat isn't the AI. It's the institutional data and local specificity around it.

---

## Architecture Decisions

### LINE as the interface layer

**Problem:** Asking students to install yet another app creates friction that kills adoption.

**Decision:** Integrate into LINE, which has near-universal penetration in Japan — no additional install required.

**Tradeoff:** Significantly constrained UI compared to a native app. But adoption beats features. Daily questions have been coming in since launch, confirming the original problem is solved.

---

### GCP (App Engine) for hosting

**Problem:** Solo developer, small budget, need managed infrastructure with minimal ops overhead.

**Decision:** App Engine free tier, plus native integration with Cloud KMS, Secret Manager, and Pub/Sub in one ecosystem.

**Tradeoff:** Vendor lock-in. Acceptable at this stage — managed services let me focus on product rather than infrastructure.

---

### SuperMemo-2 for spaced repetition

**Problem:** "Study until it feels easy" produces shallow retention. I wanted learning mechanics grounded in how memory actually works.

**Decision:** Implemented the SuperMemo-2 algorithm across all trainer modules, tracking `ease_factor`, `interval`, and `next_due_at` per item per student.

**Tradeoff:** More complex model than a simple right/wrong tracker. Worth it because it produces meaningfully better study schedules than arbitrary repetition.

---

### Async reminders via Cloud Pub/Sub

**Problem:** Sending LINE push notifications synchronously inside a web request risks timeouts and latency spikes.

**Decision:** Decoupled the reminder pipeline: `trigger_reminders.py` enqueues to Pub/Sub; an independent `listener.py` process handles delivery.

**Tradeoff:** Operational complexity increases. But web requests and reminder delivery now fail independently — a reminder backlog doesn't impact app performance, and app restarts don't drop queued messages.

---

### Envelope encryption for LINE channel credentials

**Problem:** Multi-tenant architecture means storing per-organization LINE secrets (channel keys, access tokens) in a shared database.

**Decision:** Cloud KMS-based envelope encryption — each secret encrypted with a per-tenant DEK, each DEK wrapped with a KMS-managed KEK.

**Tradeoff:** Adds a KMS round-trip on decrypt and increases implementation complexity. Necessary because storing channel secrets in plaintext in a shared DB is indefensible for a system handling student data.

---

## Technical Highlights

**Multi-tenant RBAC:** Four-layer hierarchy (Organization Admin → Classroom Admin → Teacher → Student). Role-based data filtering enforced at the QuerySet level across all models — not in view logic — so access boundaries are consistent regardless of entry point.

**Hexagonal architecture for email:** The invitation system uses a ports-and-adapters pattern (`EmailSender` interface, `GmailSMTPSender` implementation). The domain layer stays independent of the transport mechanism, and test environments swap the implementation without changing business logic.

**AI content generation:** The `processors/` module centralizes all OpenAI API interactions — reading passage generation, listening exercise creation, example sentence generation, and chat responses. Prompt design and output post-processing live here rather than in views or models.

---

## Development Process

I use Issue-driven development with AI-assisted engineering on every cycle:

```
1. Write the Issue in plain language (the "why")
2. Brainstorm with ChatGPT — validate assumptions, explore tradeoffs
3. Formalize the spec
4. Ask Claude to research and draft an implementation plan
5. Have ChatGPT review the plan (adversarial second opinion)
6. Claude implements
7. Code review → tests → merge
```

**Division of labor:** ChatGPT for open-ended discussion and skeptical review; Claude for technical research and implementation. I own the *why* and *how* — the *what* is delegated.

I'm also consciously shifting toward proposing the framework myself before handing off to AI, rather than asking AI to propose it. The goal is to maintain judgment ownership while using AI to accelerate execution.

---

## Operational Experience

**What's working:**
- Daily Q&A traffic on the LINE channel — the original problem (late-night unanswered questions) is solved
- Reminders delivering reliably through the Pub/Sub pipeline
- Production system has stayed stable — not trivial for a solo developer running live infrastructure for the first time at this scale

**What's not working yet:**

Getting LINE users to navigate to the trainer content. I added reminder-to-content links recently, but I can't measure the impact — no analytics infrastructure is in place yet.

**The measurement gap is the current critical issue.** I'm making product decisions based on intuition rather than data. This is the next thing to fix.

---

## What I'd Do Differently

**Make Organization mandatory from day one.**

I added the Organization model after the initial build, when I started thinking about multi-tenant commercial use. The problem: I didn't enforce it at registration, so some users ended up with no organization affiliation. Retrofitting a NOT NULL constraint onto a live schema is painful — I deferred it with `null=True, blank=True` and added rescue paths for orphaned users. Those rescue paths now create subtle ambiguity in tenant data boundaries, and I'm still working through that carefully.

The lesson: schema decisions about multi-tenant boundaries have outsized long-term cost. "Add it later" is expensive when "later" arrives.

**Build usage analytics before building features.**

Early on, I added features based on what I thought was needed. The result: I now have no data to tell me what's actually being used, what's not, or what to prioritize next. Measurement infrastructure should have come before the second feature.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | Python / Django 5.1.3 | Familiarity, ecosystem maturity |
| Database | PostgreSQL (Cloud SQL) | Managed, reliable |
| Hosting | Google App Engine | Free tier, GCP-native integration |
| Async | Cloud Pub/Sub | Full decoupling from web process |
| Encryption | Cloud KMS + cryptography | Envelope encryption for tenant secrets |
| AI | OpenAI API | Content generation + conversation |
| Messaging | LINE Messaging API | Near-universal Japan penetration |
| Algorithm | SuperMemo-2 | Science-backed study scheduling |

---

## Project Scale

| Metric | Value |
|--------|-------|
| Django apps | 11 |
| Models | 40+ |
| Subjects | English vocabulary, listening, reading, mathematics (chemistry and classical Japanese in development) |
| User roles | 4 (Organization Admin / Classroom Admin / Teacher / Student)
