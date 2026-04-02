"""
Azure AI Foundry Agent tool implementations.

These functions are registered as tools on the Azure AI Foundry Agent.
They orchestrate the full IBCS analysis pipeline:
1. Detect file type
2. Run appropriate processor (PPT/PDF/Excel)
3. Run metadata analysis
4. Run visual analysis (GPT-4o Vision)
5. Merge results into IBCSFeedbackReport
6. Return as JSON
"""

from __future__ import annotations

import base64
import json
import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from ibcs_agent.analysis.metadata_analyzer import (
    analyze_excel_metadata,
    analyze_pdf_metadata,
    analyze_pptx_metadata,
)
from ibcs_agent.analysis.visual_analyzer import VisualAnalyzer
from ibcs_agent.config import AppConfig, get_config
from ibcs_agent.models.feedback import (
    CategorySummary,
    IBCSFeedbackReport,
    PageFeedback,
    RuleViolation,
)
from ibcs_agent.rules.ibcs_rules import SUCCESS_CATEGORIES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

RULE_WEIGHTS = {
    "error": 1.0,
    "warning": 0.4,
    "info": 0.1,
}

MAX_PENALTY_PER_PAGE = 5.0  # Cap so a very bad page doesn't drag everything to 0


def _compute_page_score(violations: List[RuleViolation]) -> float:
    """Compute a 0.0–1.0 compliance score for a page based on violations."""
    if not violations:
        return 1.0
    penalty = sum(RULE_WEIGHTS.get(v.severity, 0.5) for v in violations)
    penalty = min(penalty, MAX_PENALTY_PER_PAGE)
    score = max(0.0, 1.0 - (penalty / MAX_PENALTY_PER_PAGE))
    return round(score, 3)


def _compute_overall_score(page_scores: List[float]) -> float:
    if not page_scores:
        return 1.0
    return round(sum(page_scores) / len(page_scores), 3)


def _compute_category_summaries(all_violations: List[RuleViolation]) -> List[CategorySummary]:
    summaries = []
    for cat in SUCCESS_CATEGORIES:
        cat_violations = [v for v in all_violations if v.category == cat]
        errors = sum(1 for v in cat_violations if v.severity == "error")
        warnings = sum(1 for v in cat_violations if v.severity == "warning")
        infos = sum(1 for v in cat_violations if v.severity == "info")
        total = len(cat_violations)
        # Score: assume 3 possible violations per category max
        penalty = sum(RULE_WEIGHTS.get(v.severity, 0.5) for v in cat_violations)
        score = max(0.0, round(1.0 - min(penalty / 3.0, 1.0), 3))
        summaries.append(CategorySummary(
            category=cat,
            total_violations=total,
            errors=errors,
            warnings=warnings,
            infos=infos,
            score=score,
        ))
    return summaries


def _select_top_violations(
    all_violations: List[RuleViolation],
    n: int = 5,
) -> List[RuleViolation]:
    """Select the top N most impactful violations (errors first, then by frequency)."""
    # Group by rule_id, keep most severe instance
    by_rule: Dict[str, RuleViolation] = {}
    rule_counts: Counter = Counter()

    for v in all_violations:
        rule_counts[v.rule_id] += 1
        if v.rule_id not in by_rule:
            by_rule[v.rule_id] = v
        else:
            # Prefer errors over warnings over infos
            sev_rank = {"error": 0, "warning": 1, "info": 2}
            if sev_rank.get(v.severity, 2) < sev_rank.get(by_rule[v.rule_id].severity, 2):
                by_rule[v.rule_id] = v

    # Sort: errors first, then by frequency
    sev_rank = {"error": 0, "warning": 1, "info": 2}
    sorted_violations = sorted(
        by_rule.values(),
        key=lambda v: (sev_rank.get(v.severity, 2), -rule_counts[v.rule_id]),
    )
    return sorted_violations[:n]


