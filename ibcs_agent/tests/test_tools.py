"""
Tests for agent tool functions.

Azure OpenAI calls are mocked so tests run without credentials.
"""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from ibcs_agent.agent.tools import (
    TOOL_DEFINITIONS,
    TOOL_FUNCTIONS,
    _compute_overall_score,
    _compute_page_score,
    _select_top_violations,
    get_ibcs_rule_details,
    list_ibcs_rules,
    analyze_file,
)
from ibcs_agent.models.feedback import RuleViolation


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

class TestScoreCalculation:
    def test_no_violations_score_one(self):
        assert _compute_page_score([]) == 1.0

    def test_single_error_reduces_score(self):
        v = _make_violation(severity="error")
        score = _compute_page_score([v])
        assert score < 1.0

    def test_warning_less_penalty_than_error(self):
        error_score = _compute_page_score([_make_violation(severity="error")])
        warning_score = _compute_page_score([_make_violation(severity="warning")])
        assert warning_score > error_score

    def test_score_never_below_zero(self):
        violations = [_make_violation(severity="error") for _ in range(20)]
        assert _compute_page_score(violations) >= 0.0

    def test_overall_score_is_average(self):
        score = _compute_overall_score([1.0, 0.5, 0.75])
        assert abs(score - 0.75) < 0.01

    def test_empty_pages_score_one(self):
        assert _compute_overall_score([]) == 1.0


def _make_violation(rule_id="CK1", severity="error") -> RuleViolation:
    return RuleViolation(
        rule_id=rule_id,
        rule_name="Test",
        category="CHECK",
        severity=severity,
        description="desc",
        suggestion="fix",
        source="metadata",
    )


# ---------------------------------------------------------------------------
# Top violations selection
# ---------------------------------------------------------------------------

class TestTopViolations:
    def test_selects_n_violations(self):
        violations = [_make_violation(f"CK{i}") for i in range(1, 8)]
        top = _select_top_violations(violations, n=5)
        assert len(top) <= 5

    def test_errors_prioritized_over_warnings(self):
        violations = [
            _make_violation("SI1", severity="warning"),
            _make_violation("CK1", severity="error"),
        ]
        top = _select_top_violations(violations, n=2)
        assert top[0].rule_id == "CK1"

    def test_deduplicates_by_rule(self):
        violations = [_make_violation("CK1")] * 5 + [_make_violation("E4")]
        top = _select_top_violations(violations, n=5)
        rule_ids = [v.rule_id for v in top]
        assert len(rule_ids) == len(set(rule_ids))


# ---------------------------------------------------------------------------
# Tool: get_ibcs_rule_details
# ---------------------------------------------------------------------------

class TestGetIbcsRuleDetails:
    def test_known_rule_returns_json(self):
        result = get_ibcs_rule_details("CK1")
        data = json.loads(result)
        assert data["id"] == "CK1"
        assert data["category"] == "CHECK"
        assert "description" in data
        assert "suggestion" in data

    def test_unknown_rule_returns_error(self):
        result = get_ibcs_rule_details("INVALID")
        data = json.loads(result)
        assert "error" in data

    def test_case_insensitive(self):
        result = get_ibcs_rule_details("ck1")
        data = json.loads(result)
        assert data["id"] == "CK1"

    def test_all_fields_present(self):
        for rule_id in ["S1", "U1", "CK2", "E4", "SI4", "ST3"]:
            data = json.loads(get_ibcs_rule_details(rule_id))
            assert "id" in data
            assert "name" in data
            assert "severity" in data


# ---------------------------------------------------------------------------
# Tool: list_ibcs_rules
# ---------------------------------------------------------------------------

class TestListIbcsRules:
    def test_lists_all_rules(self):
        result = list_ibcs_rules()
        rules = json.loads(result)
        assert isinstance(rules, list)
        assert len(rules) >= 20

    def test_filter_by_category(self):
        result = list_ibcs_rules(category="CHECK")
        rules = json.loads(result)
        assert all(r["category"] == "CHECK" for r in rules)

    def test_invalid_category_returns_error(self):
        result = list_ibcs_rules(category="INVALID")
        data = json.loads(result)
        assert "error" in data

    def test_each_rule_has_required_fields(self):
        rules = json.loads(list_ibcs_rules())
        for rule in rules:
            assert "id" in rule
            assert "category" in rule
            assert "severity" in rule


