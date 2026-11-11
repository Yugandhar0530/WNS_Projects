import os

import streamlit as st
import pytesseract

from document_loader import load_invoice_as_bgr
from invoice_pipeline import (
    annotate_invoice,
    build_ocr_word_map,
    configure_tesseract,
    extract_invoice_fields,
    preprocess_for_ocr,
    tesseract_install_hint,
)

st.set_page_config(page_title="Invoice Bounding Box Drawing", layout="wide")

st.title("Invoice Bounding Box Drawing")

model_name = st.sidebar.selectbox("Model", ["llama3.2", "mistral", "llama3.1"])
draw_table_region = st.sidebar.checkbox("Highlight table region", value=True)

uploaded = st.file_uploader(
    "Upload Invoice",
    type=["pdf", "png", "jpg", "jpeg", "docx"],
)

if uploaded is None:
    st.stop()

file_bytes = uploaded.getvalue()
bgr, load_error = load_invoice_as_bgr(file_bytes, uploaded.name, uploaded.type)

if load_error or bgr is None:
    st.error(load_error or "Could not load document.")
    st.stop()

col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader("Visualized Document")
    image_placeholder = st.empty()
    image_placeholder.image(bgr, channels="BGR", width="stretch")

with col2:
    st.subheader("AI Extraction")
    run_btn = st.button("Discover & map fields", type="primary")

if run_btn:
    tess_path = os.getenv("TESSERACT_PATH")
    if not configure_tesseract(tess_path):
        st.error("Tesseract not found. Set TESSERACT_PATH in PowerShell or install Tesseract.")
        st.code(tesseract_install_hint(), language=None)
        st.stop()

    with st.status("Processing…", expanded=True) as status:
        status.write("OCR")
        thresh = preprocess_for_ocr(bgr)
        try:
            ocr_text, word_map = build_ocr_word_map(thresh)
        except pytesseract.TesseractNotFoundError:
            status.update(label="Tesseract missing", state="error")
            st.error(tesseract_install_hint())
            st.stop()

        if not word_map:
            status.update(label="No OCR text", state="error")
            st.warning("No text detected. Check scan quality or Tesseract.")
            st.stop()

        status.write("LLM extraction")
        try:
            fields = extract_invoice_fields(ocr_text, model_name)
        except Exception as exc:
            status.update(label="Ollama error", state="error")
            st.error(f"Ollama request failed: {exc}")
            st.stop()

        st.json(fields)

        status.write("Bounding boxes")
        result_img, log = annotate_invoice(
            bgr, word_map, fields, draw_table=draw_table_region
        )
        status.update(label="Done", state="complete", expanded=False)

    image_placeholder.image(result_img, channels="BGR", width="stretch")

    if log:
        st.success(
            f"Mapped {len(log)} region(s) on the image. "
            f"JSON can list more fields than boxes when OCR text does not match extracted values."
        )
    else:
        st.warning("No boxes drawn; values may not match OCR tokens.")
