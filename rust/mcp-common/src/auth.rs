//! Optional bearer-token authentication for MCP endpoints.

use axum::{
    body::Body,
    http::{header::AUTHORIZATION, Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use std::sync::{Arc, LazyLock};
use subtle::ConstantTimeEq;

static AUTH_TOKEN: LazyLock<Option<Arc<str>>> = LazyLock::new(|| {
    std::env::var("ATLAS_MCP_AUTH_TOKEN")
        .ok()
        .filter(|value| !value.is_empty())
        .map(|value| Arc::from(value.as_str()))
});

/// Return the configured bearer token, if any.
pub fn configured_auth_token() -> Option<Arc<str>> {
    AUTH_TOKEN.clone()
}

fn bearer_matches(header_value: &str, expected: &str) -> bool {
    let prefix = "Bearer ";
    if !header_value.starts_with(prefix) {
        return false;
    }
    let provided = header_value[prefix.len()..].trim();
    if provided.len() != expected.len() {
        return false;
    }
    provided.as_bytes().ct_eq(expected.as_bytes()).into()
}

pub async fn require_bearer_auth(request: Request<Body>, next: Next) -> Response {
    let Some(expected) = AUTH_TOKEN.clone() else {
        return next.run(request).await;
    };

    let authorized = request
        .headers()
        .get(AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| bearer_matches(value, expected.as_ref()));

    if authorized {
        return next.run(request).await;
    }

    (
        StatusCode::UNAUTHORIZED,
        Json(json!({ "error": "missing or invalid Authorization bearer token" })),
    )
        .into_response()
}

/// True when `ATLAS_MCP_AUTH_TOKEN` is configured.
pub fn auth_enabled() -> bool {
    AUTH_TOKEN.is_some()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bearer_match_checks_prefix_and_value() {
        assert!(bearer_matches("Bearer secret-token", "secret-token"));
        assert!(!bearer_matches("Bearer wrong", "secret-token"));
        assert!(!bearer_matches("Basic secret-token", "secret-token"));
    }
}