# ---------------------------------------------------------------------------
# Tool: analyze_file (end-to-end with mocked config)
# ---------------------------------------------------------------------------

class TestAnalyzeFile:
    def test_invalid_base64_returns_error(self):
        result = analyze_file(
            file_content_base64="NOT_VALID_BASE64!!!",
            file_name="test.pptx",
        )
        data = json.loads(result)
        assert "error" in data

    def test_unknown_extension_returns_error(self):
        content_b64 = base64.b64encode(b"some content").decode()
        result = analyze_file(
            file_content_base64=content_b64,
            file_name="test.docx",
        )
        data = json.loads(result)
        assert "error" in data

    def test_oversized_file_returns_error(self):
        large_content = b"x" * (60 * 1024 * 1024)  # 60 MB
        content_b64 = base64.b64encode(large_content).decode()

        mock_config = MagicMock()
        mock_config.analysis.max_file_size_mb = 50.0

        with patch("ibcs_agent.agent.tools.get_config", return_value=mock_config):
            result = analyze_file(
                file_content_base64=content_b64,
                file_name="huge.pptx",
            )
        data = json.loads(result)
        assert "error" in data
        assert "large" in data["error"].lower() or "MB" in data["error"]

    def test_full_pptx_analysis(self, pptx_b64_minimal, config_no_visual):
        with patch("ibcs_agent.agent.tools.get_config", return_value=config_no_visual):
            result = analyze_file(
                file_content_base64=pptx_b64_minimal,
                file_name="test.pptx",
            )
        data = json.loads(result)
        assert "error" not in data, f"Unexpected error: {data.get('error')}"
        assert data["file_type"] == "pptx"
        assert "overall_score" in data
        assert "overall_grade" in data
        assert 0.0 <= data["overall_score"] <= 1.0
        assert data["overall_grade"] in ("A", "B", "C", "D", "F")

    def test_full_xlsx_analysis(self, xlsx_b64_minimal, config_no_visual):
        with patch("ibcs_agent.agent.tools.get_config", return_value=config_no_visual):
            result = analyze_file(
                file_content_base64=xlsx_b64_minimal,
                file_name="test.xlsx",
            )
        data = json.loads(result)
        assert "error" not in data
        assert data["file_type"] == "xlsx"
        assert "pages" in data
        assert "category_summary" in data

    def test_report_has_all_required_fields(self, pptx_b64_minimal, config_no_visual):
        with patch("ibcs_agent.agent.tools.get_config", return_value=config_no_visual):
            result = analyze_file(pptx_b64_minimal, "test.pptx")
        data = json.loads(result)
        required = [
            "file_name", "file_type", "overall_score", "overall_grade",
            "summary", "pages", "top_violations", "total_violations",
            "total_errors", "total_warnings", "total_infos", "category_summary",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_violations_have_correct_structure(self, pptx_b64_minimal, config_no_visual):
        with patch("ibcs_agent.agent.tools.get_config", return_value=config_no_visual):
            result = analyze_file(pptx_b64_minimal, "test.pptx")
        data = json.loads(result)
        for page in data["pages"]:
            for v in page["violations"]:
                assert "rule_id" in v
                assert "severity" in v
                assert v["severity"] in ("error", "warning", "info")
                assert "suggestion" in v
                assert "source" in v

    def test_explicit_file_type_override(self, pptx_b64_minimal, config_no_visual):
        with patch("ibcs_agent.agent.tools.get_config", return_value=config_no_visual):
            result = analyze_file(
                file_content_base64=pptx_b64_minimal,
                file_name="report_no_extension",
                file_type="pptx",
            )
        data = json.loads(result)
        assert "error" not in data
        assert data["file_type"] == "pptx"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_tool_definitions_non_empty(self):
        assert len(TOOL_DEFINITIONS) == 3

    def test_all_tools_have_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert tool["type"] == "function"
            assert "function" in tool
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_tool_functions_match_definitions(self):
        defined_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        implemented_names = set(TOOL_FUNCTIONS.keys())
        assert defined_names == implemented_names
