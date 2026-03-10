# Hybrid AI Marketing SaaS

Početna osnova za razvoj platforme koja omogućava korisniku da pripremi **30 dana marketinga u 10 minuta**.

## Trenutno implementirano

- FastAPI API + web UI dashboard (`/ui/`).
- JWT-like token auth with purpose scoping (`access` vs `password_reset`) and issuer/audience checks (`signup`, `login`, `Authorization: Bearer <token>`).
- Workspace management: create/list uz role članstva.
- Campaign management osnova (create/list).
- Experiment engine osnova (create A/B varijante + scoring).
- Lead event ingestion i lead scoring osnova.
- Optimization recommendation engine (KPI snapshot + preporuke + history).
- Human review queue + compliance check za rizičan sadržaj.
- 30-day content plan generator.
- Content micro-generators (hooks, caption, hashtags, batch assets).
- Autopilot strategy engine (ICP + positioning + channel mix constrained by connected channels + KPI targets + strict quality gate).
- Executive scorecard (cross-functional grade: strategy, execution, demand, revenue readiness).
- Operating review endpoint (unified go/no-go decision across scorecard + optimization signals).
- Content lifecycle statusi: `draft`, `review`, `scheduled`, `published`, `rejected`, `failed`, `dead_letter`.
- Quota enforcement po planu (`Starter`, `Pro`, `Agency`).
- Idempotency za generate-plan pozive preko `x-idempotency-key`.
- Audit log i audit API po workspaceu.
- Publish scheduling queue zapis (`publish_jobs`) + ručni publisher cycle endpoint.
- Retry + dead-letter handling za neuspješne publish jobove.
- Basic rate limiting po IP-u.
- Health stack: `/health`, `/livez`, `/readyz` (+ `/metrics`).

## Pokretanje kroz Python

```bash
cd apps/api
python run.py
```

Zatim otvori:

- `http://localhost:8080/ui/` — web dashboard
- `http://localhost:8080/docs` — OpenAPI dokumentacija

## API endpointi

Public:
- `POST /v1/auth/signup`
- `POST /v1/auth/login`

Protected (`Authorization: Bearer <token>`):
- `POST /v1/workspaces`
- `GET /v1/workspaces`
- `POST /v1/workspaces/{workspace_id}/features/overrides`
- `POST /v1/campaigns`
- `GET /v1/campaigns/{workspace_id}`
- `POST /v1/experiments`
- `POST /v1/experiments/score`
- `POST /v1/leads`
- `GET /v1/leads/{workspace_id}`
- `POST /v1/optimization/{workspace_id}/recommendations`
- `GET /v1/optimization/{workspace_id}/history`
- `POST /v1/optimization/{workspace_id}/autopilot-execute`
- `GET /v1/optimization/{workspace_id}/executive-scorecard`
- `GET /v1/optimization/{workspace_id}/operating-review`
- `GET /v1/optimization/{workspace_id}/operating-review/history`
- `GET /v1/optimization/{workspace_id}/operating-review/trend`
- `GET /v1/optimization/{workspace_id}/decision-timeline`
- `POST /v1/content/generate-plan` (+ header: `x-idempotency-key`)
- `POST /v1/content/{workspace_id}/generate-hooks`
- `POST /v1/content/{workspace_id}/generate-caption`
- `POST /v1/content/{workspace_id}/generate-hashtags`
- `POST /v1/content/{workspace_id}/batch-generate-assets`
- `POST /v1/content/{workspace_id}/post-blueprint`
- `POST /v1/content/{workspace_id}/edit-caption`
- `POST /v1/content/{workspace_id}/select-caption`
- `GET /v1/content/{workspace_id}/asset/{item_id}`
- `GET /v1/content/{workspace_id}`
- `PATCH /v1/content/{workspace_id}/status`
- `POST /v1/content/{workspace_id}/compliance-check`
- `GET /v1/content/{workspace_id}/review-queue`
- `POST /v1/content/{workspace_id}/review-resolve`
- `POST /v1/content/{workspace_id}/schedule`
- `POST /v1/content/{workspace_id}/run-publisher`
- `GET /v1/content/{workspace_id}/jobs`
- `GET /v1/content/{workspace_id}/dead-letter`
- `POST /v1/content/{workspace_id}/dead-letter/replay`
- `GET /v1/audit/{workspace_id}`

Ops:
- `GET /health`, `GET /livez`, `GET /readyz`, `GET /metrics`

## Napomena o AI generiranju (trenutno stanje)

- Trenutna implementacija content generatora je **local template + heuristic** pristup (MVP), bez direktnog cloud LLM provider poziva.
- Svaki AI izlaz se i dalje bilježi kroz audit trag (`ai_decisions`) s metadata poljima poput `model_source` i `quality_score`.
- Ovo omogućava stabilan workflow (RBAC, quota, idempotency, audit), te ostavlja jasan put za buduću nadogradnju na pravi provider routing.

## Dokumentacija

- `docs/master-plan.md`
- `docs/mvp-backlog.md`
- `docs/production-readiness.md`
- `docs/next-significant-improvements.md`
- `docs/enterprise-delivery-plan.md`
- `docs/enterprise-execution-plan.md`
