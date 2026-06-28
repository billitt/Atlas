//! MCP JSON-RPC 2.0 handlers for UN Comtrade tools.

use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use mcp_common::validation::{
    validate_classification, validate_cmd_code, validate_flow_code, validate_freq_code,
    validate_m49_code, validate_period, validate_type_code,
};

use crate::comtrade::{
    format_trade_result_text, get_tariffline, get_trade_data, preview_trade, TradeQuery,
};
use crate::AppState;

const PROTOCOL_VERSION: &str = "2024-11-05";
const SERVER_NAME: &str = "mcp-trade";
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
                "name": "get_trade_data",
                "description": "Fetch UN Comtrade final trade data (keyed; falls back to preview when no key).",
                "inputSchema": trade_input_schema()
            },
            {
                "name": "get_tariffline",
                "description": "Fetch UN Comtrade tariff-line granularity trade data.",
                "inputSchema": trade_input_schema()
            },
            {
                "name": "preview_trade",
                "description": "Keyless preview of UN Comtrade data (max 500 records).",
                "inputSchema": trade_input_schema()
            }
        ]
    }))
}

fn trade_input_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "typeCode": { "type": "string", "description": "Trade type, default C (goods)" },
            "freqCode": { "type": "string", "description": "Frequency, default A (annual)" },
            "clCode": { "type": "string", "description": "Classification, default HS" },
            "reporterCode": { "type": "string", "description": "UN M49 reporter code" },
            "partnerCode": { "type": "string", "description": "UN M49 partner code" },
            "cmdCode": { "type": "string", "description": "Commodity code (HS)" },
            "flowCode": { "type": "string", "description": "Flow: M (import), X (export)" },
            "period": { "type": "string", "description": "Period yyyy or yyyymm" },
            "maxRecords": { "type": "integer", "description": "Max rows (100k keyed, 500 preview)" }
        },
        "required": ["reporterCode", "period"]
    })
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

    let query = parse_trade_query(&args)?;

    let result = match params.name.as_str() {
        "get_trade_data" => get_trade_data(&state.http, &state.api_key, &query).await,
        "get_tariffline" => get_tariffline(&state.http, &state.api_key, &query).await,
        "preview_trade" => preview_trade(&state.http, &query).await,
        other => return Err((-32602, format!("unknown tool: {other}"))),
    };

    match result {
        Ok(trade) => Ok(json!({
            "content": [{ "type": "text", "text": format_trade_result_text(&trade) }]
        })),
        Err(message) => Ok(json!({
            "content": [{ "type": "text", "text": json!({ "error": message }).to_string() }],
            "isError": true
        })),
    }
}

fn parse_trade_query(args: &Value) -> Result<TradeQuery, (i32, String)> {
    let type_code = validate_type_code(args.get("typeCode").and_then(Value::as_str).unwrap_or("C"))
        .map_err(|m| (-32602, m))?;
    let freq_code = validate_freq_code(args.get("freqCode").and_then(Value::as_str).unwrap_or("A"))
        .map_err(|m| (-32602, m))?;
    let cl_code =
        validate_classification(args.get("clCode").and_then(Value::as_str).unwrap_or("HS"))
            .map_err(|m| (-32602, m))?;
    let reporter_code =
        validate_m49_code(required_str(args, "reporterCode")?).map_err(|m| (-32602, m))?;
    let period = validate_period(required_str(args, "period")?).map_err(|m| (-32602, m))?;

    let partner_code = match args.get("partnerCode").and_then(Value::as_str) {
        Some(value) => Some(validate_m49_code(value).map_err(|m| (-32602, m))?),
        None => None,
    };
    let cmd_code = match args.get("cmdCode").and_then(Value::as_str) {
        Some(value) => Some(validate_cmd_code(value).map_err(|m| (-32602, m))?),
        None => None,
    };
    let flow_code = match args.get("flowCode").and_then(Value::as_str) {
        Some(value) => Some(validate_flow_code(value).map_err(|m| (-32602, m))?),
        None => None,
    };
    let max_records = args
        .get("maxRecords")
        .and_then(Value::as_u64)
        .map(|v| v.min(100_000) as u32);

    Ok(TradeQuery {
        type_code,
        freq_code,
        cl_code,
        reporter_code,
        period,
        partner_code,
        cmd_code,
        flow_code,
        max_records,
    })
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
