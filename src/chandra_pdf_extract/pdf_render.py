from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image


def render_pdf_page(pdf_path: Path, page_1based: int, scale: float = 2.0) -> Image.Image:
    """Rasterize one PDF page to RGB (PNG in memory). ``page_1based`` is 1..N."""
    with pymupdf.open(pdf_path) as doc:
        if page_1based < 1 or page_1based > len(doc):
            raise ValueError(f"page {page_1based} out of range (1..{len(doc)})")
        page = doc[page_1based - 1]
        mat = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")


def pdf_page_count(pdf_path: Path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return len(doc)
