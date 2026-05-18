//! Atlas MCP EDGAR server — SEC filings over JSON-RPC 2.0.
//!
//! Python agents connect through `protocols.mcp.client.McpClient` on port 8002.

mod edgar;
mod mcp;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use mcp::{handle_json_rpc, JsonRpcRequest};
use serde_json::json;
use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};

const DEFAULT_PORT: u16 = 8002;
pub const SEC_USER_AGENT: &str = "Atlas-MCP/0.1 (atlas-project@example.com)";

#[derive(Clone)]
pub struct AppState {
    pub http: reqwest::Client,
}

#[tokio::main]
async fn main() {
    let port = std::env::var("MCP_EDGAR_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(DEFAULT_PORT);

    let state = AppState {
        http: reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(60))
            .user_agent(SEC_USER_AGENT)
            .build()
            .expect("failed to build SEC HTTP client"),
    };

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

    println!("mcp-edgar listening on http://{addr}");
    println!("  GET  /health — liveness");
    println!("  POST /mcp    — JSON-RPC 2.0 (initialize, tools/list, tools/call)");

    axum::serve(listener, app).await.expect("server error");
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok" }))
}

async fn mcp_endpoint(
    State(state): State<AppState>,
    Json(request): Json<JsonRpcRequest>,
) -> Json<serde_json::Value> {
    handle_json_rpc(state, request).await
}
