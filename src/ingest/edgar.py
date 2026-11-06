import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{filename}"

INSIDER_FORMS = {"4", "4/A"}
RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}  # SEC returns 403 when throttling


@dataclass(frozen=True)
class Filing:
    ticker: str
    cik: int
    accession: str
    form: str
    filing_date: str
    xml_filename: str

    @property
    def xml_url(self) -> str:
        return ARCHIVE_URL.format(
            cik=self.cik,
            accession_nodash=self.accession.replace("-", ""),
            filename=self.xml_filename,
        )


class EdgarClient:
    def __init__(self, user_agent: str, min_interval_s: float = 0.2, max_retries: int = 4):
        if "@" not in user_agent:
            raise ValueError("SEC requires a User-Agent that includes a contact email")
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s  # 0.2s = max 5 req/s, half the SEC limit
        self.max_retries = max_retries
        self._last_request = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get_bytes(self, url: str) -> bytes:
        for attempt in range(self.max_retries + 1):
            self._throttle()
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()
            except urllib.error.HTTPError as err:
                if err.code not in RETRYABLE_STATUS or attempt == self.max_retries:
                    raise
                time.sleep(2**attempt)  # exponential backoff: 1, 2, 4, 8 seconds
        raise RuntimeError("unreachable")

    def get_json(self, url: str) -> dict:
        return json.loads(self.get_bytes(url))


def build_ticker_map(company_tickers: dict) -> dict[str, int]:
    """company_tickers.json looks like {"0": {"cik_str": 320193, "ticker": "AAPL", ...}}."""
    return {row["ticker"].upper(): int(row["cik_str"]) for row in company_tickers.values()}


def insider_filings_on(submissions: dict, ticker: str, cik: int, filing_date: str) -> list[Filing]:
    """Pick the Form 4 / 4/A filings from an issuer's submissions JSON for one date.

    filings.recent is "column oriented": parallel lists where index i across
    every list describes one filing.
    """
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    out: list[Filing] = []
    for i, form in enumerate(forms):
        if form not in INSIDER_FORMS or recent["filingDate"][i] != filing_date:
            continue
        # primaryDocument points at the HTML-rendered view, e.g.
        # "xslF345X05/wk-form4_1712345678.xml". The raw XML is the part after the slash.
        primary = recent["primaryDocument"][i]
        out.append(
            Filing(
                ticker=ticker,
                cik=cik,
                accession=recent["accessionNumber"][i],
                form=form,
                filing_date=filing_date,
                xml_filename=primary.rsplit("/", 1)[-1],
            )
        )
    return out
