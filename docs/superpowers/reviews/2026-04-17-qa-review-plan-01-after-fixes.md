# QA Review: Plan 01 After Fixes

Date: 2026-04-17  
Updated: 2026-04-18
Reviewer: Rhea Solis

## Verdict

Plan 01 is Rhea-cleared for continued development after Docker validation and Scout-driven image hardening.

Production deployment remains blocked until the Postgres image CVE exposure is either remediated or accepted through a documented production risk decision.

## Resolved Findings

1. Backend Docker build context now uses the workspace root.

   `docker-compose.yml` sets `app.build.context: .` and `dockerfile: backend/Dockerfile`. The backend Dockerfile now copies the root workspace manifests plus `backend/Cargo.toml`, then builds with `cargo build --release -p runechat-backend`.

2. Proxy service is now present.

   `docker-compose.yml` includes a `proxy` service on `8080:80`, backed by `nginx/dev.conf`. The app and frontend are exposed internally instead of published directly.

3. Env-mutating config tests are serialized.

   `backend/src/config.rs` now uses a static `Mutex` around tests that mutate process environment variables.

4. Root `Cargo.lock` is tracked.

   The backend Dockerfile depends on `Cargo.lock`, and it is now part of the repo.

5. Root `.dockerignore` exists.

   The root Docker context excludes local secrets, `.git`, `.remember`, node dependencies, and build outputs.

## Verification Performed

- `npm run lint` from `frontend/`: passed.
- `npm run build` from `frontend/`: passed.
- Static review of `docker-compose.yml`, `backend/Dockerfile`, `nginx/dev.conf`, `.dockerignore`, `Cargo.lock`, and env-test mutex: passed.
- Pre-hardening baseline matched `origin/master` at `a3f9f13`.
- Initial `docker compose config --quiet`: passed after Docker became available.
- Initial `docker compose build`: exposed a real blocker: `rust:1.77-alpine` could not parse Cargo lockfile version 4.
- Rhea changed the backend builder image to `rust:1-alpine`, added `frontend/.dockerignore`, and removed the obsolete Compose `version` key.
- Rhea updated runtime images after Docker Scout review:
  - backend runtime: `alpine:3.23`
  - frontend runtime: `nginx:1.30-alpine-slim`
  - proxy: `nginx:1.30-alpine-slim`
  - Redis: `redis:8-alpine`
- `docker compose up --build -d`: passed.
- `docker compose ps`: all services up; Postgres and Redis healthchecks healthy.
- `curl http://localhost:8080/health`: returned `{"status":"ok"}`.
- `curl http://localhost:8080`: returned HTTP 200.
- `docker build --target builder -t runechat-backend-builder -f backend/Dockerfile .`: passed.
- `/usr/local/cargo/bin/cargo test -p runechat-backend` inside the exported builder image: passed, 7 tests.

## Docker Scout Result

- `runechat-app:latest`: 0 critical, 0 high, 1 medium, 0 low. Remaining finding is BusyBox in Alpine.
- `runechat-frontend:latest`: 0 critical, 0 high, 1 medium, 0 low. Remaining finding is BusyBox in Alpine.
- `nginx:1.30-alpine-slim`: 0 critical, 0 high, 1 medium, 0 low. Remaining finding is BusyBox in Alpine.
- `redis:8-alpine`: 0 critical, 0 high, 1 medium, 0 low. Remaining finding is BusyBox in Alpine.
- `postgres:16-alpine`: 1 critical, 10 high, 15 medium, 1 low after Scout exceptions; findings are from official-image dependencies including Go stdlib metadata, BusyBox, and OpenLDAP.

## Residual Risk

The Compose stack is acceptable for local development and Plan 2 execution. It is not acceptable as a production deployment baseline while `postgres:16-alpine` retains critical/high Docker Scout findings.

## Rhea Gate

Plan 01 development gate is cleared.

Production gate remains closed on the database image until Postgres CVE mitigation is resolved or explicitly risk-accepted in the vault.
