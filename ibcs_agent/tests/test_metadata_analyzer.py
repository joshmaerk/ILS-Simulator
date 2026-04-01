"""
Tests for the metadata-based IBCS analyzer.

Covers all helper check functions and the three main entry points
(analyze_pptx_metadata, analyze_pdf_metadata, analyze_excel_metadata).
"""

import pytest

from ibcs_agent.analysis.metadata_analyzer import (
    check_3d_chart,
    check_axis_zero,
    check_font_sizes,
    check_page_number,
    check_pie_chart,
    check_source_reference,
    check_title_hierarchy,
    check_title_insight,
    analyze_pptx_metadata,
    analyze_pdf_metadata,
    analyze_excel_metadata,
)
from ibcs_agent.models.feedback import RuleViolation


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def violation_ids(violations: list[RuleViolation]) -> list[str]:
    return [v.rule_id for v in violations]


# ---------------------------------------------------------------------------
# check_title_insight (S1, S2)
# ---------------------------------------------------------------------------

class TestCheckTitleInsight:
    def test_no_title_triggers_s1(self):
        vs = check_title_insight(None, "Folie 1")
        assert "S1" in violation_ids(vs)

    def test_bare_noun_triggers_s1(self):
        vs = check_title_insight("Umsatz", "Folie 1")
        assert "S1" in violation_ids(vs)

    def test_insight_title_no_s1(self):
        vs = check_title_insight("Umsatz steigt um 12% in Q1 2024", "Folie 1")
        assert "S1" not in violation_ids(vs)

    def test_missing_time_triggers_s2(self):
        # Has verb but no time or unit
        vs = check_title_insight("Umsatz steigt stark", "Folie 1")
        assert "S2" in violation_ids(vs)

    def test_with_time_and_unit_no_s2(self):
        vs = check_title_insight("Umsatz steigt um 12% in Q1 2024 in Mio. €", "Folie 1")
        assert "S2" not in violation_ids(vs)

    def test_english_verb_no_s1(self):
        vs = check_title_insight("Revenue increases by 15% in FY2024", "Slide 1")
        assert "S1" not in violation_ids(vs)

    def test_empty_string_triggers_s1(self):
        vs = check_title_insight("", "Folie 1")
        assert "S1" in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_axis_zero (CK1)
# ---------------------------------------------------------------------------

class TestCheckAxisZero:
    def test_axis_not_zero_bar_triggers_ck1(self):
        vs = check_axis_zero(50.0, "bar", "Chart 1")
        assert "CK1" in violation_ids(vs)

    def test_axis_not_zero_column_triggers_ck1(self):
        vs = check_axis_zero(100.0, "column", "Chart 1")
        assert "CK1" in violation_ids(vs)

    def test_axis_zero_no_violation(self):
        vs = check_axis_zero(0.0, "bar", "Chart 1")
        assert "CK1" not in violation_ids(vs)

    def test_axis_none_no_violation(self):
        vs = check_axis_zero(None, "bar", "Chart 1")
        assert "CK1" not in violation_ids(vs)

    def test_line_chart_axis_not_zero_no_ck1(self):
        """CK1 only applies to bar/column charts."""
        vs = check_axis_zero(50.0, "line", "Chart 1")
        assert "CK1" not in violation_ids(vs)

    def test_scatter_chart_no_ck1(self):
        vs = check_axis_zero(10.0, "scatter", "Chart 1")
        assert "CK1" not in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_3d_chart (CK2)
# ---------------------------------------------------------------------------

class TestCheck3DChart:
    def test_3d_chart_triggers_ck2(self):
        vs = check_3d_chart(True, "bar_3d", "Chart 1")
        assert "CK2" in violation_ids(vs)

    def test_2d_chart_no_ck2(self):
        vs = check_3d_chart(False, "bar", "Chart 1")
        assert "CK2" not in violation_ids(vs)

    def test_3d_column_triggers_ck2(self):
        vs = check_3d_chart(True, "column_3d", "Chart 2")
        assert "CK2" in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_pie_chart (E4)
# ---------------------------------------------------------------------------

