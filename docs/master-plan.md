# HYBRID AI MARKETING SAAS — FINAL MASTER PLAN

## 1. Product goal

Izgraditi SaaS koji automatizira:

1. planiranje marketinga
2. generiranje objava
3. kreiranje vizuala
4. objavljivanje
5. optimizaciju strategije

**North-star outcome:** korisnik može pripremiti 30 dana sadržaja u 10 minuta.

---

## 2. MVP v1 scope (must-have)

### In scope (launch)

- Email/password auth (signup/login/reset)
- Workspace + member roles (owner, editor)
- Brand profile konfiguracija
- 30-day content calendar generator
- Caption + hashtag generator
- Draft → review → scheduled workflow
- Manual scheduling + osnovni smart time suggestion
- Basic analytics ingest (reach, likes, comments, clicks)

### Out of scope (post-MVP)

- Full DM funnel automatizacija
- Auto-reply na sve komentare bez human review
- Napredni video engine (auto subtitles + music sync)
- Competitor radar u realnom vremenu
- 60/90-day plan generation

### MVP acceptance criteria

- Novi korisnik može kreirati račun, workspace i brand profil u < 5 min.
- Sustav može generirati 30 draft objava (caption + hashtag + platform + date) u < 10 min.
- Korisnik može ručno odobriti i zakazati objave za barem 2 platforme.
- Najmanje 95% scheduling jobova završi uspješno unutar planiranog vremena.
- Dashboard prikazuje minimalno 7 dana agregiranih performansi po platformi.

---

## 3. Hybrid AI architecture (80/20)

### Local AI (default, ~80%)

Koristi se za:

- caption generation
- hashtag generation
- content ideje
- audience i tone klasifikaciju
- osnovne comment draft odgovore

Predloženi modeli: Qwen Instruct, Mistral, DeepSeek.

### Cloud AI (escalation, ~20%)

Koristi se za:

- kompleksne strategije
- high-stakes copywriting
- content audit
- advanced analytics reasoning

Predloženi modeli: GPT, Claude, Gemini.

### Routing policy

- `LOW_COMPLEXITY`: local-first, timeout 3s, max 1 retry.
- `MEDIUM_COMPLEXITY`: local-first, fallback na cloud ako quality score < threshold.
- `HIGH_COMPLEXITY`: cloud-first s budget guardrailom.

### Fallback chain

1. primarni local model
2. sekundarni local model
3. cloud model
4. human review queue

---

## 4. System architecture

Frontend Dashboard  
↓  
API Gateway  
↓  
Task Queue  
↓  
AI Engine (routing + guardrails)  
↓  
Local Models + Cloud Models  
↓  
Publishing Engine  
↓  
Analytics Engine

---

## 5. Multi-tenant data model (core entities)

- `users`
- `workspaces`
- `memberships`
- `roles`
- `brand_profiles`
- `social_accounts`
- `content_items`
- `content_variants`
- `media_assets`
- `publish_jobs`
- `analytics_events`

### Tenancy rules

- Svaki zapis mora imati `workspace_id` gdje je primjenjivo.
- API upiti se uvijek izvršavaju u workspace scopeu.
- Row-level auth mora spriječiti cross-workspace pristup.

### Audit fields

- `created_at`, `updated_at`
- `created_by`, `updated_by`
- `model_source` (local/cloud/model-id)
- `approval_state`

---

## 6. Security & compliance baseline

- GDPR: data minimization, consent evidence, right-to-delete flow.
- Secrets management: rotacija social API tokena.
- Audit log za AI i publish akcije.
- Rate-limit + anti-abuse pravila za comment/DM module.
- Human-approval gate za osjetljive outgoing odgovore.

---

## 7. Reliability (SLO)

- Publish success rate: **≥ 95%**
- Schedule accuracy: **≥ 99%** (objava unutar definiranog vremenskog prozora)
- AI generation p95: **< 8s** za standardni caption task
- Incident acknowledgement: **< 15 min** za P1

### Resiliency controls

- retry s exponential backoff
- dead-letter queue za failed jobs
- idempotency key za publish endpoint
- health dashboard (queue depth, failures, quota)

---

## 8. Monetization model (enforced)

### Starter — 20€/month

- 30 AI posts
- 1 account

### Pro — 49€/month

- 100 AI posts
- 3 accounts
- trend analysis

### Agency — 99€/month

- unlimited posts
- 10 accounts
- competitor tracking

### Usage definition

`AI post` = calendar entry + generated caption + hashtag set (+ opcionalni visual prompt).  
Quota se broji na razini workspacea po billing periodu.

---

## 9. Execution phases

1. Core platform (auth, workspace, brand profile, media)
2. Content strategy AI (pillars, 30-day calendar, trend assist)
3. Content creation AI (hooks, captions, hashtags)
4. Creative engine (template-driven visuals)
5. Publishing engine (queue, statuses, multi-platform)
6. Lead generation (comment AI, DM assist)
7. Analytics + optimization AI
8. Unified dashboard
9. Automation brain (daily autonomous cycle)
