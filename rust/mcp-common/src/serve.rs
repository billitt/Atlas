//! HTTP/HTTPS server startup helpers.

use axum_server::tls_rustls::RustlsConfig;

/// Load TLS config when `ATLAS_TLS_CERT` and `ATLAS_TLS_KEY` are set.
pub async fn tls_config() -> Option<RustlsConfig> {
    let cert = std::env::var("ATLAS_TLS_CERT")
        .ok()
        .filter(|value| !value.is_empty())?;
    let key = std::env::var("ATLAS_TLS_KEY")
        .ok()
        .filter(|value| !value.is_empty())?;
    Some(
        RustlsConfig::from_pem_file(cert, key)
            .await
            .expect("invalid TLS certificate or key"),
    )
}

/// Return `https` when TLS env vars are configured, otherwise `http`.
pub fn listen_scheme() -> &'static str {
    if std::env::var("ATLAS_TLS_CERT")
        .ok()
        .filter(|value| !value.is_empty())
        .is_some()
        && std::env::var("ATLAS_TLS_KEY")
            .ok()
            .filter(|value| !value.is_empty())
            .is_some()
    {
        "https"
    } else {
        "http"
    }
}
