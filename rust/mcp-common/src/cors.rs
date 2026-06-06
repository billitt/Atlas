//! CORS configuration for MCP servers.

use axum::http::{HeaderValue, Method};
use tower_http::cors::{AllowOrigin, CorsLayer};

const DEFAULT_LOCAL_ORIGINS: &[&str] = &[
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
];

/// Build a CORS layer with localhost defaults or `ATLAS_CORS_ORIGINS` allowlist.
pub fn cors_layer() -> CorsLayer {
    let origins = std::env::var("ATLAS_CORS_ORIGINS")
        .ok()
        .map(|value| {
            value
                .split(',')
                .map(str::trim)
                .filter(|origin| !origin.is_empty())
                .map(|origin| {
                    HeaderValue::from_str(origin)
                        .unwrap_or_else(|_| panic!("invalid ATLAS_CORS_ORIGINS entry: {origin}"))
                })
                .collect::<Vec<_>>()
        })
        .filter(|values| !values.is_empty())
        .unwrap_or_else(|| {
            DEFAULT_LOCAL_ORIGINS
                .iter()
                .map(|origin| HeaderValue::from_static(origin))
                .collect()
        });

    CorsLayer::new()
        .allow_origin(AllowOrigin::list(origins))
        .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
        .allow_headers([
            axum::http::header::CONTENT_TYPE,
            axum::http::header::AUTHORIZATION,
        ])
}
