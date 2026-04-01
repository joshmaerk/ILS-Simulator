"""
PDF processor.

Extracts per-page:
- Text content (titles, body paragraphs)
- Page images (rendered via pdf2image / PyMuPDF fallback)
- Structural metadata (font sizes, text positions)
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

SOURCE_KEYWORDS = ["quelle", "source", "stand:", "data:", "daten:", "basis:"]


@dataclass
class TextBlock:
    """A text block with positional information."""

    text: str
    font_size: float
    x0: float
    y0: float
    x1: float
    y1: float
    is_bold: bool = False


@dataclass
class PDFPageData:
    """All extracted data from a single PDF page."""

    page_number: int          # 1-based
    title: Optional[str]      # Largest/topmost text block
    all_texts: List[str]
    text_blocks: List[TextBlock]
    font_sizes_pt: List[float]
    has_source_reference: bool
    image_base64: Optional[str] = None
    page_width_pt: float = 0.0
    page_height_pt: float = 0.0


@dataclass
class PDFProcessingResult:
    """Result of processing an entire PDF file."""

    file_name: str
    total_pages: int
    pages: List[PDFPageData]
    has_page_numbers: bool
    metadata_title: Optional[str]


def _detect_source_reference(texts: List[str]) -> bool:
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in SOURCE_KEYWORDS)


def _infer_title(text_blocks: List[TextBlock]) -> Optional[str]:
    """Infer the slide/page title as the largest font-size text near the top."""
    if not text_blocks:
        return None
    # Sort by font size descending, then by vertical position (top = small y)
    sorted_blocks = sorted(text_blocks, key=lambda b: (-b.font_size, b.y0))
    if sorted_blocks:
        return sorted_blocks[0].text.strip() or None
    return None


def _render_page_to_base64_pdf2image(pdf_bytes: bytes, page_num: int, dpi: int = 150) -> Optional[str]:
    """Render a single PDF page using pdf2image (requires poppler)."""
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_num,
            last_page=page_num,
        )
        if images:
            buf = io.BytesIO()
            images[0].save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        logger.debug("pdf2image not available")
    except Exception as e:
        logger.warning(f"pdf2image render failed for page {page_num}: {e}")
    return None


def _render_page_to_base64_pymupdf(pdf_bytes: bytes, page_num: int, dpi: int = 150) -> Optional[str]:
    """Render a single PDF page using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num - 1]  # 0-based
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return base64.b64encode(img_bytes).decode("utf-8")
    except ImportError:
        logger.debug("PyMuPDF (fitz) not available")
    except Exception as e:
        logger.warning(f"PyMuPDF render failed for page {page_num}: {e}")
    return None


def _render_page_to_base64(pdf_bytes: bytes, page_num: int) -> Optional[str]:
    """Try pdf2image, then PyMuPDF, then return None."""
    result = _render_page_to_base64_pdf2image(pdf_bytes, page_num)
    if result:
        return result
    return _render_page_to_base64_pymupdf(pdf_bytes, page_num)


def _extract_with_pdfplumber(
    pdf_bytes: bytes,
    render_images: bool,
) -> List[PDFPageData]:
    """Extract text and metadata using pdfplumber."""
    import pdfplumber

    pages_data: List[PDFPageData] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_number = page_idx + 1
            text_blocks: List[TextBlock] = []

            # Extract word-level data with font info
            words = page.extract_words(
                extra_attrs=["fontname", "size"],
                keep_blank_chars=False,
            )

            # Group words into rough text blocks by proximity
            current_line: List[dict] = []
            current_y = None
            lines: List[List[dict]] = []

            for word in words:
                word_y = round(word.get("top", 0), 1)
                if current_y is None or abs(word_y - current_y) < 3:
                    current_line.append(word)
                    current_y = word_y
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = [word]
                    current_y = word_y
            if current_line:
                lines.append(current_line)

            font_sizes_seen: List[float] = []
            for line in lines:
                line_text = " ".join(w["text"] for w in line)
                sizes = [float(w.get("size", 10)) for w in line if w.get("size")]
                avg_size = sum(sizes) / len(sizes) if sizes else 10.0
                font_sizes_seen.extend(sizes)
                x0 = min(w["x0"] for w in line)
                y0 = min(w["top"] for w in line)
                x1 = max(w["x1"] for w in line)
                y1 = max(w["bottom"] for w in line)
                text_blocks.append(TextBlock(
                    text=line_text,
                    font_size=avg_size,
                    x0=x0, y0=y0, x1=x1, y1=y1,
                ))

            all_texts = [b.text for b in text_blocks if b.text.strip()]
            title = _infer_title(text_blocks)
            has_source = _detect_source_reference(all_texts)

            image_b64: Optional[str] = None
            if render_images:
                image_b64 = _render_page_to_base64(pdf_bytes, page_number)

            pages_data.append(PDFPageData(
                page_number=page_number,
                title=title,
                all_texts=all_texts,
                text_blocks=text_blocks,
                font_sizes_pt=font_sizes_seen,
                has_source_reference=has_source,
                image_base64=image_b64,
                page_width_pt=float(page.width),
                page_height_pt=float(page.height),
            ))

    return pages_data


def _detect_page_numbers(pages_data: List[PDFPageData]) -> bool:
    """Heuristic: check if small numbers appear at the bottom of multiple pages."""
    count = 0
    for page in pages_data:
        for block in page.text_blocks:
            text = block.text.strip()
            # Small font, near bottom, is just a number
            if (
                text.isdigit()
                and block.font_size <= 10
                and block.y0 > page.page_height_pt * 0.85
            ):
                count += 1
                break
    return count >= max(2, len(pages_data) // 3)


def process_pdf(
    file_content: bytes,
    file_name: str,
    render_images: bool = True,
) -> PDFProcessingResult:
    """
    Process a PDF file and extract all IBCS-relevant metadata.

    Args:
        file_content: Raw bytes of the .pdf file
        file_name: Original filename
        render_images: Whether to render page images

    Returns:
        PDFProcessingResult with all page data
    """
    try:
        pages_data = _extract_with_pdfplumber(file_content, render_images)
    except ImportError:
        logger.error("pdfplumber is not installed. Install it with: pip install pdfplumber")
        raise
    except Exception as e:
        logger.error(f"Failed to process PDF '{file_name}': {e}")
        raise

    has_page_numbers = _detect_page_numbers(pages_data)

    # Try to get document title from PDF metadata
    metadata_title: Optional[str] = None
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            meta = pdf.metadata or {}
            metadata_title = meta.get("Title") or meta.get("/Title") or None
    except Exception:
        pass

    return PDFProcessingResult(
        file_name=file_name,
        total_pages=len(pages_data),
        pages=pages_data,
        has_page_numbers=has_page_numbers,
        metadata_title=metadata_title,
    )