def _build_summary(report: IBCSFeedbackReport) -> str:
    """Generate a human-readable German summary of the report."""
    grade_texts = {
        "A": "sehr gut – überwiegend IBCS-konform",
        "B": "gut – einige Verbesserungen empfohlen",
        "C": "befriedigend – mehrere IBCS-Verstöße vorhanden",
        "D": "mangelhaft – erhebliche IBCS-Verstöße",
        "F": "ungenügend – grundlegende IBCS-Anforderungen nicht erfüllt",
    }
    grade_text = grade_texts.get(report.overall_grade, "")

    top_cats = sorted(
        report.category_summary,
        key=lambda c: c.total_violations,
        reverse=True,
    )[:3]
    top_cat_names = ", ".join(c.category for c in top_cats if c.total_violations > 0)

    return (
        f"Das Dokument '{report.file_name}' wurde auf {report.total_pages} Seite(n) analysiert "
        f"und erhält einen IBCS-Compliance-Score von {report.overall_score:.0%} (Note {report.overall_grade}: {grade_text}). "
        f"Insgesamt wurden {report.total_violations} Verstöße gefunden "
        f"({report.total_errors} Fehler, {report.total_warnings} Warnungen, {report.total_infos} Hinweise). "
        + (f"Häufigste Problemkategorien: {top_cat_names}." if top_cat_names else "")
    )


# ---------------------------------------------------------------------------
# Core analysis orchestration
# ---------------------------------------------------------------------------

def _analyze_file_internal(
    file_content: bytes,
    file_name: str,
    file_type: str,
    config: AppConfig,
) -> IBCSFeedbackReport:
    """
    Full IBCS analysis pipeline for a single file.

    1. Process file (extract text, charts, images)
    2. Metadata analysis (rule-based)
    3. Visual analysis (GPT-4o Vision)
    4. Merge and build report
    """
    logger.info(f"Starting IBCS analysis for '{file_name}' (type: {file_type})")

    # -----------------------------------------------------------------------
    # Step 1: Process file
    # -----------------------------------------------------------------------
    render_images = config.analysis.enable_visual_analysis

    if file_type == "pptx":
        from ibcs_agent.processors.ppt_processor import process_pptx
        processing_result = process_pptx(file_content, file_name, render_images=render_images)
        pages = processing_result.slides
        meta_violations_per_page = analyze_pptx_metadata(processing_result)
        total_pages = processing_result.total_slides

    elif file_type == "pdf":
        from ibcs_agent.processors.pdf_processor import process_pdf
        processing_result = process_pdf(file_content, file_name, render_images=render_images)
        pages = processing_result.pages
        meta_violations_per_page = analyze_pdf_metadata(processing_result)
        total_pages = processing_result.total_pages

    elif file_type == "xlsx":
        from ibcs_agent.processors.excel_processor import process_excel
        processing_result = process_excel(file_content, file_name, render_images=render_images)
        pages = processing_result.sheets
        meta_violations_per_page = analyze_excel_metadata(processing_result)
        total_pages = processing_result.total_sheets

    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    # Respect max pages limit
    max_pages = config.analysis.max_pages_per_file
    if len(pages) > max_pages:
        logger.warning(f"File has {len(pages)} pages, truncating to {max_pages}")
        pages = pages[:max_pages]
        meta_violations_per_page = meta_violations_per_page[:max_pages]

    # -----------------------------------------------------------------------
    # Step 2: Visual analysis
    # -----------------------------------------------------------------------
    visual_violations_per_page: List[List[RuleViolation]] = [[] for _ in pages]

    if config.analysis.enable_visual_analysis:
        try:
            analyzer = VisualAnalyzer(config.azure)
            visual_violations_per_page = analyzer.analyze_pages(pages, file_type)
        except Exception as e:
            logger.error(f"Visual analysis failed: {e}. Continuing with metadata-only analysis.")

    # -----------------------------------------------------------------------
    # Step 3: Build PageFeedback objects
    # -----------------------------------------------------------------------
    page_feedbacks: List[PageFeedback] = []
    all_violations: List[RuleViolation] = []

    for idx, page in enumerate(pages):
        meta_violations = meta_violations_per_page[idx] if idx < len(meta_violations_per_page) else []
        visual_violations = visual_violations_per_page[idx] if idx < len(visual_violations_per_page) else []

        combined = meta_violations + visual_violations
        all_violations.extend(combined)

        page_num = (
            getattr(page, "slide_number", None)
            or getattr(page, "page_number", None)
            or idx + 1
        )
        title = getattr(page, "title", None)
        has_charts = bool(getattr(page, "charts", []))
        has_tables = bool(getattr(page, "tables", []))

        score = _compute_page_score(combined)

        page_feedbacks.append(PageFeedback(
            page_number=page_num,
            page_title=title,
            violations=combined,
            score=score,
            has_charts=has_charts,
            has_tables=has_tables,
            visual_analysis_performed=bool(visual_violations) or config.analysis.enable_visual_analysis,
        ))

    # -----------------------------------------------------------------------
    # Step 4: Aggregate
    # -----------------------------------------------------------------------
    page_scores = [p.score for p in page_feedbacks]
    overall_score = _compute_overall_score(page_scores)
    overall_grade = IBCSFeedbackReport.compute_grade(overall_score)

    category_summary = _compute_category_summaries(all_violations)
    top_violations = _select_top_violations(all_violations, n=config.analysis.top_violations_count)

    total_errors = sum(1 for v in all_violations if v.severity == "error")
    total_warnings = sum(1 for v in all_violations if v.severity == "warning")
    total_infos = sum(1 for v in all_violations if v.severity == "info")

    report = IBCSFeedbackReport(
        file_name=file_name,
        file_type=file_type,
        analysis_timestamp=datetime.utcnow(),
        total_pages=total_pages,
        overall_score=overall_score,
        overall_grade=overall_grade,
        summary="",  # Filled below
        pages=page_feedbacks,
        category_summary=category_summary,
        top_violations=top_violations,
        total_violations=len(all_violations),
        total_errors=total_errors,
        total_warnings=total_warnings,
        total_infos=total_infos,
        model_used=config.azure.model_name,
    )
    report.summary = _build_summary(report)

    logger.info(
        f"Analysis complete: score={overall_score:.0%}, grade={overall_grade}, "
        f"violations={len(all_violations)} ({total_errors}E/{total_warnings}W/{total_infos}I)"
    )
    return report


