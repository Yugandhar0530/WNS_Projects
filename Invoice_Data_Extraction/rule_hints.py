from __future__ import annotations

import re
from typing import Any

INVOICE_NO_PATTERNS = (
    r"(?i)invoice\s*(?:#|no\.?|number)\s*[:.]?\s*([A-Z0-9][\w\-/]*)",
    r"(?i)\b(?:inv|invoice)\s*[-#]?\s*([A-Z0-9][\w\-/]{2,})",
)

DATE_PATTERNS = (
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"(?i)\b(?:date|issued)\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
)

TOTAL_PATTERNS = (
    r"(?i)(?:total|amount\s+due|balance\s+due|grand\s+total)\s*[:.]?\s*\$?\s*([\d,]+\.?\d*)",
    r"(?i)\btotal\b[^\d]{0,20}\$?\s*([\d,]+\.?\d*)",
)

CURRENCY_PATTERN = r"(?i)\b(USD|EUR|GBP|INR|AUD|CAD)\b|(?<!\w)(\$|€|£|₹)(?!\w)"

VENDOR_LINE_PATTERN = re.compile(
    r"^[\w\s&.,'-]{3,80}$",
    re.MULTILINE,
)


def _first_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _guess_vendor(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:8]:
        lower = line.lower()
        if "invoice" in lower or "bill to" in lower or "tax" in lower:
            continue
        if VENDOR_LINE_PATTERN.fullmatch(line) and len(line.split()) <= 8:
            return line
    return None


def derive_rule_hints(ocr_text: str) -> dict[str, Any]:
    if not ocr_text.strip():
        return {}

    hints: dict[str, Any] = {}
    invoice_no = _first_match(ocr_text, INVOICE_NO_PATTERNS)
    if invoice_no:
        hints["invoice_number"] = invoice_no

    date_val = _first_match(ocr_text, DATE_PATTERNS)
    if date_val:
        hints["date"] = date_val

    total_val = _first_match(ocr_text, TOTAL_PATTERNS)
    if total_val:
        hints["total_amount"] = total_val.replace(",", "")

    currency_match = re.search(CURRENCY_PATTERN, ocr_text)
    if currency_match:
        token = currency_match.group(1) or currency_match.group(2)
        symbol_map = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
        hints["currency"] = symbol_map.get(token, token.upper())

    vendor = _guess_vendor(ocr_text)
    if vendor:
        hints["vendor_name"] = vendor

    return hints