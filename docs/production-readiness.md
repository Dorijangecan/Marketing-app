# Production Readiness Checklist

Ovo je popis što još treba da platforma bude production ready.

## 1) Platform i infrastruktura

- [x] Container image za API (multi-stage build, non-root user) kroz `apps/api/Dockerfile`.
- [ ] IaC (Terraform/Pulumi) za reproducibilan deployment.
- [ ] Staging i production okruženja odvojena po infrastrukturi i tajnama.
- [ ] Managed PostgreSQL i Redis s backup policyjem (lokalni `docker-compose` scaffold dodan, managed setup preostaje).
- [ ] CDN + object storage za media library.

## 2) Security i compliance

- [ ] Secrets manager (nema plaintext tajni u env fajlovima u produkciji).
- [ ] Rotacija social OAuth tokena + key rotation policy.
- [x] Osnovni RBAC enforcement (workspace role checks) za content operacije.
- [x] Osnovni audit log za generation/status/scheduling akcije je implementiran.
- [x] GDPR tokovi: export/delete user data i retention policy (MVP compliance endpoints).

## 3) API i backend pouzdanost

- [x] `/health`, `/livez`, `/readyz` endpointi.
- [x] Request ID i osnovno structured logiranje.
- [x] Osnovni rate limiting po IP-u je implementiran.
- [x] Idempotency ključevi za generate-plan operacije.
- [x] Osnovni retry + dead-letter tok za publishing jobove je implementiran.
- [x] Osnovna publish queue tablica (`publish_jobs`) je implementirana (worker još nije).

## 4) Testiranje i kvaliteta

- [x] Osnovni API testovi za health/readiness.
- [ ] Unit testovi za business logiku (auth, workspace scoping, quota).
- [ ] Integracijski testovi (DB + queue).
- [ ] E2E testovi za ključne tokove (signup -> generate -> schedule).
- [x] Security testovi (auth bypass, access control, injection) pokriveni service-level testovima.

## 5) Observability

- [x] Osnovni `/metrics` endpoint za service/readiness signal je implementiran.

- [ ] Centralizirani logovi (npr. Loki/ELK).
- [x] Metrics (error rate, queue depth, publish success rate) dostupni kroz `/metrics` runtime snapshot.
- [x] Tracing za API -> AI -> publishing tok (request trace events + `x-trace-id` + p95 latency metric).
- [x] Alerting pravila za P1/P2 incidente definirana u `docs/alerting-rules.md` i exposed kroz `GET /v1/meta/alerting-rules`.
- [x] On-call runbook i incident response procedure dokumentirani u `docs/on-call-runbook.md`.

## 6) Product spec completeness

- [x] Osnovni campaign/experiment/lead modul implementiran.
- [x] Osnovni optimization recommendation engine implementiran.

- [x] Zaključati MVP API ugovore (OpenAPI + versioning) kroz `GET /v1/meta/api-contract` endpoint.
- [x] Definiran content lifecycle state machine (`draft/review/scheduled/published/rejected`).
- [x] Osnovni quota enforcement na razini workspacea.
- [x] Osnovni human-in-the-loop review queue za rizične content akcije je implementiran.
- [x] Platform policy compliance matrix (IG/TikTok/YouTube/LinkedIn) dokumentiran u `docs/platform-policy-compliance-matrix.md`.

## 7) Go-live kriteriji

Release se smatra spremnim kada su ispunjeni svi uvjeti:

1. Auth + workspace + brand profile + 30-day plan rade end-to-end.
2. Publish success rate u stagingu >= 95% kroz 7 uzastopnih dana.
3. Nema kritičnih sigurnosnih nalaza (high/critical).
4. Svi P0/P1 bugovi zatvoreni.
5. Runbook, rollback i backup restore test potvrđeni.
