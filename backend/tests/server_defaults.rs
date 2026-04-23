use axum::body::Body;
use axum::http::{Request, StatusCode};
use base64::Engine;
use sqlx::PgPool;
use tower::ServiceExt;

#[sqlx::test(migrations = "./migrations")]
async fn create_server_seeds_general_and_announcements(pool: PgPool) {
    // 1. Insert a user to act as the server owner
    let user_id: (uuid::Uuid,) = sqlx::query_as(
        "INSERT INTO users (username, email, password_hash)
         VALUES ('dani', 'dani@example.com', 'hash') RETURNING id",
    )
    .fetch_one(&pool)
    .await
    .unwrap();

    // 2. Build config and issue a JWT for the user
    let config = cauldron_backend::Config {
        database_url: String::new(),
        redis_url: String::new(),
        jwt_secret: "test-secret-32-bytes-min-length!!".to_string(),
        jwt_expiry_seconds: 900,
        refresh_token_expiry_days: 7,
        totp_issuer: "Cauldron".to_string(),
        totp_encryption_key: base64::engine::general_purpose::STANDARD.encode([0u8; 32]),
        domain: "localhost".to_string(),
        smtp: None,
    };
    let access_token =
        cauldron_backend::auth::tokens::encode_jwt(user_id.0, "dani", "active", &config).unwrap();

    // 3. Build app state with real DB and a local Redis connection
    let redis_client = redis::Client::open("redis://127.0.0.1:6379").unwrap();
    let redis = redis::aio::ConnectionManager::new(redis_client)
        .await
        .unwrap();
    let state = cauldron_backend::AppState {
        db: pool.clone(),
        redis,
        config: config.clone(),
        ws_senders: std::sync::Arc::new(dashmap::DashMap::new()),
        rate_limiters: cauldron_backend::rate_limit::RateLimiters::new(),
        http_client: reqwest::Client::new(),
    };

    // 4. Build router and send POST /api/servers
    let app = cauldron_backend::api::router().with_state(state);
    let req = Request::builder()
        .method("POST")
        .uri("/api/servers")
        .header("content-type", "application/json")
        .header("authorization", format!("Bearer {access_token}"))
        .body(Body::from(r#"{"name":"Test Server"}"#))
        .unwrap();

    let res = app.oneshot(req).await.unwrap();
    assert_eq!(res.status(), StatusCode::CREATED);

    // 5. Verify default channels were created
    let channels: Vec<(String, String)> = sqlx::query_as(
        "SELECT display_name, slug FROM channels WHERE server_id = (SELECT id FROM servers WHERE name = 'Test Server') ORDER BY created_at ASC"
    )
    .fetch_all(&pool)
    .await
    .expect("list channels");

    assert_eq!(channels.len(), 2, "new server must have exactly 2 default channels");
    assert_eq!(channels[0], ("General".to_string(), "general".to_string()));
    assert_eq!(channels[1], ("Announcements".to_string(), "announcements".to_string()));
}
