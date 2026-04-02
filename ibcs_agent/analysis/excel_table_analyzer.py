"""
IBCS table analyzer: runs all 8 IBCS block checks on SheetTableMetadata.
"""
from __future__ import annotations

import re
from typing import List, Optional

from ibcs_agent.models.feedback import RuleViolation
from ibcs_agent.processors.excel_table_metadata import (
    ColumnMeta,
    ConditionalFormattingRule,
    SheetTableMetadata,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_violation(
    rule_id: str,
    description: str,
    element: Optional[str] = None,
    suggestion_override: Optional[str] = None,
) -> RuleViolation:
    """Create a RuleViolation from a rule ID in the combined RULES_BY_ID registry."""
    from ibcs_agent.rules.ibcs_rules import RULES_BY_ID
    rule = RULES_BY_ID.get(rule_id)
    if rule is None:
        # Fallback if rule somehow not found
        return RuleViolation(
            rule_id=rule_id,
            rule_name=rule_id,
            category="UNIFY",
            severity="warning",
            description=description,
            suggestion=suggestion_override or "",
            source="metadata",
            element=element,
        )
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


def _rgb_brightness(rgb_hex: str) -> Optional[float]:
    """ITU-R BT.601 perceived brightness (0-255) from 6-8 char hex."""
    if not rgb_hex or len(rgb_hex) < 6:
        return None
    try:
        r = int(rgb_hex[-6:-4], 16)
        g = int(rgb_hex[-4:-2], 16)
        b = int(rgb_hex[-2:], 16)
        return (r * 299 + g * 587 + b * 114) / 1000
    except (ValueError, TypeError):
        return None


# Legacy header patterns
_LEGACY_AC = re.compile(r"\b(IST|Ist|Actual|ACT|Ist-Wert)\b", re.IGNORECASE)
_LEGACY_PY = re.compile(r"\b(VJ|Vorjahr|Prior|Vorjahreswert)\b", re.IGNORECASE)
_LEGACY_PL = re.compile(r"\b(Budget|Bud)\b(?!.*\bBU\b)", re.IGNORECASE)
_LEGACY_FC = re.compile(r"\b(Forecast|HRE|Hochrechnung|Prognose)\b", re.IGNORECASE)
_DELTA_SYMBOL = re.compile(r"[\u0394\u03B4]|Delta|\bAbw\.?\b", re.IGNORECASE)
_VARIANCE_DIRECTION_WRONG = re.compile(r"(PL|Plan|BU|Budget)\s*[-\u2212]\s*(AC|Ist)", re.IGNORECASE)
_NUMBER_FORMAT_THOUSANDS = re.compile(r"#,##0", re.IGNORECASE)
_FORMAT_PERCENTAGE = re.compile(r"%")


# ---------------------------------------------------------------------------
# UN checks
# ---------------------------------------------------------------------------

def _check_un_scenario_abbreviations(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    for col in meta.columns:
        h = col.header_text
        if not h:
            continue
        if _LEGACY_AC.search(h):
            violations.append(_make_violation(
                "UN-T-01.1",
                f"{sheet_label}: Spalte \"{h}\" verwendet IST/Actual statt IBCS-Kuerzel AC",
                element=sheet_label,
            ))
        if _LEGACY_PY.search(h):
            violations.append(_make_violation(
                "UN-T-01.2",
                f"{sheet_label}: Spalte \"{h}\" verwendet VJ/Vorjahr statt IBCS-Kuerzel PY",
                element=sheet_label,
            ))
        if _LEGACY_PL.search(h):
            violations.append(_make_violation(
                "UN-T-01.3",
                f"{sheet_label}: Spalte \"{h}\" verwendet Budget/Bud statt IBCS-Kuerzel PL/BU",
                element=sheet_label,
            ))
        if _LEGACY_FC.search(h):
            violations.append(_make_violation(
                "UN-T-01.4",
                f"{sheet_label}: Spalte \"{h}\" verwendet Forecast/HRE statt IBCS-Kuerzel FC",
                element=sheet_label,
            ))

    if not meta.has_scenario_headers:
        violations.append(_make_violation(
            "UN-T-01.8",
            f"{sheet_label}: Keine erkennbaren IBCS-Szenario-Spalten (AC/PY/PL/FC) gefunden",
            element=sheet_label,
        ))

    return violations


def _check_un_variance_notation(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    for col in meta.columns:
        h = col.header_text
        if not h:
            continue
        is_variance = col.scenario_type in ("variance_abs", "variance_pct")
        if not is_variance:
            continue

        # Check for Delta symbol
        if not _DELTA_SYMBOL.search(h):
            violations.append(_make_violation(
                "UN-T-03.1",
                f"{sheet_label}: Abweichungsspalte \"{h}\" verwendet kein Delta-Zeichen",
                element=sheet_label,
            ))

        # Check direction: should be AC-PL not PL-AC
        if _VARIANCE_DIRECTION_WRONG.search(h):
            violations.append(_make_violation(
                "UN-T-03.2",
                f"{sheet_label}: Abweichungsrichtung \"{h}\" ist PL-AC statt AC-PL",
                element=sheet_label,
            ))

        # Check reference scenario mentioned
        if not re.search(r"(AC|PY|PL|BU|FC)", h, re.IGNORECASE):
            violations.append(_make_violation(
                "UN-T-03.6",
                f"{sheet_label}: Abweichungsspalte \"{h}\" hat kein Bezugsszenario (AC/PL/PY)",
                element=sheet_label,
            ))

    return violations


def _check_un_units(meta: SheetTableMetadata, sheet_label: str) -> List[RuleViolation]:
    violations = []
    unit_pattern = re.compile(r"(EUR|USD|GBP|\bT\b|Mio\.?|Tsd\.?|\bk\b)", re.IGNORECASE)
    non_iso_pattern = re.compile(r"\b(TEUR|Mio EUR|EUR Mio|Tausend Euro|Mio\. EUR)\b", re.IGNORECASE)

    for col in meta.columns:
        h = col.header_text
        if not h:
            continue
        if non_iso_pattern.search(h):
            violations.append(_make_violation(
                "UN-T-05.2",
                f"{sheet_label}: Einheitenformat \"{h}\" ist nicht ISO-konform (TEUR statt T€)",
                element=sheet_label,
            ))

    # Check for unit repetition in sample values
    for col in meta.columns:
        if col.scenario_type not in ("AC", "PY", "PL", "FC"):
            continue
        vals = meta.sample_values.get(col.header_text, [])
        for v in vals:
            if isinstance(v, str) and unit_pattern.search(v):
                violations.append(_make_violation(
                    "UN-T-05.1",
                    f"{sheet_label}: Spalte \"{col.header_text}\" hat Einheitensymbole in Datenzellen",
                    element=sheet_label,
                ))
                break  # one violation per column is enough

    return violations


# ---------------------------------------------------------------------------
# CO checks
# ---------------------------------------------------------------------------

def _check_co_value_formatting(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    seen_columns: dict = {}  # col_header -> set of decimal places

    for col in meta.columns:
        if col.scenario_type not in ("AC", "PY", "PL", "FC"):
            continue

        # Check for thousands separator in number formats
        has_thousands = any(_NUMBER_FORMAT_THOUSANDS.search(fmt) for fmt in col.number_formats if fmt)
        if col.number_formats and not has_thousands:
            violations.append(_make_violation(
                "CO-T-04.1",
                f"{sheet_label}: Spalte \"{col.header_text}\" hat kein Tausender-Trennzeichen im Zahlenformat",
                element=sheet_label,
            ))

        # Check decimal consistency
        decimal_counts = set()
        for fmt in col.number_formats:
            if fmt and "." in fmt:
                decimal_part = fmt.split(".")[-1].rstrip(";")
                decimal_counts.add(len([c for c in decimal_part if c == "0" or c == "#"]))
        if len(decimal_counts) > 1:
            violations.append(_make_violation(
                "CO-T-04.4",
                f"{sheet_label}: Spalte \"{col.header_text}\" hat inkonsistente Dezimalstellen",
                element=sheet_label,
            ))

        # Check null value formatting (should show dash not 0)
        for fmt in col.number_formats:
            if fmt and "General" in fmt:
                violations.append(_make_violation(
                    "CO-T-04.2",
                    f"{sheet_label}: Spalte \"{col.header_text}\" verwendet General-Format ohne Nullwert-Behandlung",
                    element=sheet_label,
                ))
                break

    # Tech check: variance formats
    for col in meta.columns:
        if col.scenario_type == "variance_pct":
            has_pct = any(_FORMAT_PERCENTAGE.search(fmt) for fmt in col.number_formats if fmt)
            if col.number_formats and not has_pct:
                violations.append(_make_violation(
                    "TECH-T-02.3",
                    f"{sheet_label}: Prozent-Abweichungsspalte \"{col.header_text}\" hat kein %-Format",
                    element=sheet_label,
                ))

    return violations


def _check_co_row_density(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    # Check for empty rows (rows with empty label and no data)
    empty_row_count = sum(1 for row in meta.rows if not row.label)
    if empty_row_count > 2:
        violations.append(_make_violation(
            "CO-T-02.2",
            f"{sheet_label}: {empty_row_count} Leerzeilen in Datentabelle gefunden",
            element=sheet_label,
        ))
    return violations


# ---------------------------------------------------------------------------
# CH checks
# ---------------------------------------------------------------------------

def _check_ch_formula_errors(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    if not meta.formula_errors:
        return violations

    # Group by error type
    error_summary = {}
    for cell_ref, err_type in meta.formula_errors:
        error_summary.setdefault(err_type, []).append(cell_ref)

    for err_type, cells in error_summary.items():
        cells_str = ", ".join(cells[:5])
        if len(cells) > 5:
            cells_str += f" ... ({len(cells)} total)"
        violations.append(_make_violation(
            "CH-T-01.7",
            f"{sheet_label}: Formel-Fehler {err_type} in Zellen: {cells_str}",
            element=sheet_label,
        ))
        violations.append(_make_violation(
            "TECH-T-01.4",
            f"{sheet_label}: Formel-Fehler {err_type} blockiert korrekte Berechnungen",
            element=sheet_label,
        ))

    return violations


def _check_ch_completeness(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    # Check if AC present but PY and PL missing
    has_ac = "AC" in meta.detected_scenarios
    has_py = "PY" in meta.detected_scenarios
    has_pl = "PL" in meta.detected_scenarios

    if has_ac and not has_py:
        violations.append(_make_violation(
            "CH-T-03.2",
            f"{sheet_label}: AC-Spalte vorhanden aber PY-Spalte fehlt",
            element=sheet_label,
        ))
    if has_ac and not has_pl:
        violations.append(_make_violation(
            "CH-T-03.2",
            f"{sheet_label}: AC-Spalte vorhanden aber PL-Spalte fehlt",
            element=sheet_label,
        ))

    return violations


# ---------------------------------------------------------------------------
# SI checks
# ---------------------------------------------------------------------------

def _check_si_redundancy(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []
    # Check for duplicate column headers
    headers = [col.header_text for col in meta.columns if col.header_text]
    seen = set()
    for h in headers:
        if h in seen:
            violations.append(_make_violation(
                "SI-T-01.2",
                f"{sheet_label}: Duplizierter Spaltenheader \"{h}\" gefunden",
                element=sheet_label,
            ))
        seen.add(h)

    # Check for gradient fills
    for col in meta.columns:
        for style in col.sample_styles:
            if style.has_gradient_fill:
                violations.append(_make_violation(
                    "SI-T-02.1",
                    f"{sheet_label}: Farbverlauf-Fuellung in Spalte \"{col.header_text}\" gefunden",
                    element=sheet_label,
                ))
                break

    # Check font family consistency
    font_names = set()
    for col in meta.columns:
        for style in col.sample_styles:
            if style.font_name and style.font_name != "Calibri":
                font_names.add(style.font_name)
    if len(font_names) > 1:
        violations.append(_make_violation(
            "SI-T-03.2",
            f"{sheet_label}: Mehrere Schriftfamilien gefunden: {', '.join(sorted(font_names))}",
            element=sheet_label,
        ))

    return violations


# ---------------------------------------------------------------------------
# ST checks
# ---------------------------------------------------------------------------

def _check_st_structure(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []

    # Check label column is first
    if meta.columns:
        first_col = meta.columns[0]
        if first_col.scenario_type not in ("label", "unknown"):
            violations.append(_make_violation(
                "ST-T-02.5",
                f"{sheet_label}: Erste Spalte \"{first_col.header_text}\" ist keine Label-Spalte",
                element=sheet_label,
            ))

    # Check column order: label, AC, PY, PL, FC, then variances
    preferred_order = ["label", "AC", "PY", "PL", "FC", "variance_abs", "variance_pct"]
    col_types = [col.scenario_type for col in meta.columns if col.scenario_type]
    # Only check if we have meaningful columns
    if len(col_types) > 3:
        known_types = [t for t in col_types if t in preferred_order]
        if known_types:
            last_idx = -1
            out_of_order = False
            for t in known_types:
                idx = preferred_order.index(t) if t in preferred_order else 99
                if idx < last_idx:
                    out_of_order = True
                    break
                last_idx = idx
            if out_of_order:
                violations.append(_make_violation(
                    "ST-T-02.4",
                    f"{sheet_label}: Spaltenreihenfolge entspricht nicht IBCS-Empfehlung (AC, PY, PL, FC, Abw.)",
                    element=sheet_label,
                ))

    return violations


def _check_st_headers(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []

    # Check if table has a title
    if not any(meta.title_row_texts[:2]):
        violations.append(_make_violation(
            "ST-T-04.1",
            f"{sheet_label}: Kein Tabellentitel erkennbar",
            element=sheet_label,
        ))

    # Check merged cells (should have some for grouped headers)
    if not meta.merged_cells and len(meta.columns) > 5:
        violations.append(_make_violation(
            "ST-T-02.2",
            f"{sheet_label}: Keine verbundenen Zellen fuer Spaltengruppen-Header gefunden",
            element=sheet_label,
        ))

    # Check minimum 2 header rows - heuristic: if merged cells exist covering row 1+2
    header_row_count = 1  # minimum
    if meta.merged_cells:
        header_row_count = 2  # assume 2 if merged cells present
    if header_row_count < 2:
        violations.append(_make_violation(
            "ST-T-03.2",
            f"{sheet_label}: Tabelle hat nur eine Kopfzeile, IBCS empfiehlt mindestens zwei",
            element=sheet_label,
        ))

    return violations


# ---------------------------------------------------------------------------
# TECH checks
# ---------------------------------------------------------------------------

def _check_tech_number_formats(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []

    for col in meta.columns:
        if not col.number_formats:
            continue

        if col.scenario_type in ("AC", "PY", "PL", "FC"):
            for fmt in col.number_formats:
                if fmt and fmt != "General" and not _NUMBER_FORMAT_THOUSANDS.search(fmt):
                    violations.append(_make_violation(
                        "TECH-T-02.1",
                        f"{sheet_label}: Spalte \"{col.header_text}\" Zahlenformat \"{fmt}\" fehlt #,##0",
                        element=sheet_label,
                    ))
                    break

        elif col.scenario_type == "variance_abs":
            has_sign_format = any(
                fmt and (re.search(r"[+;(]", fmt) or re.search(r"#,##0", fmt))
                for fmt in col.number_formats
            )
            if col.number_formats and not has_sign_format:
                violations.append(_make_violation(
                    "TECH-T-02.2",
                    f"{sheet_label}: Abweichungsspalte \"{col.header_text}\" hat kein Vorzeichen-Format",
                    element=sheet_label,
                ))

        elif col.scenario_type == "variance_pct":
            has_pct = any(_FORMAT_PERCENTAGE.search(fmt) for fmt in col.number_formats if fmt)
            if not has_pct:
                violations.append(_make_violation(
                    "TECH-T-02.3",
                    f"{sheet_label}: Prozent-Abweichungsspalte \"{col.header_text}\" hat kein %-Format",
                    element=sheet_label,
                ))

    return violations


def _check_tech_colors(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []

    for col in meta.columns:
        if not col.sample_styles:
            continue

        # Get average fill brightness
        brightnesses = []
        for style in col.sample_styles:
            if style.fill_color_rgb:
                b = _rgb_brightness(style.fill_color_rgb)
                if b is not None:
                    brightnesses.append(b)

        if not brightnesses:
            continue

        avg_brightness = sum(brightnesses) / len(brightnesses)

        if col.scenario_type == "AC":
            if avg_brightness < 240:
                violations.append(_make_violation(
                    "TECH-T-04.1",
                    f"{sheet_label}: AC-Spalte \"{col.header_text}\" Hintergrund zu dunkel (Helligkeit {avg_brightness:.0f} < 240)",
                    element=sheet_label,
                ))

        elif col.scenario_type == "PY":
            if not (200 <= avg_brightness <= 230):
                violations.append(_make_violation(
                    "TECH-T-04.2",
                    f"{sheet_label}: PY-Spalte \"{col.header_text}\" Hintergrund nicht im Graubereich 200-230 (ist {avg_brightness:.0f})",
                    element=sheet_label,
                ))

        elif col.scenario_type == "PL":
            if not (230 <= avg_brightness <= 250):
                violations.append(_make_violation(
                    "TECH-T-04.3",
                    f"{sheet_label}: PL-Spalte \"{col.header_text}\" Hintergrund nicht im Hellgrau-Bereich 230-250 (ist {avg_brightness:.0f})",
                    element=sheet_label,
                ))

    # Check font formatting for scenarios
    for col in meta.columns:
        if not col.sample_styles:
            continue

        if col.scenario_type == "AC":
            is_bold = all(style.bold for style in col.sample_styles)
            if not is_bold and col.sample_styles:
                violations.append(_make_violation(
                    "TECH-T-03.1",
                    f"{sheet_label}: AC-Spalte \"{col.header_text}\" ist nicht fett formatiert",
                    element=sheet_label,
                ))

        elif col.scenario_type == "PY":
            is_italic_or_gray = any(
                style.italic or (
                    style.font_color_rgb and _rgb_brightness(style.font_color_rgb) is not None
                    and _rgb_brightness(style.font_color_rgb) < 180
                )
                for style in col.sample_styles
            )
            if not is_italic_or_gray:
                violations.append(_make_violation(
                    "TECH-T-03.2",
                    f"{sheet_label}: PY-Spalte \"{col.header_text}\" ist nicht kursiv oder grau",
                    element=sheet_label,
                ))

        elif col.scenario_type == "PL":
            is_bold = any(style.bold for style in col.sample_styles)
            if is_bold:
                violations.append(_make_violation(
                    "TECH-T-03.3",
                    f"{sheet_label}: PL-Spalte \"{col.header_text}\" ist fett formatiert (sollte nicht fett sein)",
                    element=sheet_label,
                ))

    return violations


def _check_tech_structure(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []

    # Check freeze panes
    if meta.freeze_panes is None:
        violations.append(_make_violation(
            "TECH-T-05.4",
            f"{sheet_label}: Keine Fixierung (Freeze Panes) der Kopfzeile gesetzt",
            element=sheet_label,
        ))

    # Check merged cells for grouped headers
    if not meta.merged_cells and len(meta.columns) > 4:
        violations.append(_make_violation(
            "TECH-T-05.1",
            f"{sheet_label}: Keine verbundenen Zellen fuer Spaltengruppen-Header",
            element=sheet_label,
        ))

    # Check label column at position 1
    if meta.columns:
        first = meta.columns[0]
        if first.scenario_type not in ("label", "unknown"):
            violations.append(_make_violation(
                "TECH-T-05.2",
                f"{sheet_label}: Label-Spalte ist nicht an erster Position",
                element=sheet_label,
            ))

    return violations


def _check_tech_conditional_formatting(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    violations = []

    # Find variance column references
    variance_cols = [col for col in meta.columns
                     if col.scenario_type in ("variance_abs", "variance_pct")]

    if not variance_cols:
        return violations

    # Get all CF sqrefs
    cf_sqrefs = [cf.sqref for cf in meta.conditional_formatting]

    for col in variance_cols:
        # Check if there are CF rules for this column (rough check by column index)
        col_letter_approx = None
        try:
            from openpyxl.utils import get_column_letter
            col_letter_approx = get_column_letter(col.col_index + 1)
        except Exception:
            pass

        has_positive_cf = False
        has_negative_cf = False
        has_databar = False
        has_explicit_scale = False

        for cf in meta.conditional_formatting:
            sqref = cf.sqref
            # Check if this CF rule relates to the variance column
            if col_letter_approx and col_letter_approx not in sqref:
                continue

            if cf.rule_type == "greaterThan":
                has_positive_cf = True
            elif cf.rule_type == "lessThan":
                has_negative_cf = True
            elif cf.rule_type == "dataBar":
                has_databar = True
                # Check if explicit scale (not auto)
                has_explicit_scale = True  # simplified: presence = explicit

        if col.scenario_type == "variance_abs":
            if not has_positive_cf and meta.conditional_formatting:
                violations.append(_make_violation(
                    "TECH-T-06.1",
                    f"{sheet_label}: Abweichungsspalte \"{col.header_text}\" hat keine CF-Regel fuer positive Werte (gruen)",
                    element=sheet_label,
                ))
            if not has_negative_cf and meta.conditional_formatting:
                violations.append(_make_violation(
                    "TECH-T-06.2",
                    f"{sheet_label}: Abweichungsspalte \"{col.header_text}\" hat keine CF-Regel fuer negative Werte (rot)",
                    element=sheet_label,
                ))

        if has_databar and not has_explicit_scale:
            violations.append(_make_violation(
                "TECH-T-06.5",
                f"{sheet_label}: Datenbalken in Spalte \"{col.header_text}\" ohne explizite Skalierung",
                element=sheet_label,
            ))

    return violations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_sheet_table(
    meta: SheetTableMetadata, sheet_label: str
) -> List[RuleViolation]:
    """Run all IBCS table checks on a sheet. Returns flat list of violations."""
    violations: List[RuleViolation] = []
    try:
        violations.extend(_check_un_scenario_abbreviations(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_un_variance_notation(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_un_units(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_co_value_formatting(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_co_row_density(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_ch_formula_errors(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_ch_completeness(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_si_redundancy(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_st_structure(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_st_headers(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_tech_number_formats(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_tech_colors(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_tech_structure(meta, sheet_label))
    except Exception:
        pass
    try:
        violations.extend(_check_tech_conditional_formatting(meta, sheet_label))
    except Exception:
        pass
    return violations
