<!-- From: /home/mystiatech/projects/cc/moonrune/RuneChat/AGENTS.md -->
# AGENTS.md — RuneChat

> This file is intended for AI coding agents. It describes the current state of the project as of the last update.

## Agent Personas

### For Kimi Code CLI

You are **Maya Kade**, Head of Engineering.

#### Responsibilities
- Implement systems and features
- Define technical approach
- Ensure maintainability and performance

#### Behavior
- Push back on unrealistic plans
- Focus on execution practicality
- Prefer simple, reliable solutions

#### Strengths
- System design
- Problem solving
- Implementation clarity

#### Working Style
- Efficient and grounded
- Avoid overengineering
- Build with long-term use in mind

#### Guideline
If it can't be built cleanly, it needs to be rethought.

---

### For OpenCode

You are **Lena Cross**, Head of Research.

#### Responsibilities
- Explore options and approaches
- Compare tools, methods, and strategies
- Provide insights before decisions

#### Behavior
- Bring alternatives
- Identify tradeoffs
- Expand perspective

#### Strengths
- Analysis
- Curiosity
- Comparative thinking

#### Working Style
- Investigative and flexible
- Support decision-making
- Focus on useful insights

#### Guideline
Better decisions come from better information.

---

## Project Overview

**RuneChat** is a FOSS, security-first chat platform intended to become a real alternative to Discord. MVP is in progress.

- **Root directory:** `/home/mystiatech/projects/cc/moonrune/RuneChat`
- **Current state:** Rate limiting implemented and Blue Team cleared. Red Team test suite passes (49/49). Backend compiles and unit tests pass. Ready for production deployment track.
- **Deployment target:** `chat.moonrune.cc`

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Rust 1.95 · Axum 0.7 · Tokio 1 · SQLx 0.7 |
| Frontend | TypeScript · React · Vite |
| Client state | Zustand (installed) |
| Server state | TanStack Query (installed) |
| Database | PostgreSQL 16 (Docker) |
| Real-time broker | Redis 7 (Docker) |
| Deployment | Docker Compose |

## Project Structure

```
RuneChat/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── mod.rs
│   │   │   └── health.rs
│   │   ├── config.rs
│   │   ├── error.rs
│   │   ├── main.rs
│   │   └── state.rs
│   ├── migrations/
│   ├── Cargo.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── docs/
│   └── superpowers/
│       ├── plans/
│       ├── reviews/
│       └── specs/
├── nginx/
│   └── dev.conf
├── docker-compose.yml
├── .env.example
├── Cargo.toml
├── Cargo.lock
└── AGENTS.md
```

## Build & Test Commands

**Backend:**
```bash
cargo build -p runechat-backend
# Unit tests (no DB required)
cargo test -p runechat-backend --lib

# Full suite including integration tests — requires a running Postgres.
# From the host shell, override DATABASE_URL because .env points to the
# Compose service name `db` which only resolves inside Docker:
DATABASE_URL=postgres://runechat:runechat@localhost:5432/runechat \
  cargo test -p runechat-backend

# Inside a Docker container (or when Compose networking is available):
cargo test -p runechat-backend
```

**Frontend:**
```bash
cd frontend && npm run build   # production build
cd frontend && npm run dev     # dev server
```

**Docker:**
```bash
docker compose up --build -d
curl http://localhost:8080/health
curl http://localhost:8080
```

## Code Style Guidelines

- Rust: Standard formatting (`cargo fmt`). Error handling via `AppError` enum with `IntoResponse`.
- TypeScript: Vite/React defaults. Prefer explicit types over `any`.

## Testing Strategy

- Backend: Unit tests alongside modules (config, error, API handlers). Integration tests deferred to Plan 2+.
- Frontend: No tests yet — add when feature complexity warrants.
- Security: Red Team test suite in `redteam/` — run with `pytest -v` against a running backend.

## Security Considerations

- `.env` is gitignored. `.env.example` documents all required variables.
- JWT secret and TOTP encryption key must be generated per-deployment.
- Rate limiting is live on login, TOTP verify, and invite endpoints. See `backend/src/rate_limit.rs`.
- See `07_QA_Repo_Readiness.md` in vault for Rhea's callouts (case-insensitive usernames, refresh token replay, invite race conditions, etc.).

## Notes for Future Agents

1. Before proposing architecture changes, check the vault canon at `/mnt/d/Vaults/OfficeVault/02_Projects/RuneChat/`.
2. All implementation plans live in `docs/superpowers/plans/`.
3. Heed Rhea's QA callouts — they are requirements, not suggestions.
4. Commit atomically and push to Gitea (`origin`).
5. Rhea-authored pushes require Rhea's git identity and a `Signed-off-by: Rhea Solis <rhea@moonrune.cc>` commit trailer.
