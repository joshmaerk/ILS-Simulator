"""
Shared pytest fixtures for IBCS Agent tests.

Creates in-memory test files (PPTX, PDF, XLSX) and mock objects
so tests run without Azure credentials or real files.
"""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure tests use metadata-only mode (no Azure calls by default)
# ---------------------------------------------------------------------------
os.environ.setdefault("ENABLE_VISUAL_ANALYSIS", "false")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key-for-ci")
os.environ.setdefault("AZURE_OPENAI_MODEL_NAME", "gpt-4o")


# ---------------------------------------------------------------------------
# In-memory PPTX fixtures
# ---------------------------------------------------------------------------

def _make_minimal_pptx(
    title: str = "Umsatz Q1 2024",
    add_chart: bool = False,
    add_table: bool = False,
) -> bytes:
    """Create a minimal PPTX file in memory using python-pptx."""
    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    slide_layout = prs.slide_layouts[0]  # Title Slide
    slide = prs.slides.add_slide(slide_layout)

    # Set title
    if slide.shapes.title:
        slide.shapes.title.text = title

    # Add body text if layout has placeholder
    try:
        body = slide.placeholders[1]
        body.text = "Testinhalt für IBCS-Prüfung"
    except (KeyError, IndexError):
        pass

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


def _make_pptx_with_insight_title() -> bytes:
    """PPTX with a proper IBCS insight title (contains verb + time + unit)."""
    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    if slide.shapes.title:
        slide.shapes.title.text = "Umsatz steigt um 12% in Q1 2024 in Mio. €"
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


def _make_pptx_no_title() -> bytes:
    """PPTX with blank title — triggers S1, ST2."""
    from pptx import Presentation
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


@pytest.fixture
def pptx_bytes_minimal() -> bytes:
    return _make_minimal_pptx()


@pytest.fixture
def pptx_bytes_insight_title() -> bytes:
    return _make_pptx_with_insight_title()


@pytest.fixture
def pptx_bytes_no_title() -> bytes:
    return _make_pptx_no_title()


@pytest.fixture
def pptx_b64_minimal(pptx_bytes_minimal: bytes) -> str:
    return base64.b64encode(pptx_bytes_minimal).decode("utf-8")


# ---------------------------------------------------------------------------
# In-memory XLSX fixtures
# ---------------------------------------------------------------------------

def _make_minimal_xlsx(
    title_cell: str = "Umsatzentwicklung",
    sheet_name: str = "Sheet1",
) -> bytes:
    """Create a minimal XLSX file with openpyxl."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    # Header row
    ws["A1"] = title_cell
    ws["A1"].font = Font(size=14, bold=True)
    ws["A2"] = "Monat"
    ws["B2"] = "Umsatz (€)"
    ws["A3"] = "Januar"
    ws["B3"] = 100000
    ws["A4"] = "Februar"
    ws["B4"] = 120000
    ws["A5"] = "März"
    ws["B5"] = 95000

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _make_xlsx_with_source() -> bytes:
    """XLSX that contains a source reference."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Daten"
    ws["A10"] = "Quelle: SAP BW, Stand: 2024-01"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


@pytest.fixture
def xlsx_bytes_minimal() -> bytes:
    return _make_minimal_xlsx()


@pytest.fixture
def xlsx_bytes_with_source() -> bytes:
    return _make_xlsx_with_source()


@pytest.fixture
def xlsx_b64_minimal(xlsx_bytes_minimal: bytes) -> str:
    return base64.b64encode(xlsx_bytes_minimal).decode("utf-8")


