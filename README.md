# RuneChat

A FOSS, security-first chat platform — a Discord alternative deployed at `chat.moonrune.cc`.

## Stack

| Layer | Technology |
|---|---|
| Backend | Rust · Axum · SQLx · Tokio |
| Frontend | TypeScript · React · Vite · Zustand · TanStack Query |
| Database | PostgreSQL 16 |
| Real-time | Redis pub/sub |
| Deployment | Docker Compose · Nginx |

## Quick Start

```bash
cp .env.example .env
# Fill in JWT_SECRET and TOTP_ENCRYPTION_KEY (see .env.example for generation commands)

docker compose up --build
```

App available at `http://localhost:8080`.

## Development

**Backend tests** (requires the compose DB to be running):

```bash
docker compose up -d db redis
cd backend && cargo test
```

**Backend only** (hot-reload via `cargo watch`):

```bash
docker compose up -d db redis
cd backend && cargo run
```

**Frontend only:**

```bash
cd frontend && npm install && npm run dev
```

## Environment

Copy `.env.example` to `.env` and fill in the required secrets:

| Variable | Required | Notes |
|---|---|---|
| `JWT_SECRET` | Yes | `openssl rand -hex 64` |
| `TOTP_ENCRYPTION_KEY` | Yes | `openssl rand -base64 32` |
| `DATABASE_URL` | Yes | Pre-filled for local compose |
| `REDIS_URL` | Yes | Pre-filled for local compose |
| `SMTP_*` | No | Required for email OTP account unlock |

## API

Base path: `/api`

| Prefix | Description |
|---|---|
| `/api/auth` | Registration, login, refresh, logout, TOTP, account unlock |
| `/api/servers` | Server creation, membership |
| `/api/servers/:id/invites` | Invite management |
| `/api/channels` | Channel CRUD |
| `/api/messages` | Message history |
| `/ws` | WebSocket real-time messaging |
| `/health` | Health check |

## Security Model

- JWT access tokens: 15-minute expiry, in-memory only (never `localStorage`)
- Refresh tokens: `httpOnly` + `Secure` + `SameSite=Strict` cookie, one-time use with rotation
- Replay attack detection: reused refresh token → all sessions killed, account marked `compromised`
- Compromised accounts: login blocked, visible badge on username, messages after compromise flagged
- Account unlock: TOTP (primary) or email OTP (fallback if no TOTP enrolled)
- TOTP secrets: AES-256-GCM encrypted at rest
- WebSocket connections: JWT-authenticated, compromised accounts rejected at connect and during fan-out

## License

FOSS — license to be decided before public release.
