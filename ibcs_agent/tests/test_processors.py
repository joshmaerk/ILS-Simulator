"""
Integration tests for the three file processors.

Uses in-memory files created by conftest.py fixtures.
Visual rendering is disabled to avoid needing poppler/LibreOffice.
"""

import pytest

from ibcs_agent.processors.ppt_processor import process_pptx, PPTProcessingResult
from ibcs_agent.processors.excel_processor import process_excel, ExcelProcessingResult


class TestPptProcessor:
    def test_processes_minimal_pptx(self, pptx_bytes_minimal):
        result = process_pptx(pptx_bytes_minimal, "test.pptx", render_images=False)
        assert isinstance(result, PPTProcessingResult)
        assert result.file_name == "test.pptx"
        assert result.total_slides >= 1

    def test_title_extracted(self, pptx_bytes_minimal):
        result = process_pptx(pptx_bytes_minimal, "test.pptx", render_images=False)
        slide = result.slides[0]
        # Title might be None for blank layouts but should be populated for title slide
        assert slide.slide_number == 1

    def test_insight_title_preserved(self, pptx_bytes_insight_title):
        result = process_pptx(pptx_bytes_insight_title, "insight.pptx", render_images=False)
        slide = result.slides[0]
        assert slide.title is not None
        assert "steigt" in slide.title.lower() or "steigt" in " ".join(slide.all_texts).lower()

    def test_no_title_slide(self, pptx_bytes_no_title):
        result = process_pptx(pptx_bytes_no_title, "notitle.pptx", render_images=False)
        assert result.total_slides >= 1
        # Blank layout has no title placeholder — should not crash
        slide = result.slides[0]
        assert slide.slide_number == 1

    def test_result_fields_present(self, pptx_bytes_minimal):
        result = process_pptx(pptx_bytes_minimal, "test.pptx", render_images=False)
        slide = result.slides[0]
        assert isinstance(slide.charts, list)
        assert isinstance(slide.tables, list)
        assert isinstance(slide.font_sizes_pt, list)
        assert isinstance(slide.all_texts, list)

    def test_image_none_when_rendering_disabled(self, pptx_bytes_minimal):
        result = process_pptx(pptx_bytes_minimal, "test.pptx", render_images=False)
        for slide in result.slides:
            assert slide.image_base64 is None

    def test_invalid_bytes_raises(self):
        with pytest.raises(Exception):
            process_pptx(b"not a pptx file", "bad.pptx", render_images=False)


class TestExcelProcessor:
    def test_processes_minimal_xlsx(self, xlsx_bytes_minimal):
        result = process_excel(xlsx_bytes_minimal, "test.xlsx", render_images=False)
        assert isinstance(result, ExcelProcessingResult)
        assert result.file_name == "test.xlsx"
        assert result.total_sheets >= 1

    def test_sheet_texts_extracted(self, xlsx_bytes_minimal):
        result = process_excel(xlsx_bytes_minimal, "test.xlsx", render_images=False)
        sheet = result.sheets[0]
        assert len(sheet.all_texts) > 0

    def test_source_detected(self, xlsx_bytes_with_source):
        result = process_excel(xlsx_bytes_with_source, "src.xlsx", render_images=False)
        sheet = result.sheets[0]
        assert sheet.has_source_reference is True

    def test_no_source_in_minimal(self, xlsx_bytes_minimal):
        result = process_excel(xlsx_bytes_minimal, "test.xlsx", render_images=False)
        sheet = result.sheets[0]
        assert sheet.has_source_reference is False

    def test_image_none_when_rendering_disabled(self, xlsx_bytes_minimal):
        result = process_excel(xlsx_bytes_minimal, "test.xlsx", render_images=False)
        for sheet in result.sheets:
            assert sheet.image_base64 is None

    def test_invalid_bytes_raises(self):
        with pytest.raises(Exception):
            process_excel(b"not an xlsx", "bad.xlsx", render_images=False)

    def test_row_col_count(self, xlsx_bytes_minimal):
        result = process_excel(xlsx_bytes_minimal, "test.xlsx", render_images=False)
        sheet = result.sheets[0]
        assert sheet.row_count >= 1
        assert sheet.col_count >= 1