# ---------------------------------------------------------------------------
# Public tool functions (called by Azure AI Foundry agent)
# ---------------------------------------------------------------------------

def analyze_file(
    file_content_base64: str,
    file_name: str,
    file_type: Optional[str] = None,
) -> str:
    """
    Analyze a PPT, PDF, or Excel file for IBCS compliance.

    This is the main tool called by the Azure AI Foundry Agent.

    Args:
        file_content_base64: Base64-encoded file content
        file_name: Original filename (used for type detection if file_type not given)
        file_type: Optional explicit type: "pptx", "pdf", "xlsx"

    Returns:
        JSON string containing the IBCSFeedbackReport
    """
    config = get_config()

    # Decode file
    try:
        file_content = base64.b64decode(file_content_base64)
    except Exception as e:
        return json.dumps({"error": f"Could not decode file content: {e}"})

    # Check file size
    size_mb = len(file_content) / (1024 * 1024)
    if size_mb > config.analysis.max_file_size_mb:
        return json.dumps({
            "error": f"File too large: {size_mb:.1f} MB (max {config.analysis.max_file_size_mb} MB)"
        })

    # Detect file type
    if file_type is None:
        lower_name = file_name.lower()
        if lower_name.endswith(".pptx") or lower_name.endswith(".ppt"):
            file_type = "pptx"
        elif lower_name.endswith(".pdf"):
            file_type = "pdf"
        elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
            file_type = "xlsx"
        else:
            return json.dumps({"error": f"Cannot detect file type from '{file_name}'. Provide file_type explicitly."})

    try:
        report = _analyze_file_internal(file_content, file_name, file_type, config)
        return report.model_dump_json(indent=2)
    except Exception as e:
        logger.exception(f"Analysis failed for '{file_name}'")
        return json.dumps({"error": f"Analysis failed: {str(e)}"})


