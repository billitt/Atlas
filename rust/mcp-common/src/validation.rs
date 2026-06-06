//! Input validation for MCP tool arguments.

use std::sync::LazyLock;

static SYMBOL_RE: LazyLock<regex::Regex> =
    LazyLock::new(|| regex::Regex::new(r"^[A-Za-z0-9.\-]{1,12}$").expect("valid symbol regex"));
static TICKER_RE: LazyLock<regex::Regex> =
    LazyLock::new(|| regex::Regex::new(r"^[A-Za-z0-9.\-]{1,10}$").expect("valid ticker regex"));
static CIK_RE: LazyLock<regex::Regex> =
    LazyLock::new(|| regex::Regex::new(r"^[0-9]{1,10}$").expect("valid cik regex"));
static ACCESSION_RE: LazyLock<regex::Regex> = LazyLock::new(|| {
    regex::Regex::new(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$").expect("valid accession regex")
});
static DATE_RE: LazyLock<regex::Regex> =
    LazyLock::new(|| regex::Regex::new(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$").expect("valid date regex"));
static FORM_TYPE_RE: LazyLock<regex::Regex> =
    LazyLock::new(|| regex::Regex::new(r"^[A-Za-z0-9\-/]{1,20}$").expect("valid form type regex"));

/// Validate a stock ticker symbol for Yahoo Finance requests.
pub fn validate_symbol(symbol: &str) -> Result<String, String> {
    let trimmed = symbol.trim();
    if trimmed.is_empty() {
        return Err("symbol must not be empty".into());
    }
    if !SYMBOL_RE.is_match(trimmed) {
        return Err(format!(
            "invalid symbol '{trimmed}': use 1-12 alphanumeric characters, dots, or hyphens"
        ));
    }
    Ok(trimmed.to_uppercase())
}

/// Validate an SEC ticker symbol.
pub fn validate_ticker(ticker: &str) -> Result<String, String> {
    let trimmed = ticker.trim();
    if trimmed.is_empty() {
        return Err("ticker must not be empty".into());
    }
    if !TICKER_RE.is_match(trimmed) {
        return Err(format!(
            "invalid ticker '{trimmed}': use 1-10 alphanumeric characters, dots, or hyphens"
        ));
    }
    Ok(trimmed.to_uppercase())
}

/// Validate a SEC CIK (digits only, up to 10).
pub fn validate_cik(cik: &str) -> Result<String, String> {
    let trimmed = cik.trim();
    if trimmed.is_empty() {
        return Err("cik must not be empty".into());
    }
    if !CIK_RE.is_match(trimmed) {
        return Err(format!("invalid cik '{trimmed}': use 1-10 digits"));
    }
    Ok(trimmed.to_string())
}

/// Validate an SEC accession number (`##########-##-######`).
pub fn validate_accession_number(accession: &str) -> Result<String, String> {
    let trimmed = accession.trim();
    if trimmed.is_empty() {
        return Err("accession_number must not be empty".into());
    }
    if !ACCESSION_RE.is_match(trimmed) {
        return Err(format!(
            "invalid accession_number '{trimmed}': expected format ##########-##-######"
        ));
    }
    Ok(trimmed.to_string())
}

/// Validate a SEC full-text search query (length and printable ASCII).
pub fn validate_search_query(query: &str) -> Result<String, String> {
    let trimmed = query.trim();
    if trimmed.is_empty() {
        return Err("query must not be empty".into());
    }
    if trimmed.len() > 500 {
        return Err("query must be at most 500 characters".into());
    }
    if !trimmed.is_ascii() {
        return Err("query must contain ASCII characters only".into());
    }
    Ok(trimmed.to_string())
}

/// Validate an optional SEC form type filter.
pub fn validate_form_type(form_type: &str) -> Result<String, String> {
    let trimmed = form_type.trim();
    if trimmed.is_empty() {
        return Err("form_type must not be empty".into());
    }
    if !FORM_TYPE_RE.is_match(trimmed) {
        return Err(format!("invalid form_type '{trimmed}'"));
    }
    Ok(trimmed.to_uppercase())
}

/// Validate an optional YYYY-MM-DD date filter.
pub fn validate_date_from(date_from: &str) -> Result<String, String> {
    let trimmed = date_from.trim();
    if trimmed.is_empty() {
        return Err("date_from must not be empty".into());
    }
    if !DATE_RE.is_match(trimmed) {
        return Err(format!(
            "invalid date_from '{trimmed}': expected YYYY-MM-DD"
        ));
    }
    Ok(trimmed.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_valid_symbols() {
        assert_eq!(validate_symbol("aapl").unwrap(), "AAPL");
        assert_eq!(validate_symbol("BRK.B").unwrap(), "BRK.B");
    }

    #[test]
    fn rejects_path_like_symbols() {
        assert!(validate_symbol("../../etc").is_err());
        assert!(validate_symbol("").is_err());
    }

    #[test]
    fn accepts_valid_cik_and_accession() {
        assert_eq!(validate_cik("320193").unwrap(), "320193");
        assert_eq!(
            validate_accession_number("0000320193-23-000106").unwrap(),
            "0000320193-23-000106"
        );
    }

    #[test]
    fn rejects_invalid_accession() {
        assert!(validate_accession_number("not-an-accession").is_err());
    }

    #[test]
    fn rejects_sql_injection_in_symbol() {
        assert!(validate_symbol("'; DROP TABLE--").is_err());
        assert!(validate_symbol("AAPL; DELETE FROM quotes").is_err());
    }

    #[test]
    fn rejects_symbol_attack_patterns() {
        for bad in [
            "../../etc",
            "%2e%2e/",
            "TSM©",
            "ABCDEFGHIJKLM",
            "   ",
            "AAPL/MSFT",
            "AAPL\nTSM",
        ] {
            assert!(validate_symbol(bad).is_err(), "expected reject for {bad:?}");
        }
    }

    #[test]
    fn rejects_ticker_attack_patterns() {
        for bad in [
            "'; DROP TABLE--",
            "../../etc",
            "ABCDEFGHIJK",
            "TSM©",
            "",
        ] {
            assert!(validate_ticker(bad).is_err(), "expected reject for {bad:?}");
        }
    }

    #[test]
    fn rejects_invalid_cik_values() {
        for bad in ["abc", "12345678901", "-1", "32o193", ""] {
            assert!(validate_cik(bad).is_err(), "expected reject for {bad:?}");
        }
    }

    #[test]
    fn rejects_invalid_accession_formats() {
        for bad in [
            "0000320193-23",
            "0000320193-23-000106-extra",
            "not-an-accession",
            "",
        ] {
            assert!(
                validate_accession_number(bad).is_err(),
                "expected reject for {bad:?}"
            );
        }
    }

    #[test]
    fn rejects_invalid_search_queries() {
        assert!(validate_search_query("").is_err());
        assert!(validate_search_query(&"a".repeat(501)).is_err());
        assert!(validate_search_query("semiconductor 🔥").is_err());
    }

    #[test]
    fn accepts_ascii_search_query() {
        assert_eq!(
            validate_search_query("  export restriction  ").unwrap(),
            "export restriction"
        );
    }

    #[test]
    fn rejects_invalid_form_types() {
        assert!(validate_form_type("").is_err());
        assert!(validate_form_type("10-K; DROP").is_err());
    }

    #[test]
    fn accepts_valid_form_type() {
        assert_eq!(validate_form_type("10-k").unwrap(), "10-K");
    }

    #[test]
    fn rejects_invalid_date_from_values() {
        assert!(validate_date_from("").is_err());
        assert!(validate_date_from("2024/01/15").is_err());
        assert!(validate_date_from("not-a-date").is_err());
    }

    #[test]
    fn accepts_valid_date_from() {
        assert_eq!(validate_date_from("2024-01-15").unwrap(), "2024-01-15");
    }
}
