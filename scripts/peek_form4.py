"""Print the trades inside a Form 4 xml file to see what was collected """
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

CODES = {
    "P": "BUY (open market)",
    "S": "SELL (open market)" ,
    "M" : "option exercise",
    "A": "grant/award",
    "F": "tax withholding",
    "G": "gift",
}

def _text(node, path: str) -> str | None:
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None

def parse_form4(xml_bytes: bytes)-> list[dict]:
    root = ET.fromstring(xml_bytes)
    base = {
        "ticker": _text(root, "issuer/issuerTradingSymbol"),
        "insider": _text(root, "reportingOwner/reportingOwnerId/rptOwnerName"),
        "title": _text(root, "reportingOwner/reportingOwnerRelationship/officerTitle")
        or (
            "Director"
            if _text(root, "reportingOwner/reportingOwnerRelationship/isDirector") in ("1", "True")
            else None
        ),
    }
    trades = []
    for tx in root.iter("nonDerivativeTransaction"):
        shares = _text(tx, "transactionAmounts/transactionShares/value")
        price = _text(tx, "transactionAmounts/transactionPricePerShare/value")
        trades.append(
            {
                **base,
                "date": _text(tx, "transactionDate/value"),
                "code": _text(tx, "transactionCoding/transactionCode"),
                "shares": float(shares) if shares else None,
                "price": float(price) if price else None,
                
            }
        )
    return trades

def main(paths: list[str]) -> None:
    for path in paths:
        with open(path, "rb") as f:
            for t in parse_form4(f.read):
                value = t["shares"] * t["price"] if t["shares"] and t["price"] else 0
                label = CODES.get(t["code"],t["code"])
                print(
                    f"{t['date']} {t['ticker']:<6} {t['insider']:<28} {label:<20}"
                    f"{t['shares'] or 0:>12,.0f} sh @ ${t['price'] or 0:>9,.2f}  = ${value:>14,.0f}"
                )

if __name__ == "__main__":
    main(sys.argv[1:])