def get_ibcs_rule_details(rule_id: str) -> str:
    """
    Get detailed information about a specific IBCS rule.

    Args:
        rule_id: Rule ID, e.g. "CK1", "E4", "U1"

    Returns:
        JSON string with rule details
    """
    from ibcs_agent.rules.ibcs_rules import RULES_BY_ID

    rule_id = rule_id.strip().upper()
    if rule_id not in RULES_BY_ID:
        available = ", ".join(sorted(RULES_BY_ID.keys()))
        return json.dumps({
            "error": f"Rule '{rule_id}' not found. Available rules: {available}"
        })

    rule = RULES_BY_ID[rule_id]
    return json.dumps({
        "id": rule.id,
        "category": rule.category,
        "name": rule.name,
        "description": rule.description,
        "check_type": rule.check_type,
        "severity": rule.severity,
        "violation_hint": rule.violation_hint,
        "suggestion": rule.suggestion_template,
        "applies_to": rule.applies_to,
    }, ensure_ascii=False, indent=2)


def list_ibcs_rules(category: Optional[str] = None) -> str:
    """
    List all IBCS rules, optionally filtered by SUCCESS category.

    Args:
        category: Optional category filter: SAY, UNIFY, CONDENSE, CHECK, EXPRESS, SIMPLIFY, STRUCTURE

    Returns:
        JSON string with list of rules
    """
    from ibcs_agent.rules.ibcs_rules import ALL_RULES, RULES_BY_CATEGORY

    if category:
        category = category.strip().upper()
        rules = RULES_BY_CATEGORY.get(category, [])
        if not rules:
            return json.dumps({
                "error": f"Category '{category}' not found.",
                "available_categories": SUCCESS_CATEGORIES,
            })
    else:
        rules = ALL_RULES

    return json.dumps([{
        "id": r.id,
        "category": r.category,
        "name": r.name,
        "severity": r.severity,
        "check_type": r.check_type,
    } for r in rules], ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tool definitions for Azure AI Foundry (OpenAI function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_file",
            "description": (
                "Analysiert eine hochgeladene PPT-, PDF- oder Excel-Datei auf Einhaltung der IBCS "
                "(International Business Communication Standards) SUCCESS-Regeln. "
                "Gibt einen detaillierten JSON-Report mit seitenspezifischem Feedback, "
                "Regelverstoßen und Korrekturvorschlägen zurück."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_content_base64": {
                        "type": "string",
                        "description": "Base64-kodierter Inhalt der Datei",
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Originaler Dateiname inkl. Endung (z.B. 'bericht_q1.pptx')",
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["pptx", "pdf", "xlsx"],
                        "description": "Optionaler expliziter Dateityp (wird sonst aus dem Dateinamen erkannt)",
                    },
                },
                "required": ["file_content_base64", "file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ibcs_rule_details",
            "description": (
                "Gibt detaillierte Informationen zu einer spezifischen IBCS-Regel zurück, "
                "z.B. was die Regel prüft, warum sie wichtig ist und wie Verstöße behoben werden."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "description": "Die Regel-ID, z.B. 'CK1', 'E4', 'U1'",
                    },
                },
                "required": ["rule_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_ibcs_rules",
            "description": "Listet alle verfügbaren IBCS-Regeln auf, optional gefiltert nach SUCCESS-Kategorie.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["SAY", "UNIFY", "CONDENSE", "CHECK", "EXPRESS", "SIMPLIFY", "STRUCTURE"],
                        "description": "Optionale Filterung nach SUCCESS-Kategorie",
                    },
                },
            },
        },
    },
]

# Tool function dispatch map
TOOL_FUNCTIONS: Dict[str, Any] = {
    "analyze_file": analyze_file,
    "get_ibcs_rule_details": get_ibcs_rule_details,
    "list_ibcs_rules": list_ibcs_rules,
}
