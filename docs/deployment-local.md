# Local Deployment (Docker)

## What this provides

- Multi-stage API image (`apps/api/Dockerfile`) with a non-root runtime user.
- Local infra stack via `docker-compose.yml`:
  - API
  - PostgreSQL (with healthcheck)
  - Redis (with healthcheck)

## Run

```bash
docker compose up --build
```

API is available at:
- `http://localhost:8080/health`
- `http://localhost:8080/ui/`

## Notes

- Current app persistence logic is still SQLite-first in code, while compose includes PostgreSQL/Redis as the next infra step.
- Compose/env scaffolding is included to accelerate migration from SQLite to managed infra.

- Compose waits for PostgreSQL/Redis healthchecks before starting API dependency chain.
