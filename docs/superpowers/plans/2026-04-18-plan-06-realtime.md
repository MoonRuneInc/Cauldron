# Real-time (WebSocket + Redis pub/sub) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WebSocket support — JWT auth on connect, per-user sender registry in a `DashMap`, Redis pub/sub subscriber that fans out incoming messages to connected WebSocket clients in the correct server/channel.

**Architecture:**
- Client connects to `GET /ws?token=<jwt>`
- Backend validates JWT from query param (browsers cannot send custom headers on WS upgrades)
- Backend also validates the `Origin` header to block cross-site WebSocket hijacking
- On connect, a Tokio channel (`mpsc::UnboundedSender<String>`) is registered in `AppState.ws_senders`
- A background Tokio task subscribes to Redis. For each Redis pub/sub message on `channel:{id}`, it looks up all members of that channel's server and fans out to their registered senders
- On disconnect, the sender is removed from the map
- If Redis is unavailable, clients can replay via `GET /api/channels/{id}/messages?before=<last_id>` — the Redis layer is delivery only, not durability

**WebSocket events (MVP):** `message.created` — matching the payload published by Plan 5's send handler.

**Tech Stack:** Rust, Axum 0.7, Redis (pub/sub), `dashmap` v5, `futures-util` v0.3. Tokio async channels (`tokio::sync::mpsc`).

**Prerequisite:** Plans 3, 4, 5 must be executed first.

---

## File Map

**Create:**
- `backend/src/realtime/mod.rs`
- `backend/src/realtime/ws.rs`
- `backend/src/realtime/broker.rs`

**Modify:**
- `backend/Cargo.toml` — add `dashmap`, `futures-util`
- `backend/src/state.rs` — add `ws_senders` field
- `backend/src/main.rs` — start broker background task, add `mod realtime;`
- `backend/src/api/mod.rs` — add `/ws` route

---

## Task 0: Set Git Identity

- [ ] **Step 1: Configure git identity**

```bash
git config user.name "Maya Kade"
git config user.email "maya@moonrune.cc"
```

- [ ] **Step 2: Verify**

```bash
git config user.name && git config user.email
```

Expected: `Maya Kade` / `maya@moonrune.cc`

---

## Task 1: Add Real-time Dependencies

**Files:**
- Modify: `backend/Cargo.toml`

- [ ] **Step 1: Add dependencies**

Add to `[dependencies]` in `backend/Cargo.toml`:

```toml
dashmap = "5"
futures-util = "0.3"
```

- [ ] **Step 2: Verify build**

```bash
cd backend && cargo build 2>&1 | tail -3
```

Expected: `Finished`.

- [ ] **Step 3: Commit**

```bash
git add backend/Cargo.toml
git commit -m "feat(realtime): add dashmap and futures-util dependencies"
```

---

## Task 2: Update AppState

**Files:**
- Modify: `backend/src/state.rs`

- [ ] **Step 1: Replace state.rs**

```rust
use std::sync::Arc;
use dashmap::DashMap;
use sqlx::PgPool;
use redis::aio::ConnectionManager;
use tokio::sync::mpsc;
use uuid::Uuid;
use crate::config::Config;

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub redis: ConnectionManager,
    pub config: Config,
    pub ws_senders: Arc<DashMap<Uuid, mpsc::UnboundedSender<String>>>,
}
```

- [ ] **Step 2: Update main.rs to initialise ws_senders**

In `backend/src/main.rs`, update the `AppState` construction to:

```rust
let state = AppState {
    db,
    redis,
    config,
    ws_senders: Arc::new(DashMap::new()),
};
```

Add `use std::sync::Arc;` and `use dashmap::DashMap;` at the top of `main.rs`.

- [ ] **Step 3: Build check**

```bash
cd backend && cargo build 2>&1 | grep -E "^error"
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/src/state.rs backend/src/main.rs
git commit -m "feat(realtime): add ws_senders DashMap to AppState"
```

---

## Task 3: Redis Broker

**Files:**
- Create: `backend/src/realtime/mod.rs`
- Create: `backend/src/realtime/broker.rs`

- [ ] **Step 1: Write realtime/mod.rs**

```rust
pub mod broker;
pub mod ws;
```

- [ ] **Step 2: Write realtime/broker.rs**

The broker subscribes to all `channel:*` Redis pub/sub keys using a pattern subscription (`PSUBSCRIBE`). For each message, it looks up who is a member of the channel's server and fans out to connected users.

