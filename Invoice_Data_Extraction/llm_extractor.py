from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

SUPPORTED_MODELS = ("llama3.2", "llama3", "mistral")

INVOICE_FIELDS = (
    "invoice_number",
    "date",
    "vendor_name",
    "vendor_address",
    "currency",
    "total_amount",
    "subtotal",
    "tax_amount",
    "items",
)


def strip_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: strip_empty(v)
            for k, v in value.items()
            if v is not None and v != "" and v != []
        }
    if isinstance(value, list):
        return [strip_empty(v) for v in value if v is not None]
    return value


def reconcile_currency(ocr_text: str, payload: dict[str, Any]) -> dict[str, Any]:
    lower = ocr_text.lower()
    has_dollar = "$" in ocr_text or "usd" in lower
    has_euro = "€" in ocr_text or re.search(r"\beur\b", lower)

    if not has_dollar and not has_euro:
        return payload

    if has_dollar and not has_euro:
        payload["currency"] = "USD"
    elif has_euro and not has_dollar:
        payload["currency"] = "EUR"
    return payload


def build_extractor(model: str) -> ChatOllama:
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model: {model}")
    return ChatOllama(model=model, temperature=0, format="json")


def extract_invoice_fields(
    ocr_text: str,
    model: str,
    rule_hints: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    llm = build_extractor(model)
    hints_block = json.dumps(rule_hints or {}, indent=2)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You extract invoice data into JSON. Use only information present in the OCR text.
Do not invent values. If a field is missing, omit it or use null.
Normalize dates to YYYY-MM-DD when possible.
Items is a list of objects with description, quantity, unit_price, total_price when available.
For currency: use ISO codes only when supported by the OCR text ($ or USD means USD; € or EUR means EUR). Never substitute EUR when the document shows dollars.
Rule-based hints may be correct but must be verified against the OCR text; discard hints that conflict.
""".strip(),
            ),
            (
                "user",
                "Rule-based hints (verify against OCR):\n{hints}\n\nOCR text:\n{text}",
            ),
        ]
    )

    chain = prompt | llm
    try:
        response = chain.invoke({"text": ocr_text, "hints": hints_block})
        parsed = json.loads(response.content)
        cleaned = strip_empty(parsed) or {}
        if isinstance(cleaned, dict):
            cleaned = reconcile_currency(ocr_text, cleaned)
        return cleaned
    except Exception:
        return None