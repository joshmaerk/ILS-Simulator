"""Tests for IBCS rule definitions and lookup functions."""

import pytest

from ibcs_agent.rules.ibcs_rules import (
    ALL_RULES,
    RULES_BY_CATEGORY,
    RULES_BY_ID,
    SUCCESS_CATEGORIES,
    IBCSRule,
    get_metadata_rules,
    get_rule,
    get_rules_for_file_type,
    get_visual_rules,
)


class TestRuleRegistry:
    def test_all_rules_non_empty(self):
        assert len(ALL_RULES) >= 20, "Expected at least 20 IBCS rules"

    def test_rules_by_id_covers_all(self):
        assert set(RULES_BY_ID.keys()) == {r.id for r in ALL_RULES}

    def test_no_duplicate_ids(self):
        ids = [r.id for r in ALL_RULES]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs found"

    def test_all_success_categories_represented(self):
        covered = set(RULES_BY_CATEGORY.keys())
        assert covered == set(SUCCESS_CATEGORIES)

    def test_rule_fields_non_empty(self):
        for rule in ALL_RULES:
            assert rule.id, f"Rule has empty ID"
            assert rule.name, f"Rule {rule.id} has empty name"
            assert rule.description, f"Rule {rule.id} has empty description"
            assert rule.suggestion_template, f"Rule {rule.id} has empty suggestion_template"
            assert rule.check_type in ("metadata", "visual", "both")
            assert rule.severity in ("error", "warning", "info")


class TestRuleLookup:
    def test_get_rule_known_id(self):
        rule = get_rule("CK1")
        assert rule.id == "CK1"
        assert rule.category == "CHECK"

    def test_get_rule_unknown_raises(self):
        with pytest.raises(KeyError):
            get_rule("NONEXISTENT")

    def test_get_visual_rules_non_empty(self):
        visual = get_visual_rules()
        assert len(visual) > 0
        for r in visual:
            assert r.check_type in ("visual", "both")

    def test_get_metadata_rules_non_empty(self):
        meta = get_metadata_rules()
        assert len(meta) > 0
        for r in meta:
            assert r.check_type in ("metadata", "both")

    def test_get_rules_for_file_type_pptx(self):
        rules = get_rules_for_file_type("pptx")
        assert any(r.id == "CK1" for r in rules)

    def test_get_rules_for_file_type_xlsx(self):
        rules = get_rules_for_file_type("xlsx")
        assert len(rules) > 0


class TestSpecificRules:
    """Verify critical rules exist with correct severity."""

    @pytest.mark.parametrize("rule_id,expected_severity,expected_category", [
        ("S1",  "error",   "SAY"),
        ("S2",  "warning", "SAY"),
        ("U1",  "error",   "UNIFY"),
        ("CK1", "error",   "CHECK"),
        ("CK2", "error",   "CHECK"),
        ("E4",  "error",   "EXPRESS"),
        ("SI4", "error",   "SIMPLIFY"),
        ("ST3", "info",    "STRUCTURE"),
    ])
    def test_rule_severity_and_category(self, rule_id, expected_severity, expected_category):
        rule = get_rule(rule_id)
        assert rule.severity == expected_severity, f"{rule_id}: expected {expected_severity}"
        assert rule.category == expected_category, f"{rule_id}: expected {expected_category}"
