"""
Extended metadata dataclasses for deep IBCS Excel table inspection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CellStyle:
    bold: bool = False
    italic: bool = False
    font_color_rgb: Optional[str] = None   # e.g. "FF0000"
    fill_color_rgb: Optional[str] = None   # e.g. "FFFFFF"
    number_format: str = "General"
    font_size: float = 10.0
    font_name: str = "Calibri"
    has_gradient_fill: bool = False


@dataclass
class ColumnMeta:
    col_index: int           # 0-based
    header_text: str         # e.g. "AC", "DeltaPL", "Q1 2024"
    scenario_type: Optional[str]   # "AC","PY","PL","FC","variance_abs","variance_pct","label","unknown"
    width: Optional[float]
    sample_styles: List[CellStyle] = field(default_factory=list)
    number_formats: List[str] = field(default_factory=list)  # unique formats


@dataclass
class RowMeta:
    row_index: int
    indent_level: int        # estimated from leading spaces in label cell
    is_sum_row: bool         # estimated from bold font + position
    label: str
    row_style: Optional[CellStyle] = None


@dataclass
class ConditionalFormattingRule:
    sqref: str               # e.g. "D5:D30"
    rule_type: str           # "greaterThan","lessThan","dataBar","colorScale"
    operator: Optional[str]
    formula: Optional[str]
    fill_color: Optional[str]
    font_color: Optional[str]


@dataclass
class SheetTableMetadata:
    """Extended metadata for deep IBCS table checking."""
    sheet_name: str
    columns: List[ColumnMeta]
    rows: List[RowMeta]
    merged_cells: List[str]          # e.g. ["A1:D1", "E1:G1"]
    freeze_panes: Optional[str]      # e.g. "B5"
    conditional_formatting: List[ConditionalFormattingRule]
    title_row_texts: List[str]       # first 3 rows text
    has_scenario_headers: bool       # True if AC/PY/PL detected in headers
    detected_scenarios: List[str]    # e.g. ["AC", "PY", "PL"]
    formula_errors: List[Tuple[str, str]]   # [(cell_ref, error_type), ...]
    sample_values: Dict[str, List]   # col_header -> first 5 values


# ---------------------------------------------------------------------------
# Scenario detection patterns
# ---------------------------------------------------------------------------

# Patterns that are IBCS-correct (exact match preferred) or legacy (flag as violation)
_AC_CORRECT = re.compile(r"\bAC\b", re.IGNORECASE)
_AC_LEGACY = re.compile(r"\b(IST|Ist|Actual|ACT|Ist-Wert)\b", re.IGNORECASE)

_PY_CORRECT = re.compile(r"\bPY\b", re.IGNORECASE)
_PY_LEGACY = re.compile(r"\b(VJ|Vorjahr|Prior|Vorjahreswert)\b", re.IGNORECASE)

_PL_CORRECT = re.compile(r"\b(PL|BU)\b", re.IGNORECASE)
_PL_LEGACY = re.compile(r"\b(Budget|Bud|Plan|Planung)\b", re.IGNORECASE)

_FC_CORRECT = re.compile(r"\bFC\b", re.IGNORECASE)
_FC_LEGACY = re.compile(r"\b(Forecast|HRE|Hochrechnung|Prognose)\b", re.IGNORECASE)

_VAR_ABS = re.compile(r"(\u0394|Delta|Abw\.?)((?!%)[^%])*$", re.IGNORECASE)
_VAR_PCT = re.compile(r"(%|Prozent).*(\u0394|Delta|Abw\.?)|"
                       r"(\u0394|Delta|Abw\.?).*%", re.IGNORECASE)

_FORMULA_ERRORS = ("#REF!", "#DIV/0!", "#NAME?", "#VALUE!", "#N/A", "#NULL!", "#NUM!")

_BRIGHTNESS_THRESHOLD_WHITE = 240   # AC columns
_BRIGHTNESS_THRESHOLD_PY_MIN = 200  # PY columns lower bound
_BRIGHTNESS_THRESHOLD_PY_MAX = 230  # PY columns upper bound
_BRIGHTNESS_THRESHOLD_PL_MIN = 230  # PL columns lower bound
_BRIGHTNESS_THRESHOLD_PL_MAX = 250  # PL columns upper bound


def _classify_scenario(header: str) -> str:
    """Heuristic: classify column header as scenario type."""
    h = header.strip()

    # Variance percentage first (more specific)
    if _VAR_PCT.search(h):
        return "variance_pct"

    # Variance absolute
    if _VAR_ABS.search(h):
        return "variance_abs"

    # Exact IBCS keywords
    if _AC_CORRECT.search(h):
        return "AC"
    if _PY_CORRECT.search(h):
        return "PY"
    if _PL_CORRECT.search(h):
        return "PL"
    if _FC_CORRECT.search(h):
        return "FC"

    # Legacy (also classify but will trigger violation)
    if _AC_LEGACY.search(h):
        return "AC"
    if _PY_LEGACY.search(h):
        return "PY"
    if _PL_LEGACY.search(h):
        return "PL"
    if _FC_LEGACY.search(h):
        return "FC"

    return "unknown"


def _rgb_brightness(rgb_hex: str) -> Optional[float]:
    """Return ITU-R BT.601 perceived brightness for a 6-char hex string."""
    if not rgb_hex or len(rgb_hex) < 6:
        return None
    try:
        r = int(rgb_hex[-6:-4], 16)
        g = int(rgb_hex[-4:-2], 16)
        b = int(rgb_hex[-2:], 16)
        return (r * 299 + g * 587 + b * 114) / 1000
    except ValueError:
        return None


def _get_cell_style(cell) -> CellStyle:
    """Extract CellStyle from an openpyxl cell, handling None gracefully."""
    style = CellStyle()
    try:
        if cell.font:
            style.bold = bool(cell.font.bold)
            style.italic = bool(cell.font.italic)
            if cell.font.size:
                style.font_size = float(cell.font.size)
            if cell.font.name:
                style.font_name = str(cell.font.name)
            if cell.font.color and cell.font.color.rgb:
                style.font_color_rgb = str(cell.font.color.rgb)
    except Exception:
        pass

    try:
        if cell.fill and cell.fill.fill_type not in (None, "none"):
            ftype = cell.fill.fill_type
            if ftype == "gradient":
                style.has_gradient_fill = True
            elif ftype == "solid":
                fg = cell.fill.fgColor
                if fg and fg.rgb and fg.rgb != "00000000":
                    style.fill_color_rgb = str(fg.rgb)
    except Exception:
        pass

    try:
        if cell.number_format:
            style.number_format = str(cell.number_format)
    except Exception:
        pass

    return style


def extract_table_metadata(ws, max_rows: int = 200) -> SheetTableMetadata:
    """Extract deep IBCS-relevant metadata from an openpyxl worksheet."""

    # --- Title rows (first 3 rows as text) ---
    title_row_texts: List[str] = []
    for row_idx in range(1, 4):
        texts = []
        for cell in ws[row_idx] if ws.max_row and ws.max_row >= row_idx else []:
            if cell.value is not None:
                texts.append(str(cell.value).strip())
        title_row_texts.append(" | ".join(filter(None, texts)))

    # --- Detect header row (first row with mostly text) ---
    header_row_idx = 1
    for candidate in range(1, min(6, (ws.max_row or 1) + 1)):
        row_cells = list(ws.iter_rows(min_row=candidate, max_row=candidate))[0]
        text_cells = sum(1 for c in row_cells if isinstance(c.value, str) and c.value.strip())
        if text_cells >= max(1, len(row_cells) // 3):
            header_row_idx = candidate
            break

    # --- Build column metadata ---
    columns: List[ColumnMeta] = []
    detected_scenarios: List[str] = []

    if ws.max_column:
        header_cells = list(ws.iter_rows(
            min_row=header_row_idx, max_row=header_row_idx,
            min_col=1, max_col=ws.max_column
        ))[0]

        for col_idx, hcell in enumerate(header_cells):
            header_text = str(hcell.value).strip() if hcell.value is not None else ""
            scenario = _classify_scenario(header_text) if header_text else "unknown"

            # Column width
            col_letter = hcell.column_letter
            width = None
            try:
                cd = ws.column_dimensions.get(col_letter)
                if cd:
                    width = cd.width
            except Exception:
                pass

            # Sample styles from data rows (up to 5)
            sample_styles: List[CellStyle] = []
            number_formats: List[str] = []
            data_start = header_row_idx + 1
            sample_values: List = []

            for r in range(data_start, min(data_start + 5, (ws.max_row or data_start) + 1)):
                try:
                    cell = ws.cell(row=r, column=col_idx + 1)
                    style = _get_cell_style(cell)
                    sample_styles.append(style)
                    if style.number_format not in number_formats:
                        number_formats.append(style.number_format)
                    if cell.value is not None:
                        sample_values.append(cell.value)
                except Exception:
                    pass

            col_meta = ColumnMeta(
                col_index=col_idx,
                header_text=header_text,
                scenario_type=scenario if scenario != "unknown" else (
                    "label" if col_idx == 0 else "unknown"
                ),
                width=width,
                sample_styles=sample_styles,
                number_formats=number_formats,
            )
            columns.append(col_meta)

            if scenario in ("AC", "PY", "PL", "FC") and scenario not in detected_scenarios:
                detected_scenarios.append(scenario)

    has_scenario_headers = bool(detected_scenarios)

    # --- Build row metadata ---
    rows: List[RowMeta] = []
    data_start = header_row_idx + 1
    label_col = 1  # Usually first column

    for row_idx in range(data_start, min(data_start + max_rows, (ws.max_row or data_start) + 1)):
        try:
            label_cell = ws.cell(row=row_idx, column=label_col)
            label = str(label_cell.value).strip() if label_cell.value is not None else ""

            # Estimate indent level from leading spaces
            raw_label = str(label_cell.value) if label_cell.value is not None else ""
            indent = len(raw_label) - len(raw_label.lstrip())
            indent_level = indent // 2  # 2 spaces per level

            # Sum row heuristic: bold label + typically short/starts with capital
            style = _get_cell_style(label_cell)
            is_sum = style.bold and bool(label)

            rows.append(RowMeta(
                row_index=row_idx,
                indent_level=indent_level,
                is_sum_row=is_sum,
                label=label,
                row_style=style,
            ))
        except Exception:
            pass

    # --- Merged cells ---
    merged: List[str] = []
    try:
        for rng in ws.merged_cells.ranges:
            merged.append(str(rng))
    except Exception:
        pass

    # --- Freeze panes ---
    freeze_panes: Optional[str] = None
    try:
        if ws.freeze_panes:
            freeze_panes = str(ws.freeze_panes)
    except Exception:
        pass

    # --- Conditional formatting ---
    cf_rules: List[ConditionalFormattingRule] = []
    try:
        for sqref, rules in ws.conditional_formatting._cf_rules.items():
            for rule in rules:
                rtype = getattr(rule, "type", "unknown") or "unknown"
                operator = getattr(rule, "operator", None)
                formula = None
                try:
                    formulas = getattr(rule, "formula", None)
                    if formulas:
                        formula = str(formulas[0]) if hasattr(formulas, "__iter__") else str(formulas)
                except Exception:
                    pass

                fill_color = None
                font_color = None
                try:
                    if rule.dxf and rule.dxf.fill:
                        fg = rule.dxf.fill.fgColor
                        if fg and fg.rgb:
                            fill_color = str(fg.rgb)
                except Exception:
                    pass
                try:
                    if rule.dxf and rule.dxf.font and rule.dxf.font.color:
                        font_color = str(rule.dxf.font.color.rgb)
                except Exception:
                    pass

                cf_rules.append(ConditionalFormattingRule(
                    sqref=str(sqref),
                    rule_type=rtype,
                    operator=operator,
                    formula=formula,
                    fill_color=fill_color,
                    font_color=font_color,
                ))
    except Exception:
        pass

    # --- Formula errors ---
    formula_errors: List[Tuple[str, str]] = []
    for row in ws.iter_rows(min_row=1, max_row=min(max_rows, ws.max_row or 1)):
        for cell in row:
            if isinstance(cell.value, str):
                for err in _FORMULA_ERRORS:
                    if cell.value.startswith(err):
                        formula_errors.append((cell.coordinate, cell.value))
                        break

    # --- Sample values per column ---
    sample_values_map: Dict[str, List] = {}
    for col in columns:
        key = col.header_text or f"col_{col.col_index}"
        vals = []
        for r in range(header_row_idx + 1, min(header_row_idx + 6, (ws.max_row or header_row_idx) + 1)):
            try:
                cell = ws.cell(row=r, column=col.col_index + 1)
                if cell.value is not None:
                    vals.append(cell.value)
            except Exception:
                pass
        sample_values_map[key] = vals

    return SheetTableMetadata(
        sheet_name=ws.title,
        columns=columns,
        rows=rows,
        merged_cells=merged,
        freeze_panes=freeze_panes,
        conditional_formatting=cf_rules,
        title_row_texts=title_row_texts,
        has_scenario_headers=has_scenario_headers,
        detected_scenarios=detected_scenarios,
        formula_errors=formula_errors,
        sample_values=sample_values_map,
    )
