"""Load invoice files (PDF, image, DOCX) into an OpenCV BGR image."""

from __future__ import annotations

import os
import tempfile
from typing import Optional, Tuple

import cv2
import pymupdf as fitz
import numpy as np


def _pdf_first_page_to_bgr(pdf_bytes: bytes, zoom: float = 2.0) -> np.ndarray:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    finally:
        doc.close()


def _image_bytes_to_bgr(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes.")
    return img


def _docx_to_bgr_via_pdf(docx_bytes: bytes) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
  Convert DOCX to a single-page raster via temporary PDF (requires docx2pdf + MS Word on Windows).
    """
    try:
        from docx2pdf import convert
    except ImportError:
        return None, (
            "DOCX support needs `pip install docx2pdf` and Microsoft Word (Windows). "
            "Alternatively, export the invoice as PDF and upload again."
        )

    with tempfile.TemporaryDirectory() as tmp:
        docx_path = os.path.join(tmp, "invoice.docx")
        pdf_path = os.path.join(tmp, "invoice.pdf")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        try:
            convert(docx_path, pdf_path)
        except Exception as exc:
            return None, f"DOCX conversion failed: {exc}"

        if not os.path.isfile(pdf_path):
            return None, "DOCX conversion did not produce a PDF file."

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return _pdf_first_page_to_bgr(pdf_bytes), None


def load_invoice_as_bgr(
    file_bytes: bytes,
    filename: str,
    mime_type: Optional[str],
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Returns (bgr_image, error_message). On success, error_message is None.
    """
    name_lower = (filename or "").lower()
    mime = (mime_type or "").lower()

    if mime == "application/pdf" or name_lower.endswith(".pdf"):
        return _pdf_first_page_to_bgr(file_bytes), None

    if mime in ("image/png", "image/jpeg", "image/jpg") or name_lower.endswith(
        (".png", ".jpg", ".jpeg", ".bmp", ".webp")
    ):
        try:
            return _image_bytes_to_bgr(file_bytes), None
        except ValueError as exc:
            return None, str(exc)

    if (
        mime
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or name_lower.endswith(".docx")
    ):
        return _docx_to_bgr_via_pdf(file_bytes)

    return None, "Unsupported file type. Use PDF, PNG, JPG, or DOCX."
