"""
Metadata-based IBCS analyzer.

Runs purely structural/text-based IBCS checks without calling any AI model.
Works on the output of the three processors (PPT, PDF, Excel).

Returns a list of RuleViolation objects per page/slide/sheet.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Union

from ibcs_agent.models.feedback import RuleViolation
from ibcs_agent.rules.ibcs_rules import RULES_BY_ID, IBCSRule

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

INSIGHT_TITLE_PATTERN = re.compile(
    r"(steigt|sinkt|wächst|nimmt zu|nimmt ab|erhöht|reduziert|übertrifft|"
    r"erreicht|liegt|beträgt|verbessert|verschlechtert|verdoppelt|halbiert|"
    r"increases|decreases|grows|drops|exceeds|reaches|improves|rises|falls)",
    re.IGNORECASE,
)

TIME_PATTERN = re.compile(
    r"\b(jan|feb|mär|apr|mai|jun|jul|aug|sep|okt|nov|dez|"
    r"q[1-4]|h[12]|20\d\d|19\d\d|ytd|mtd|fy|gj)\b",
    re.IGNORECASE,
)

UNIT_PATTERN = re.compile(
    r"(€|eur|usd|\$|£|%|mio|mrd|tsd|k\b|bn\b|m\b|million|billion|tausend|hundert|stück|pcs)",
    re.IGNORECASE,
)


def _make_violation(
    rule_id: str,
    description: str,
    element: Optional[str] = None,
    suggestion_override: Optional[str] = None,
) -> RuleViolation:
    rule: IBCSRule = RULES_BY_ID[rule_id]
    return RuleViolation(
        rule_id=rule.id,
        rule_name=rule.name,
        category=rule.category,
        severity=rule.severity,
        description=description,
        suggestion=suggestion_override or rule.suggestion_template,
        source="metadata",
        element=element,
    )


# ---------------------------------------------------------------------------
# Title checks (S1, S2)
# ---------------------------------------------------------------------------

def check_title_insight(title: Optional[str], element: str) -> List[RuleViolation]:
    violations = []
    if not title:
        violations.append(_make_violation(
            "S1",
            f"{element}: Kein Titel vorhanden. Ein Aussage-Titel fehlt.",
            element=element,
        ))
        return violations

    # S1: Does the title contain a verb / insight?
    if not INSIGHT_TITLE_PATTERN.search(title):
        violations.append(_make_violation(
            "S1",
            f"{element}: Titel '{title}' enthält keine Aussage/kein Verb. "
            "Es handelt sich um ein reines Thema-Label.",
            element=element,
        ))

    # S2: Time period and unit
    has_time = bool(TIME_PATTERN.search(title))
    has_unit = bool(UNIT_PATTERN.search(title))
    if not has_time or not has_unit:
        missing = []
        if not has_time:
            missing.append("Zeitraum")
        if not has_unit:
            missing.append("Einheit")
        violations.append(_make_violation(
            "S2",
            f"{element}: Titel '{title}' fehlt: {', '.join(missing)}.",
            element=element,
        ))

    return violations


# ---------------------------------------------------------------------------
# Axis checks (CK1, U3)
# ---------------------------------------------------------------------------

def check_axis_zero(axis_min: Optional[float], chart_type: str, element: str) -> List[RuleViolation]:
    violations = []
    bar_types = {"bar", "column", "bar_stacked", "column_stacked", "bar_or_column"}
    if chart_type not in bar_types:
        return violations

    if axis_min is not None and axis_min != 0.0:
        violations.append(_make_violation(
            "CK1",
            f"{element}: Y-Achse beginnt bei {axis_min}, nicht bei 0. "
            f"Bei {chart_type}-Charts ist das eine visuelle Verzerrung.",
            element=element,
        ))
    return violations


# ---------------------------------------------------------------------------
# 3D chart check (CK2, SI4)
# ---------------------------------------------------------------------------

def check_3d_chart(is_3d: bool, chart_type: str, element: str) -> List[RuleViolation]:
    if is_3d:
        return [_make_violation(
            "CK2",
            f"{element}: Chart ist als 3D-Variante ({chart_type}) dargestellt. "
            "3D-Effekte verzerren Datenwerte und sind nach IBCS nicht erlaubt.",
            element=element,
        )]
    return []


# ---------------------------------------------------------------------------
# Pie chart check (E4)
# ---------------------------------------------------------------------------

def check_pie_chart(chart_type: str, series_count: int, element: str) -> List[RuleViolation]:
    if chart_type in ("pie", "doughnut") and series_count > 2:
        return [_make_violation(
            "E4",
            f"{element}: Tortendiagramm mit {series_count} Segmenten. "
            "IBCS erlaubt Torten-/Donut-Charts nur für 2 Segmente.",
            element=element,
        )]
    return []


# ---------------------------------------------------------------------------
# Font size variety check (SI3)
# ---------------------------------------------------------------------------

def check_font_sizes(font_sizes: List[float], page_label: str) -> List[RuleViolation]:
    if not font_sizes:
        return []
    unique_sizes = set(round(s) for s in font_sizes)
    if len(unique_sizes) > 4:
        sizes_str = ", ".join(str(s) for s in sorted(unique_sizes))
        return [_make_violation(
            "SI3",
            f"{page_label}: {len(unique_sizes)} verschiedene Schriftgrößen gefunden ({sizes_str} pt). "
            "IBCS empfiehlt maximal 3 Schriftgrößen pro Seite.",
            element=page_label,
        )]
    return []


# ---------------------------------------------------------------------------
# Page number / source checks (ST3, ST4)
# ---------------------------------------------------------------------------

def check_page_number(has_page_number: bool, page_label: str) -> List[RuleViolation]:
    if not has_page_number:
        return [_make_violation(
            "ST3",
            f"{page_label}: Keine Seitennummer gefunden.",
            element=page_label,
        )]
    return []


def check_source_reference(has_source: bool, page_label: str) -> List[RuleViolation]:
    if not has_source:
        return [_make_violation(
            "ST4",
            f"{page_label}: Keine Quellenangabe gefunden.",
            element=page_label,
        )]
    return []


# ---------------------------------------------------------------------------
# Header row check for tables (ST2 heuristic)
# ---------------------------------------------------------------------------

def check_title_hierarchy(title: Optional[str], font_sizes: List[float], page_label: str) -> List[RuleViolation]:
    violations = []
    if not title:
        violations.append(_make_violation(
            "ST2",
            f"{page_label}: Kein Haupttitel erkennbar. Klare Hierarchie fehlt.",
            element=page_label,
        ))
    return violations


# ---------------------------------------------------------------------------
# Main entry points for each file type
# ---------------------------------------------------------------------------

def analyze_pptx_metadata(processing_result: Any) -> List[List[RuleViolation]]:
    """
    Run all metadata-based IBCS checks on a PPTProcessingResult.

    Returns a list of violations per slide (indexed 0-based).
    """
    from ibcs_agent.processors.ppt_processor import PPTProcessingResult, SlideData

    result: PPTProcessingResult = processing_result
    per_slide_violations: List[List[RuleViolation]] = []

    # Global: check if any slide has page numbers (ST3)
    if not result.has_slide_numbers:
        # Will be reported on slide 1 only to avoid duplication
        pass

    for slide in result.slides:
        violations: List[RuleViolation] = []
        page_label = f"Folie {slide.slide_number}"

        # Title checks
        violations.extend(check_title_insight(slide.title, page_label))

        # Font variety
        violations.extend(check_font_sizes(slide.font_sizes_pt, page_label))

        # Page number (ST3) — report on slide 1 if missing globally
        if slide.slide_number == 1 and not result.has_slide_numbers:
            violations.extend(check_page_number(False, "Präsentation"))

        # Source reference (ST4)
        violations.extend(check_source_reference(slide.has_source_reference, page_label))

        # Title hierarchy (ST2)
        violations.extend(check_title_hierarchy(slide.title, slide.font_sizes_pt, page_label))

        # Per-chart checks
        for chart in slide.charts:
            chart_label = f"Folie {slide.slide_number} – Chart {chart.index + 1}"

            # Chart title as insight (S1, S2)
            violations.extend(check_title_insight(chart.title, chart_label))

            # Axis starts at zero (CK1)
            violations.extend(check_axis_zero(chart.axis_min_y, chart.chart_type, chart_label))

            # 3D check (CK2)
            violations.extend(check_3d_chart(chart.is_3d, chart.chart_type, chart_label))

            # Pie chart (E4)
            violations.extend(check_pie_chart(chart.chart_type, chart.series_count, chart_label))

        per_slide_violations.append(violations)

    return per_slide_violations


def analyze_pdf_metadata(processing_result: Any) -> List[List[RuleViolation]]:
    """
    Run all metadata-based IBCS checks on a PDFProcessingResult.

    Returns a list of violations per page (indexed 0-based).
    """
    result = processing_result
    per_page_violations: List[List[RuleViolation]] = []

    for page in result.pages:
        violations: List[RuleViolation] = []
        page_label = f"Seite {page.page_number}"

        # Title / insight
        violations.extend(check_title_insight(page.title, page_label))

        # Font variety
        violations.extend(check_font_sizes(page.font_sizes_pt, page_label))

        # Page numbers (reported once on page 1)
        if page.page_number == 1 and not result.has_page_numbers:
            violations.extend(check_page_number(False, "Dokument"))

        # Source reference
        violations.extend(check_source_reference(page.has_source_reference, page_label))

        # Hierarchy
        violations.extend(check_title_hierarchy(page.title, page.font_sizes_pt, page_label))

        per_page_violations.append(violations)

    return per_page_violations


def analyze_excel_metadata(processing_result: Any) -> List[List[RuleViolation]]:
    """
    Run all metadata-based IBCS checks on an ExcelProcessingResult.

    Returns a list of violations per sheet (indexed 0-based).
    """
    result = processing_result
    per_sheet_violations: List[List[RuleViolation]] = []

    for sheet in result.sheets:
        violations: List[RuleViolation] = []
        sheet_label = f"Sheet '{sheet.sheet_name}'"

        # Title / insight
        violations.extend(check_title_insight(sheet.title, sheet_label))

        # Font variety
        violations.extend(check_font_sizes(sheet.font_sizes_pt, sheet_label))

        # Source reference
        violations.extend(check_source_reference(sheet.has_source_reference, sheet_label))

        # Per-chart checks
        for chart in sheet.charts:
            chart_label = f"Sheet '{sheet.sheet_name}' – Chart {chart.index + 1}"

            violations.extend(check_title_insight(chart.title, chart_label))
            violations.extend(check_axis_zero(chart.axis_min_y, chart.chart_type, chart_label))
            violations.extend(check_3d_chart(chart.is_3d, chart.chart_type, chart_label))
            violations.extend(check_pie_chart(chart.chart_type, chart.series_count, chart_label))

        per_sheet_violations.append(violations)

    return per_sheet_violations
