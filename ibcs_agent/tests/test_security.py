"""Tests for security utilities."""

import base64
import pytest

from ibcs_agent.security import (
    SecurityError,
    decode_and_validate_file,
    validate_file_magic,
    validate_file_size,
    validate_filename,
    validate_rule_id,
    _ZIP_MAGIC,
    _PDF_MAGIC,
)


class TestValidateFileMagic:
    def test_valid_pptx_magic(self):
        file_bytes = _ZIP_MAGIC + b"\x00" * 100
        validate_file_magic(file_bytes, "pptx")  # Should not raise

    def test_valid_xlsx_magic(self):
        file_bytes = _ZIP_MAGIC + b"\x00" * 100
        validate_file_magic(file_bytes, "xlsx")  # Should not raise

    def test_valid_pdf_magic(self):
        file_bytes = _PDF_MAGIC + b"-1.4\n" + b"\x00" * 100
        validate_file_magic(file_bytes, "pdf")  # Should not raise

    def test_wrong_magic_for_pptx_raises(self):
        with pytest.raises(SecurityError, match="ZIP"):
            validate_file_magic(b"\x00\x00\x00\x00\x00\x00\x00\x00", "pptx")

    def test_wrong_magic_for_pdf_raises(self):
        with pytest.raises(SecurityError, match="%PDF"):
            validate_file_magic(_ZIP_MAGIC + b"\x00" * 100, "pdf")

    def test_too_small_raises(self):
        with pytest.raises(SecurityError, match="too small"):
            validate_file_magic(b"\x50\x4b", "pptx")

    def test_exe_as_pptx_rejected(self):
        exe_magic = b"\x4d\x5a\x00\x00\x00\x00\x00\x00"  # MZ header
        with pytest.raises(SecurityError):
            validate_file_magic(exe_magic, "pptx")


class TestValidateFileSize:
    def test_within_limit_passes(self):
        validate_file_size(b"x" * (10 * 1024 * 1024), max_mb=50.0)

    def test_exactly_at_limit_passes(self):
        validate_file_size(b"x" * (50 * 1024 * 1024), max_mb=50.0)

    def test_over_limit_raises(self):
        with pytest.raises(SecurityError, match="exceeds"):
            validate_file_size(b"x" * (51 * 1024 * 1024), max_mb=50.0)

    def test_custom_limit(self):
        with pytest.raises(SecurityError):
            validate_file_size(b"x" * (6 * 1024 * 1024), max_mb=5.0)


class TestValidateFilename:
    def test_valid_pptx(self):
        result = validate_filename("report_q1_2024.pptx")
        assert result == "report_q1_2024.pptx"

    def test_valid_pdf(self):
        result = validate_filename("bericht.pdf")
        assert result == "bericht.pdf"

    def test_valid_xlsx(self):
        result = validate_filename("data.xlsx")
        assert result == "data.xlsx"

    def test_path_traversal_stripped(self):
        result = validate_filename("../../etc/passwd.pptx")
        assert result == "passwd.pptx"

    def test_windows_path_stripped(self):
        result = validate_filename("C:\\Users\\test\\report.xlsx")
        assert result == "report.xlsx"

    def test_empty_filename_raises(self):
        with pytest.raises(SecurityError):
            validate_filename("")

    def test_unsupported_extension_raises(self):
        with pytest.raises(SecurityError, match="extension"):
            validate_filename("malware.exe")

    def test_docx_rejected(self):
        with pytest.raises(SecurityError):
            validate_filename("report.docx")

    def test_no_extension_raises(self):
        with pytest.raises(SecurityError):
            validate_filename("filename_without_extension")

    def test_null_byte_raises(self):
        with pytest.raises(SecurityError, match="control"):
            validate_filename("report\x00.pptx")

    def test_too_long_raises(self):
        long_name = "a" * 250 + ".pptx"
        with pytest.raises(SecurityError, match="long"):
            validate_filename(long_name)

    def test_german_umlauts_accepted(self):
        result = validate_filename("Bericht_Übersicht.pptx")
        assert result.endswith(".pptx")


