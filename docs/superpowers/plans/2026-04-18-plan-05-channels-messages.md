# Channels and Messages (REST) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement REST endpoints for channel management (with automatic slug generation) and message history/sending. Message sends also publish to Redis to trigger real-time delivery in Plan 6.

**Architecture:** Channel and message handlers live in `backend/src/api/channels.rs` and `backend/src/api/messages.rs`. Slug generation is a utility function using `unicode-normalization`. Slug uniqueness within a server is enforced at the DB layer (UNIQUE constraint) with application-level collision handling (append -2, -3). Message sends publish a JSON payload to Redis pub/sub on `channel:{channel_id}`.

**Tech Stack:** Rust, Axum 0.7, SQLx 0.7, PostgreSQL 16, Redis. New crate: `unicode-normalization = "0.1"`.

**Prerequisite:** Plans 3 and 4 must be executed first.

---

## File Map

**Create:**
- `backend/src/api/channels.rs`
- `backend/src/api/messages.rs`

**Modify:**
- `backend/Cargo.toml` — add `unicode-normalization`
- `backend/src/api/mod.rs` — add channel and message routes

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

## Task 1: Add unicode-normalization

**Files:**
- Modify: `backend/Cargo.toml`

- [ ] **Step 1: Add dependency**

Add to `[dependencies]` in `backend/Cargo.toml`:

```toml
unicode-normalization = "0.1"
```

- [ ] **Step 2: Verify build**

```bash
cd backend && cargo build 2>&1 | tail -3
```

Expected: `Finished`.

- [ ] **Step 3: Commit**

```bash
git add backend/Cargo.toml
git commit -m "feat(channels): add unicode-normalization for slug generation"
```

---

## Task 2: Channel Handlers

**Files:**
- Create: `backend/src/api/channels.rs`

- [ ] **Step 1: Write channels.rs**

