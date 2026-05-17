//! Ollama health check — Rust equivalent of `scripts/verify_ollama.py`.
//!
//! Confirms the local Ollama instance is reachable, Granite 4.1 8B is installed,
//! and the model returns a response to a fixed test prompt.

use serde::Deserialize;
use std::env;
use std::process::ExitCode;

const DEFAULT_BASE_URL: &str = "http://localhost:11434";
const EXPECTED_MODEL: &str = "ibm/granite4.1:8b";
const TEST_PROMPT: &str = "Reply with exactly: Atlas Phase 0 OK";

// #[derive(Deserialize)] tells serde to auto-generate JSON parsing code for this struct.
// Field names must match the JSON keys Ollama returns (e.g. "models", "name", "response").
#[derive(Debug, Deserialize)]
struct TagsResponse {
    models: Vec<ModelEntry>,
}

#[derive(Debug, Deserialize)]
struct ModelEntry {
    name: String,
}

#[derive(Debug, Deserialize)]
struct GenerateResponse {
    response: String,
}

// #[tokio::main] is a macro that rewrites this into a normal `fn main()` which
// creates a Tokio async runtime and runs this async body on it — required because
// reqwest's HTTP calls are async and need an executor to `.await` them.
#[tokio::main]
async fn main() -> ExitCode {
    match run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("FAIL: {err}");
            eprintln!();
            eprintln!("Install Ollama: https://ollama.com/download");
            eprintln!("Then pull Granite: ollama pull {EXPECTED_MODEL}");
            ExitCode::FAILURE
        }
    }
}

// Result<(), Box<dyn std::error::Error>> is Rust's error-handling pattern:
//   Ok(())  = success (unit type — "no value, just done")
//   Err(e)  = failure; `?` in the body propagates errors up to main
// Box<dyn Error> lets us return any error type (reqwest, JSON, etc.) from one function.
async fn run() -> Result<(), Box<dyn std::error::Error>> {
    // `env::var` returns Result<String, VarError>. `unwrap_or_else` takes the Ok
    // value, or runs the closure on Err (here: missing var → use default).
    // `.to_string()` allocates an owned String — needed because the fallback is a &str.
    let base_url = env::var("OLLAMA_BASE_URL").unwrap_or_else(|_| DEFAULT_BASE_URL.to_string());

    println!("Ollama base URL: {base_url}");
    println!("Expected model:  {EXPECTED_MODEL}");
    println!();

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()?;

    let models = list_models(&client, &base_url).await?;

    println!("Available models:");
    for name in &models {
        let marker = if model_matches(name, EXPECTED_MODEL) {
            " <-- configured"
        } else {
            ""
        };
        println!("  - {name}{marker}");
    }

    if !models.iter().any(|m| model_matches(m, EXPECTED_MODEL)) {
        println!();
        println!("WARN: {EXPECTED_MODEL} not found. Pull it with:");
        println!("      ollama pull {EXPECTED_MODEL}");
        return Err(format!("model {EXPECTED_MODEL} not in /api/tags").into());
    }

    println!();
    println!("Sending test prompt to Granite...");
    let reply = generate(&client, &base_url, TEST_PROMPT).await?;
    println!("Response: {}", reply.trim());
    println!();
    println!("PASS: Ollama + Granite are responding.");

    Ok(())
}

async fn list_models(
    client: &reqwest::Client,
    base_url: &str,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let url = format!("{base_url}/api/tags");
    let response = client.get(&url).send().await?;
    let response = response.error_for_status()?;

    let tags: TagsResponse = response.json().await?;
    Ok(tags.models.into_iter().map(|m| m.name).collect())
}

async fn generate(
    client: &reqwest::Client,
    base_url: &str,
    prompt: &str,
) -> Result<String, Box<dyn std::error::Error>> {
    let url = format!("{base_url}/api/generate");
    let body = serde_json::json!({
        "model": EXPECTED_MODEL,
        "prompt": prompt,
        "stream": false,
    });

    let response = client.post(&url).json(&body).send().await?;
    let response = response.error_for_status()?;

    let gen: GenerateResponse = response.json().await?;
    Ok(gen.response)
}

// `expected` is a &str (borrowed string slice) — we only read it, we don't need ownership.
// Comparing with == or starts_with avoids allocating new strings.
fn model_matches(name: &str, expected: &str) -> bool {
    name == expected || name.starts_with(expected)
}