class TestValidateRuleId:
    def test_valid_rule_ids(self):
        for rule_id in ["CK1", "S1", "SI4", "ST3", "E4", "U1"]:
            result = validate_rule_id(rule_id)
            assert result == rule_id

    def test_lowercase_normalized(self):
        assert validate_rule_id("ck1") == "CK1"

    def test_whitespace_stripped(self):
        assert validate_rule_id("  CK1  ") == "CK1"

    def test_sql_injection_rejected(self):
        with pytest.raises(SecurityError):
            validate_rule_id("'; DROP TABLE rules;--")

    def test_empty_raises(self):
        with pytest.raises(SecurityError):
            validate_rule_id("")

    def test_too_long_raises(self):
        with pytest.raises(SecurityError):
            validate_rule_id("TOOLONGRULEID123")

    def test_special_chars_rejected(self):
        with pytest.raises(SecurityError):
            validate_rule_id("CK1<script>")


class TestDecodeAndValidateFile:
    def test_valid_pptx(self, pptx_bytes_minimal):
        b64 = base64.b64encode(pptx_bytes_minimal).decode()
        file_bytes, safe_name, file_type = decode_and_validate_file(b64, "test.pptx")
        assert file_type == "pptx"
        assert safe_name == "test.pptx"
        assert len(file_bytes) > 0

    def test_valid_xlsx(self, xlsx_bytes_minimal):
        b64 = base64.b64encode(xlsx_bytes_minimal).decode()
        file_bytes, safe_name, file_type = decode_and_validate_file(b64, "test.xlsx")
        assert file_type == "xlsx"

    def test_invalid_base64_raises(self):
        with pytest.raises(ValueError, match="base64"):
            decode_and_validate_file("NOT_VALID_BASE64!!!", "test.pptx")

    def test_path_traversal_in_name_sanitized(self, pptx_bytes_minimal):
        b64 = base64.b64encode(pptx_bytes_minimal).decode()
        _, safe_name, _ = decode_and_validate_file(b64, "../../etc/test.pptx")
        assert "/" not in safe_name
        assert ".." not in safe_name

    def test_oversized_raises(self, pptx_bytes_minimal):
        b64 = base64.b64encode(pptx_bytes_minimal).decode()
        with pytest.raises(SecurityError, match="exceeds"):
            decode_and_validate_file(b64, "test.pptx", max_mb=0.000001)


class TestObservability:
    def test_health_check_structure(self):
        from ibcs_agent.observability import health_check
        result = health_check(check_azure=False)
        assert "status" in result
        assert result["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in result
        assert "timestamp_utc" in result

    def test_health_check_rules_component(self):
        from ibcs_agent.observability import health_check
        result = health_check(check_azure=False)
        assert "rules" in result["components"]
        assert result["components"]["rules"]["status"] == "ok"

    def test_correlation_id_generated(self):
        from ibcs_agent.observability import get_correlation_id, clear_correlation_id
        clear_correlation_id()
        cid = get_correlation_id()
        assert len(cid) == 36  # UUID format
        assert "-" in cid

    def test_set_correlation_id(self):
        from ibcs_agent.observability import set_correlation_id, get_correlation_id
        set_correlation_id("test-cid-123")
        assert get_correlation_id() == "test-cid-123"

    def test_metrics_counter(self):
        from ibcs_agent.observability import Metrics
        m = Metrics()
        m.increment("analyses")
        m.increment("analyses")
        snapshot = m.snapshot()
        assert snapshot["counters"]["analyses"] == 2

    def test_timed_operation_context(self):
        from ibcs_agent.observability import timed_operation
        with timed_operation("test_op") as ctx:
            ctx["result"] = "ok"
        # Should not raise
