//! Optional per-IP rate limiting for MCP endpoints.

use axum::{
    body::Body,
    extract::ConnectInfo,
    http::{Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use dashmap::DashMap;
use governor::{
    clock::DefaultClock,
    state::{InMemoryState, NotKeyed},
    Quota, RateLimiter,
};
use serde_json::json;
use std::net::{IpAddr, SocketAddr};
use std::num::NonZeroU32;
use std::sync::{Arc, LazyLock};

type DirectLimiter = RateLimiter<NotKeyed, InMemoryState, DefaultClock>;

static RATE_LIMIT_RPS: LazyLock<Option<u32>> = LazyLock::new(|| {
    std::env::var("ATLAS_RATE_LIMIT_RPS")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .filter(|value| *value > 0)
});

static IP_LIMITERS: LazyLock<Option<Arc<DashMap<IpAddr, DirectLimiter>>>> =
    LazyLock::new(|| RATE_LIMIT_RPS.is_some().then(|| Arc::new(DashMap::new())));

fn peer_ip(request: &Request<Body>) -> Option<IpAddr> {
    request
        .extensions()
        .get::<ConnectInfo<SocketAddr>>()
        .map(|info| info.0.ip())
}

fn check_rate(ip: Option<IpAddr>) -> bool {
    let Some(rps) = *RATE_LIMIT_RPS else {
        return true;
    };
    let Some(limiters) = IP_LIMITERS.as_ref() else {
        return true;
    };
    let Some(ip) = ip else {
        return true;
    };

    let quota = Quota::per_second(NonZeroU32::new(rps).expect("positive rps"));
    let entry = limiters
        .entry(ip)
        .or_insert_with(|| RateLimiter::direct(quota));
    entry.check().is_ok()
}

pub async fn require_rate_limit(request: Request<Body>, next: Next) -> Response {
    if !check_rate(peer_ip(&request)) {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(json!({ "error": "rate limit exceeded" })),
        )
            .into_response();
    }
    next.run(request).await
}

/// True when `ATLAS_RATE_LIMIT_RPS` is configured.
pub fn rate_limit_enabled() -> bool {
    RATE_LIMIT_RPS.is_some()
}
