# Sljedeća značajna poboljšanja (prioritetno)

Ovaj dokument daje **kratki, praktični prioritet** što dalje nakon MVP scaffolda.

## P0 (najveći utjecaj na pouzdanost i go-live)

1. **Migracija sa SQLite na PostgreSQL + Redis u aplikacijskom sloju**
   - Ukloniti SQLite-first putanje i prebaciti ključne tokove (auth, content, publish queue, rate limit) na produkcijski data stack.
   - Dodati migracijski mehanizam (npr. Alembic) i rollback plan.

2. **Staging/Production okruženja + IaC**
   - Terraform/Pulumi za reproducibilan deployment.
   - Odvojene mreže, tajne i baze po okruženju.

3. **Secrets management i key rotation**
   - Prebaciti JWT/OAuth tajne u secrets manager (npr. AWS Secrets Manager, Vault).
   - Uvesti policy i automatizaciju rotacije ključeva/tokena.

4. **Kvaliteta i release gateovi**
   - Integracijski testovi (DB + queue) i E2E tokovi (signup -> generate -> schedule -> publish).
   - Obavezni quality gate u CI prije deploya.

## P1 (skaliranje i operativna izvrsnost)

5. **Pravi worker + scheduler runtime**
   - Odvojeni worker proces(i), periodic scheduler i backoff/retry tuning po provideru.
   - Idempotency enforcement na API i worker granici.

6. **Observability upgrade**
   - Centralizirani logovi + dashboardi (error rate, queue depth, publish success).
   - SLO/SLA alerting sa jasnim ownershipom i runbook linkovima.

7. **Sigurnosno očvršćivanje API-ja**
   - Fine-grained RBAC/ABAC, audit korelacija po request trace-u.
   - Hardening token validacije (issuer/audience/expiry policy), revocation strategija.

## P2 (produkt i enterprise readiness)

8. **Media pipeline**
   - Object storage + CDN i lifecycle policy za medijske artefakte.

9. **Policy/compliance automation**
   - Proširiti compliance engine sa strožim pravilima po platformi i explainability zapisima.

10. **FinOps i capacity planning**
   - Budžeti, kvote, metering po workspaceu i cost visibility (AI usage + publishing).

## Predloženi redoslijed implementacije (6-8 tjedana)

- **Sprint 1-2:** PostgreSQL/Redis migracija + Alembic + integracijski testovi.
- **Sprint 3:** IaC + staging/prod separation + secrets manager.
- **Sprint 4:** Worker/scheduler hardening + observability + SLO alerting.
- **Sprint 5+:** E2E gateovi, policy automation, media pipeline.