# ---------------------------------------------------------------------------
# Minimal PDF bytes (handcrafted — no external lib needed)
# ---------------------------------------------------------------------------

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj
2 0 obj<</Type /Pages /Kids[3 0 R] /Count 1>>endobj
3 0 obj<</Type /Page /MediaBox[0 0 612 792] /Parent 2 0 R /Resources<</Font<</F1 4 0 R>>>>>>
endobj
4 0 obj<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>endobj
5 0 obj<</Length 44>>
stream
BT /F1 12 Tf 100 700 Td (Umsatz Q1 2024) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000352 00000 n
trailer<</Size 6 /Root 1 0 R>>
startxref
448
%%EOF"""


@pytest.fixture
def pdf_bytes_minimal() -> bytes:
    return MINIMAL_PDF


@pytest.fixture
def pdf_b64_minimal() -> str:
    return base64.b64encode(MINIMAL_PDF).decode("utf-8")


# ---------------------------------------------------------------------------
# Processor result fixtures (bypass file I/O for unit tests)
# ---------------------------------------------------------------------------

from ibcs_agent.processors.ppt_processor import (
    ChartMetadata,
    PPTProcessingResult,
    SlideData,
    TableMetadata,
)
from ibcs_agent.processors.excel_processor import (
    ExcelChartMetadata,
    ExcelProcessingResult,
    SheetData,
)
from ibcs_agent.processors.pdf_processor import (
    PDFPageData,
    PDFProcessingResult,
    TextBlock,
)


def _make_slide(
    slide_number: int = 1,
    title: Optional[str] = "Umsatz",
    charts: Optional[List[ChartMetadata]] = None,
    tables: Optional[List[TableMetadata]] = None,
    font_sizes: Optional[List[float]] = None,
    has_page_number: bool = False,
    has_source: bool = False,
) -> SlideData:
    return SlideData(
        slide_number=slide_number,
        title=title,
        body_texts=["Some body text"],
        all_texts=[title or "", "Some body text"],
        font_sizes_pt=font_sizes or [18.0, 12.0],
        charts=charts or [],
        tables=tables or [],
        has_page_number=has_page_number,
        has_source_reference=has_source,
        image_base64=None,
        layout_name="Title Slide",
    )


def _make_chart(
    index: int = 0,
    chart_type: str = "column",
    is_3d: bool = False,
    title: Optional[str] = "Umsatz",
    axis_min_y: Optional[float] = None,
    series_count: int = 1,
) -> ChartMetadata:
    return ChartMetadata(
        index=index,
        chart_type=chart_type,
        is_3d=is_3d,
        title=title,
        has_axis_title_x=False,
        has_axis_title_y=False,
        axis_min_y=axis_min_y,
        axis_max_y=None,
        series_count=series_count,
        series_names=[f"Series {i}" for i in range(series_count)],
        has_legend=False,
        has_gridlines_major=False,
        has_data_labels=False,
    )


def _make_ppt_result(slides: Optional[List[SlideData]] = None) -> PPTProcessingResult:
    if slides is None:
        slides = [_make_slide()]
    return PPTProcessingResult(
        file_name="test.pptx",
        total_slides=len(slides),
        slides=slides,
        has_slide_numbers=False,
        presentation_title="Test Presentation",
    )


def _make_pdf_page(
    page_number: int = 1,
    title: Optional[str] = "Umsatz Q1",
    font_sizes: Optional[List[float]] = None,
    has_source: bool = False,
) -> PDFPageData:
    texts = [title] if title else []
    blocks = [
        TextBlock(
            text=title or "text",
            font_size=(font_sizes or [12.0])[0],
            x0=10.0, y0=10.0, x1=200.0, y1=30.0,
        )
    ] if title else []
    return PDFPageData(
        page_number=page_number,
        title=title,
        all_texts=texts,
        text_blocks=blocks,
        font_sizes_pt=font_sizes or [12.0],
        has_source_reference=has_source,
        image_base64=None,
        page_width_pt=612.0,
        page_height_pt=792.0,
    )


def _make_pdf_result(pages: Optional[List[PDFPageData]] = None) -> PDFProcessingResult:
    if pages is None:
        pages = [_make_pdf_page()]
    return PDFProcessingResult(
        file_name="test.pdf",
        total_pages=len(pages),
        pages=pages,
        has_page_numbers=False,
        metadata_title=None,
    )


def _make_excel_chart(
    index: int = 0,
    chart_type: str = "bar_or_column",
    is_3d: bool = False,
    title: Optional[str] = "Umsatz",
    axis_min_y: Optional[float] = None,
    series_count: int = 1,
    pie_slices: int = 0,
) -> ExcelChartMetadata:
    return ExcelChartMetadata(
        index=index,
        chart_type=chart_type,
        is_3d=is_3d,
        title=title,
        has_axis_title_x=False,
        has_axis_title_y=False,
        axis_min_y=axis_min_y,
        axis_max_y=None,
        series_count=series_count,
        series_names=[f"S{i}" for i in range(series_count)],
        has_legend=False,
        has_gridlines=False,
        pie_slice_count=pie_slices,
    )


def _make_sheet(
    sheet_name: str = "Sheet1",
    title: Optional[str] = "Umsatz",
    charts: Optional[List[ExcelChartMetadata]] = None,
    font_sizes: Optional[List[float]] = None,
    has_source: bool = False,
) -> SheetData:
    return SheetData(
        sheet_index=0,
        sheet_name=sheet_name,
        title=title,
        all_texts=[title or ""],
        charts=charts or [],
        has_source_reference=has_source,
        has_header_row=True,
        row_count=10,
        col_count=5,
        font_sizes_pt=font_sizes or [11.0],
        image_base64=None,
    )


def _make_excel_result(sheets: Optional[List[SheetData]] = None) -> ExcelProcessingResult:
    if sheets is None:
        sheets = [_make_sheet()]
    return ExcelProcessingResult(
        file_name="test.xlsx",
        total_sheets=len(sheets),
        sheets=sheets,
    )


# Expose as fixtures
@pytest.fixture
def slide_factory():
    return _make_slide


@pytest.fixture
def chart_factory():
    return _make_chart


@pytest.fixture
def ppt_result_factory():
    return _make_ppt_result


@pytest.fixture
def pdf_page_factory():
    return _make_pdf_page


@pytest.fixture
def pdf_result_factory():
    return _make_pdf_result


@pytest.fixture
def excel_chart_factory():
    return _make_excel_chart


@pytest.fixture
def sheet_factory():
    return _make_sheet


@pytest.fixture
def excel_result_factory():
    return _make_excel_result


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

from ibcs_agent.config import AnalysisConfig, AppConfig, AzureConfig


@pytest.fixture
def config_no_visual() -> AppConfig:
    """Config with visual analysis disabled (no Azure calls)."""
    cfg = AppConfig()
    cfg.azure.openai_endpoint = "https://test.openai.azure.com/"
    cfg.azure.openai_api_key = "test-key"
    cfg.azure.model_name = "gpt-4o"
    cfg.analysis.enable_visual_analysis = False
    cfg.analysis.enable_metadata_analysis = True
    return cfg


@pytest.fixture
def config_with_visual() -> AppConfig:
    """Config with visual analysis enabled (requires mocking Azure calls)."""
    cfg = AppConfig()
    cfg.azure.openai_endpoint = "https://test.openai.azure.com/"
    cfg.azure.openai_api_key = "test-key"
    cfg.azure.model_name = "gpt-4o"
    cfg.analysis.enable_visual_analysis = True
    return cfg
