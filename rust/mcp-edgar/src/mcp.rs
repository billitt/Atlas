//! MCP JSON-RPC 2.0 handlers for SEC EDGAR tools.

use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use mcp_common::validation::{
    validate_accession_number, validate_cik, validate_date_from, validate_form_type,
    validate_search_query, validate_ticker,
};

use crate::edgar::{company_filings, filing_text, full_text_search};
use crate::AppState;

const PROTOCOL_VERSION: &str = "2024-11-05";
const SERVER_NAME: &str = "mcp-edgar";
const SERVER_VERSION: &str = "0.1.0";

#[derive(Debug, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: Value,
    pub method: String,
    #[serde(default)]
    pub params: Option<Value>,
}

#[derive(Debug, Deserialize)]
struct ToolsCallParams {
    name: String,
    #[serde(default)]
    arguments: Option<Value>,
}

pub async fn handle_json_rpc(state: AppState, request: JsonRpcRequest) -> Json<Value> {
    if request.jsonrpc != "2.0" {
        return Json(json_rpc_error(
            request.id,
            -32600,
            "jsonrpc must be \"2.0\"",
        ));
    }

    let result = match request.method.as_str() {
        "initialize" => handle_initialize(),
        "tools/list" => handle_tools_list(),
        "tools/call" => handle_tools_call(&state, request.params).await,
        other => {
            return Json(json_rpc_error(
                request.id,
                -32601,
                &format!("method not found: {other}"),
            ));
        }
    };

    match result {
        Ok(value) => Json(json_rpc_success(request.id, value)),
        Err((code, message)) => Json(json_rpc_error(request.id, code, &message)),
    }
}

fn handle_initialize() -> Result<Value, (i32, String)> {
    Ok(json!({
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": { "tools": {} },
        "serverInfo": { "name": SERVER_NAME, "version": SERVER_VERSION }
    }))
}

fn handle_tools_list() -> Result<Value, (i32, String)> {
    Ok(json!({
        "tools": [
            {
                "name": "company_filings",
                "description": "List recent SEC filings for a company by ticker or CIK.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ticker": { "type": "string", "description": "Ticker symbol, e.g. AAPL" },
                        "cik": { "type": "string", "description": "SEC CIK, with or without zero padding" }
                    }
                }
            },
            {
                "name": "filing_text",
                "description": "Fetch and clean the first ~10,000 characters of a filing document.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "accession_number": { "type": "string" },
                        "cik": { "type": "string" }
                    },
                    "required": ["accession_number", "cik"]
                }
            },
            {
                "name": "full_text_search",
                "description": "Search SEC full-text filings by query, form type, and start date.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": { "type": "string" },
                        "form_type": { "type": "string", "description": "Form type such as 10-K" },
                        "date_from": { "type": "string", "description": "YYYY-MM-DD start date" }
                    },
                    "required": ["query"]
                }
            }
        ]
    }))
}

async fn handle_tools_call(
    state: &AppState,
    params: Option<Value>,
) -> Result<Value, (i32, String)> {
    let params: ToolsCallParams =
        serde_json::from_value(params.unwrap_or(Value::Object(Default::default())))
            .map_err(|e| (-32602, format!("invalid tools/call params: {e}")))?;
    let args = params
        .arguments
        .unwrap_or(Value::Object(Default::default()));

    let result = match params.name.as_str() {
        "company_filings" => {
            let ticker = match args.get("ticker").and_then(Value::as_str) {
                Some(value) => Some(validate_ticker(value).map_err(|message| (-32602, message))?),
                None => None,
            };
            let cik = match args.get("cik").and_then(Value::as_str) {
                Some(value) => Some(validate_cik(value).map_err(|message| (-32602, message))?),
                None => None,
            };
            if ticker.is_none() && cik.is_none() {
                return Err((-32602, "company_filings requires ticker or cik".into()));
            }
            company_filings(&state.http, ticker.as_deref(), cik.as_deref())
                .await
                .map(|filings| json!({ "filings": filings }))
        }
        "filing_text" => {
            let accession = validate_accession_number(required_str(&args, "accession_number")?)
                .map_err(|message| (-32602, message))?;
            let cik =
                validate_cik(required_str(&args, "cik")?).map_err(|message| (-32602, message))?;
            filing_text(&state.http, &cik, &accession)
                .await
                .map(|text| json!({ "cik": cik, "accession_number": accession, "text": text }))
        }
        "full_text_search" => {
            let query = validate_search_query(required_str(&args, "query")?)
                .map_err(|message| (-32602, message))?;
            let form_type = match args.get("form_type").and_then(Value::as_str) {
                Some(value) => {
                    Some(validate_form_type(value).map_err(|message| (-32602, message))?)
                }
                None => None,
            };
            let date_from = match args.get("date_from").and_then(Value::as_str) {
                Some(value) => {
                    Some(validate_date_from(value).map_err(|message| (-32602, message))?)
                }
                None => None,
            };
            full_text_search(
                &state.http,
                &query,
                form_type.as_deref(),
                date_from.as_deref(),
            )
            .await
        }
        other => Err(format!("unknown tool: {other}")),
    };

    match result {
        Ok(value) => Ok(json!({
            "content": [{ "type": "text", "text": serde_json::to_string_pretty(&value).unwrap_or_else(|_| value.to_string()) }]
        })),
        Err(message) => Ok(json!({
            "content": [{ "type": "text", "text": json!({ "error": message }).to_string() }],
            "isError": true
        })),
    }
}

fn required_str<'a>(args: &'a Value, key: &str) -> Result<&'a str, (i32, String)> {
    args.get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| (-32602, format!("missing required argument: {key}")))
}

fn json_rpc_success(id: Value, result: Value) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "result": result })
}

fn json_rpc_error(id: Value, code: i32, message: &str) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "error": { "code": code, "message": message } })
}