class TestCheckPieChart:
    def test_pie_3_segments_triggers_e4(self):
        vs = check_pie_chart("pie", 3, "Chart 1")
        assert "E4" in violation_ids(vs)

    def test_pie_4_segments_triggers_e4(self):
        vs = check_pie_chart("pie", 4, "Chart 1")
        assert "E4" in violation_ids(vs)

    def test_pie_2_segments_no_e4(self):
        vs = check_pie_chart("pie", 2, "Chart 1")
        assert "E4" not in violation_ids(vs)

    def test_pie_1_segment_no_e4(self):
        vs = check_pie_chart("pie", 1, "Chart 1")
        assert "E4" not in violation_ids(vs)

    def test_doughnut_3_segments_triggers_e4(self):
        vs = check_pie_chart("doughnut", 3, "Chart 1")
        assert "E4" in violation_ids(vs)

    def test_bar_chart_no_e4(self):
        vs = check_pie_chart("bar", 5, "Chart 1")
        assert "E4" not in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_font_sizes (SI3)
# ---------------------------------------------------------------------------

class TestCheckFontSizes:
    def test_many_font_sizes_triggers_si3(self):
        sizes = [8, 10, 12, 14, 16, 18, 20, 24]
        vs = check_font_sizes(sizes, "Folie 1")
        assert "SI3" in violation_ids(vs)

    def test_three_font_sizes_no_si3(self):
        vs = check_font_sizes([12.0, 18.0, 24.0], "Folie 1")
        assert "SI3" not in violation_ids(vs)

    def test_empty_font_sizes_no_violation(self):
        vs = check_font_sizes([], "Folie 1")
        assert vs == []

    def test_four_font_sizes_no_si3(self):
        vs = check_font_sizes([10, 12, 18, 24], "Folie 1")
        assert "SI3" not in violation_ids(vs)

    def test_five_unique_triggers_si3(self):
        vs = check_font_sizes([8, 10, 12, 16, 24], "Folie 1")
        assert "SI3" in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_page_number (ST3)
# ---------------------------------------------------------------------------

class TestCheckPageNumber:
    def test_no_page_number_triggers_st3(self):
        vs = check_page_number(False, "Präsentation")
        assert "ST3" in violation_ids(vs)

    def test_has_page_number_no_st3(self):
        vs = check_page_number(True, "Präsentation")
        assert "ST3" not in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_source_reference (ST4)
# ---------------------------------------------------------------------------

class TestCheckSourceReference:
    def test_no_source_triggers_st4(self):
        vs = check_source_reference(False, "Folie 1")
        assert "ST4" in violation_ids(vs)

    def test_has_source_no_st4(self):
        vs = check_source_reference(True, "Folie 1")
        assert "ST4" not in violation_ids(vs)


# ---------------------------------------------------------------------------
# check_title_hierarchy (ST2)
# ---------------------------------------------------------------------------

class TestCheckTitleHierarchy:
    def test_no_title_triggers_st2(self):
        vs = check_title_hierarchy(None, [12.0], "Folie 1")
        assert "ST2" in violation_ids(vs)

    def test_has_title_no_st2(self):
        vs = check_title_hierarchy("Mein Titel", [18.0, 12.0], "Folie 1")
        assert "ST2" not in violation_ids(vs)


# ---------------------------------------------------------------------------
# Integration: analyze_pptx_metadata
# ---------------------------------------------------------------------------

