# Enterprise Execution Plan — Marketing Autopilot (Professional Outcomes)

Cilj: platforma mora davati **konzistentne, mjerljive i enterprise-grade marketinške rezultate** uz minimalnu ručnu intervenciju.

## 1) North Star i outcome model

## North Star
- "From brief to pipeline": od business briefa do kvalificiranog pipeline-a uz kontroliranu CAC efikasnost.

## Primarni poslovni outcome-i
- `MQL/month` rast po workspaceu
- `Pipeline value` rast po mjesecu
- `Publish success rate >= 98%`
- `Time-to-launch` kampanje < 24h

## Produktni outcome-i
- `Autopilot strategy quality score >= 0.80` (median)
- `Review pass-through rate >= 85%`
- `Content-to-meeting conversion` rast sprint-over-sprint

## 2) Enterprise target operating model

- **AI Strategist Layer**: generiranje positioning-a, poruka, channel mixa, KPI targeta i quality gate odluke.
- **Campaign Orchestrator Layer**: raspoređivanje kampanja i content cadence po kanalima.
- **Execution Layer**: publishing engine (queue, retry, DLQ, reconciliation).
- **Control Layer**: compliance, audit, approvals, incident i rollback procedure.
- **Intelligence Layer**: attribution, optimization loop, budget reallocation preporuke.

## 3) Delivery plan po valovima (16 tjedana)

### Wave A (tjedni 1-4) — Platform hardening za enterprise

**Must-have isporuke**
1. PostgreSQL + Redis migracija (uklanjanje SQLite-first putanja).
2. IaC za staging/prod + izolacija tajni i mreže.
3. Secrets manager + key rotation.
4. CI quality gates (unit + integration + e2e smoke + security checks).

**Acceptance gate**
- 0 blocker security nalaza.
- Staging stabilnost 7 dana bez P1 incidenta.

### Wave B (tjedni 5-8) — Autopilot marketing operations

**Must-have isporuke**
1. Autopilot strategy endpoint kao default entrypoint za nove kampanje.
2. Multi-objective quality gate (clarity, ICP fit, channel fit, budget realism).
3. Review workflow s obveznim razlogom za reject/revise.
4. KPI budget planner (plan-vs-actual).

**Acceptance gate**
- >= 80% strategija prolazi quality gate bez manualnog rewrite-a.
- >= 90% kampanja ima kompletan brief + KPI contract.

### Wave C (tjedni 9-12) — Revenue loop automation

**Must-have isporuke**
1. Automated optimization ciklus (weekly): budget shift, cadence tuning, message iteration.
2. Lead scoring feedback loop prema content/campaign varijantama.
3. Alerting za pad performansi i predloženi remediation playbook.

**Acceptance gate**
- Mjerljiv uplift u MQL i conversion metricima (workspace cohorts).

### Wave D (tjedni 13-16) — Enterprise go-live

**Must-have isporuke**
1. SLO dashboard + on-call ownership model.
2. DR/backup/restore testovi i dokumentirani runbook.
3. RBAC/ABAC policy hardening i audit evidence package.
4. Customer success playbook za rollout po enterprise accountima.

**Acceptance gate**
- Go-live criteria potpisan od Product + Engineering + Security.

## 4) KPI contract (weekly operating cadence)

Svaki workspace/kampanja mora imati:
- poslovni cilj (pipeline/MQL target)
- ICP definiciju
- budget granice i channel allocation
- expected cadence
- SLA za review i publish

Ako neki element nedostaje, strategija ide u `revise`.

## 5) Engineering execution discipline

- Trunk-based workflow + obavezni PR template s rizikom i rollback planom.
- Definition of Done uključuje: test coverage, observability, audit evente i docs update.
- Svaka nova automacija mora imati feature flag i safe fallback.

## 6) Risk register (top 5)

1. **Model quality drift** -> canary + periodic eval benchmark.
2. **Channel policy violation** -> stricter policy matrix + pre-publish checks.
3. **Queue congestion** -> worker autoscaling + retry backoff tuning.
4. **Attribution noise** -> standardized event schema + data QA checks.
5. **Security debt** -> monthly security review + key/token rotation audit.

## 7) 30-60-90 day immediate plan

### 0-30 dana
- završi infra i security P0 (Postgres/Redis + IaC + secrets + CI gates)

### 31-60 dana
- standardiziraj autopilot strategy quality gate i review policy

### 61-90 dana
- uključi closed-loop optimization i cost/performance governance

## 8) Definition of success

Projekt se smatra uspješnim kada platforma:
1. konzistentno isporučuje profesionalne marketinške preporuke i egzekuciju,
2. smanjuje potrebu za ručnim operativnim marketing radom,
3. pokazuje mjerljiv poslovni uplift uz enterprise-grade sigurnost i pouzdanost.
