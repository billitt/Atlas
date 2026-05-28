//! Atlas MCP market-data server — Yahoo Finance quotes over JSON-RPC 2.0.
//!
//! Python agents connect via `protocols.mcp.client.McpClient` on port 8001.

mod mcp;
mod yahoo;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use mcp::{handle_json_rpc, JsonRpcRequest};
use serde_json::json;
use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};

const DEFAULT_PORT: u16 = 8001;

/// Shared state cloned into each axum handler (cheap: inner data is behind `Arc`).
#[derive(Clone)]
pub struct AppState {
    pub http: reqwest::Client,
}

#[tokio::main]
async fn main() {
    let port = std::env::var("MCP_MARKET_DATA_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(DEFAULT_PORT);

    let state = AppState {
        http: reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("failed to build HTTP client"),
    };

    // CorsLayer is tower middleware: runs before/after our handlers.
    // `Any` allows all origins — fine for local dev; tighten in production.
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health))
        .route("/mcp", post(mcp_endpoint))
        .layer(cors)
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .unwrap_or_else(|e| panic!("cannot bind to {addr}: {e}"));

    println!("mcp-market-data listening on http://{addr}");
    println!("  GET  /health — liveness");
    println!("  POST /mcp    — JSON-RPC 2.0 (initialize, tools/list, tools/call)");

    axum::serve(listener, app).await.expect("server error");
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok" }))
}

/// `State<AppState>` is axum's extractor: it pulls the shared state from the router.
/// `Json<T>` deserializes the request body; the handler returns `Json<Value>` as the response.
async fn mcp_endpoint(
    State(state): State<AppState>,
    Json(request): Json<JsonRpcRequest>,
) -> Json<serde_json::Value> {
    handle_json_rpc(state, request).await
}
