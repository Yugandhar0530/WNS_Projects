"""OCR, LLM field extraction, and OpenCV bounding-box drawing for invoices."""

from __future__ import annotations

import difflib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pytesseract
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

_WINDOWS_TESS_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def configure_tesseract(explicit_path: str | None = None) -> str | None:
    candidates: list[str] = []
    if explicit_path:
        candidates.append(explicit_path.strip())
    env = os.getenv("TESSERACT_PATH")
    if env:
        candidates.append(env.strip())
    candidates.extend(_WINDOWS_TESS_CANDIDATES)

    for path in candidates:
        if path and os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return path

    try:
        pytesseract.get_tesseract_version()
        return "tesseract"
    except pytesseract.TesseractNotFoundError:
        return None


def tesseract_install_hint() -> str:
    return (
        "Install Tesseract OCR for Windows:\n"
        "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
        "Then set in PowerShell before streamlit run:\n"
        '$env:TESSERACT_PATH = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"'
    )

SECTION_COLORS: Dict[str, Tuple[int, int, int]] = {
    "header": (0, 180, 255),
    "financial": (0, 200, 0),
    "party": (255, 120, 0),
    "reference": (200, 0, 200),
    "other": (180, 180, 0),
}
TABLE_OUTLINE_BGR = (255, 0, 255)

_AMOUNT_2DP_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})*|\d+)\.\d{2}\b")
_GSTIN_RE = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)
_TOTAL_KEY_HINTS = (
    "grand total",
    "invoice total",
    "total amount",
    "amount payable",
    "net amount",
    "total payable",
)


