"""
Excel (.xlsx) processor.

Extracts per-sheet:
- Text content (cell values, chart titles, axis labels)
- Chart metadata (chart types, axis settings, series info)
- Table/data structure metadata
- Sheet images (via openpyxl + Pillow for chart placeholders)
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import load_workbook
from ibcs_agent.processors.excel_table_metadata import SheetTableMetadata, extract_table_metadata
from openpyxl.chart import (
    AreaChart,
    BarChart,
    BubbleChart,
    DoughnutChart,
    LineChart,
    PieChart,
    RadarChart,
    ScatterChart,
    StockChart,
)
from openpyxl.chart.label import DataLabelList

logger = logging.getLogger(__name__)

SOURCE_KEYWORDS = ["quelle", "source", "stand:", "data:", "daten:", "basis:"]

# Map openpyxl chart class to IBCS type name
CHART_CLASS_MAP = {
    BarChart: "bar_or_column",
    LineChart: "line",
    PieChart: "pie",
    DoughnutChart: "doughnut",
    AreaChart: "area",
    ScatterChart: "scatter",
    BubbleChart: "bubble",
    RadarChart: "radar",
    StockChart: "stock",
}


@dataclass
class ExcelChartMetadata:
    """Extracted metadata from a single Excel chart."""

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
    has_gridlines: bool = False
    pie_slice_count: int = 0


@dataclass
class SheetData:
    """All extracted data from a single Excel sheet."""

    sheet_index: int          # 0-based
    sheet_name: str
    title: Optional[str]      # Largest font cell or first non-empty cell
    all_texts: List[str]
    charts: List[ExcelChartMetadata]
    has_source_reference: bool
    has_header_row: bool
    row_count: int
    col_count: int
    font_sizes_pt: List[float]
    image_base64: Optional[str] = None
    table_metadata: Optional[SheetTableMetadata] = None


@dataclass
class ExcelProcessingResult:
    """Result of processing an entire Excel file."""

    file_name: str
    total_sheets: int
    sheets: List[SheetData]


def _classify_chart(chart) -> Tuple[str, bool]:
    """Return (type_name, is_3d) for an openpyxl chart object."""
    is_3d = False
    for cls, name in CHART_CLASS_MAP.items():
        if isinstance(chart, cls):
            # openpyxl marks 3D charts via grouping or class name
            grouping = getattr(chart, "grouping", "") or ""
            if hasattr(chart, "__class__") and "3D" in chart.__class__.__name__:
                is_3d = True
            if "3D" in type(chart).__name__:
                is_3d = True
            return name, is_3d
    return "unknown", False


def _extract_chart_metadata(chart, index: int) -> ExcelChartMetadata:
    """Extract IBCS-relevant metadata from an openpyxl chart object."""
    chart_type, is_3d = _classify_chart(chart)

    # Title
    title: Optional[str] = None
    try:
        if chart.title:
            if hasattr(chart.title, "tx") and chart.title.tx:
                title = str(chart.title)
            else:
                title = str(chart.title).strip() or None
    except Exception:
        pass

    # Axes
    has_axis_title_x = False
    has_axis_title_y = False
    axis_min_y: Optional[float] = None
    axis_max_y: Optional[float] = None
    has_gridlines = False

    try:
        if hasattr(chart, "x_axis") and chart.x_axis:
            has_axis_title_x = bool(chart.x_axis.title)
        if hasattr(chart, "y_axis") and chart.y_axis:
            has_axis_title_y = bool(chart.y_axis.title)
            axis_min_y = chart.y_axis.scaling.min if chart.y_axis.scaling else None
            axis_max_y = chart.y_axis.scaling.max if chart.y_axis.scaling else None
            has_gridlines = chart.y_axis.majorGridlines is not None
    except Exception:
        pass

    # Series
    series_names: List[str] = []
    try:
        for s in chart.series:
            try:
                name = s.title.v if s.title and hasattr(s.title, "v") else str(s.title or "")
                series_names.append(name)
            except Exception:
                series_names.append("")
    except Exception:
        pass

    # Legend
    has_legend = False
    try:
        has_legend = chart.legend is not None
    except Exception:
        pass

    # Pie slice count (for E4 rule)
    pie_slice_count = 0
    if chart_type in ("pie", "doughnut"):
        pie_slice_count = len(series_names)

    return ExcelChartMetadata(
        index=index,
        chart_type=chart_type,
        is_3d=is_3d,
        title=title,
        has_axis_title_x=has_axis_title_x,
        has_axis_title_y=has_axis_title_y,
        axis_min_y=axis_min_y,
        axis_max_y=axis_max_y,
        series_count=len(series_names),
        series_names=series_names,
        has_legend=has_legend,
        has_gridlines=has_gridlines,
        pie_slice_count=pie_slice_count,
    )


def _extract_sheet_texts(ws) -> Tuple[List[str], List[float], Optional[str]]:
    """Extract all non-empty cell texts, font sizes, and infer a title."""
    texts: List[str] = []
    font_sizes: List[float] = []
    title_candidate: Optional[str] = None
    max_font_size = 0.0

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            val = str(cell.value).strip()
            if not val:
                continue
            texts.append(val)

            # Font size
            size = 10.0
            try:
                if cell.font and cell.font.size:
                    size = float(cell.font.size)
            except Exception:
                pass
            font_sizes.append(size)

            # Track largest font text as potential title
            if size > max_font_size:
                max_font_size = size
                title_candidate = val

    # Fallback: first non-empty cell in row 1
    if title_candidate is None and texts:
        title_candidate = texts[0]

    return texts, font_sizes, title_candidate


def _detect_source_reference(texts: List[str]) -> bool:
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in SOURCE_KEYWORDS)


def _has_header_row(ws) -> bool:
    """Heuristic: check if first row has bold or all-text cells."""
    first_row = list(ws.iter_rows(min_row=1, max_row=1))[0] if ws.max_row else []
    if not first_row:
        return False
    text_count = sum(1 for c in first_row if isinstance(c.value, str))
    return text_count >= len(first_row) // 2


def _render_sheet_placeholder(sheet_name: str) -> Optional[str]:
    """Create a minimal placeholder image for a sheet (charts are embedded in xlsx)."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (800, 600), color=(248, 248, 248))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), f"Sheet: {sheet_name}", fill=(100, 100, 100))
        draw.text(
            (20, 50),
            "[For visual chart analysis, export sheet as PDF or image]",
            fill=(180, 180, 180),
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        return None


def process_excel(
    file_content: bytes,
    file_name: str,
    render_images: bool = True,
) -> ExcelProcessingResult:
    """
    Process an Excel (.xlsx) file and extract all IBCS-relevant metadata.

    Args:
        file_content: Raw bytes of the .xlsx file
        file_name: Original filename
        render_images: Whether to generate placeholder sheet images

    Returns:
        ExcelProcessingResult with all sheet data
    """
    try:
        wb = load_workbook(io.BytesIO(file_content), data_only=True)
    except Exception as e:
        logger.error(f"Failed to open Excel file '{file_name}': {e}")
        raise

    sheets_data: List[SheetData] = []

    for sheet_idx, ws in enumerate(wb.worksheets):
        charts: List[ExcelChartMetadata] = []
        chart_idx = 0

        # Extract charts from the sheet
        for drawing in ws._charts:
            try:
                charts.append(_extract_chart_metadata(drawing, chart_idx))
                chart_idx += 1
            except Exception as e:
                logger.warning(f"Sheet '{ws.title}': Could not extract chart {chart_idx}: {e}")

        texts, font_sizes, title = _extract_sheet_texts(ws)
        has_source = _detect_source_reference(texts)
        has_header = _has_header_row(ws)

        image_b64: Optional[str] = None
        if render_images:
            image_b64 = _render_sheet_placeholder(ws.title)

        sheet_data = SheetData(
            sheet_index=sheet_idx,
            sheet_name=ws.title,
            title=title,
            all_texts=texts,
            charts=charts,
            has_source_reference=has_source,
            has_header_row=has_header,
            row_count=ws.max_row or 0,
            col_count=ws.max_column or 0,
            font_sizes_pt=font_sizes,
            image_base64=image_b64,
        )
        try:
            sheet_data.table_metadata = extract_table_metadata(ws)
        except Exception as e:
            logger.warning(f"Could not extract table metadata for '{ws.title}': {e}")
        sheets_data.append(sheet_data)

    return ExcelProcessingResult(
        file_name=file_name,
        total_sheets=len(sheets_data),
        sheets=sheets_data,
    )
