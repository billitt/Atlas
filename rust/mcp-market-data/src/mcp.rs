//! MCP JSON-RPC 2.0 handlers for the `/mcp` endpoint.

use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::yahoo::{fetch_quote, quote_to_text};
use crate::AppState;

const PROTOCOL_VERSION: &str = "2024-11-05";
const SERVER_NAME: &str = "mcp-market-data";
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

/// Route one JSON-RPC request to the appropriate MCP handler.
pub async fn handle_json_rpc(
    state: AppState,
    request: JsonRpcRequest,
) -> Json<Value> {
    if request.jsonrpc != "2.0" {
        return Json(json_rpc_error(
            request.id,
            -32600,
            "jsonrpc must be \"2.0\"",
        ));
    }

    let result = match request.method.as_str() {
        "initialize" => handle_initialize(request.params),
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

fn handle_initialize(_params: Option<Value>) -> Result<Value, (i32, String)> {
    Ok(json!({
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION
        }
    }))
}

fn handle_tools_list() -> Result<Value, (i32, String)> {
    Ok(json!({
        "tools": [
            {
                "name": "get_quote",
                "description": "Fetch the latest stock quote from Yahoo Finance for a ticker symbol.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g. AAPL, TSMC)"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        ]
    }))
}

async fn handle_tools_call(
    state: &AppState,
    params: Option<Value>,
) -> Result<Value, (i32, String)> {
    let params: ToolsCallParams = serde_json::from_value(
        params.unwrap_or(Value::Object(Default::default())),
    )
    .map_err(|e| (-32602, format!("invalid tools/call params: {e}")))?;

    if params.name != "get_quote" {
        return Err((
            -32602,
            format!("unknown tool: {}", params.name),
        ));
    }

    let symbol = params
        .arguments
        .as_ref()
        .and_then(|v| v.get("symbol"))
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| {
            (
                -32602,
                "get_quote requires arguments.symbol (non-empty string)".into(),
            )
        })?;

    match fetch_quote(&state.http, symbol).await {
        Ok(quote) => Ok(json!({
            "content": [
                {
                    "type": "text",
                    "text": quote_to_text(&quote)
                }
            ]
        })),
        Err(message) => Ok(json!({
            "content": [
                {
                    "type": "text",
                    "text": json!({ "error": message, "symbol": symbol }).to_string()
                }
            ],
            "isError": true
        })),
    }
}

fn json_rpc_success(id: Value, result: Value) -> Value {
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": result
    })
}

fn json_rpc_error(id: Value, code: i32, message: &str) -> Value {
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "error": {
            "code": code,
            "message": message
        }
    })
}