def _parse_amount_string(raw: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


_WORD_NUMS: Dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_WORDS_IN_AMOUNT_RE = re.compile(
    r"(?i)(?:amount|total)\s+in\s+words|(?:say|in\s+words)\s*[:\-]",
)
_TABLE_ROW_HINT = re.compile(
    r"(?i)\b(qty|quantity|sku|item|description|hsn|sac|unit|rate|price|part)\b",
)
_TABLE_ROW_SKIP = re.compile(
    r"(?i)\b(total\s*taxable|taxable\s*value|total\s*cgst|total\s*sgst|total\s*igst|"
    r"invoice\s*value|grand\s*total|sub\s*total|round\s*off|amount\s*in\s*words)\b",
)
_LABELED_TOTAL_RE = re.compile(
    r"(?i)(?:grand\s*total|invoice\s*(?:total|value)|total\s*(?:amount|due)|"
    r"amount\s*(?:due|payable)|balance\s*due|net\s*(?:amount|payable)|total\s*payable)"
    r"[\s:]*(?:[$€£]?\s*)?(?:rs\.?|inr\.?|usd\.?|eur\.?)?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?",
)
_INVOICE_NO_LINE_RE = re.compile(
    r"(?i)invoice\s*(?:no|number|#)\.?\s*[:\s]*(.*)$",
)
_INVOICE_PLACEHOLDERS = frozenset(
    {"inv", "invoice", "tax", "na", "n/a", "doc", "document", "bill", "supply"}
)


def _parse_amount_in_words(ocr_text: str) -> Optional[float]:
    """Parse common English number phrases from any 'amount/total in words' line."""
    for line in ocr_text.splitlines():
        if not _WORDS_IN_AMOUNT_RE.search(line):
            continue
        phrase = _WORDS_IN_AMOUNT_RE.split(line, maxsplit=1)[-1].lower()
        paise = 0.0
        paise_match = re.search(r"(?i)\b(\w+)\s+paise\b", phrase)
        if paise_match:
            pval = _WORD_NUMS.get(paise_match.group(1).lower())
            if pval is not None:
                paise = pval / 100.0
            phrase = phrase[: paise_match.start()]
        phrase = re.sub(
            r"\b(rupees?|inr|dollars?|usd|euros?|eur|pounds?|gbp|ps|and|only)\b",
            " ",
            phrase,
        )
        words = [w for w in re.split(r"\s+", phrase.strip()) if w]
        current = 0
        for word in words:
            if word in ("lakh", "lakhs"):
                current = (current or 1) * 100_000
            elif word in ("crore", "crores"):
                current = (current or 1) * 10_000_000
            elif word in ("thousand", "thousands"):
                current = (current or 1) * 1000
            elif word in ("hundred", "hundreds"):
                current = (current or 1) * 100
            elif word in _WORD_NUMS:
                current += _WORD_NUMS[word]
            elif word.isdigit():
                current += int(word)
        amount = float(current) + paise
        if amount > 0:
            return amount
    return None


def _table_section_end(lines: List[str]) -> int:
    for idx, line in enumerate(lines):
        if _WORDS_IN_AMOUNT_RE.search(line):
            return idx
        if re.search(r"(?i)\bterms\s*&?\s*conditions\b", line):
            return idx
    return len(lines)


def _looks_like_table_row(line: str) -> bool:
    if _TABLE_ROW_SKIP.search(line):
        return False
    if not re.search(r"[A-Za-z]{3,}", line):
        return False
    amounts = list(_AMOUNT_2DP_RE.finditer(line))
    if len(amounts) < 1:
        return False
    if _TABLE_ROW_HINT.search(line):
        return True
    if re.match(r"^\s*\d+[\s.)|:\-]", line):
        return True
    return len(amounts) >= 2


def _sum_table_row_totals(ocr_text: str) -> Tuple[Optional[float], int]:
    """Sum trailing column totals on lines that look like item rows (any vendor layout)."""
    lines = ocr_text.splitlines()
    end = _table_section_end(lines)
    subtotal = 0.0
    rows = 0
    for line in lines[:end]:
        if not _looks_like_table_row(line):
            continue
        amounts = [m.group(0) for m in _AMOUNT_2DP_RE.finditer(line)]
        value = _parse_amount_string(amounts[-1])
        if value is None or value > 5_000_000:
            continue
        subtotal += value
        rows += 1
    return (subtotal if rows else None, rows)


def _labeled_total_from_ocr(ocr_text: str) -> Optional[str]:
    match = _LABELED_TOTAL_RE.search(ocr_text)
    if match:
        raw = match.group(1).replace(",", "")
        if "." not in raw:
            return f"{raw}.00"
        return raw if re.search(r"\.\d{2}$", raw) else f"{float(raw):.2f}"
    for line in reversed(ocr_text.splitlines()):
        if not re.search(r"(?i)\b(invoice\s*value|grand\s*total|total\s*due)\b", line):
            continue
        if _TABLE_ROW_SKIP.search(line):
            continue
        amounts = [m.group(0).replace(",", "") for m in _AMOUNT_2DP_RE.finditer(line)]
        if amounts and len(line) < 160:
            return amounts[-1]
    return None


def _totals_agree(a: float, b: float, pct: float = 0.02) -> bool:
    return abs(a - b) <= max(1.0, abs(b) * pct)


def _resolve_invoice_total(ocr_text: str) -> Optional[str]:
    """Document-level total: words line is the anchor; labels/rows must agree."""
    labeled = _labeled_total_from_ocr(ocr_text)
    labeled_num = _parse_amount_string(labeled) if labeled else None
    words_num = _parse_amount_in_words(ocr_text)
    summed, row_count = _sum_table_row_totals(ocr_text)

    def fmt(value: float) -> str:
        return f"{value:.2f}"

    if words_num is not None:
        if summed is not None and row_count >= 2 and _totals_agree(summed, words_num):
            return fmt(summed)
        if labeled_num is not None and _totals_agree(labeled_num, words_num):
            return fmt(labeled_num)
        return fmt(words_num)

    if labeled_num is not None:
        return fmt(labeled_num)

    if summed is not None and row_count >= 1:
        return fmt(summed)
    return None


def _find_total_field_key(fields: Dict[str, Any]) -> Optional[str]:
    for key in fields:
        normalized = key.lower().replace("_", " ").replace("-", " ")
        if any(hint in normalized for hint in _TOTAL_KEY_HINTS):
            return key
        if normalized in ("total", "grandtotal"):
            return key
    return None


def _should_replace_total(
    llm_value: float,
    resolved_value: float,
    llm_raw: str,
    ocr_text: str,
) -> bool:
    if abs(llm_value - resolved_value) < 0.01:
        return False
    words_amount = _parse_amount_in_words(ocr_text)
    if words_amount is not None and abs(resolved_value - words_amount) <= 1.0:
        return abs(llm_value - words_amount) > 0.5
    if "." not in llm_raw and resolved_value > 0 and llm_value > resolved_value * 20:
        return True
    if resolved_value > 0 and llm_value > resolved_value * 100:
        return True
    return False


def _heuristic_gstin(ocr_text: str) -> Optional[str]:
    for line in ocr_text.splitlines():
        if re.search(r"(?i)fssai", line):
            continue
        if not re.search(r"(?i)\bgstin\b", line):
            continue
        for match in _GSTIN_RE.finditer(line):
            return match.group(0).upper()
        compact = re.sub(r"[^A-Z0-9]", "", line.upper())
        loose = re.search(r"GSTIN([0-9]{2}[A-Z0-9]{13})", compact)
        if loose:
            return loose.group(1)[:15]
    for match in _GSTIN_RE.finditer(ocr_text):
        return match.group(0).upper()
    return None


def _heuristic_fssai(ocr_text: str) -> Optional[str]:
    match = re.search(
        r"(?i)fssai\s*l?\s*(?:lic\.?|license)?\s*(?:number|no\.?)?\s*[:.\s-]*(\d{14,17})",
        ocr_text,
    )
    return match.group(1) if match else None


def _valid_gstin_value(value: str) -> bool:
    compact = re.sub(r"\s+", "", value.upper())
    if _GSTIN_RE.search(compact):
        return True
    return bool(re.fullmatch(r"[0-9]{2}[A-Z0-9]{13}", compact))


def _looks_like_money_id(value: str) -> bool:
    parsed = _parse_amount_string(value)
    return parsed is not None and "." in value and len(value) <= 12


def _heuristic_invoice_number(ocr_text: str) -> Optional[str]:
    for line in ocr_text.splitlines():
        match = _INVOICE_NO_LINE_RE.search(line)
        if not match:
            continue
        tail = re.split(
            r"(?i)\b(place\s+of|date|category|state|order|gstin)\b",
            match.group(1),
            maxsplit=1,
        )[0]
        candidate = re.sub(r"[^A-Z0-9]", "", tail.upper())
        if len(candidate) >= 6 and candidate.lower() not in _INVOICE_PLACEHOLDERS:
            return candidate
    return None


def _normalize_field_names_and_values(
    fields: Dict[str, Any],
    ocr_text: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(fields)
    gstin_canonical = _heuristic_gstin(ocr_text)

    for key in list(out.keys()):
        value = str(out.get(key, "")).strip()
        if not value or value.lower() in ("not available", "n/a", "na"):
            out.pop(key, None)
            continue

        norm_key = key.lower().replace("_", " ").replace("-", " ")

        if ("amount" in norm_key and "due" in norm_key) or (
            "amount" in norm_key and "payable" in norm_key
        ):
            if not re.search(r"\d", value) and re.search(r"[a-z]", value, re.IGNORECASE):
                out.setdefault("Amount In Words", value)
                out.pop(key, None)
                continue

        if any(t in norm_key for t in ("gstin", "tax id", "vat", "tin")) and "food" not in norm_key:
            if not _valid_gstin_value(value) or _looks_like_money_id(value):
                if gstin_canonical:
                    out[key] = gstin_canonical
                else:
                    out.pop(key, None)

        if len(value) <= 2 and any(
            t in norm_key for t in ("reg", "tax", "company", "cin", "pan")
        ):
            out.pop(key, None)

    if gstin_canonical:
        if not _find_gstin_field_key(out):
            out["GSTIN"] = gstin_canonical
        seen_gstin = gstin_canonical.upper()
        for key in list(out.keys()):
            nk = key.lower()
            if nk in ("tax id", "taxid", "company reg", "companyreg") and str(out[key]).upper() == seen_gstin:
                out.pop(key, None)

    inv = _heuristic_invoice_number(ocr_text)
    inv_key = _find_invoice_number_key(out)
    if inv_key and inv:
        current = _normalize_invoice_number(str(out.get(inv_key, "")))
        ocr_inv = _normalize_invoice_number(inv)
        if (
            current.lower() in _INVOICE_PLACEHOLDERS
            or len(ocr_inv) > len(current)
            or (ocr_inv.startswith(current) and len(ocr_inv) > len(current))
        ):
            out[inv_key] = ocr_inv
    elif inv:
        out.setdefault("Invoice Number", _normalize_invoice_number(inv))

    food_key = _find_field_key(out, "food") or _find_field_key(out, "fssai")
    fssai = _heuristic_fssai(ocr_text)
    if fssai and food_key is None:
        out.setdefault("FSSAI License", fssai)
    elif fssai and food_key:
        val = str(out.get(food_key, "")).strip().lower()
        if not val or val in ("not available", "n/a"):
            out[food_key] = fssai

    return out


def _find_gstin_field_key(fields: Dict[str, Any]) -> Optional[str]:
    for key in fields:
        if "gstin" in key.lower().replace("_", " ").replace("-", " "):
            return key
    return None


def _looks_like_fssai(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return len(digits) == 14 and digits.isdigit()


_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_CIN_RE = re.compile(
    r"\b[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b",
    re.IGNORECASE,
)


def _heuristic_pan(ocr_text: str) -> Optional[str]:
    for line in ocr_text.splitlines():
        if not re.search(r"(?i)\bpan\b", line):
            continue
        match = _PAN_RE.search(line.upper())
        if match:
            return match.group(0).upper()
    match = _PAN_RE.search(ocr_text.upper())
    return match.group(0).upper() if match else None


def _heuristic_cin(ocr_text: str) -> Optional[str]:
    for line in ocr_text.splitlines():
        if not re.search(r"(?i)\bcin\b", line):
            continue
        match = _CIN_RE.search(line.upper().replace(" ", ""))
        if match:
            return match.group(0).upper()
    match = _CIN_RE.search(re.sub(r"\s+", "", ocr_text.upper()))
    return match.group(0).upper() if match else None


def _find_field_key(fields: Dict[str, Any], needle: str) -> Optional[str]:
    for key in fields:
        if needle in key.lower().replace("_", " ").replace("-", " "):
            return key
    return None


def _find_invoice_number_key(fields: Dict[str, Any]) -> Optional[str]:
    for key in fields:
        nk = key.lower().replace("_", " ").replace("-", " ")
        if "invoice" in nk and "date" not in nk and "order" not in nk and "value" not in nk:
            return key
    return None


def _normalize_invoice_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


_JUNK_VALUE_TITLE_RE = re.compile(
    r"(?i)^(?:tax\s+)?invoice(?:\s*/\s*bill\s+of\s+supply)?$|^bill\s+of\s+supply$",
)


def _is_junk_field(key: str, value: str) -> bool:
    nk = key.lower().replace("_", " ").replace("-", " ").strip()
    if re.search(r"(?i)^(tax\s*invoice|document\s*type|doc\s*type)$", nk):
        return True
    if _JUNK_VALUE_TITLE_RE.match(value.strip()):
        return True
    if len(value) > 200 and "invoice" in value.lower() and "/" in value:
        return True
    return False


def _strip_license_from_address(text: str, license_digits: Optional[str]) -> str:
    cleaned = re.sub(r"(?i)fssai\s*l?\s*[:.\s]*\d{14,17}", "", text)
    cleaned = re.sub(r"(?i)essai\s*lic\.?\s*no\.?\s*[:.\s]*\d{14,17}", "", cleaned)
    if license_digits:
        cleaned = cleaned.replace(license_digits, "")
    return re.sub(r"\s{2,}|,\s*,", " ", cleaned).strip(" ,;")


def _is_implausible_table_integer(value: str) -> bool:
    if re.search(r"\.\d", value):
        return False
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 5 and digits.isdigit()


def _consolidate_gstin_keys(out: Dict[str, Any]) -> None:
    canonical: Optional[str] = None
    for key, raw in list(out.items()):
        if "gstin" not in key.lower().replace("_", " "):
            continue
        val = str(raw).strip().upper()
        if _valid_gstin_value(val):
            canonical = re.sub(r"\s+", "", val)
    if not canonical:
        return
    out["GSTIN"] = canonical
    for key in list(out.keys()):
        nk = key.lower().replace("_", " ")
        if "gstin" in nk and key != "GSTIN":
            out.pop(key, None)


def _polish_extracted_fields(out: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
    fssai = _heuristic_fssai(ocr_text)
    inv_ocr = _heuristic_invoice_number(ocr_text)
    total_key = _find_total_field_key(out)
    grand_str = (
        str(out[total_key]).strip()
        if total_key
        else (_resolve_invoice_total(ocr_text) or "")
    )
    grand_num = _parse_amount_string(grand_str)

    for key in list(out.keys()):
        value = str(out.get(key, "")).strip()
        nk = key.lower().replace("_", " ").replace("-", " ")

        if _is_junk_field(key, value):
            out.pop(key, None)
            continue

        if any(word in nk for word in ("quantity", "taxable", "mrp")):
            if _is_implausible_table_integer(value):
                out.pop(key, None)
                continue

        if "address" in nk or "bill to" in nk or "ship to" in nk:
            out[key] = _strip_license_from_address(value, fssai)

        if ("amount" in nk and "due" in nk) and re.search(r"\d", value):
            due_num = _parse_amount_string(value)
            if grand_num is not None and due_num is not None and abs(due_num - grand_num) > 0.5:
                out[key] = f"{grand_num:.2f}"

    inv_key = _find_invoice_number_key(out)
    if inv_ocr and inv_key:
        cur = _normalize_invoice_number(str(out[inv_key]))
        ocr_n = _normalize_invoice_number(inv_ocr)
        if len(ocr_n) >= len(cur) and (len(ocr_n) > len(cur) or not re.search(r"[A-Z]", cur)):
            out[inv_key] = ocr_n

    _consolidate_gstin_keys(out)

    if fssai:
        lic_key = _find_field_key(out, "fssai") or _find_field_key(out, "food")
        if lic_key:
            out[lic_key] = fssai
        else:
            out.setdefault("FSSAI License", fssai)

    return out


def refine_extracted_fields(fields: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
    out = _normalize_field_names_and_values(fields, ocr_text)

    resolved_total = _resolve_invoice_total(ocr_text)
    if resolved_total:
        total_key = _find_total_field_key(out)
        if total_key is None:
            out["Grand Total"] = resolved_total
        else:
            llm_raw = str(out.get(total_key, "")).strip()
            llm_num = _parse_amount_string(llm_raw)
            res_num = _parse_amount_string(resolved_total)
            if res_num is not None and (
                llm_num is None
                or _should_replace_total(llm_num, res_num, llm_raw, ocr_text)
            ):
                out[total_key] = resolved_total

    gstin = _heuristic_gstin(ocr_text)
    gstin_key = _find_gstin_field_key(out)
    fssai = _heuristic_fssai(ocr_text)
    if gstin_key:
        current = str(out.get(gstin_key, "")).strip()
        if gstin and (_looks_like_fssai(current) or current.upper() != gstin):
            out[gstin_key] = gstin
        elif _looks_like_fssai(current) and fssai:
            if gstin:
                out[gstin_key] = gstin
            else:
                out.pop(gstin_key, None)
                out.setdefault("FSSAI License", fssai)
    elif gstin:
        out["GSTIN"] = gstin

    if fssai and not any("fssai" in k.lower() for k in out):
        out["FSSAI License"] = fssai

    pan = _heuristic_pan(ocr_text)
    cin = _heuristic_cin(ocr_text)
    pan_key = _find_field_key(out, "pan")
    if pan_key and pan:
        current_pan = str(out.get(pan_key, "")).strip().upper()
        if _CIN_RE.search(current_pan.replace(" ", "")) or current_pan != pan:
            out[pan_key] = pan
    elif pan:
        out["PAN"] = pan

    if cin:
        cin_key = _find_field_key(out, "cin")
        if cin_key:
            out[cin_key] = cin
        else:
            out.setdefault("CIN", cin)

    return _polish_extracted_fields(out, ocr_text)


def classify_field_label(label: str) -> str:
    """Map LLM field names to a colour bucket."""
    key = label.lower()
    if any(w in key for w in ("total", "tax", "amount", "balance", "due", "subtotal", "price")):
        return "financial"
    if any(w in key for w in ("address", "vendor", "customer", "bill to", "ship to", "supplier", "client")):
        return "party"
    if any(w in key for w in ("invoice", "po", "order", "reference", "id", "number", "date", "due date")):
        return "header" if "date" in key or "due" in key else "reference"
    return "other"


def build_ocr_word_map(
    preprocessed_gray: np.ndarray,
    min_confidence: int = 35,
) -> Tuple[str, List[Dict[str, Any]]]:
    data = pytesseract.image_to_data(
        preprocessed_gray,
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )
    parts: List[str] = []
    word_map: List[Dict[str, Any]] = []

    for i, conf in enumerate(data["conf"]):
        if int(conf) < min_confidence:
            continue
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        parts.append(text)
        word_map.append(
            {
                "text": text,
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
            }
        )

    full_text = pytesseract.image_to_string(preprocessed_gray, config="--psm 6")
    return full_text, word_map


def extract_invoice_fields(ocr_text: str, model_name: str) -> Dict[str, Any]:
    llm = ChatOllama(model=model_name, temperature=0, format="json")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You analyze invoice OCR text. Return ONE flat JSON object of important fields.

Rules:
- Keys: short human-readable names (e.g. "Invoice Number", "Grand Total", "Vendor Name").
- Values: strings only (no nested objects or arrays in this JSON).
- Include header IDs, dates, parties, tax IDs, and money fields when present.
- Skip boilerplate ("Page 1", long terms and conditions).
- Do NOT invent values missing from the text.
- Grand Total / Amount Due = final payable total for the whole document (including all
  line items, fees, and tax), not a single line MRP, qty, SKU, or intermediate subtotal.
- If both a numeric total and "amount/total in words" exist, they must agree; prefer
  the final document total over a single table row.
- Put each ID on the correct label (tax ID vs company reg. vs food license, etc.).
- Do NOT return document titles, column headers, or line-item table values as top-level
  fields (Quantity, TaxableAmount, Description blocks, "TAX INVOICE" text).
- Prefer one GSTIN key; put food license numbers only under FSSAI / Food License.
                """.strip(),
            ),
            ("user", "OCR text:\n{text}"),
        ]
    )
    chain = prompt | llm
    try:
        response = chain.invoke({"text": ocr_text})
        payload = json.loads(response.content)
        if not isinstance(payload, dict):
            return {}
        return refine_extracted_fields(payload, ocr_text)
    except Exception:
        return {}


def _fuzzy_match_value_on_page(
    word_map: List[Dict[str, Any]],
    value: str,
    first_word_threshold: float = 0.82,
    next_word_threshold: float = 0.62,
) -> Optional[Tuple[int, int, int, int]]:
    tokens = value.split()
    if not tokens:
        return None

    for i, word in enumerate(word_map):
        if difflib.SequenceMatcher(None, word["text"], tokens[0]).ratio() < first_word_threshold:
            continue

        x1, y1 = word["x"], word["y"]
        x2, y2 = x1 + word["w"], y1 + word["h"]
        idx = i
        ok = True
        for token in tokens[1:]:
            idx += 1
            if idx >= len(word_map):
                ok = False
                break
            nxt = word_map[idx]
            if difflib.SequenceMatcher(None, nxt["text"], token).ratio() < next_word_threshold:
                ok = False
                break
            x2 = max(x2, nxt["x"] + nxt["w"])
            y2 = max(y2, nxt["y"] + nxt["h"])

        if ok:
            return x1, y1, x2, y2
    return None


def _amount_search_strings(value: str) -> List[str]:
    out = [value.strip()]
    num = _parse_amount_string(value)
    if num is not None:
        out.append(f"{num:.2f}")
        out.append(f"{num:g}")
        if num == int(num):
            out.append(str(int(num)))
    seen: List[str] = []
    for s in out:
        if s and s not in seen:
            seen.append(s)
    return seen


def _merge_word_boxes(words: List[Dict[str, Any]]) -> Tuple[int, int, int, int]:
    x1 = min(w["x"] for w in words)
    y1 = min(w["y"] for w in words)
    x2 = max(w["x"] + w["w"] for w in words)
    y2 = max(w["y"] + w["h"] for w in words)
    return x1, y1, x2, y2


def _locate_field_on_page(
    word_map: List[Dict[str, Any]],
    label: str,
    value: str,
) -> Optional[Tuple[int, int, int, int]]:
    lk = label.lower().replace("_", " ").replace("-", " ")

    if any(k in lk for k in ("total", "amount due", "grand", "payable")):
        for candidate in _amount_search_strings(value):
            box = _fuzzy_match_value_on_page(
                word_map, candidate, first_word_threshold=0.85, next_word_threshold=0.75
            )
            if box:
                return box
        return None

    if "address" in lk:
        head = " ".join(value.split()[:4])
        box = _fuzzy_match_value_on_page(
            word_map, head, first_word_threshold=0.72, next_word_threshold=0.55
        )
        if box:
            return box
        return None

    if "invoice" in lk and "number" in lk:
        compact = re.sub(r"[^A-Z0-9]", "", value.upper())
        chunks = re.findall(r"[A-Z0-9]{5,}", value.upper()) or [compact]
        for chunk in chunks:
            hits = [
                w
                for w in word_map
                if difflib.SequenceMatcher(
                    None, re.sub(r"[^A-Z0-9]", "", w["text"].upper()), chunk
                ).ratio()
                >= 0.82
            ]
            if hits:
                return _merge_word_boxes(hits)
        return _fuzzy_match_value_on_page(
            word_map, value, first_word_threshold=0.75, next_word_threshold=0.6
        )

    box = _fuzzy_match_value_on_page(word_map, value)
    if box:
        return box

    if len(value) > 20:
        head = " ".join(value.split()[:3])
        return _fuzzy_match_value_on_page(
            word_map, head, first_word_threshold=0.75, next_word_threshold=0.55
        )
    return None


def detect_line_items_table_bbox(gray: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    inv = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 8
    )
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min(gray.shape[1] // 4, 80), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min(gray.shape[0] // 4, 80)))
    horizontal = cv2.morphologyEx(inv, cv2.MORPH_OPEN, h_kernel, iterations=2)
    vertical = cv2.morphologyEx(inv, cv2.MORPH_OPEN, v_kernel, iterations=2)
    grid = cv2.bitwise_or(horizontal, vertical)
    grid = cv2.dilate(grid, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = gray.shape[0] * gray.shape[1]
    best: Optional[Tuple[int, int, int, int, float]] = None

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        if area < img_area * 0.05 or area > img_area * 0.85:
            continue
        aspect = w / float(h) if h else 0
        if aspect < 1.2 or h < 40:
            continue
        if best is None or area > best[4]:
            best = (x, y, x + w, y + h, float(area))

    if best is None:
        return None
    return best[0], best[1], best[2], best[3]


def _put_section_label(
    canvas: np.ndarray,
    text: str,
    x: int,
    y: int,
    color_bgr: Tuple[int, int, int],
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 0.45, 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    y_top = max(th + 4, y - 6)
    cv2.rectangle(canvas, (x, y_top - th - 4), (x + tw + 4, y_top), color_bgr, -1)
    cv2.putText(canvas, text, (x + 2, y_top - 3), font, scale, (255, 255, 255), thickness)


def annotate_invoice(
    bgr: np.ndarray,
    word_map: List[Dict[str, Any]],
    extracted: Dict[str, Any],
    draw_table: bool = True,
) -> Tuple[np.ndarray, List[str]]:
    overlay = bgr.copy()
    mapped_labels: List[str] = []

    if draw_table:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        table_box = detect_line_items_table_bbox(gray)
        if table_box:
            tx1, ty1, tx2, ty2 = table_box
            cv2.rectangle(overlay, (tx1, ty1), (tx2, ty2), TABLE_OUTLINE_BGR, 3)
            _put_section_label(overlay, "Line items table", tx1, ty1, TABLE_OUTLINE_BGR)
            mapped_labels.append("Line items table")

    for label, raw_value in extracted.items():
        if raw_value is None:
            continue
        if isinstance(raw_value, (list, dict)):
            continue
        value = str(raw_value).strip()
        if not value:
            continue

        box = _locate_field_on_page(word_map, label, value)
        if not box:
            continue

        section = classify_field_label(label)
        color = SECTION_COLORS.get(section, SECTION_COLORS["other"])
        x1, y1, x2, y2 = box
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
        _put_section_label(overlay, label, x1, y1, color)
        mapped_labels.append(label)

    return overlay, mapped_labels


def preprocess_for_ocr(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