```rust
use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{delete, get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;
use uuid::Uuid;
use crate::{auth::middleware::AuthUser, error::AppError, state::AppState};

pub fn router() -> Router<AppState> {
    Router::new()
        // Nested under /api/servers/:server_id/channels
        .route("/", post(create_channel).get(list_channels))
        .route("/:channel_id", get(get_channel).delete(delete_channel))
}

pub fn channel_router() -> Router<AppState> {
    // Mounted at /api/channels for direct channel access
    Router::new()
        .route("/:id", get(get_channel_by_id).delete(delete_channel_by_id))
}

// --- Slug generation ---

pub fn generate_slug(name: &str) -> String {
    use unicode_normalization::UnicodeNormalization;

    // NFKC normalize and lowercase
    let normalized: String = name
        .nfkc()
        .flat_map(|c| c.to_lowercase())
        .collect();

    // Replace spaces with hyphens, strip non-alphanumeric (except hyphen)
    let mut slug = String::with_capacity(normalized.len());
    let mut prev_hyphen = false;
    for c in normalized.chars() {
        if c.is_ascii_alphanumeric() {
            slug.push(c);
            prev_hyphen = false;
        } else if c == ' ' || c == '-' || c == '_' {
            if !prev_hyphen && !slug.is_empty() {
                slug.push('-');
                prev_hyphen = true;
            }
        }
        // All other characters (punctuation, emoji, etc.) are dropped
    }

    let slug = slug.trim_end_matches('-').to_string();

    if slug.is_empty() {
        format!("channel-{}", &Uuid::new_v4().to_string()[..8])
    } else {
        slug.chars().take(80).collect()
    }
}

// --- Types ---

#[derive(Serialize)]
struct ChannelResponse {
    id: Uuid,
    server_id: Uuid,
    display_name: String,
    slug: String,
    created_at: OffsetDateTime,
}

// --- Handlers ---

#[derive(Deserialize)]
struct CreateChannelBody {
    display_name: String,
}

pub async fn create_channel(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(server_id): Path<Uuid>,
    Json(body): Json<CreateChannelBody>,
) -> crate::error::Result<(StatusCode, Json<ChannelResponse>)> {
    let display_name = body.display_name.trim().to_string();
    if display_name.is_empty() || display_name.len() > 80 {
        return Err(AppError::BadRequest(
            "channel name must be 1-80 characters".to_string(),
        ));
    }

    // Validate requester is a member
    let is_member = sqlx::query_scalar::<_, i64>(
        "SELECT COUNT(*) FROM server_members WHERE server_id = $1 AND user_id = $2",
    )
    .bind(server_id)
    .bind(auth.user_id)
    .fetch_one(&state.db)
    .await?;

    if is_member == 0 {
        return Err(AppError::Forbidden);
    }

    // Generate slug and handle collisions
    let base_slug = generate_slug(&display_name);
    let slug = resolve_slug_collision(&state, server_id, &base_slug).await?;

    #[derive(sqlx::FromRow)]
    struct Row {
        id: Uuid,
        created_at: OffsetDateTime,
    }

    let row = sqlx::query_as::<_, Row>(
        "INSERT INTO channels (server_id, display_name, slug)
         VALUES ($1, $2, $3)
         RETURNING id, created_at",
    )
    .bind(server_id)
    .bind(&display_name)
    .bind(&slug)
    .fetch_one(&state.db)
    .await?;

    Ok((
        StatusCode::CREATED,
        Json(ChannelResponse {
            id: row.id,
            server_id,
            display_name,
            slug,
            created_at: row.created_at,
        }),
    ))
}

async fn resolve_slug_collision(
    state: &AppState,
    server_id: Uuid,
    base_slug: &str,
) -> crate::error::Result<String> {
    let existing: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM channels WHERE server_id = $1 AND slug = $2",
    )
    .bind(server_id)
    .bind(base_slug)
    .fetch_one(&state.db)
    .await?;

    if existing == 0 {
        return Ok(base_slug.to_string());
    }

    for suffix in 2..=99u32 {
        let candidate = format!("{base_slug}-{suffix}");
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM channels WHERE server_id = $1 AND slug = $2",
        )
        .bind(server_id)
        .bind(&candidate)
        .fetch_one(&state.db)
        .await?;

        if count == 0 {
            return Ok(candidate);
        }
    }

    // Extremely unlikely — fall back to UUID suffix
    Ok(format!("{base_slug}-{}", &Uuid::new_v4().to_string()[..8]))
}

async fn list_channels(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(server_id): Path<Uuid>,
) -> crate::error::Result<Json<Vec<ChannelResponse>>> {
    let is_member = sqlx::query_scalar::<_, i64>(
        "SELECT COUNT(*) FROM server_members WHERE server_id = $1 AND user_id = $2",
    )
    .bind(server_id)
    .bind(auth.user_id)
    .fetch_one(&state.db)
    .await?;

    if is_member == 0 {
        return Err(AppError::Forbidden);
    }

    #[derive(sqlx::FromRow)]
    struct Row {
        id: Uuid,
        display_name: String,
        slug: String,
        created_at: OffsetDateTime,
    }

    let rows = sqlx::query_as::<_, Row>(
        "SELECT id, display_name, slug, created_at
         FROM channels
         WHERE server_id = $1
         ORDER BY created_at ASC",
    )
    .bind(server_id)
    .fetch_all(&state.db)
    .await?;

    Ok(Json(
        rows.into_iter()
            .map(|r| ChannelResponse {
                id: r.id,
                server_id,
                display_name: r.display_name,
                slug: r.slug,
                created_at: r.created_at,
            })
            .collect(),
    ))
}

async fn get_channel(
    State(state): State<AppState>,
    auth: AuthUser,
    Path((server_id, channel_id)): Path<(Uuid, Uuid)>,
) -> crate::error::Result<Json<ChannelResponse>> {
    get_channel_internal(&state, auth.user_id, server_id, channel_id).await
}

async fn get_channel_by_id(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(channel_id): Path<Uuid>,
) -> crate::error::Result<Json<ChannelResponse>> {
    #[derive(sqlx::FromRow)]
    struct Row {
        server_id: Uuid,
    }
    let row = sqlx::query_as::<_, Row>("SELECT server_id FROM channels WHERE id = $1")
        .bind(channel_id)
        .fetch_optional(&state.db)
        .await?
        .ok_or(AppError::NotFound)?;

    get_channel_internal(&state, auth.user_id, row.server_id, channel_id).await
}

async fn get_channel_internal(
    state: &AppState,
    user_id: Uuid,
    server_id: Uuid,
    channel_id: Uuid,
) -> crate::error::Result<Json<ChannelResponse>> {
    let is_member = sqlx::query_scalar::<_, i64>(
        "SELECT COUNT(*) FROM server_members WHERE server_id = $1 AND user_id = $2",
    )
    .bind(server_id)
    .bind(user_id)
    .fetch_one(&state.db)
    .await?;

    if is_member == 0 {
        return Err(AppError::Forbidden);
    }

    #[derive(sqlx::FromRow)]
    struct Row {
        display_name: String,
        slug: String,
        created_at: OffsetDateTime,
    }

    let row = sqlx::query_as::<_, Row>(
        "SELECT display_name, slug, created_at FROM channels WHERE id = $1 AND server_id = $2",
    )
    .bind(channel_id)
    .bind(server_id)
    .fetch_optional(&state.db)
    .await?
    .ok_or(AppError::NotFound)?;

    Ok(Json(ChannelResponse {
        id: channel_id,
        server_id,
        display_name: row.display_name,
        slug: row.slug,
        created_at: row.created_at,
    }))
}

async fn delete_channel(
    State(state): State<AppState>,
    auth: AuthUser,
    Path((server_id, channel_id)): Path<(Uuid, Uuid)>,
) -> crate::error::Result<StatusCode> {
    delete_channel_internal(&state, auth.user_id, server_id, channel_id).await
}

async fn delete_channel_by_id(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(channel_id): Path<Uuid>,
) -> crate::error::Result<StatusCode> {
    #[derive(sqlx::FromRow)]
    struct Row {
        server_id: Uuid,
    }
    let row = sqlx::query_as::<_, Row>("SELECT server_id FROM channels WHERE id = $1")
        .bind(channel_id)
        .fetch_optional(&state.db)
        .await?
        .ok_or(AppError::NotFound)?;

    delete_channel_internal(&state, auth.user_id, row.server_id, channel_id).await
}

async fn delete_channel_internal(
    state: &AppState,
    user_id: Uuid,
    server_id: Uuid,
    channel_id: Uuid,
) -> crate::error::Result<StatusCode> {
    let role: Option<String> = sqlx::query_scalar(
        "SELECT role FROM server_members WHERE server_id = $1 AND user_id = $2",
    )
    .bind(server_id)
    .bind(user_id)
    .fetch_optional(&state.db)
    .await?;

    match role.as_deref() {
        Some("owner") | Some("admin") => {}
        Some(_) => return Err(AppError::Forbidden),
        None => return Err(AppError::Forbidden),
    }

    let deleted = sqlx::query(
        "DELETE FROM channels WHERE id = $1 AND server_id = $2",
    )
    .bind(channel_id)
    .bind(server_id)
    .execute(&state.db)
    .await?;

    if deleted.rows_affected() == 0 {
        return Err(AppError::NotFound);
    }

    Ok(StatusCode::NO_CONTENT)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slug_basic_cases() {
        assert_eq!(generate_slug("General Discussion"), "general-discussion");
        assert_eq!(generate_slug("Dev — Backend"), "dev-backend");
        assert_eq!(generate_slug("Off Topic"), "off-topic");
        assert_eq!(generate_slug("  leading spaces  "), "leading-spaces");
    }

    #[test]
    fn slug_collapses_consecutive_separators() {
        assert_eq!(generate_slug("hello   world"), "hello-world");
        assert_eq!(generate_slug("a---b"), "a-b");
    }

    #[test]
    fn slug_truncates_to_80() {
        let long = "a".repeat(100);
        assert_eq!(generate_slug(&long).len(), 80);
    }

    #[test]
    fn slug_empty_fallback_starts_with_channel() {
        let slug = generate_slug("---");
        assert!(slug.starts_with("channel-"), "got: {slug}");
    }

    #[test]
    fn slug_unicode_normalization() {
        // NFKC: ﬁ (fi ligature) → fi
        assert_eq!(generate_slug("ﬁnance"), "finance");
    }
}
```

