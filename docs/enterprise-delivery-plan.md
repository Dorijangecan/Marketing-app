# Enterprise Delivery Plan — Hybrid AI Marketing SaaS

Ovaj plan definira kako podići završni enterprise proizvod: stabilan, siguran, skalabilan i jednostavan za korištenje.

## 1) Product Operating Model

## Ciljevi

- 30 dana marketinga u 10 minuta
- multi-workspace i multi-brand podrška
- enterprise security i auditability

## KPI-jevi

- onboarding completion rate
- generation-to-publish conversion rate
- publish success rate
- time-to-value (prva objava)
- monthly churn i net revenue retention

## 2) Enterprise Architecture Blueprint

- **UI Layer:** web dashboard (Python-served UI)
- **API Layer:** FastAPI (modularni routeri)
- **Orchestration:** async queue + worker pool
- **AI Layer:** local-first routing + cloud fallback
- **Data Layer:** PostgreSQL + Redis + object storage
- **Observability:** logs, metrics, traces, alerts
- **Security Layer:** SSO/OAuth, RBAC, audit logs, secrets manager

## 3) Delivery Roadmap (12–16 tjedana)

### Wave 1 — Foundation (tjedni 1–3)

- auth + workspace + brand profile
- content entities i state machine
- health/readiness/liveness + request tracing
- UI shell i osnovna navigacija

### Wave 2 — Core Value (tjedni 4–7)

- 30-day calendar generator
- caption/hashtag generator
- review i scheduling workflow
- osnovni analytics dashboard

### Wave 3 — Enterprise Hardening (tjedni 8–11)

- RBAC enforcement i audit trails
- quota/billing enforcement
- retry, DLQ, idempotency
- SLO dashboard i incident runbook

### Wave 4 — Scale & GTM (tjedni 12–16)

- multi-platform publishing hardening
- performance tuning i cost controls
- beta rollout, customer success playbooks
- production go-live gate

## 4) Enterprise Non-Functional Requirements

- **Availability:** 99.9% monthly
- **Security:** nema high/critical nalaza prije go-live
- **Performance:** p95 generation latency < 8s
- **Reliability:** publish success >= 95%
- **Compliance:** GDPR data lifecycle i delete workflow

## 5) UX Strategy (User-friendly by default)

- Wizard onboarding (brand profile + connected channels + prvi 30-day plan)
- One-click “Generate next 30 days”
- Human review inbox (AI drafts, risk flags)
- Jasne status oznake (draft/review/scheduled/published)
- Ugrađeni “What should I do next?” assistant panel

## 6) Governance

- RACI matrica (Product, Engineering, AI, Security, QA, CS)
- architecture review board za ključne promjene
- weekly release train + change approval
- rollback strategy i incident drills

## 7) Go-live gate

Release dopušten isključivo kada:

1. kritični user tokovi prolaze e2e (signup -> plan -> generate -> schedule)
2. SLO i security gateovi zadovoljeni u stagingu
3. backup/restore i disaster-recovery testirani
4. support i on-call procesi spremni
