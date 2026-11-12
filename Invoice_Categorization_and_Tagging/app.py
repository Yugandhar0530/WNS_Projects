import html
import json
import os
import re

import cv2
import fitz
import numpy as np
import pytesseract
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

TESSERACT_PATH = os.getenv("TESSERACT_PATH")
if TESSERACT_PATH and os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

st.set_page_config(
    page_title="Invoice Categorization & Tagging",
    page_icon="📄",
    layout="wide",
)

DEFAULT_DEPARTMENTS = "IT, HR, Finance, Marketing, Operations, Sales, Legal, Engineering"
DEFAULT_CATEGORIES = (
    "Software Subscription, Hardware, Travel, Meals, Office Supplies, "
    "Utilities, Consulting, Advertising, Training, Facilities"
)


def preprocess_for_ocr(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]


def read_uploaded_invoice(uploaded_file):
    combined_text = ""
    preview = None
    page_images = []

    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        first_pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
        preview = cv2.imdecode(
            np.frombuffer(first_pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR
        )
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
            page_images.append(img)
    else:
        raw = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        preview = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        page_images.append(preview)

    with st.spinner("Extracting text from document..."):
        for img in page_images:
            combined_text += pytesseract.image_to_string(preprocess_for_ocr(img)) + "\n"

    return combined_text.strip(), preview


def categorize_with_llm(ocr_text, department_list, category_list, model_id):
    llm = ChatOllama(model=model_id, temperature=0, format="json")

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are a financial operations assistant. Parse invoice text and return accounting metadata.

Pick values only from these lists:
- Departments: {departments}
- Categories: {categories}

Extract merchant, date (YYYY-MM-DD), and total when present.
For total use the numeric invoice amount only (e.g. 334.20), never amount-in-words text.
Assign the best-matching department and expense category (food, snacks, or grocery line items -> Meals, not Utilities).
Add 3-5 lowercase tags useful for search.
Write a clear one-line summary (about 10-20 words) explaining why department and category were chosen.

Return JSON only:
{{
    "merchant": "string",
    "date": "YYYY-MM-DD",
    "total": "string",
    "department": "string",
    "category": "string",
    "tags": ["tag1", "tag2"],
    "summary": "string"
}}
""",
            ),
            ("user", "Invoice text:\n{text}"),
        ]
    )

    try:
        result = (template | llm).invoke(
            {
                "text": ocr_text,
                "departments": department_list,
                "categories": category_list,
            }
        )
        payload = json.loads(result.content)
        return refine_payload(ocr_text, payload)
    except Exception as exc:
        st.error(f"Classification failed: {exc}")
        return None


def _total_looks_like_words(value):
    if not value:
        return True
    lower = value.lower()
    return "rupee" in lower or "paise" in lower or len(value) > 40


def _fix_ocr_amount_digits(raw):
    if "." in raw:
        return raw
    if len(raw) >= 3 and raw.isdigit():
        return f"{raw[:-1]}.{raw[-1]}"
    return raw


def extract_total_from_ocr(text):
    patterns = [
        r"Invoice\s+Value\s*\|?\s*(\d+(?:\.\d+)?)",
        r"Invoice\s+Value[:\s]+(\d+(?:\.\d+)?)",
        r"Grand\s+Total[:\s]+(\d+(?:\.\d+)?)",
        r"Total\s+Amount[:\s]+(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _fix_ocr_amount_digits(match.group(1))
    return None


def refine_payload(ocr_text, payload):
    llm_total = (payload.get("total") or "").strip()
    ocr_total = extract_total_from_ocr(ocr_text)

    if ocr_total:
        payload["total"] = ocr_total
    elif _total_looks_like_words(llm_total):
        payload["total_note"] = llm_total
        payload["total"] = ""
    else:
        digits = re.sub(r"[^\d.]", "", llm_total)
        if digits and digits.replace(".", "", 1).isdigit() and "." not in digits:
            payload["total"] = _fix_ocr_amount_digits(digits)

    return payload


def render_detail_card(title, body):
    safe_title = html.escape(str(title))
    safe_body = html.escape(str(body))
    st.markdown(
        f"""
        <div style="
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 10px;
        ">
            <div style="font-size: 0.78rem; font-weight: 600; color: #64748b;
                text-transform: uppercase; letter-spacing: 0.04em;">{safe_title}</div>
            <div style="font-size: 1rem; color: #0f172a; margin-top: 6px;
                word-wrap: break-word; white-space: normal; line-height: 1.45;">{safe_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_analysis_results(payload):
    st.markdown("#### Invoice details")
    render_detail_card("Merchant", payload.get("merchant", "—"))

    amount_col, date_col = st.columns(2)
    with amount_col:
        total = payload.get("total") or "—"
        render_detail_card("Total amount", total)
    with date_col:
        render_detail_card("Invoice date", payload.get("date") or "—")

    if payload.get("total_note"):
        st.caption(f"Amount in words (OCR): {payload['total_note']}")

    st.divider()
    st.markdown("#### Classification")
    dept_col, cat_col = st.columns(2)
    with dept_col:
        render_detail_card("Department", payload.get("department", "Unassigned"))
    with cat_col:
        render_detail_card("Category", payload.get("category", "Uncategorized"))

    summary = (payload.get("summary") or "").strip()
    if summary:
        st.markdown("#### Analysis summary")
        st.info(summary)

    st.divider()
    st.markdown("#### Tags")
    render_tag_chips(payload.get("tags", []))

    st.divider()
    st.download_button(
        label="Download metadata (JSON)",
        data=json.dumps(payload, indent=2),
        file_name="invoice_classification.json",
        mime="application/json",
    )


def render_tag_chips(tag_list):
    chips = []
    for label in tag_list:
        chips.append(
            f'<span style="background:#eef2f7;color:#1f2933;padding:4px 10px;'
            f'border-radius:12px;margin:0 6px 6px 0;display:inline-block;'
            f'border:1px solid #cbd5e0;">#{label}</span>'
        )
    st.markdown("".join(chips), unsafe_allow_html=True)


st.sidebar.header("Rules & model")
selected_model = st.sidebar.selectbox("Ollama model", ["llama3.2", "mistral", "llama3"])

st.sidebar.markdown("---")
st.sidebar.subheader("Allowed values")
departments_input = st.sidebar.text_area("Departments", DEFAULT_DEPARTMENTS, height=70)
categories_input = st.sidebar.text_area("Expense categories", DEFAULT_CATEGORIES, height=90)

st.title("Invoice Categorization and Tagging")
st.markdown(
    "Upload a PDF or image invoice to extract text, assign department and category, "
    "and generate searchable tags."
)

uploaded = st.file_uploader("Invoice file", type=["pdf", "png", "jpg", "jpeg"])

if uploaded:
    upload_key = f"{uploaded.name}:{uploaded.size}"
    if st.session_state.get("invoice_upload_key") != upload_key:
        st.session_state.invoice_upload_key = upload_key
        st.session_state.invoice_result = None

    ocr_text, preview_img = read_uploaded_invoice(uploaded)

    left, right = st.columns([1, 1.4])

    with left:
        st.subheader("Preview")
        if preview_img is not None:
            st.image(preview_img, channels="BGR", use_container_width=True)
        with st.expander("OCR text"):
            st.text_area("Extracted content", ocr_text, height=220, disabled=True)

    with right:
        st.subheader("Categorization")

        if st.button("Run categorization", type="primary"):
            with st.spinner("Analyzing invoice..."):
                payload = categorize_with_llm(
                    ocr_text,
                    departments_input,
                    categories_input,
                    selected_model,
                )
            if payload:
                st.session_state.invoice_result = payload
            else:
                st.session_state.invoice_result = None
                st.warning(
                    "No classification result. Check that Ollama is running and OCR text is not empty."
                )

        if st.session_state.get("invoice_result"):
            render_analysis_results(st.session_state.invoice_result)
