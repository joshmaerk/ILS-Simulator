"""Tests for Pydantic output models and score/grade logic."""

import pytest
from datetime import datetime

from ibcs_agent.models.feedback import (
    CategorySummary,
    IBCSFeedbackReport,
    PageFeedback,
    RuleViolation,
)


def _violation(rule_id="CK1", severity="error", source="metadata") -> RuleViolation:
    return RuleViolation(
        rule_id=rule_id,
        rule_name="Test Rule",
        category="CHECK",
        severity=severity,
        description="Test description",
        suggestion="Test suggestion",
        source=source,
    )


def _page(page_number=1, score=1.0, violations=None) -> PageFeedback:
    return PageFeedback(
        page_number=page_number,
        page_title="Test Page",
        violations=violations or [],
        score=score,
        has_charts=False,
        has_tables=False,
        visual_analysis_performed=False,
    )


def _minimal_report(**kwargs) -> IBCSFeedbackReport:
    defaults = dict(
        file_name="test.pptx",
        file_type="pptx",
        analysis_timestamp=datetime.utcnow(),
        total_pages=1,
        overall_score=0.8,
        overall_grade="B",
        summary="Test summary",
        pages=[_page()],
        category_summary=[],
        top_violations=[],
        total_violations=0,
        total_errors=0,
        total_warnings=0,
        total_infos=0,
        model_used="gpt-4o",
    )
    defaults.update(kwargs)
    return IBCSFeedbackReport(**defaults)


class TestGradeComputation:
    @pytest.mark.parametrize("score,expected_grade", [
        (1.00, "A"),
        (0.90, "A"),
        (0.89, "B"),
        (0.75, "B"),
        (0.74, "C"),
        (0.60, "C"),
        (0.59, "D"),
        (0.40, "D"),
        (0.39, "F"),
        (0.00, "F"),
    ])
    def test_grade_boundaries(self, score, expected_grade):
        assert IBCSFeedbackReport.compute_grade(score) == expected_grade


class TestRuleViolation:
    def test_valid_violation(self):
        v = _violation()
        assert v.rule_id == "CK1"
        assert v.severity == "error"
        assert v.source == "metadata"

    def test_severity_values(self):
        for sev in ("error", "warning", "info"):
            v = _violation(severity=sev)
            assert v.severity == sev

    def test_invalid_severity_raises(self):
        with pytest.raises(Exception):
            RuleViolation(
                rule_id="CK1",
                rule_name="x",
                category="CHECK",
                severity="critical",  # invalid
                description="x",
                suggestion="x",
                source="metadata",
            )

    def test_element_optional(self):
        v = _violation()
        assert v.element is None
        v2 = RuleViolation(
            rule_id="CK1", rule_name="x", category="CHECK",
            severity="error", description="x", suggestion="x",
            source="metadata", element="Chart 1",
        )
        assert v2.element == "Chart 1"


class TestPageFeedback:
    def test_score_clamped(self):
        page = _page(score=1.0)
        assert 0.0 <= page.score <= 1.0

    def test_score_below_zero_raises(self):
        with pytest.raises(Exception):
            PageFeedback(
                page_number=1, page_title=None,
                violations=[], score=-0.1,
                has_charts=False, has_tables=False,
                visual_analysis_performed=False,
            )

    def test_score_above_one_raises(self):
        with pytest.raises(Exception):
            PageFeedback(
                page_number=1, page_title=None,
                violations=[], score=1.1,
                has_charts=False, has_tables=False,
                visual_analysis_performed=False,
            )


class TestIBCSFeedbackReport:
    def test_json_serializable(self):
        report = _minimal_report()
        json_str = report.model_dump_json()
        assert "test.pptx" in json_str
        assert "overall_score" in json_str

    def test_json_round_trip(self):
        report = _minimal_report()
        json_str = report.model_dump_json()
        restored = IBCSFeedbackReport.model_validate_json(json_str)
        assert restored.file_name == report.file_name
        assert restored.overall_grade == report.overall_grade

    def test_file_type_validation(self):
        report = _minimal_report(file_type="pdf")
        assert report.file_type == "pdf"

    def test_invalid_file_type_raises(self):
        with pytest.raises(Exception):
            _minimal_report(file_type="docx")

    def test_grade_and_score_consistency(self):
        for score, grade in [(0.95, "A"), (0.50, "C"), (0.20, "F")]:
            report = _minimal_report(
                overall_score=score,
                overall_grade=IBCSFeedbackReport.compute_grade(score),
            )
            assert report.overall_grade == grade
