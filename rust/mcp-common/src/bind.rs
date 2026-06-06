//! Bind address resolution from environment.

use std::net::{IpAddr, SocketAddr};

const DEFAULT_BIND_HOST: &str = "127.0.0.1";

/// Resolve listen address from `ATLAS_BIND_HOST` (default `127.0.0.1`) and `port`.
pub fn bind_addr(port: u16) -> SocketAddr {
    let host = std::env::var("ATLAS_BIND_HOST").unwrap_or_else(|_| DEFAULT_BIND_HOST.to_string());
    let ip: IpAddr = host
        .parse()
        .unwrap_or_else(|_| panic!("invalid ATLAS_BIND_HOST: {host}"));
    SocketAddr::from((ip, port))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_bind_is_localhost() {
        std::env::remove_var("ATLAS_BIND_HOST");
        let addr = bind_addr(8001);
        assert_eq!(addr.ip().to_string(), "127.0.0.1");
        assert_eq!(addr.port(), 8001);
    }
}
