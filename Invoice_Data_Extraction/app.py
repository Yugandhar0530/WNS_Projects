import json

import streamlit as st
from PIL import Image

from llm_extractor import SUPPORTED_MODELS, extract_invoice_fields
from ocr_engine import ocr_document, pdf_bytes_to_images
from rule_hints import derive_rule_hints

st.set_page_config(
    page_title="Invoice Field Parser",
    page_icon="📄",
    layout="wide",
)

st.sidebar.header("Extraction settings")
model_name = st.sidebar.selectbox("Ollama model", SUPPORTED_MODELS)
psm_mode = st.sidebar.selectbox(
    "OCR page layout (PSM)",
    options=[6, 3, 11],
    format_func=lambda v: {6: "Uniform block (6)", 3: "Fully automatic (3)", 11: "Sparse text (11)"}[v],
)
st.sidebar.caption(
    "Set TESSERACT_PATH if Tesseract is not on PATH. "
    "Ollama must be running with the selected model pulled."
)

st.title("Invoice Field Parser")
st.markdown(
    "Upload a PDF or image invoice. Text is read with Tesseract OCR, "
    "rule-based patterns supply hints, and a local LLM returns structured JSON."
)

uploaded = st.file_uploader(
    "Invoice file",
    type=["pdf", "png", "jpg", "jpeg"],
    help="PDF or raster image (PNG, JPG, JPEG).",
)

if uploaded is not None:
    images: list[Image.Image] = []
    if uploaded.type == "application/pdf":
        with st.spinner("Rendering PDF pages…"):
            images = pdf_bytes_to_images(uploaded.getvalue())
    else:
        images = [Image.open(uploaded)]

    if not images:
        st.error("No pages could be loaded from this file.")
        st.stop()

    preview_col, action_col = st.columns([1, 1.2])

    with preview_col:
        st.subheader("Document preview")
        st.image(images[0], caption=f"Page 1 of {len(images)}", use_container_width=True)
        if len(images) > 1:
            st.caption(f"{len(images)} page(s) will be processed.")

    with action_col:
        st.subheader("Run extraction")
        run = st.button("Extract fields", type="primary", use_container_width=True)

        if run:
            with st.spinner("Running OCR…"):
                full_text = ocr_document(images, psm=psm_mode)
            hints = derive_rule_hints(full_text)

            with st.spinner("Structuring with LLM…"):
                result = extract_invoice_fields(full_text, model_name, hints)

            if not full_text.strip():
                st.warning("OCR returned no text. Check image quality and Tesseract installation.")
            elif result is None:
                st.error("LLM extraction failed. Confirm Ollama is running and the model is installed.")
            else:
                st.success("Extraction complete.")
                st.json(result, expanded=True)

                st.download_button(
                    label="Download JSON",
                    data=json.dumps(result, indent=2),
                    file_name="invoice_fields.json",
                    mime="application/json",
                    use_container_width=True,
                )

                with st.expander("OCR text", expanded=False):
                    st.text(full_text)

                if hints:
                    with st.expander("Rule-based hints (used as LLM context)", expanded=False):
                        st.json(hints)