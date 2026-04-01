"""
Pydantic models for the IBCS Feedback Report output.
All analysis results are serialized into these structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RuleViolation(BaseModel):
    """A single IBCS rule violation found on a page/slide."""

    rule_id: str = Field(description="IBCS rule ID, e.g. 'CK1'")
    rule_name: str = Field(description="Short rule name, e.g. 'Achse beginnt nicht bei Null'")
    category: str = Field(description="SUCCESS category: SAY | UNIFY | CONDENSE | CHECK | EXPRESS | SIMPLIFY | STRUCTURE")
    severity: Literal["error", "warning", "info"] = Field(
        description="error = clear violation, warning = potential issue, info = best-practice hint"
    )
    description: str = Field(description="Konkrete Beschreibung des Befunds auf dieser Seite/Folie")
    suggestion: str = Field(description="Konkreter Korrekturvorschlag")
    source: Literal["metadata", "visual"] = Field(
        description="metadata = structural/text-based check, visual = GPT-4o Vision check"
    )
    element: Optional[str] = Field(
        default=None,
        description="Betroffenes Element auf der Folie, z.B. 'Chart 2' oder 'Tabelle 1'"
    )


class PageFeedback(BaseModel):
    """IBCS feedback for a single page or slide."""

    page_number: int = Field(description="1-basierte Seitennummer")
    page_title: Optional[str] = Field(default=None, description="Titel der Folie/Seite, falls erkennbar")
    violations: List[RuleViolation] = Field(default_factory=list)
    score: float = Field(
        ge=0.0, le=1.0,
        description="IBCS-Compliance-Score dieser Seite: 1.0 = vollständig konform"
    )
    has_charts: bool = Field(default=False, description="Enthält die Seite Charts/Diagramme?")
    has_tables: bool = Field(default=False, description="Enthält die Seite Tabellen?")
    visual_analysis_performed: bool = Field(
        default=False,
        description="Wurde eine visuelle GPT-4o-Analyse durchgeführt?"
    )


class CategorySummary(BaseModel):
    """Aggregated result per SUCCESS category."""

    category: str
    total_violations: int
    errors: int
    warnings: int
    infos: int
    score: float = Field(ge=0.0, le=1.0)


class IBCSFeedbackReport(BaseModel):
    """
    Top-level IBCS compliance report.
    This is the main output returned by the agent as JSON.
    """

    file_name: str
    file_type: Literal["pptx", "pdf", "xlsx"]
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_pages: int

    overall_score: float = Field(
        ge=0.0, le=1.0,
        description="Gesamter IBCS-Compliance-Score über alle Seiten: 1.0 = vollständig konform"
    )
    overall_grade: Literal["A", "B", "C", "D", "F"] = Field(
        description="Schulnoten-ähnliche Bewertung: A=>=90%, B=>=75%, C=>=60%, D=>=40%, F=<40%"
    )
    summary: str = Field(description="Kurze Zusammenfassung der wichtigsten Befunde (2-4 Sätze)")

    pages: List[PageFeedback]
    category_summary: List[CategorySummary] = Field(default_factory=list)

    top_violations: List[RuleViolation] = Field(
        default_factory=list,
        description="Top 5 häufigste oder schwerwiegendste Verstöße über das gesamte Dokument"
    )

    total_violations: int = Field(default=0)
    total_errors: int = Field(default=0)
    total_warnings: int = Field(default=0)
    total_infos: int = Field(default=0)

    model_used: str = Field(default="gpt-4o", description="Azure OpenAI Modell für visuelle Analyse")

    @classmethod
    def compute_grade(cls, score: float) -> Literal["A", "B", "C", "D", "F"]:
        if score >= 0.90:
            return "A"
        elif score >= 0.75:
            return "B"
        elif score >= 0.60:
            return "C"
        elif score >= 0.40:
            return "D"
        return "F"