- [ ] **Step 2: Build and run slug tests**

```bash
cd backend && cargo test channels 2>&1 | tail -15
```

Expected: All 5 slug tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/channels.rs
git commit -m "feat(channels): channel CRUD with automatic slug generation and collision handling"
```

---

## Task 3: Message Handlers

**Files:**
- Create: `backend/src/api/messages.rs`

- [ ] **Step 1: Write messages.rs**

```rust
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;
use uuid::Uuid;
use crate::{auth::middleware::AuthUser, error::AppError, state::AppState};

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(send_message).get(get_messages))
}

// --- Types ---

#[derive(Serialize)]
struct MessageResponse {
    id: Uuid,
    channel_id: Uuid,
    author_id: Uuid,
    author_username: String,
    author_status: String,
    content: String,
    compromised_at_send: bool,
    created_at: OffsetDateTime,
    edited_at: Option<OffsetDateTime>,
}

// --- Handlers ---

#[derive(Deserialize)]
struct SendMessageBody {
    content: String,
}

async fn send_message(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(channel_id): Path<Uuid>,
    Json(body): Json<SendMessageBody>,
) -> crate::error::Result<(StatusCode, Json<MessageResponse>)> {
    // Compromised accounts cannot send messages
    if auth.account_status == "compromised" {
        return Err(AppError::Forbidden);
    }

    let content = body.content.trim().to_string();
    if content.is_empty() {
        return Err(AppError::BadRequest("message content cannot be empty".to_string()));
    }
    if content.len() > 4000 {
        return Err(AppError::BadRequest(
            "message content must be 4000 characters or fewer".to_string(),
        ));
    }

    // Verify channel exists and user is a member of its server
    let server_id: Option<Uuid> = sqlx::query_scalar(
        "SELECT server_id FROM channels WHERE id = $1",
    )
    .bind(channel_id)
    .fetch_optional(&state.db)
    .await?;

    let server_id = server_id.ok_or(AppError::NotFound)?;

    let is_member = sqlx::query_scalar::<_, i64>(
        "SELECT COUNT(*) FROM server_members WHERE server_id = $1 AND user_id = $2",
    )
    .bind(server_id)
    .bind(auth.user_id)
    .fetch_one(&state.db)
    .await?;

    if is_member == 0 {
        return Err(AppError::Forbidden);
    }

    #[derive(sqlx::FromRow)]
    struct Row {
        id: Uuid,
        created_at: OffsetDateTime,
    }

    let row = sqlx::query_as::<_, Row>(
        "INSERT INTO messages (channel_id, author_id, content, compromised_at_send)
         VALUES ($1, $2, $3, false)
         RETURNING id, created_at",
    )
    .bind(channel_id)
    .bind(auth.user_id)
    .bind(&content)
    .fetch_one(&state.db)
    .await?;

    let msg = MessageResponse {
        id: row.id,
        channel_id,
        author_id: auth.user_id,
        author_username: auth.username.clone(),
        author_status: auth.account_status.clone(),
        content: content.clone(),
        compromised_at_send: false,
        created_at: row.created_at,
        edited_at: None,
    };

    // Publish to Redis for real-time delivery (Plan 6 consumes this)
    let payload = serde_json::json!({
        "type": "message.created",
        "channel_id": channel_id,
        "server_id": server_id,
        "message": {
            "id": msg.id,
            "author_id": msg.author_id,
            "author_username": msg.author_username,
            "author_status": msg.author_status,
            "content": msg.content,
            "compromised_at_send": msg.compromised_at_send,
            "created_at": msg.created_at,
        }
    });

    let redis_channel = format!("channel:{channel_id}");
    let mut redis = state.redis.clone();
    if let Err(e) = redis::cmd("PUBLISH")
        .arg(&redis_channel)
        .arg(payload.to_string())
        .query_async::<_, i64>(&mut redis)
        .await
    {
        // Log but don't fail the request — message is durably stored in DB
        tracing::warn!("redis publish failed for channel {channel_id}: {e}");
    }

    Ok((StatusCode::CREATED, Json(msg)))
}

