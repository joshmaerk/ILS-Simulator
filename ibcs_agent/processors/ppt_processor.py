"""
PowerPoint (.pptx) processor.

Extracts per-slide:
- Text content (titles, body, chart titles, table cells)
- Slide images (rendered as PNG via python-pptx + Pillow)
- Structural metadata (chart types, table presence, layout info, font sizes)
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Pt

logger = logging.getLogger(__name__)


# Map pptx chart type enums to human-readable IBCS-relevant names
CHART_TYPE_NAMES = {
    XL_CHART_TYPE.BAR_CLUSTERED: "bar",
    XL_CHART_TYPE.BAR_STACKED: "bar_stacked",
    XL_CHART_TYPE.BAR_STACKED_100: "bar_stacked_100",
    XL_CHART_TYPE.COLUMN_CLUSTERED: "column",
    XL_CHART_TYPE.COLUMN_STACKED: "column_stacked",
    XL_CHART_TYPE.COLUMN_STACKED_100: "column_stacked_100",
    XL_CHART_TYPE.LINE: "line",
    XL_CHART_TYPE.LINE_MARKERS: "line",
    XL_CHART_TYPE.LINE_STACKED: "line_stacked",
    XL_CHART_TYPE.PIE: "pie",
    XL_CHART_TYPE.PIE_EXPLODED: "pie",
    XL_CHART_TYPE.DOUGHNUT: "doughnut",
    XL_CHART_TYPE.AREA: "area",
    XL_CHART_TYPE.AREA_STACKED: "area_stacked",
    XL_CHART_TYPE.XY_SCATTER: "scatter",
    XL_CHART_TYPE.BUBBLE: "bubble",
    XL_CHART_TYPE.RADAR: "radar",
    XL_CHART_TYPE.SURFACE: "surface",
    # 3D variants
    XL_CHART_TYPE.THREE_D_BAR_CLUSTERED: "bar_3d",
    XL_CHART_TYPE.THREE_D_BAR_STACKED: "bar_stacked_3d",
    XL_CHART_TYPE.THREE_D_COLUMN: "column_3d",
    XL_CHART_TYPE.THREE_D_COLUMN_CLUSTERED: "column_3d",
    XL_CHART_TYPE.THREE_D_LINE: "line_3d",
    XL_CHART_TYPE.THREE_D_PIE: "pie_3d",
    XL_CHART_TYPE.THREE_D_PIE_EXPLODED: "pie_3d",
    XL_CHART_TYPE.THREE_D_AREA: "area_3d",
}

THREE_D_CHART_TYPES = {k for k, v in CHART_TYPE_NAMES.items() if "3d" in v}


@dataclass
class ChartMetadata:
    """Extracted metadata from a single chart shape."""

    index: int
    chart_type: str
    is_3d: bool
    title: Optional[str]
    has_axis_title_x: bool
    has_axis_title_y: bool
    axis_min_y: Optional[float]
    axis_max_y: Optional[float]
    series_count: int
    series_names: List[str] = field(default_factory=list)
    has_legend: bool = False
    has_gridlines_major: bool = False
    has_data_labels: bool = False


@dataclass
class TableMetadata:
    """Extracted metadata from a table shape."""

    index: int
    rows: int
    cols: int
    has_header_row: bool
    sample_text: str  # First few cell values joined


@dataclass
class SlideData:
    """All extracted data from a single PowerPoint slide."""

    slide_number: int           # 1-based
    title: Optional[str]
    body_texts: List[str]
    all_texts: List[str]        # All text on slide concatenated
    font_sizes_pt: List[float]  # All detected font sizes
    charts: List[ChartMetadata]
    tables: List[TableMetadata]
    has_page_number: bool
    has_source_reference: bool
    image_base64: Optional[str] = None   # PNG of slide, base64-encoded
    layout_name: Optional[str] = None


@dataclass
class PPTProcessingResult:
    """Result of processing an entire PPTX file."""

    file_name: str
    total_slides: int
    slides: List[SlideData]
    has_slide_numbers: bool
    presentation_title: Optional[str]


def _extract_chart_metadata(chart_shape, index: int) -> ChartMetadata:
    """Extract IBCS-relevant metadata from a pptx chart shape."""
    chart = chart_shape.chart
    chart_type_enum = chart.chart_type

    chart_type_name = CHART_TYPE_NAMES.get(chart_type_enum, "unknown")
    is_3d = chart_type_enum in THREE_D_CHART_TYPES

    # Chart title
    title = None
    try:
        if chart.has_title and chart.chart_title.has_text_frame:
            title = chart.chart_title.text_frame.text.strip() or None
    except Exception:
        pass

    # Axis information
    has_axis_title_x = False
    has_axis_title_y = False
    axis_min_y = None
    axis_max_y = None
    has_gridlines = False

    try:
        plot = chart.plots[0]
        if hasattr(plot, "category_axis"):
            ax = chart.category_axis
            has_axis_title_x = ax.has_title
        if hasattr(chart, "value_axis"):
            vax = chart.value_axis
            has_axis_title_y = vax.has_title
            axis_min_y = vax.minimum_scale
            axis_max_y = vax.maximum_scale
            has_gridlines = vax.major_gridlines is not None
    except Exception:
        pass

    # Series
    series_names = []
    has_data_labels = False
    try:
        for s in chart.series:
            try:
                series_names.append(s.name or "")
            except Exception:
                series_names.append("")
            try:
                if s.data_labels.showValue:
                    has_data_labels = True
            except Exception:
                pass
    except Exception:
        pass

    # Legend
    has_legend = False
    try:
        has_legend = chart.has_legend
    except Exception:
        pass

    return ChartMetadata(
        index=index,
        chart_type=chart_type_name,
        is_3d=is_3d,
        title=title,
        has_axis_title_x=has_axis_title_x,
        has_axis_title_y=has_axis_title_y,
        axis_min_y=axis_min_y,
        axis_max_y=axis_max_y,
        series_count=len(series_names),
        series_names=series_names,
        has_legend=has_legend,
        has_gridlines_major=has_gridlines,
        has_data_labels=has_data_labels,
    )


def _extract_table_metadata(table_shape, index: int) -> TableMetadata:
    """Extract metadata from a pptx table shape."""
    table = table_shape.table
    rows = len(table.rows)
    cols = len(table.columns)

    sample_cells = []
    for r_idx, row in enumerate(table.rows):
        if r_idx > 2:
            break
        for cell in row.cells:
            text = cell.text_frame.text.strip()
            if text:
                sample_cells.append(text)

    return TableMetadata(
        index=index,
        rows=rows,
        cols=cols,
        has_header_row=rows > 1,
        sample_text=" | ".join(sample_cells[:10]),
    )


def _collect_texts_and_fonts(slide) -> tuple[list[str], list[float]]:
    """Collect all text runs and font sizes from a slide."""
    texts = []
    font_sizes = []

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            para_text = ""
            for run in para.runs:
                para_text += run.text
                if run.font.size:
                    font_sizes.append(run.font.size / Pt(1))  # Convert EMU → pt
            if para_text.strip():
                texts.append(para_text.strip())

    return texts, font_sizes


SOURCE_KEYWORDS = ["quelle", "source", "stand:", "data:", "daten:", "basis:"]
PAGE_NUMBER_KEYWORDS = ["<a:fldType", "slidenum"]  # In XML


def _detect_page_number(slide) -> bool:
    """Check if slide has a page number placeholder or field."""
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt
    import pptx.oxml.ns as ns

    slide_xml = slide._element.xml.lower()
    return any(kw in slide_xml for kw in PAGE_NUMBER_KEYWORDS)


def _detect_source_reference(texts: List[str]) -> bool:
    """Check if any text block looks like a source reference."""
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in SOURCE_KEYWORDS)


def process_pptx(file_content: bytes, file_name: str, render_images: bool = True) -> PPTProcessingResult:
    """
    Process a PPTX file and extract all IBCS-relevant metadata.

    Args:
        file_content: Raw bytes of the .pptx file
        file_name: Original filename (for reporting)
        render_images: Whether to render slide thumbnails (requires Pillow)

    Returns:
        PPTProcessingResult with all slide data
    """
    prs = Presentation(io.BytesIO(file_content))
    slides_data: List[SlideData] = []

    # Try to get presentation title from core properties
    presentation_title = None
    try:
        presentation_title = prs.core_properties.title or None
    except Exception:
        pass

    for slide_idx, slide in enumerate(prs.slides):
        slide_number = slide_idx + 1
        charts: List[ChartMetadata] = []
        tables: List[TableMetadata] = []
        chart_idx = 0
        table_idx = 0

        title_text: Optional[str] = None

        # Try slide title placeholder
        try:
            if slide.shapes.title and slide.shapes.title.has_text_frame:
                title_text = slide.shapes.title.text_frame.text.strip() or None
        except Exception:
            pass

        body_texts: List[str] = []

        for shape in slide.shapes:
            # Charts
            if shape.has_chart:
                try:
                    charts.append(_extract_chart_metadata(shape, chart_idx))
                    chart_idx += 1
                except Exception as e:
                    logger.warning(f"Slide {slide_number}: Could not extract chart {chart_idx}: {e}")

            # Tables
            elif shape.has_table:
                try:
                    tables.append(_extract_table_metadata(shape, table_idx))
                    table_idx += 1
                except Exception as e:
                    logger.warning(f"Slide {slide_number}: Could not extract table {table_idx}: {e}")

            # Text (body)
            elif shape.has_text_frame and shape != slide.shapes.title:
                for para in shape.text_frame.paragraphs:
                    t = " ".join(r.text for r in para.runs).strip()
                    if t:
                        body_texts.append(t)

        all_texts, font_sizes = _collect_texts_and_fonts(slide)
        has_page_num = _detect_page_number(slide)
        has_source = _detect_source_reference(all_texts)

        # Render slide image
        image_b64: Optional[str] = None
        if render_images:
            try:
                image_b64 = _render_slide_to_base64(slide, prs)
            except Exception as e:
                logger.warning(f"Slide {slide_number}: Could not render image: {e}")

        # Layout name
        layout_name: Optional[str] = None
        try:
            layout_name = slide.slide_layout.name
        except Exception:
            pass

        slides_data.append(SlideData(
            slide_number=slide_number,
            title=title_text,
            body_texts=body_texts,
            all_texts=all_texts,
            font_sizes_pt=font_sizes,
            charts=charts,
            tables=tables,
            has_page_number=has_page_num,
            has_source_reference=has_source,
            image_base64=image_b64,
            layout_name=layout_name,
        ))

    has_slide_numbers = any(s.has_page_number for s in slides_data)

    return PPTProcessingResult(
        file_name=file_name,
        total_slides=len(slides_data),
        slides=slides_data,
        has_slide_numbers=has_slide_numbers,
        presentation_title=presentation_title,
    )


def _render_slide_to_base64(slide, prs, max_width: int = 1280) -> Optional[str]:
    """
    Render a slide to a base64-encoded PNG.

    Uses python-pptx's built-in thumbnail capability if available,
    otherwise falls back to a blank placeholder indicating images are unavailable
    without LibreOffice or a headless renderer.

    Note: Full rendering requires LibreOffice or a commercial library.
    This implementation exports slide XML thumbnail if available.
    """
    # python-pptx does not natively render slides to images.
    # We create a minimal representation using the slide's thumbnail from PPTX XML.
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Check if pptx has a thumbnail in its package
        thumbnail_part = None
        try:
            thumbnail_part = prs.part.thumbnail_part
        except Exception:
            pass

        if thumbnail_part is not None:
            img_bytes = thumbnail_part.blob
            img = Image.open(io.BytesIO(img_bytes))
        else:
            # Fallback: create a white slide image placeholder
            # In production, use LibreOffice: `libreoffice --headless --convert-to png`
            width_emu = prs.slide_width
            height_emu = prs.slide_height
            # Convert EMU to pixels at 96 DPI
            px_w = min(max_width, int(width_emu / 914400 * 96))
            px_h = int(height_emu / 914400 * 96 * (px_w / (width_emu / 914400 * 96)))
            img = Image.new("RGB", (px_w, px_h), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "[Slide render not available — install LibreOffice for full rendering]",
                      fill=(180, 180, 180))

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    except ImportError:
        logger.warning("Pillow not installed — slide images unavailable")
        return None
