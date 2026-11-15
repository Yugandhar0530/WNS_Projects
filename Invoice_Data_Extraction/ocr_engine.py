from __future__ import annotations

import os
from typing import List

import fitz
import pytesseract
from PIL import Image

DEFAULT_PSM = 6

_tesseract_path = os.getenv("TESSERACT_PATH")
if _tesseract_path and os.path.isfile(_tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path


def ocr_image(image: Image.Image, psm: int = DEFAULT_PSM) -> str:
    config = f"--psm {psm}"
    try:
        return pytesseract.image_to_string(image, config=config)
    except Exception:
        return ""


def pdf_bytes_to_images(file_bytes: bytes, dpi_scale: float = 2.0) -> List[Image.Image]:
    images: List[Image.Image] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for index in range(doc.page_count):
            page = doc.load_page(index)
            matrix = fitz.Matrix(dpi_scale, dpi_scale)
            pix = page.get_pixmap(matrix=matrix)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    finally:
        doc.close()
    return images


def ocr_document(images: List[Image.Image], psm: int = DEFAULT_PSM) -> str:
    chunks = [ocr_image(img, psm=psm) for img in images]
    return "\n".join(part for part in chunks if part.strip())