```rust
use futures_util::StreamExt;
use sqlx::PgPool;
use std::sync::Arc;
use dashmap::DashMap;
use uuid::Uuid;

pub async fn run(
    redis_url: String,
    db: PgPool,
    ws_senders: Arc<DashMap<Uuid, tokio::sync::mpsc::UnboundedSender<String>>>,
) {
    loop {
        match try_run(&redis_url, &db, &ws_senders).await {
            Ok(()) => {
                tracing::info!("broker loop exited cleanly");
                break;
            }
            Err(e) => {
                tracing::error!("broker error: {e} — reconnecting in 3s");
                tokio::time::sleep(tokio::time::Duration::from_secs(3)).await;
            }
        }
    }
}

async fn try_run(
    redis_url: &str,
    db: &PgPool,
    ws_senders: &Arc<DashMap<Uuid, tokio::sync::mpsc::UnboundedSender<String>>>,
) -> anyhow::Result<()> {
    let client = redis::Client::open(redis_url)?;
    let mut conn = client.get_async_connection().await?;

    let mut pubsub = conn.into_pubsub();
    pubsub.psubscribe("channel:*").await?;

    tracing::info!("broker subscribed to channel:* on Redis");

    let mut stream = pubsub.into_on_message();

    while let Some(msg) = stream.next().await {
        let payload: String = match msg.get_payload() {
            Ok(p) => p,
            Err(e) => {
                tracing::warn!("broker: failed to decode payload: {e}");
                continue;
            }
        };

        let value: serde_json::Value = match serde_json::from_str(&payload) {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!("broker: invalid JSON payload: {e}");
                continue;
            }
        };

        let channel_id_str = match value.get("channel_id").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => {
                tracing::warn!("broker: no channel_id in payload");
                continue;
            }
        };

        let channel_id = match Uuid::parse_str(&channel_id_str) {
            Ok(id) => id,
            Err(_) => continue,
        };

        // Look up which users are members of this channel's server
        let member_ids = match fetch_channel_members(db, channel_id).await {
            Ok(ids) => ids,
            Err(e) => {
                tracing::warn!("broker: DB error fetching members for channel {channel_id}: {e}");
                continue;
            }
        };

        // Fan out to connected users
        let mut dead_senders = Vec::new();
        for user_id in &member_ids {
            if let Some(sender) = ws_senders.get(user_id) {
                if sender.send(payload.clone()).is_err() {
                    dead_senders.push(*user_id);
                }
            }
        }

        // Clean up disconnected senders
        for user_id in dead_senders {
            ws_senders.remove(&user_id);
        }
    }

    Ok(())
}

async fn fetch_channel_members(
    db: &PgPool,
    channel_id: Uuid,
) -> Result<Vec<Uuid>, sqlx::Error> {
    sqlx::query_scalar::<_, Uuid>(
        r#"
        SELECT sm.user_id
        FROM server_members sm
        JOIN channels c ON c.server_id = sm.server_id
        WHERE c.id = $1
        "#,
    )
    .bind(channel_id)
    .fetch_all(db)
    .await
}
```

- [ ] **Step 3: Build check**

```bash
cd backend && cargo build 2>&1 | grep -E "^error"
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/src/realtime/mod.rs backend/src/realtime/broker.rs
git commit -m "feat(realtime): Redis pub/sub broker with fan-out to WebSocket senders"
```

---

## Task 4: WebSocket Handler

**Files:**
- Create: `backend/src/realtime/ws.rs`

- [ ] **Step 1: Write ws.rs**

```rust
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Query, State,
    },
    http::{header::ORIGIN, HeaderValue, StatusCode},
    response::IntoResponse,
};
use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use tokio::sync::mpsc;
use uuid::Uuid;
use crate::{auth::tokens, error::AppError, state::AppState};

#[derive(Deserialize)]
pub struct WsQuery {
    token: String,
}

pub async fn ws_handler(
    State(state): State<AppState>,
    Query(params): Query<WsQuery>,
    ws: WebSocketUpgrade,
    axum::extract::OriginalUri(uri): axum::extract::OriginalUri,
    headers: axum::http::HeaderMap,
) -> impl IntoResponse {
    // Validate Origin header to block cross-site WebSocket hijacking
    let allowed_origin = HeaderValue::from_str(&format!("https://{}", state.config.domain))
        .unwrap_or_else(|_| HeaderValue::from_static("https://chat.moonrune.cc"));

    // Also allow localhost for development
    let origin = headers.get(ORIGIN);
    let origin_ok = match origin {
        None => true, // No origin = non-browser client (CLI tools, tests) — allow
        Some(o) => {
            o == &allowed_origin
                || o == HeaderValue::from_static("http://localhost:5173")
                || o == HeaderValue::from_static("http://localhost:3000")
        }
    };

    if !origin_ok {
        return (StatusCode::FORBIDDEN, "forbidden origin").into_response();
    }

    // Validate JWT from query param
    let claims = match tokens::decode_jwt(&params.token, &state.config) {
        Ok(c) => c,
        Err(_) => return (StatusCode::UNAUTHORIZED, "invalid token").into_response(),
    };

    let user_id = match Uuid::parse_str(&claims.sub) {
        Ok(id) => id,
        Err(_) => return (StatusCode::UNAUTHORIZED, "invalid token").into_response(),
    };

    ws.on_upgrade(move |socket| handle_socket(socket, state, user_id))
}

async fn handle_socket(socket: WebSocket, state: AppState, user_id: Uuid) {
    let (mut sender, mut receiver) = socket.split();

    // Create an mpsc channel — broker writes to tx, we read from rx and forward to WS
    let (tx, mut rx) = mpsc::unbounded_channel::<String>();

    // Register this connection
    state.ws_senders.insert(user_id, tx);

    tracing::info!("ws: user {user_id} connected");

    // Task 1: forward broker messages → WebSocket
    let send_task = tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            if sender.send(Message::Text(msg)).await.is_err() {
                break;
            }
        }
    });

    // Task 2: read from WebSocket (heartbeat / client messages, discard for MVP)
    let recv_task = tokio::spawn(async move {
        while let Some(Ok(msg)) = receiver.next().await {
            match msg {
                Message::Close(_) => break,
                Message::Ping(_) => {} // axum handles pong automatically
                _ => {}               // No client→server messages in MVP
            }
        }
    });

    // Wait for either task to finish (disconnect from either side)
    tokio::select! {
        _ = send_task => {}
        _ = recv_task => {}
    }

    // Deregister
    state.ws_senders.remove(&user_id);
    tracing::info!("ws: user {user_id} disconnected");
}
```

