# On-call Runbook (MVP)

## 1) P1 incident definition

P1 = incident koji direktno blokira core tokove:
- signup/login
- generiranje plana
- scheduling/publishing
- ozbiljan rast `dead_letter` jobova

## 2) Immediate triage (first 15 min)

1. Provjeri `/health`, `/readyz`, `/metrics`.
2. Provjeri queue stanje:
   - `queue_depth`
   - `publish_success_rate`
   - `dead_letter_total`
3. Provjeri najnovije zapise u `audit_logs` za problematični workspace.
4. Ako su stuck jobovi prisutni:
   - pozovi reconcile endpoint
   - replay dead-letter po potrebi.

## 3) Manual recovery actions

- `POST /v1/content/{workspace_id}/jobs/reconcile-stuck`
- `POST /v1/content/{workspace_id}/jobs/retry-now`
- `POST /v1/content/{workspace_id}/dead-letter/replay`

## 4) Escalation

- Ako publish success rate padne ispod 95% > 30 min, eskalirati Engineering + Product.
- Ako postoji sumnja na security incident, odmah disable problem workspace tokene i eskalirati Security.

## 5) Post-incident

- Zabilježiti timeline, root cause, impact, corrective actions.
- Dodati regresijski test gdje je moguće.
