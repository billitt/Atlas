//! SEC EDGAR API client.
//!
//! SEC requires an identifying User-Agent on every request and asks clients not
//! to exceed 10 requests/second. This module centralizes those API rules so MCP
//! handlers can stay focused on tool behavior.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::time::{sleep, Duration};

use crate::SEC_USER_AGENT;

const SEC_ARCHIVES: &str = "https://www.sec.gov/Archives/edgar/data";
const SEC_COMPANY_TICKERS: &str = "https://www.sec.gov/files/company_tickers.json";
const SEC_SUBMISSIONS: &str = "https://data.sec.gov/submissions";
const SEC_SEARCH: &str = "https://efts.sec.gov/LATEST/search-index";

#[derive(Debug, Clone, Serialize)]
pub struct FilingSummary {
    pub accession_number: String,
    pub filing_date: String,
    pub form_type: String,
    pub primary_document: String,
    pub primary_document_url: String,
}

#[derive(Debug, Deserialize)]
struct CompanyTicker {
    cik_str: u64,
    ticker: String,
    title: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SubmissionResponse {
    cik: String,
    name: String,
    filings: SubmissionFilings,
}

#[derive(Debug, Deserialize)]
struct SubmissionFilings {
    recent: RecentFilings,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RecentFilings {
    accession_number: Vec<String>,
    filing_date: Vec<String>,
    form: Vec<String>,
    primary_document: Vec<String>,
}

/// Resolve a ticker to a zero-padded CIK using SEC's company_tickers.json.
pub async fn resolve_ticker(client: &reqwest::Client, ticker: &str) -> Result<String, String> {
    sec_delay().await;
    let response = sec_get(client, SEC_COMPANY_TICKERS).await?;
    let tickers: Value = response
        .json()
        .await
        .map_err(|e| format!("invalid SEC ticker JSON: {e}"))?;

    let wanted = ticker.trim().to_uppercase();
    let companies = tickers
        .as_object()
        .ok_or_else(|| "SEC ticker response was not an object".to_string())?;

    for company in companies.values() {
        let company: CompanyTicker = serde_json::from_value(company.clone())
            .map_err(|e| format!("invalid company ticker row: {e}"))?;
        if company.ticker.to_uppercase() == wanted {
            println!(
                "[edgar] resolved ticker {} to CIK {} ({})",
                wanted, company.cik_str, company.title
            );
            return Ok(pad_cik(&company.cik_str.to_string()));
        }
    }
    Err(format!("ticker not found in SEC company_tickers.json: {ticker}"))
}

pub async fn company_filings(
    client: &reqwest::Client,
    ticker: Option<&str>,
    cik: Option<&str>,
) -> Result<Vec<FilingSummary>, String> {
    let cik = match (cik, ticker) {
        (Some(cik), _) => pad_cik(cik),
        (None, Some(ticker)) => resolve_ticker(client, ticker).await?,
        (None, None) => return Err("company_filings requires ticker or cik".into()),
    };

    sec_delay().await;
    let url = format!("{SEC_SUBMISSIONS}/CIK{cik}.json");
    let response = sec_get(client, &url).await?;
    let submissions: SubmissionResponse = response
        .json()
        .await
        .map_err(|e| format!("invalid SEC submissions JSON: {e}"))?;

    println!(
        "[edgar] loaded submissions for {} ({})",
        submissions.name, submissions.cik
    );

    let recent = submissions.filings.recent;
    let mut filings = Vec::new();
    let count = recent.accession_number.len().min(10);
    for index in 0..count {
        let accession = recent.accession_number.get(index).cloned().unwrap_or_default();
        let accession_no_dashes = accession.replace('-', "");
        let primary_document = recent.primary_document.get(index).cloned().unwrap_or_default();
        let primary_document_url = format!(
            "{SEC_ARCHIVES}/{}/{}/{}",
            cik.trim_start_matches('0'),
            accession_no_dashes,
            primary_document
        );
        filings.push(FilingSummary {
            accession_number: accession,
            filing_date: recent.filing_date.get(index).cloned().unwrap_or_default(),
            form_type: recent.form.get(index).cloned().unwrap_or_default(),
            primary_document,
            primary_document_url,
        });
    }
    Ok(filings)
}

pub async fn filing_text(
    client: &reqwest::Client,
    cik: &str,
    accession_number: &str,
) -> Result<String, String> {
    let cik = pad_cik(cik);
    let accession_no_dashes = accession_number.replace('-', "");

    let filings = company_filings(client, None, Some(&cik)).await?;
    let primary = filings
        .iter()
        .find(|filing| filing.accession_number == accession_number)
        .map(|filing| filing.primary_document.clone())
        .unwrap_or_else(|| format!("{accession_no_dashes}.txt"));

    let url = format!(
        "{SEC_ARCHIVES}/{}/{}/{}",
        cik.trim_start_matches('0'),
        accession_no_dashes,
        primary
    );

    sec_delay().await;
    let response = sec_get(client, &url).await?;
    let html = response
        .text()
        .await
        .map_err(|e| format!("failed reading filing text: {e}"))?;
    let clean = strip_html(&html);
    Ok(clean.chars().take(10_000).collect())
}

pub async fn full_text_search(
    client: &reqwest::Client,
    query: &str,
    form_type: Option<&str>,
    date_from: Option<&str>,
) -> Result<Value, String> {
    sec_delay().await;
    let mut request = client
        .get(SEC_SEARCH)
        .header(reqwest::header::USER_AGENT, SEC_USER_AGENT)
        .query(&[
            ("q", query),
            ("dateRange", "custom"),
            ("startdt", date_from.unwrap_or("2024-01-01")),
        ]);
    if let Some(form_type) = form_type {
        request = request.query(&[("forms", form_type)]);
    }

    let response = request
        .send()
        .await
        .map_err(|e| format!("SEC full-text search failed: {e}"))?;
    let status = response.status();
    let response = response
        .error_for_status()
        .map_err(|e| format!("SEC full-text search HTTP {status}: {e}"))?;
    response
        .json()
        .await
        .map_err(|e| format!("invalid SEC full-text search JSON: {e}"))
}

/// EDGAR expects CIKs as 10 digits in submissions URLs.
pub fn pad_cik(cik: &str) -> String {
    let digits: String = cik.chars().filter(|c| c.is_ascii_digit()).collect();
    format!("{:0>10}", digits)
}

async fn sec_get(client: &reqwest::Client, url: &str) -> Result<reqwest::Response, String> {
    let response = client
        .get(url)
        .header(reqwest::header::USER_AGENT, SEC_USER_AGENT)
        .send()
        .await
        .map_err(|e| format!("SEC request failed: {e}"))?;
    let status = response.status();
    response
        .error_for_status()
        .map_err(|e| format!("SEC returned HTTP {status}: {e}"))
}

async fn sec_delay() {
    // SEC guidance is no more than 10 requests/second. A small delay keeps this
    // local demo comfortably below the limit even when tools chain requests.
    sleep(Duration::from_millis(125)).await;
}

fn strip_html(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut in_tag = false;
    let mut last_space = false;

    for ch in input.chars() {
        match ch {
            '<' => in_tag = true,
            '>' => {
                in_tag = false;
                if !last_space {
                    out.push(' ');
                    last_space = true;
                }
            }
            _ if in_tag => {}
            _ if ch.is_whitespace() => {
                if !last_space {
                    out.push(' ');
                    last_space = true;
                }
            }
            _ => {
                out.push(ch);
                last_space = false;
            }
        }
    }

    out.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .trim()
        .to_string()
}