- [ ] **Step 2: Build check**

```bash
cd backend && cargo build 2>&1 | grep -E "^error"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/src/realtime/ws.rs
git commit -m "feat(realtime): WebSocket upgrade handler with JWT auth and origin validation"
```

---

## Task 5: Wire into main.rs and API Router

**Files:**
- Modify: `backend/src/main.rs`
- Modify: `backend/src/api/mod.rs`

- [ ] **Step 1: Update main.rs to start broker and add realtime mod**

Add `mod realtime;` to `backend/src/main.rs` after the other `mod` declarations.

In `main()`, after the `let state = AppState { ... };` line, add:

```rust
// Start Redis broker as a background task
let broker_state = state.clone();
tokio::spawn(async move {
    crate::realtime::broker::run(
        broker_state.config.redis_url.clone(),
        broker_state.db.clone(),
        broker_state.ws_senders.clone(),
    )
    .await;
});
```

- [ ] **Step 2: Update api/mod.rs to add /ws route**

Replace the content of `backend/src/api/mod.rs`:

```rust
pub mod auth;
pub mod channels;
pub mod health;
pub mod invites;
pub mod messages;
pub mod servers;

use axum::Router;
use crate::state::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/health", axum::routing::get(health::health_check))
        .route("/ws", axum::routing::get(crate::realtime::ws::ws_handler))
        .nest("/api/auth", auth::router())
        .nest("/api/servers", servers::router())
        .nest("/api/servers/:server_id/channels", channels::router())
        .nest("/api/channels", channels::channel_router())
        .nest("/api/channels/:channel_id/messages", messages::router())
        .nest("/api/invite", invites::router())
}
```

- [ ] **Step 3: Build check**

```bash
cd backend && cargo build 2>&1 | grep -E "^error"
```

Expected: no errors.

- [ ] **Step 4: Run all tests**

```bash
cd backend && cargo test 2>&1 | tail -15
```

Expected: All tests pass.

- [ ] **Step 5: Smoke test with running stack**

Start the full stack:

```bash
docker compose up --build -d
sleep 5
```

Check backend is up:
```bash
curl -s http://localhost/health | grep ok
```

Expected: `{"status":"ok"}`

Verify WebSocket endpoint is reachable (should return 400 without valid token — that's correct):
```bash
curl -i http://localhost/ws
```

Expected: HTTP 400 or 426 (Upgrade Required) — not 404.

- [ ] **Step 6: Stop stack**

```bash
docker compose down
```

- [ ] **Step 7: Commit**

```bash
git add backend/src/main.rs backend/src/api/mod.rs
git commit -m "feat(realtime): wire broker and WebSocket handler into app startup and router"
```

---

## Self-Review

| Requirement | Status |
|---|---|
| WebSocket endpoint at `/ws` | ✅ Task 4, 5 |
| JWT validation from `?token=` query param | ✅ Task 4 |
| Origin validation (block CSWSH, allow localhost dev) | ✅ Task 4 |
| Per-user UnboundedSender registered in DashMap on connect | ✅ Task 4 |
| Sender removed from DashMap on disconnect | ✅ Task 4 |
| Redis PSUBSCRIBE to `channel:*` pattern | ✅ Task 3 |
| Fan-out to server members only (DB membership check per message) | ✅ Task 3 |
| Dead sender cleanup on send error | ✅ Task 3 |
| Broker reconnect loop on Redis failure | ✅ Task 3 |
| Broker started as background task in main | ✅ Task 5 |
| `message.created` event from Plan 5 publish reaches connected clients | ✅ Integrated design |
| Redis failure is non-fatal for message send (Plan 5) | ✅ Plan 5 Task 3 |

**Placeholder scan:** No TBDs. All code is complete.

---

*Next: Plan 7 — Frontend (React, Tailwind, routing, stores, WebSocket hook, all pages)*
