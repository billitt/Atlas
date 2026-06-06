//! Shared security helpers for Atlas Rust MCP servers.

pub mod auth;
pub mod bind;
pub mod cors;
pub mod rate_limit;
pub mod serve;
pub mod validation;

pub use auth::{auth_enabled, configured_auth_token, require_bearer_auth};
pub use bind::bind_addr;
pub use cors::cors_layer;
pub use rate_limit::{rate_limit_enabled, require_rate_limit};
pub use serve::{listen_scheme, tls_config};

use axum::{middleware, Router};

/// Apply CORS, optional rate limiting, and optional bearer auth to a router.
pub fn apply_security_layers<S>(router: Router<S>) -> Router<S>
where
    S: Clone + Send + Sync + 'static,
{
    let mut router = router.layer(cors_layer());
    if rate_limit_enabled() {
        router = router.layer(middleware::from_fn(require_rate_limit));
    }
    if auth_enabled() {
        router = router.layer(middleware::from_fn(require_bearer_auth));
    }
    router
}
