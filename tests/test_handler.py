import json
from datetime import date

import pytest

from handler import partition_prefix, resolve_filing_date, run
from scripts.peek_form4 import parse_form4


class FakeEdgar:
    """Stands in for EdgarClient so tests never touch the network."""

    def __init__(self, submissions):
        self.submissions = submissions

    def get_json(self, url):
        if url.endswith("company_tickers.json"):
            return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        return self.submissions

    def get_bytes(self, url):
        return b"<ownershipDocument/>"


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body


def test_default_date_is_yesterday():
    assert resolve_filing_date({}, today=date(2026, 10, 17)) == "2026-10-16"


def test_backfill_date_from_event():
    assert resolve_filing_date({"filing_date": "2026-10-01"}) == "2026-10-01"


def test_bad_backfill_date_raises():
    with pytest.raises(ValueError):
        resolve_filing_date({"filing_date": "10/01/2026"})


def test_run_writes_partitioned_files_and_manifest(submissions):
    s3 = FakeS3()
    manifest = run("2026-10-16", ["AAPL", "NOTREAL"], FakeEdgar(submissions), s3, "bucket")

    prefix = partition_prefix("2026-10-16")
    assert f"{prefix}/ticker=AAPL/0000320193-26-000101.xml" in s3.objects
    assert manifest["files_written"] == 2
    assert manifest["tickers_unknown"] == ["NOTREAL"]
    assert json.loads(s3.objects[f"{prefix}/_manifest.json"])["files_written"] == 2


def test_manifest_written_even_when_no_filings(submissions):
    s3 = FakeS3()
    run("2026-01-01", ["AAPL"], FakeEdgar(submissions), s3, "bucket")
    assert list(s3.objects) == [f"{partition_prefix('2026-01-01')}/_manifest.json"]


def test_parse_form4_reads_trades(form4_xml):
    trades = parse_form4(form4_xml)
    assert [t["code"] for t in trades] == ["S", "P"]
    assert trades[0]["shares"] == 10000 and trades[0]["price"] == 250.5
    assert trades[0]["title"] == "Chief Example Officer"
