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
use mcp_common::{apply_security_layers, bind_addr, listen_scheme, tls_config};
use serde_json::json;
use std::net::SocketAddr;

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

    let app = apply_security_layers(
        Router::new()
            .route("/health", get(health))
            .route("/mcp", post(mcp_endpoint))
            .with_state(state),
    );

    let addr = bind_addr(port);
    let scheme = listen_scheme();
    println!("mcp-market-data");
    println!("  {scheme}://{addr}");
    println!("  GET  /health — liveness");
    println!("  POST /mcp    — JSON-RPC 2.0 (initialize, tools/list, tools/call)");

    if let Some(tls) = tls_config().await {
        axum_server::bind_rustls(addr, tls)
            .serve(app.into_make_service_with_connect_info::<SocketAddr>())
            .await
            .expect("server error");
        return;
    }

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .unwrap_or_else(|e| panic!("cannot bind to {addr}: {e}"));
    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .await
    .expect("server error");
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
