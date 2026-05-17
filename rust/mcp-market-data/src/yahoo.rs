//! Yahoo Finance chart API — upstream data for `get_quote`.

use serde::Deserialize;
use serde_json::json;

const CHART_URL: &str = "https://query1.finance.yahoo.com/v8/finance/chart";

/// Quote fields we expose to MCP clients.
#[derive(Debug, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub struct Quote {
    pub symbol: String,
    pub regular_market_price: f64,
    pub previous_close: f64,
    pub change_percent: f64,
    pub currency: String,
    pub regular_market_volume: u64,
    pub previous_day_volume: Option<u64>,
    pub average_volume_5d: Option<f64>,
    pub volume_vs_average_percent: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct ChartResponse {
    chart: ChartEnvelope,
}

#[derive(Debug, Deserialize)]
struct ChartEnvelope {
    result: Option<Vec<ChartResult>>,
    error: Option<ChartError>,
}

#[derive(Debug, Deserialize)]
struct ChartResult {
    meta: ChartMeta,
    indicators: Option<ChartIndicators>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ChartMeta {
    symbol: Option<String>,
    currency: Option<String>,
    regular_market_price: Option<f64>,
    previous_close: Option<f64>,
    chart_previous_close: Option<f64>,
    regular_market_volume: Option<u64>,
}

#[derive(Debug, Deserialize)]
struct ChartIndicators {
    quote: Vec<ChartQuote>,
}

#[derive(Debug, Deserialize)]
struct ChartQuote {
    volume: Option<Vec<Option<u64>>>,
}

#[derive(Debug, Deserialize)]
struct ChartError {
    code: Option<String>,
    description: Option<String>,
}

/// Fetch and parse recent chart data for `symbol`.
pub async fn fetch_quote(
    client: &reqwest::Client,
    symbol: &str,
) -> Result<Quote, String> {
    let symbol = symbol.trim().to_uppercase();
    if symbol.is_empty() {
        return Err("symbol must not be empty".into());
    }

    // Keep the latest quote on a 1d request. Yahoo's `chartPreviousClose` changes
    // meaning on wider ranges, so using 1d here preserves the previous-session close.
    let quote_chart = fetch_chart(client, &symbol, "1d").await?;
    let results = chart_results(quote_chart, &symbol)?;

    let result = &results[0];
    let meta = &result.meta;

    let price = meta
        .regular_market_price
        .ok_or_else(|| format!("missing regularMarketPrice for '{symbol}'"))?;
    // Yahoo uses `chartPreviousClose` on chart endpoints; `previousClose` appears on other APIs.
    let previous_close = meta
        .previous_close
        .or(meta.chart_previous_close)
        .ok_or_else(|| format!("missing previous close for '{symbol}'"))?;
    let currency = meta
        .currency
        .clone()
        .unwrap_or_else(|| "USD".into());
    let volume = meta.regular_market_volume.unwrap_or(0);
    // Fetch separate history only for volume baselines. This avoids corrupting the
    // previous-close semantics used above while still grounding volume comparisons.
    let volume_chart = fetch_chart(client, &symbol, "1mo").await?;
    let volume_results = chart_results(volume_chart, &symbol)?;
    let recent_volumes = extract_recent_volumes(&volume_results[0]);
    let previous_day_volume = previous_completed_volume(&recent_volumes);
    let average_volume_5d = average_completed_volume(&recent_volumes, 5);
    let volume_vs_average_percent = match (average_volume_5d, volume) {
        (Some(avg), current) if avg.abs() > f64::EPSILON => {
            Some(((current as f64 - avg) / avg) * 100.0)
        }
        _ => None,
    };

    let change_percent = if previous_close.abs() < f64::EPSILON {
        0.0
    } else {
        ((price - previous_close) / previous_close) * 100.0
    };

    Ok(Quote {
        symbol: meta.symbol.clone().unwrap_or(symbol),
        regular_market_price: price,
        previous_close,
        change_percent,
        currency,
        regular_market_volume: volume,
        previous_day_volume,
        average_volume_5d,
        volume_vs_average_percent,
    })
}

async fn fetch_chart(
    client: &reqwest::Client,
    symbol: &str,
    range: &str,
) -> Result<ChartResponse, String> {
    let url = format!("{CHART_URL}/{symbol}?range={range}&interval=1d");

    let response = client
        .get(&url)
        .header(
            reqwest::header::USER_AGENT,
            "Atlas-MCP/0.1 (https://github.com/atlas)",
        )
        .send()
        .await
        .map_err(|e| format!("Yahoo Finance request failed: {e}"))?;

    let status = response.status();
    let response = response
        .error_for_status()
        .map_err(|e| format!("Yahoo Finance returned HTTP {status}: {e}"))?;

    response
        .json()
        .await
        .map_err(|e| format!("invalid JSON from Yahoo Finance: {e}"))
}

fn chart_results(chart: ChartResponse, symbol: &str) -> Result<Vec<ChartResult>, String> {
    if let Some(err) = chart.chart.error {
        let msg = err
            .description
            .or(err.code)
            .unwrap_or_else(|| "unknown chart error".into());
        return Err(format!("Yahoo Finance error for {symbol}: {msg}"));
    }

    chart
        .chart
        .result
        .filter(|r| !r.is_empty())
        .ok_or_else(|| format!("no market data for symbol '{symbol}' (unknown or delisted?)"))
}

fn extract_recent_volumes(result: &ChartResult) -> Vec<u64> {
    result
        .indicators
        .as_ref()
        .and_then(|indicators| indicators.quote.first())
        .and_then(|quote| quote.volume.as_ref())
        .map(|volumes| {
            volumes
                .iter()
                .filter_map(|v| *v)
                .filter(|v| *v > 0)
                .collect()
        })
        .unwrap_or_default()
}

fn previous_completed_volume(recent_volumes: &[u64]) -> Option<u64> {
    // With range=5d, Yahoo returns daily volume buckets. The last bucket is the most
    // recent day, so the prior bucket is the previous completed trading day.
    recent_volumes
        .len()
        .checked_sub(2)
        .and_then(|idx| recent_volumes.get(idx).copied())
}

fn average_completed_volume(recent_volumes: &[u64], days: usize) -> Option<f64> {
    if recent_volumes.len() < 2 {
        return None;
    }

    // Exclude the latest bucket from the baseline; it may represent today's partial
    // session. Then take up to `days` completed sessions from the end.
    let completed = &recent_volumes[..recent_volumes.len() - 1];
    let start = completed.len().saturating_sub(days);
    let baseline = &completed[start..];
    if baseline.is_empty() {
        return None;
    }

    let sum: u64 = baseline.iter().sum();
    Some(sum as f64 / baseline.len() as f64)
}

/// Serialize quote as pretty JSON for MCP `content[].text`.
pub fn quote_to_text(quote: &Quote) -> String {
    serde_json::to_string_pretty(quote).unwrap_or_else(|_| {
        json!({
            "symbol": quote.symbol,
            "error": "failed to serialize quote"
        })
        .to_string()
    })
}
