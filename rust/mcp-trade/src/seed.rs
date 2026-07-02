//! Curated UN Comtrade rows for reproducible demos.
//!
//! When seed mode is enabled (`ATLAS_COMTRADE_SEED`), matching queries return
//! curated rows through the normal MCP path (`used_preview: false`) so the
//! full pipeline — validation, caching, agent reflection — is exercised
//! identically to a live keyed Comtrade response. This keeps demos
//! deterministic on the rate-limited free tier without special-casing any
//! downstream code.

use serde_json::{json, Value};
use std::sync::OnceLock;

use crate::comtrade::{TradeQuery, TradeResult};

const SEED_JSON: &str = include_str!("../seed/trade_seed.json");
const SEED_ENDPOINT: &str = "/data/v1/get/C/A/HS";

fn seed_entries() -> &'static Vec<Value> {
    static ENTRIES: OnceLock<Vec<Value>> = OnceLock::new();
    ENTRIES.get_or_init(|| {
        let parsed: Value =
            serde_json::from_str(SEED_JSON).expect("trade_seed.json must be valid JSON");
        parsed
            .get("entries")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default()
    })
}

fn entry_matches(criteria: &Value, query: &TradeQuery) -> bool {
    if let Some(reporter) = criteria.get("reporterCode").and_then(Value::as_str) {
        if reporter != query.reporter_code {
            return false;
        }
    }
    if let Some(partner) = criteria.get("partnerCode").and_then(Value::as_str) {
        if query.partner_code.as_deref() != Some(partner) {
            return false;
        }
    }
    if let Some(cmd) = criteria.get("cmdCode").and_then(Value::as_str) {
        match query.cmd_code.as_deref() {
            Some(value) if value.starts_with(cmd) => {}
            _ => return false,
        }
    }
    if let Some(flow) = criteria.get("flowCode").and_then(Value::as_str) {
        if query.flow_code.as_deref() != Some(flow) {
            return false;
        }
    }
    true
}

/// Return curated rows for a matching query, or None to fall through to the
/// real Comtrade API. Never seeds the explicit keyless `preview_trade` tool.
pub fn seed_result(tool: &str, query: &TradeQuery) -> Option<TradeResult> {
    if tool == "preview_trade" {
        return None;
    }

    for entry in seed_entries() {
        let criteria = match entry.get("match") {
            Some(value) => value,
            None => continue,
        };
        if !entry_matches(criteria, query) {
            continue;
        }
        let mut rows: Vec<Value> = entry
            .get("rows")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if rows.is_empty() {
            continue;
        }

        let ref_year: i64 = query
            .period
            .get(0..4)
            .and_then(|year| year.parse().ok())
            .unwrap_or(0);
        for row in rows.iter_mut() {
            row["period"] = json!(query.period);
            if ref_year > 0 {
                row["refYear"] = json!(ref_year);
                row["refPeriodId"] = json!(ref_year * 10000 + 101);
            }
        }

        eprintln!(
            "[mcp-trade] serving seed rows: reporter={} partner={:?} cmd={:?} period={}",
            query.reporter_code, query.partner_code, query.cmd_code, query.period
        );

        let count = rows.len() as i64;
        return Some(TradeResult {
            count,
            rows,
            endpoint: SEED_ENDPOINT.to_string(),
            used_preview: false,
            note: None,
        });
    }
    None
}
