
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime, timedelta

from edgar import SUBMISSIONS_URL, TICKERS_URL, EdgarClient, build_ticker_map, insider_filings_on

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SOURCE = "sec_form4"


def partition_prefix(filing_date: str) -> str:
    return f"raw/source={SOURCE}/filing_date={filing_date}"


def resolve_filing_date(event: dict | None, today: date | None = None) -> str:
    if event and event.get("filing_date"):
        return date.fromisoformat(event["filing_date"]).isoformat()  # validates format
    today = today or datetime.now(UTC).date()
    return (today - timedelta(days=1)).isoformat()


def run(filing_date: str, tickers: list[str], client, s3, bucket: str) -> dict:
    ticker_map = build_ticker_map(client.get_json(TICKERS_URL))
    prefix = partition_prefix(filing_date)
    written, missing = [], []

    for ticker in tickers:
        cik = ticker_map.get(ticker)
        if cik is None:
            missing.append(ticker)
            logger.warning(json.dumps({"event": "unknown_ticker", "ticker": ticker}))
            continue

        submissions = client.get_json(SUBMISSIONS_URL.format(cik=cik))
        for filing in insider_filings_on(submissions, ticker, cik, filing_date):
            key = f"{prefix}/ticker={ticker}/{filing.accession}.xml"
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=client.get_bytes(filing.xml_url),
                ContentType="application/xml",
                Metadata={"form": filing.form, "source-url": filing.xml_url},
            )
            written.append(key)

    manifest = {
        "source": SOURCE,
        "filing_date": filing_date,
        "tickers_requested": tickers,
        "tickers_unknown": missing,
        "files_written": len(written),
        "keys": written,
        "run_at": datetime.now(UTC).isoformat(),
    }
    # Written last, on purpose: in Project 2, Airflow will wait for this file to know
    # the day's load is complete.
    s3.put_object(
        Bucket=bucket,
        Key=f"{prefix}/_manifest.json",
        Body=json.dumps(manifest, indent=2).encode(),
        ContentType="application/json",
    )
    logger.info(json.dumps({"event": "run_complete", **{k: v for k, v in manifest.items() if k != "keys"}}))
    return manifest


def lambda_handler(event, context):
    import boto3  # available in the Lambda runtime; imported here so tests don't need AWS

    tickers = [t.strip().upper() for t in os.environ["WATCHLIST"].split(",") if t.strip()]
    manifest = run(
        filing_date=resolve_filing_date(event),
        tickers=tickers,
        client=EdgarClient(os.environ["SEC_USER_AGENT"]),
        s3=boto3.client("s3"),
        bucket=os.environ["BUCKET_NAME"],
    )
    return {"filing_date": manifest["filing_date"], "files_written": manifest["files_written"]}
