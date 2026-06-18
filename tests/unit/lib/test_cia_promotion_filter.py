"""Unit tests for cia_promotion_filter.

GitHub Issue: #1251
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest

_LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(_LIB_DIR))

from cia_promotion_filter import load_filter_config, should_promote  # noqa: E402


def _signal(*, freq=3, max_label="warning", confidence=None, distinct_sessions=2):
    raw = {"max_severity_label": max_label, "distinct_sessions": distinct_sessions}
    if confidence is not None:
        raw["confidence"] = confidence
    return {"frequency": freq, "raw_data": raw}


class TestShouldPromote:
    def test_low_severity_low_recurrence_rejected(self):
        """Severity=info and recurrence=1 should be rejected when thresholds are higher."""
        cfg = {"min_severity": "medium", "min_confidence": 0.0, "min_recurrence": 2, "recurrence_window_days": 7}
        s = _signal(freq=1, max_label="info")
        allow, reason = should_promote(s, config=cfg)
        
        assert allow is False
        # Reason should mention either severity or recurrence (both are below threshold)
        assert "severity" in reason.lower() or "recurrence" in reason.lower()

    def test_low_confidence_rejected(self):
        """Confidence=0.5 below min_confidence=0.7 should be rejected."""
        cfg = {"min_severity": "info", "min_confidence": 0.7, "min_recurrence": 1, "recurrence_window_days": 7}
        s = _signal(freq=3, max_label="warning", confidence=0.5)
        allow, reason = should_promote(s, config=cfg)
        
        assert allow is False
        assert "confidence" in reason.lower()

    def test_passes_all_thresholds(self):
        """Signal passing all thresholds should be promoted."""
        cfg = {"min_severity": "medium", "min_confidence": 0.7, "min_recurrence": 2, "recurrence_window_days": 7}
        s = _signal(freq=2, max_label="warning", confidence=0.8)
        allow, reason = should_promote(s, config=cfg)
        
        assert allow is True
        # Reason could mention "passed" or "promoted" or specific thresholds met
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_error_severity_always_bypasses(self):
        """Error severity should always bypass all other thresholds."""
        cfg = {"min_severity": "high", "min_confidence": 0.99, "min_recurrence": 100, "recurrence_window_days": 7}
        s = _signal(freq=1, max_label="error", confidence=0.0)
        allow, reason = should_promote(s, config=cfg)
        
        assert allow is True
        assert "error" in reason.lower() or "bypass" in reason.lower()

    def test_missing_confidence_treated_as_one(self):
        """Missing confidence should be treated as 1.0 and pass 0.7 threshold."""
        cfg = {"min_severity": "info", "min_confidence": 0.7, "min_recurrence": 1, "recurrence_window_days": 7}
        s = _signal(freq=2, max_label="warning", confidence=None)
        allow, reason = should_promote(s, config=cfg)
        
        assert allow is True
        # Should pass because missing confidence is treated as 1.0 >= 0.7

    def test_info_passes_low_severity_threshold(self):
        """Info severity should pass when min_severity is 'info' or 'low'."""
        # Test with min_severity = "info"
        cfg = {"min_severity": "info", "min_confidence": 0.0, "min_recurrence": 1, "recurrence_window_days": 7}
        s = _signal(freq=1, max_label="info")
        allow, reason = should_promote(s, config=cfg)
        assert allow is True
        
        # Test with min_severity = "low"
        cfg["min_severity"] = "low"
        allow, reason = should_promote(s, config=cfg)
        assert allow is True

    def test_info_fails_medium_severity_threshold(self):
        """Info severity should fail when min_severity is 'medium' or 'high'."""
        # Test with min_severity = "medium"
        cfg = {"min_severity": "medium", "min_confidence": 0.0, "min_recurrence": 1, "recurrence_window_days": 7}
        s = _signal(freq=1, max_label="info")
        allow, reason = should_promote(s, config=cfg)
        assert allow is False
        assert "severity" in reason.lower()
        
        # Test with min_severity = "high"
        cfg["min_severity"] = "high"
        allow, reason = should_promote(s, config=cfg)
        assert allow is False
        assert "severity" in reason.lower()

    def test_warning_passes_medium_fails_high(self):
        """Warning severity should pass medium threshold but fail high threshold."""
        # Pass with medium
        cfg = {"min_severity": "medium", "min_confidence": 0.0, "min_recurrence": 1, "recurrence_window_days": 7}
        s = _signal(freq=1, max_label="warning")
        allow, reason = should_promote(s, config=cfg)
        assert allow is True
        
        # Fail with high
        cfg["min_severity"] = "high"
        allow, reason = should_promote(s, config=cfg)
        assert allow is False
        assert "severity" in reason.lower()

    def test_exact_recurrence_threshold(self):
        """Signal with exact min_recurrence should pass."""
        cfg = {"min_severity": "info", "min_confidence": 0.0, "min_recurrence": 5, "recurrence_window_days": 7}
        s = _signal(freq=5, max_label="info")
        allow, reason = should_promote(s, config=cfg)
        assert allow is True
        
        # One below should fail
        s = _signal(freq=4, max_label="info")
        allow, reason = should_promote(s, config=cfg)
        assert allow is False
        assert "recurrence" in reason.lower()

    def test_exact_confidence_threshold(self):
        """Signal with exact min_confidence should pass."""
        cfg = {"min_severity": "info", "min_confidence": 0.85, "min_recurrence": 1, "recurrence_window_days": 7}
        s = _signal(freq=1, max_label="info", confidence=0.85)
        allow, reason = should_promote(s, config=cfg)
        assert allow is True
        
        # Slightly below should fail
        s = _signal(freq=1, max_label="info", confidence=0.84)
        allow, reason = should_promote(s, config=cfg)
        assert allow is False
        assert "confidence" in reason.lower()


class TestLoadFilterConfig:
    def test_loads_defaults_when_no_project_config(self, tmp_path):
        """Should load defaults when no project config exists."""
        # tmp_path has no .claude/config/cia_filter.json
        cfg = load_filter_config(tmp_path)
        
        # Should have all required fields
        assert "min_severity" in cfg
        assert "min_confidence" in cfg
        assert "min_recurrence" in cfg
        assert "recurrence_window_days" in cfg
        
        # Types should be correct
        assert isinstance(cfg["min_confidence"], (int, float))
        assert isinstance(cfg["min_recurrence"], int)
        assert isinstance(cfg["recurrence_window_days"], int)
        assert cfg["min_severity"] in ["info", "low", "medium", "high"]

    def test_project_config_overrides_defaults(self, tmp_path):
        """Project config should override default values."""
        proj_cfg_dir = tmp_path / ".claude" / "config"
        proj_cfg_dir.mkdir(parents=True)
        proj_cfg = proj_cfg_dir / "cia_filter.json"
        proj_cfg.write_text(json.dumps({
            "min_severity": "high",
            "min_confidence": 0.9,
            "min_recurrence": 5,
            "recurrence_window_days": 14,
        }))
        
        cfg = load_filter_config(tmp_path)
        
        assert cfg["min_severity"] == "high"
        assert cfg["min_confidence"] == 0.9
        assert cfg["min_recurrence"] == 5
        assert cfg["recurrence_window_days"] == 14

    def test_partial_project_config_merges_with_defaults(self, tmp_path):
        """Partial project config should merge with defaults."""
        proj_cfg_dir = tmp_path / ".claude" / "config"
        proj_cfg_dir.mkdir(parents=True)
        proj_cfg = proj_cfg_dir / "cia_filter.json"
        # Only override severity and confidence
        proj_cfg.write_text(json.dumps({
            "min_severity": "high",
            "min_confidence": 0.95,
        }))
        
        cfg = load_filter_config(tmp_path)
        
        # Overridden values
        assert cfg["min_severity"] == "high"
        assert cfg["min_confidence"] == 0.95
        
        # Default values should still be present
        assert "min_recurrence" in cfg
        assert "recurrence_window_days" in cfg
        assert isinstance(cfg["min_recurrence"], int)
        assert isinstance(cfg["recurrence_window_days"], int)

    def test_invalid_json_falls_back_to_defaults(self, tmp_path):
        """Invalid JSON in project config should fall back to defaults."""
        proj_cfg_dir = tmp_path / ".claude" / "config"
        proj_cfg_dir.mkdir(parents=True)
        proj_cfg = proj_cfg_dir / "cia_filter.json"
        proj_cfg.write_text("{ invalid json }")
        
        # Should not raise, should fall back to defaults
        cfg = load_filter_config(tmp_path)
        
        # Should have all default fields
        assert "min_severity" in cfg
        assert "min_confidence" in cfg
        assert "min_recurrence" in cfg
        assert "recurrence_window_days" in cfg

    def test_none_project_root_uses_git_root(self):
        """None project_root should use git rev-parse to find root."""
        # This test will work in the actual repo
        cfg = load_filter_config(None)
        
        # Should load some config (either project or defaults)
        assert "min_severity" in cfg
        assert "min_confidence" in cfg
        assert "min_recurrence" in cfg
        assert "recurrence_window_days" in cfg

    def test_empty_project_config_uses_defaults(self, tmp_path):
        """Empty JSON object in project config should use all defaults."""
        proj_cfg_dir = tmp_path / ".claude" / "config"
        proj_cfg_dir.mkdir(parents=True)
        proj_cfg = proj_cfg_dir / "cia_filter.json"
        proj_cfg.write_text("{}")
        
        cfg = load_filter_config(tmp_path)
        
        # Should have all default fields
        assert "min_severity" in cfg
        assert "min_confidence" in cfg
        assert "min_recurrence" in cfg
        assert "recurrence_window_days" in cfg