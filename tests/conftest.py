import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))
sys.path.insert(0, str(ROOT / "scripts"))

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def submissions():
    return json.loads((FIXTURES / "submissions_sample.json").read_text())

@pytest.fixture
def form4_xml():
    return (FIXTURES / "form4_sample.xml").read_bytes()

