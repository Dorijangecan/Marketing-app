# MVP BACKLOG — START EXECUTION

## Sprint 0 (Foundation)

1. Postaviti repo standarde (lint, formatting, commit konvencije).
2. Definirati env konfiguraciju i secrets strategiju.
3. Postaviti PostgreSQL + Redis lokalni setup.
4. Definirati početni ERD i migracije.
5. Dodati health, readiness i liveness endpointe.

## Sprint 1 (Auth + Workspace)

6. Implementirati signup/login/reset.
7. Dodati JWT/session mehanizam.
8. Implementirati workspaces CRUD.
9. Implementirati memberships i role enforcement.
10. Napraviti middleware za workspace scoping.

## Sprint 2 (Brand + Calendar AI)

11. Brand profile CRUD.
12. Content pillar generator endpoint.
13. 30-day calendar generator endpoint.
14. Spremanje AI outputa uz metadata model_source i quality_score.
15. UI flow za pregled i edit generated plana.

## Sprint 3 (Content generation)

16. Hook generator (10+ varijanti).
17. Caption generator (short/long/story/thread).
18. Hashtag intelligence po niši/lokaciji.
19. Human-review status tok za generated sadržaj.
20. Batch generation pipeline za 30 objava.

## Sprint 4 (Publishing + analytics)

21. Draft/review/scheduled/published/rejected state machine.
22. Scheduler worker + retry/backoff + DLQ.
23. Integracija s prve 2 platforme (npr. IG + LinkedIn).
24. Analytics ingest job + dnevna agregacija.
25. Dashboard KPI endpointi.

## Sprint 5 (Hardening + billing)

26. Quota counters i plan enforcement.
27. Feature flags po paketu.
28. Audit log i admin pregled kritičnih akcija.
29. SLO dashboard i alerting.
30. Beta onboarding flow i feedback loop.