#[derive(Deserialize)]
struct GetMessagesQuery {
    before: Option<Uuid>,
    limit: Option<i64>,
}

async fn get_messages(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(channel_id): Path<Uuid>,
    Query(params): Query<GetMessagesQuery>,
) -> crate::error::Result<Json<Vec<MessageResponse>>> {
    // Verify channel exists and user is a member
    let server_id: Option<Uuid> = sqlx::query_scalar(
        "SELECT server_id FROM channels WHERE id = $1",
    )
    .bind(channel_id)
    .fetch_optional(&state.db)
    .await?;

    let server_id = server_id.ok_or(AppError::NotFound)?;

    let is_member = sqlx::query_scalar::<_, i64>(
        "SELECT COUNT(*) FROM server_members WHERE server_id = $1 AND user_id = $2",
    )
    .bind(server_id)
    .bind(auth.user_id)
    .fetch_one(&state.db)
    .await?;

    if is_member == 0 {
        return Err(AppError::Forbidden);
    }

    let limit = params.limit.unwrap_or(50).clamp(1, 100);

    #[derive(sqlx::FromRow)]
    struct Row {
        id: Uuid,
        author_id: Uuid,
        author_username: String,
        author_status: String,
        content: String,
        compromised_at_send: bool,
        created_at: OffsetDateTime,
        edited_at: Option<OffsetDateTime>,
    }

    let rows = if let Some(before_id) = params.before {
        // Cursor-based pagination: messages before a given message ID
        let before_ts: Option<OffsetDateTime> = sqlx::query_scalar(
            "SELECT created_at FROM messages WHERE id = $1",
        )
        .bind(before_id)
        .fetch_optional(&state.db)
        .await?;

        let before_ts = before_ts.ok_or(AppError::NotFound)?;

        sqlx::query_as::<_, Row>(
            r#"
            SELECT
                m.id,
                m.author_id,
                u.username::TEXT AS author_username,
                u.account_status AS author_status,
                m.content,
                m.compromised_at_send,
                m.created_at,
                m.edited_at
            FROM messages m
            JOIN users u ON u.id = m.author_id
            WHERE m.channel_id = $1 AND m.created_at < $2
            ORDER BY m.created_at DESC
            LIMIT $3
            "#,
        )
        .bind(channel_id)
        .bind(before_ts)
        .bind(limit)
        .fetch_all(&state.db)
        .await?
    } else {
        sqlx::query_as::<_, Row>(
            r#"
            SELECT
                m.id,
                m.author_id,
                u.username::TEXT AS author_username,
                u.account_status AS author_status,
                m.content,
                m.compromised_at_send,
                m.created_at,
                m.edited_at
            FROM messages m
            JOIN users u ON u.id = m.author_id
            WHERE m.channel_id = $1
            ORDER BY m.created_at DESC
            LIMIT $2
            "#,
        )
        .bind(channel_id)
        .bind(limit)
        .fetch_all(&state.db)
        .await?
    };

    // Return in chronological order (oldest first)
    let mut messages: Vec<MessageResponse> = rows
        .into_iter()
        .map(|r| MessageResponse {
            id: r.id,
            channel_id,
            author_id: r.author_id,
            author_username: r.author_username,
            author_status: r.author_status,
            content: r.content,
            compromised_at_send: r.compromised_at_send,
            created_at: r.created_at,
            edited_at: r.edited_at,
        })
        .collect();
    messages.sort_by_key(|m| m.created_at);
    Ok(Json(messages))
}
```

- [ ] **Step 2: Build check**

```bash
cd backend && cargo build 2>&1 | grep -E "^error"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/messages.rs
git commit -m "feat(messages): message history and send endpoints with Redis publish"
```

---

## Task 4: Wire Routes into API

**Files:**
- Modify: `backend/src/api/mod.rs`

- [ ] **Step 1: Update api/mod.rs**

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
        .nest("/api/auth", auth::router())
        .nest("/api/servers", servers::router())
        .nest("/api/servers/:server_id/channels", channels::router())
        .nest("/api/channels", channels::channel_router())
        .nest("/api/channels/:channel_id/messages", messages::router())
        .nest("/api/invite", invites::router())
}
```

