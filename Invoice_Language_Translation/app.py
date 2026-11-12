import io

import argostranslate.package
import argostranslate.translate
import easyocr
import fitz
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

SOURCE_CODE = "en"

TARGET_LANGUAGES = {
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Hindi": "hi",
    "Chinese (Simplified)": "zh",
}


st.set_page_config(page_title="Invoice Language Translation", layout="wide")
st.title("Invoice Language Translation")
st.caption("Local OCR and translation with Argos Translate (language packs download on first use).")


@st.cache_resource
def ocr_reader():
    return easyocr.Reader([SOURCE_CODE], gpu=False)


@st.cache_resource
def ensure_lang_package(from_code: str, to_code: str) -> bool:
    argostranslate.package.update_package_index()
    catalog = argostranslate.package.get_available_packages()
    match = next(
        (p for p in catalog if p.from_code == from_code and p.to_code == to_code),
        None,
    )
    if match is None:
        return False

    installed = argostranslate.package.get_installed_packages()
    if any(p.from_code == from_code and p.to_code == to_code for p in installed):
        return True

    argostranslate.package.install_from_path(match.download())
    return True


def translate_line(text: str, from_code: str, to_code: str) -> str:
    try:
        return argostranslate.translate.translate(text, from_code, to_code)
    except Exception as exc:
        return f"Error: {exc}"


def skip_translation(line: str) -> bool:
    candidate = line.replace(".", "", 1)
    return candidate.isdigit() or len(line) < 2


def extract_pdf_lines(file_bytes: bytes) -> list[str]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    lines: list[str] = []
    reader = ocr_reader()

    with st.status("Processing PDF…", expanded=True) as status:
        for index, page in enumerate(doc):
            page_text = page.get_text()
            if page_text.strip():
                status.write(f"Page {index + 1}: text layer found.")
                lines.extend(s.strip() for s in page_text.split("\n") if s.strip())
            else:
                status.write(f"Page {index + 1}: running OCR.")
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image = np.array(Image.open(io.BytesIO(pixmap.tobytes("png"))))
                lines.extend(reader.readtext(image, detail=0))
        status.update(label="PDF complete", state="complete", expanded=False)

    return lines


def extract_image_lines(file_bytes: bytes) -> list[str]:
    image = Image.open(io.BytesIO(file_bytes))
    return ocr_reader().readtext(np.array(image), detail=0)


with st.sidebar:
    st.header("Settings")
    target_label = st.selectbox("Target language", list(TARGET_LANGUAGES.keys()))
    target_code = TARGET_LANGUAGES[target_label]
    st.markdown(f"Source language for translation: **{SOURCE_CODE}** (English).")

uploaded = st.file_uploader("Upload invoice (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])

if uploaded:
    raw = uploaded.read()
    is_pdf = uploaded.type == "application/pdf"

    if is_pdf:
        invoice_lines = extract_pdf_lines(raw)
    else:
        st.image(Image.open(io.BytesIO(raw)), caption="Uploaded invoice")
        with st.spinner("Running OCR…"):
            invoice_lines = extract_image_lines(raw)

    if not invoice_lines:
        st.warning("No text could be extracted from this file.")
    else:
        st.write(f"Extracted **{len(invoice_lines)}** line(s). Preparing translation…")

        with st.spinner("Installing language pack if needed…"):
            if not ensure_lang_package(SOURCE_CODE, target_code):
                st.error(f"No Argos package for {SOURCE_CODE} → {target_code}.")
                st.stop()

        pairs: list[tuple[str, str]] = []
        progress = st.progress(0.0)

        for idx, line in enumerate(invoice_lines):
            if skip_translation(line):
                pairs.append((line, line))
            else:
                pairs.append((line, translate_line(line, SOURCE_CODE, target_code)))
            progress.progress((idx + 1) / len(invoice_lines))

        table = pd.DataFrame(pairs, columns=["Original", "Translated"])
        st.dataframe(table, use_container_width=True)

        st.download_button(
            label="Download CSV",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name="translated_invoice.csv",
            mime="text/csv",
        )
