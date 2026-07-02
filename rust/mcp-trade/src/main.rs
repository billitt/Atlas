//! Atlas MCP UN Comtrade server — trade data over JSON-RPC 2.0.
//!
//! Python agents connect through `protocols.mcp.client.McpClient` on port 8003.

mod comtrade;
mod mcp;
mod seed;

use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use mcp::{handle_json_rpc, JsonRpcRequest};
use mcp_common::{apply_security_layers, bind_addr, listen_scheme, tls_config};
use serde_json::json;
use std::net::SocketAddr;

const DEFAULT_PORT: u16 = 8003;
pub const COMTRADE_USER_AGENT: &str = "Atlas-MCP/0.1";
pub const COMTRADE_DELAY_MS: u64 = 250;

#[derive(Clone)]
pub struct AppState {
    pub http: reqwest::Client,
    pub api_key: Option<String>,
    pub seed_enabled: bool,
}

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();

    let port = std::env::var("ATLAS_MCP_TRADE_PORT")
        .or_else(|_| std::env::var("MCP_TRADE_PORT"))
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(DEFAULT_PORT);

    let api_key = std::env::var("ATLAS_COMTRADE_API_KEY")
        .ok()
        .map(|k| k.trim().to_string())
        .filter(|k| !k.is_empty());

    if api_key.is_some() {
        println!("mcp-trade: keyed (100k cap)");
    } else {
        println!("mcp-trade: preview-only (500 cap)");
    }

    let seed_enabled = std::env::var("ATLAS_COMTRADE_SEED")
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false);
    if seed_enabled {
        println!("mcp-trade: seed mode ON (curated rows served as live data)");
    }

    let state = AppState {
        http: reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(60))
            .user_agent(COMTRADE_USER_AGENT)
            .build()
            .expect("failed to build Comtrade HTTP client"),
        api_key,
        seed_enabled,
    };

    let app = apply_security_layers(
        Router::new()
            .route("/health", get(health))
            .route("/mcp", post(mcp_endpoint))
            .with_state(state),
    );

    let addr = bind_addr(port);
    let scheme = listen_scheme();
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