- [ ] **Step 2: Build check**

```bash
cd backend && cargo build 2>&1 | grep -E "^error"
```

Expected: no errors.

- [ ] **Step 3: Run all tests**

```bash
cd backend && cargo test 2>&1 | tail -15
```

Expected: All existing tests pass including new slug tests.

- [ ] **Step 4: Commit**

```bash
git add backend/src/api/mod.rs
git commit -m "feat(api): wire channel and message routes into API router"
```

---

## Self-Review

| Requirement | Status |
|---|---|
| Create channel with display_name (user-friendly) | ✅ Task 2 |
| Automatic slug generation (lowercase, hyphens, unicode-safe) | ✅ Task 2 |
| Slug collision handling (append -2, -3 etc.) | ✅ Task 2 |
| Slug unit tests (basic cases, collapsing, truncation, empty fallback, unicode) | ✅ Task 2 |
| List channels (members only) | ✅ Task 2 |
| Get channel by server+id and by id alone | ✅ Task 2 |
| Delete channel (admin/owner only) | ✅ Task 2 |
| Send message (not compromised, member only) | ✅ Task 3 |
| Message length validation (max 4000 chars) | ✅ Task 3 |
| Compromised user blocked from sending | ✅ Task 3 |
| Redis publish on send (non-fatal on failure) | ✅ Task 3 |
| Get message history with cursor pagination (?before=<uuid>&limit=N) | ✅ Task 3 |
| Messages returned in chronological order | ✅ Task 3 |
| Author username + status included in message responses | ✅ Task 3 |

**Placeholder scan:** No TBDs. All handlers are complete.

---

*Next: Plan 6 — Real-time (WebSocket + Redis pub/sub)*
