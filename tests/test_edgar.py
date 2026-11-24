import pytest 

from ingest.edgar import EdgarClient, Filing, build_ticker_map, insider_filings_on

def test_build_ticker_map_uppercase_and_casts():
    raw = {"0": {"cik_str": 320193, "ticker": "aapl", "title":"Apple Inc."}}
    assert build_ticker_map(raw) == {"AAPL": 320193}

def test_insider_filings_only_form4_on_requested_date(submissions):
    filings = insider_filings_on(submissions, "AAPL", 320193, "2026-10-16")
    assert[f.form for f in filings] == ["4", "4/A"]

def test_xml_filename_strips_rendered_view_prefix(submissions):
    first = insider_filings_on(submissions, "AAPL", 320193, "2026-10-16")[0]
    assert first.xml_filename == "wk-form4_1760600000.xml"

def test_xml_url_uses_unpadded_cik_and_accession_without_dashes():
    f = Filing("AAPL", 320193, "0000320193-26-000101", "4", "2026-10-16", "x.xml")
    assert f.xml_url == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000101/x.xml"

def test_no_filing_returns_empty_list():
    assert insider_filings_on({}, "AAPL", 1, "2026-10-16") == []

def test_client_requires_email():
    with pytest.raises(ValueError):
        EdgarClient("no-email-here")

