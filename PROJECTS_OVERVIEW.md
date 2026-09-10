# Projects Overview — A Coherent Portfolio

> A unified view of four university coursework briefs and the one project I implemented end-to-end, showing how they share a single, transferable tech stack.

## Positioning

**"Self-hostable, privacy-first AI web systems."**

Three of the four briefs (#1, #4, and the production-backend emphasis of #3) converge on the same idea: AI features delivered through a backend service the user controls, with transparent, explainable logic. The Expense-Sharing App is the **reference implementation** of that theme — built to production quality — and the other three are variations on the same stack I have now mastered.

## The shared stack (the "spine")

- **Python 3.11+** — FastAPI, Pydantic v2, uvicorn
- **Containerization** — Docker, docker-compose (self-hostable by design)
- **LLM / Vision-Language Model integration** — Qwen-VL via OpenAI-compatible API, pluggable backend (mock + real)
- **Auth & multi-tenancy** — standard-library only: `pbkdf2` password hashing + `hmac`-signed bearer tokens, SQLite storage
- **Observability** — JSONL access logging middleware, Locust / httpx load-test harness
- **Deterministic algorithms** — float-safe split engine, greedy minimum-cash-flow settlement, (rate-limiting for #3)
- **Frontend dashboards** — vanilla-JS SPA, no build step

## Implementation status

| Project | Status |
|---------|--------|
| #4 AI Expense-Sharing App | **Implemented to production quality** (23 tests, Docker, real VLM end-to-end, load report) |
| #1 Learning Buddy | Course assignment brief (specification) |
| #2 Location-Recommender | Course assignment brief (specification) |
| #3 Rate Limiting & Abuse Detection API Gateway | Course assignment brief (specification); next candidate to implement |

## Capability matrix

| Competency | #1 Learning Buddy | #2 Location-Recommender | #3 API Gateway | #4 Expense App (built) |
|------------|:---:|:---:|:---:|:---:|
| Python | ✅ | — | ✅/Java | ✅ |
| FastAPI / web backend | ✅ (Web UI) | ✅ (app) | ✅ (middleware) | ✅ FastAPI |
| Docker / containerization | — | — | ✅ (optional) | ✅ |
| LLM / OCR / CV | ✅ LLM | (sentiment) | — | ✅ Qwen-VL |
| Auth / multi-user | — | ✅ users/social | ✅ API keys | ✅ pbkdf2/hmac |
| Observability (logging/metrics) | — | — | ✅ | ✅ JSONL/Locust |
| Deterministic algorithms | (adaptive) | — | ✅ rate-limit/abuse | ✅ split/min-cash |
| Frontend dashboard | ✅ | ✅ | (admin opt.) | ✅ SPA |
| Self-hostable / privacy | ✅ | — | — | ✅ |

The ✅ marks are not coincidental — they trace a single spine reused across products.

## Per-project detail

### #4 AI Powered Expense-Sharing App — *Flagship, implemented*
- **Tech stack:** Python · FastAPI · Docker · Qwen-VL OCR · integer-cent split engine (4 strategies) · greedy min-cash-flow · pbkdf2/hmac auth + SQLite · JSONL logging · Locust · vanilla-JS dashboard.
- **Overlap:** This *is* the reference implementation of the brief — 100% correspondence (OCR extraction, equal/item/proportional/weighted splits, transaction-reduction algorithm, self-hosted containerization).
- **What I did:** Designed and built the whole system from scratch; verified a real receipt end-to-end through Qwen-VL; 23 passing tests; load-tested and documented (QPS / p99).

### #3 Rate Limiting & Abuse Detection API Gateway
- **Tech stack (from brief):** middleware-based backend, API-key validation, fixed/sliding-window rate limiting, abuse-pattern detection, HTTP 429, in-memory counters, request logging + metrics, optional token-bucket / JA4 / Redis / Docker / CI.
- **Overlap with my stack:** API-key auth pattern ✅ · observability (logging/metrics) ✅ · Docker ✅ · middleware-style JSONL logging ✅ (Stages 5–6 of the Expense App already implement these). **Not yet built:** token-bucket, JA4 fingerprints, distributed Redis counters.
- **Why it matters:** Directly addresses a backend-systems / experimental-evidence gap. The Expense App already covers 3 of its core objectives; the remaining pieces (rate limiting, abuse detection) are the natural next build on the same spine.

### #1 Learning Buddy — Adaptive AI Study Assistant
- **Tech stack (from brief):** LLM-based question generation & evaluation, content chunking, mistake-to-topic mapping, progress dashboard, privacy/minimal-retention.
- **Overlap:** LLM/Vision-LM call pattern ✅ · self-hosted ✅ · frontend dashboard ✅. The OCR→structured-data→compute pipeline in the Expense App demonstrates the same LLM-integration competence.
- **Note:** Shows the LLM-integration skill applied to a different domain (education).

### #2 Location-Recommender
- **Tech stack (from brief):** geo-data classification, social-graph modeling, photo storage, proximity alerts, sentiment analysis.
- **Overlap:** Only the generic web-app + dashboard + user-model pattern. Domain-specific tech (geo / social graph) is outside the shared spine.
- **Note:** Demonstrates breadth; included to show range, not depth of the core stack.

## How this strengthens an application

1. **One production-grade implementation de-risks the others.** Reviewers see a real, tested, deployed system — not four partial course exercises.
2. **Recurring stack = transferable competence.** The matrix shows the same spine reused across four products, which reads as mastery, not a collection of toy apps.
3. **The #3 overlap targets a known gap.** Stages 5–6 of the Expense App already deliver the auth / observability / containerization that #3 requires, framing the API-Gateway project as the credible next step.

## Originality note

The four documents are **course assignment briefs (specifications)**. The Expense-Sharing App is an **independent, from-scratch implementation**. Overlap is in *skills and stack*, not in copied code — each project would be built on its own repository and architecture.

## Next step

Implement **#3 (API Gateway + Abuse Detection)** to close the backend-systems gap, reusing the exact same FastAPI / Docker / observability spine and adding rate-limiting + abuse-detection as the new capabilities.
