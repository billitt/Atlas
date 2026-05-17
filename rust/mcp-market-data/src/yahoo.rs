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
struct ChartError {
    code: Option<String>,
    description: Option<String>,
}

/// Fetch and parse a single-day chart for `symbol`.
pub async fn fetch_quote(
    client: &reqwest::Client,
    symbol: &str,
) -> Result<Quote, String> {
    let symbol = symbol.trim().to_uppercase();
    if symbol.is_empty() {
        return Err("symbol must not be empty".into());
    }

    let url = format!("{CHART_URL}/{symbol}?range=1d&interval=1d");

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

    let chart: ChartResponse = response
        .json()
        .await
        .map_err(|e| format!("invalid JSON from Yahoo Finance: {e}"))?;

    if let Some(err) = chart.chart.error {
        let msg = err
            .description
            .or(err.code)
            .unwrap_or_else(|| "unknown chart error".into());
        return Err(format!("Yahoo Finance error for {symbol}: {msg}"));
    }

    let results = chart
        .chart
        .result
        .filter(|r| !r.is_empty())
        .ok_or_else(|| format!("no market data for symbol '{symbol}' (unknown or delisted?)"))?;

    let meta = &results[0].meta;

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
    })
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
