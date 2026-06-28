//! UN Comtrade API client.
//!
//! Keyed endpoints use `/data/v1/get` and `/data/v1/getTariffline`.
//! Preview (keyless) uses `/public/v1/preview`.

use serde::Deserialize;
use serde_json::{json, Value};
use tokio::time::{sleep, Duration};

use crate::COMTRADE_DELAY_MS;
use crate::COMTRADE_USER_AGENT;

const COMTRADE_BASE: &str = "https://comtradeapi.un.org";
const PREVIEW_NOTE: &str = "preview mode, 500-record cap (no key / key rejected).";

#[derive(Debug, Deserialize)]
struct ComtradeEnvelope {
    count: i64,
    data: Vec<Value>,
}

#[derive(Debug, Clone)]
pub struct TradeQuery {
    pub type_code: String,
    pub freq_code: String,
    pub cl_code: String,
    pub reporter_code: String,
    pub period: String,
    pub partner_code: Option<String>,
    pub cmd_code: Option<String>,
    pub flow_code: Option<String>,
    pub max_records: Option<u32>,
}

pub struct TradeResult {
    pub count: i64,
    pub rows: Vec<Value>,
    pub endpoint: String,
    pub used_preview: bool,
    pub note: Option<String>,
}

pub async fn get_trade_data(
    client: &reqwest::Client,
    api_key: &Option<String>,
    query: &TradeQuery,
) -> Result<TradeResult, String> {
    let path = format!(
        "/data/v1/get/{}/{}/{}",
        query.type_code, query.freq_code, query.cl_code
    );
    fetch_with_preview_fallback(client, api_key, query, &path, "get_trade_data").await
}

pub async fn get_tariffline(
    client: &reqwest::Client,
    api_key: &Option<String>,
    query: &TradeQuery,
) -> Result<TradeResult, String> {
    let path = format!(
        "/data/v1/getTariffline/{}/{}/{}",
        query.type_code, query.freq_code, query.cl_code
    );
    fetch_with_preview_fallback(client, api_key, query, &path, "get_tariffline").await
}

pub async fn preview_trade(
    client: &reqwest::Client,
    query: &TradeQuery,
) -> Result<TradeResult, String> {
    let path = format!(
        "/public/v1/preview/{}/{}/{}",
        query.type_code, query.freq_code, query.cl_code
    );
    let max = query.max_records.unwrap_or(500).min(500);
    let q = build_query_params(query, max);
    let url = format!("{COMTRADE_BASE}{path}");
    comtrade_delay().await;
    let envelope = comtrade_get(client, &url, None, &q).await?;
    Ok(TradeResult {
        count: envelope.count,
        rows: envelope.data,
        endpoint: path,
        used_preview: true,
        note: Some(PREVIEW_NOTE.to_string()),
    })
}

async fn fetch_with_preview_fallback(
    client: &reqwest::Client,
    api_key: &Option<String>,
    query: &TradeQuery,
    path: &str,
    endpoint_name: &str,
) -> Result<TradeResult, String> {
    let key = match api_key {
        Some(k) if !k.is_empty() => k.as_str(),
        _ => {
            let mut preview = preview_trade(client, query).await?;
            preview.endpoint = format!("{endpoint_name} -> preview");
            return Ok(preview);
        }
    };

    let max = query.max_records.unwrap_or(100_000).min(100_000);
    let q = build_query_params(query, max);
    let url = format!("{COMTRADE_BASE}{path}");
    comtrade_delay().await;

    match comtrade_get(client, &url, Some(key), &q).await {
        Ok(envelope) => Ok(TradeResult {
            count: envelope.count,
            rows: envelope.data,
            endpoint: path.to_string(),
            used_preview: false,
            note: None,
        }),
        Err(err) if err.contains("401") || err.contains("403") => {
            let mut preview = preview_trade(client, query).await?;
            preview.endpoint = format!("{endpoint_name} -> preview (key rejected)");
            Ok(preview)
        }
        Err(err) => Err(err),
    }
}

fn build_query_params(query: &TradeQuery, max_records: u32) -> Vec<(&str, String)> {
    let mut params = vec![
        ("reportercode", query.reporter_code.clone()),
        ("period", query.period.clone()),
        ("maxRecords", max_records.to_string()),
    ];
    if let Some(ref partner) = query.partner_code {
        params.push(("partnerCode", partner.clone()));
    }
    if let Some(ref cmd) = query.cmd_code {
        params.push(("cmdCode", cmd.clone()));
    }
    if let Some(ref flow) = query.flow_code {
        params.push(("flowCode", flow.clone()));
    }
    params
}

async fn comtrade_get(
    client: &reqwest::Client,
    url: &str,
    api_key: Option<&str>,
    query: &[(&str, String)],
) -> Result<ComtradeEnvelope, String> {
    let mut request = client
        .get(url)
        .header(reqwest::header::USER_AGENT, COMTRADE_USER_AGENT);
    if let Some(key) = api_key {
        request = request.header("Ocp-Apim-Subscription-Key", key);
    }
    for (name, value) in query {
        request = request.query(&[(*name, value.as_str())]);
    }

    let response = request
        .send()
        .await
        .map_err(|e| format!("Comtrade request failed: {e}"))?;
    let status = response.status();
    if status == reqwest::StatusCode::UNAUTHORIZED || status == reqwest::StatusCode::FORBIDDEN {
        return Err(format!("Comtrade returned HTTP {status}"));
    }
    let response = response
        .error_for_status()
        .map_err(|e| format!("Comtrade returned HTTP {status}: {e}"))?;

    let body: Value = response
        .json()
        .await
        .map_err(|e| format!("invalid Comtrade JSON: {e}"))?;

    if let Some(message) = body.get("message").and_then(Value::as_str) {
        if body.get("data").is_none() {
            return Err(format!("Comtrade API error: {message}"));
        }
    }

    let count = body.get("count").and_then(Value::as_i64).unwrap_or(0);
    let data = body
        .get("data")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    Ok(ComtradeEnvelope { count, data })
}

pub fn trade_result_to_json(result: &TradeResult) -> Value {
    let mut payload = json!({
        "count": result.count,
        "rows": result.rows,
        "endpoint": result.endpoint,
        "used_preview": result.used_preview,
    });
    if let Some(note) = &result.note {
        payload["note"] = json!(note);
    }
    payload
}

pub fn format_trade_result_text(result: &TradeResult) -> String {
    serde_json::to_string_pretty(&trade_result_to_json(result))
        .unwrap_or_else(|_| trade_result_to_json(result).to_string())
}

async fn comtrade_delay() {
    sleep(Duration::from_millis(COMTRADE_DELAY_MS)).await;
}