class TestAnalyzePptxMetadata:
    def test_returns_list_per_slide(self, ppt_result_factory, slide_factory):
        result = ppt_result_factory([slide_factory(1), slide_factory(2)])
        per_slide = analyze_pptx_metadata(result)
        assert len(per_slide) == 2

    def test_topic_title_generates_s1(self, ppt_result_factory, slide_factory):
        slide = slide_factory(title="Umsatz")  # bare noun
        result = ppt_result_factory([slide])
        violations = analyze_pptx_metadata(result)[0]
        assert any(v.rule_id == "S1" for v in violations)

    def test_no_slide_numbers_reports_st3(self, ppt_result_factory, slide_factory):
        slide = slide_factory(has_page_number=False)
        result = ppt_result_factory([slide])
        result.has_slide_numbers = False
        violations = analyze_pptx_metadata(result)[0]
        assert any(v.rule_id == "ST3" for v in violations)

    def test_3d_chart_detected(self, ppt_result_factory, slide_factory, chart_factory):
        chart = chart_factory(is_3d=True, chart_type="column_3d")
        slide = slide_factory(charts=[chart])
        result = ppt_result_factory([slide])
        violations = analyze_pptx_metadata(result)[0]
        assert any(v.rule_id == "CK2" for v in violations)

    def test_pie_chart_with_many_series_detected(self, ppt_result_factory, slide_factory, chart_factory):
        chart = chart_factory(chart_type="pie", series_count=4)
        slide = slide_factory(charts=[chart])
        result = ppt_result_factory([slide])
        violations = analyze_pptx_metadata(result)[0]
        assert any(v.rule_id == "E4" for v in violations)

    def test_axis_not_zero_detected(self, ppt_result_factory, slide_factory, chart_factory):
        chart = chart_factory(chart_type="column", axis_min_y=50.0)
        slide = slide_factory(charts=[chart])
        result = ppt_result_factory([slide])
        violations = analyze_pptx_metadata(result)[0]
        assert any(v.rule_id == "CK1" for v in violations)

    def test_source_missing_triggers_st4(self, ppt_result_factory, slide_factory):
        slide = slide_factory(has_source=False)
        result = ppt_result_factory([slide])
        violations = analyze_pptx_metadata(result)[0]
        assert any(v.rule_id == "ST4" for v in violations)

    def test_insight_title_no_s1(self, ppt_result_factory, slide_factory):
        slide = slide_factory(title="Umsatz steigt um 15% in Q1 2024 in Mio. €")
        result = ppt_result_factory([slide])
        violations = analyze_pptx_metadata(result)[0]
        assert all(v.rule_id != "S1" for v in violations)


# ---------------------------------------------------------------------------
# Integration: analyze_pdf_metadata
# ---------------------------------------------------------------------------

class TestAnalyzePdfMetadata:
    def test_returns_list_per_page(self, pdf_result_factory, pdf_page_factory):
        result = pdf_result_factory([pdf_page_factory(1), pdf_page_factory(2)])
        per_page = analyze_pdf_metadata(result)
        assert len(per_page) == 2

    def test_topic_title_s1(self, pdf_result_factory, pdf_page_factory):
        page = pdf_page_factory(title="Kosten")
        result = pdf_result_factory([page])
        violations = analyze_pdf_metadata(result)[0]
        assert any(v.rule_id == "S1" for v in violations)

    def test_no_page_numbers_st3(self, pdf_result_factory, pdf_page_factory):
        page = pdf_page_factory()
        result = pdf_result_factory([page])
        result.has_page_numbers = False
        violations = analyze_pdf_metadata(result)[0]
        assert any(v.rule_id == "ST3" for v in violations)


# ---------------------------------------------------------------------------
# Integration: analyze_excel_metadata
# ---------------------------------------------------------------------------

class TestAnalyzeExcelMetadata:
    def test_returns_list_per_sheet(self, excel_result_factory, sheet_factory):
        result = excel_result_factory([sheet_factory("S1"), sheet_factory("S2")])
        per_sheet = analyze_excel_metadata(result)
        assert len(per_sheet) == 2

    def test_3d_chart_in_excel(self, excel_result_factory, sheet_factory, excel_chart_factory):
        chart = excel_chart_factory(is_3d=True, chart_type="bar_3d")
        sheet = sheet_factory(charts=[chart])
        result = excel_result_factory([sheet])
        violations = analyze_excel_metadata(result)[0]
        assert any(v.rule_id == "CK2" for v in violations)

    def test_pie_chart_in_excel(self, excel_result_factory, sheet_factory, excel_chart_factory):
        chart = excel_chart_factory(chart_type="pie", series_count=5)
        sheet = sheet_factory(charts=[chart])
        result = excel_result_factory([sheet])
        violations = analyze_excel_metadata(result)[0]
        assert any(v.rule_id == "E4" for v in violations)

    def test_source_present_no_st4(self, excel_result_factory, sheet_factory):
        sheet = sheet_factory(has_source=True)
        result = excel_result_factory([sheet])
        violations = analyze_excel_metadata(result)[0]
        assert all(v.rule_id != "ST4" for v in violations)
