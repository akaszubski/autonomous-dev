"""Tests for context_window_manager.py."""

import os
from unittest.mock import patch

import pytest


class TestBackendDetection:
    """Test backend detection and configuration."""

    def test_default_backend_is_claude(self):
        """Test Claude is default backend."""
        from plugins.autonomous_dev.lib.context_window_manager import get_backend_name

        with patch.dict(os.environ, {}, clear=True):
            assert get_backend_name() == "claude"

    def test_backend_from_env(self):
        """Test backend detection from BACKEND env var."""
        from plugins.autonomous_dev.lib.context_window_manager import get_backend_name

        with patch.dict(os.environ, {"BACKEND": "openai"}):
            assert get_backend_name() == "openai"

    def test_unknown_backend_fallback(self):
        """Test unknown backend falls back to 'custom'."""
        from plugins.autonomous_dev.lib.context_window_manager import get_backend_name

        with patch.dict(os.environ, {"BACKEND": "unknown_backend_xyz"}):
            assert get_backend_name() == "custom"

    def test_backend_name_sanitization(self):
        """Test backend name is sanitized (CWE-117 prevention)."""
        from plugins.autonomous_dev.lib.context_window_manager import _sanitize_backend_name

        # Normal names pass through
        assert _sanitize_backend_name("claude") == "claude"
        assert _sanitize_backend_name("OpenAI") == "openai"

        # Special characters removed
        assert _sanitize_backend_name("my-backend") == "my_backend"
        assert _sanitize_backend_name("back\nend") == "back_end"

        # Length limited
        long_name = "a" * 100
        assert len(_sanitize_backend_name(long_name)) <= 50


class TestContextWindowSize:
    """Test context window size detection."""

    def test_claude_default_200k(self):
        """Test Claude default is 200K tokens."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"BACKEND": "claude"}, clear=True):
            assert get_context_window_size() == 200_000

    def test_openai_default_128k(self):
        """Test OpenAI default is 128K tokens."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"BACKEND": "openai"}, clear=True):
            assert get_context_window_size() == 128_000

    def test_gemini_default_1m(self):
        """Test Gemini default is 1M tokens."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"BACKEND": "gemini"}, clear=True):
            assert get_context_window_size() == 1_000_000

    def test_ollama_default_8k(self):
        """Test Ollama default is 8K tokens (conservative)."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"BACKEND": "ollama"}, clear=True):
            assert get_context_window_size() == 8_192

    def test_custom_window_size_from_env(self):
        """Test custom window size from environment."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"CONTEXT_WINDOW_SIZE": "100000"}):
            assert get_context_window_size() == 100_000

    def test_invalid_window_size_fallback(self):
        """Test invalid window size falls back to default."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"CONTEXT_WINDOW_SIZE": "not_a_number", "BACKEND": "claude"}):
            assert get_context_window_size() == 200_000

    def test_window_size_out_of_range_raises(self):
        """Test window size out of range raises ValueError."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_window_size

        with patch.dict(os.environ, {"CONTEXT_WINDOW_SIZE": "100"}):  # Too small
            with pytest.raises(ValueError, match="out of valid range"):
                get_context_window_size()


class TestCompactionThreshold:
    """Test compaction threshold calculation."""

    def test_default_threshold_85_percent(self):
        """Test default threshold is 85%."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_threshold_pct

        with patch.dict(os.environ, {}, clear=True):
            assert get_compaction_threshold_pct() == 85

    def test_custom_threshold_from_env(self):
        """Test custom threshold from environment."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_threshold_pct

        with patch.dict(os.environ, {"COMPACTION_THRESHOLD_PCT": "90"}):
            assert get_compaction_threshold_pct() == 90

    def test_threshold_tokens_calculation(self):
        """Test threshold token calculation."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_threshold

        # Claude: 200K * 85% = 170K
        with patch.dict(os.environ, {"BACKEND": "claude"}, clear=True):
            assert get_compaction_threshold() == 170_000

    def test_should_trigger_compaction(self):
        """Test compaction trigger detection."""
        from plugins.autonomous_dev.lib.context_window_manager import should_trigger_compaction

        with patch.dict(os.environ, {"BACKEND": "claude"}, clear=True):
            # Below threshold (170K) - no trigger
            assert should_trigger_compaction(100_000) is False
            assert should_trigger_compaction(169_999) is False

            # At or above threshold - trigger
            assert should_trigger_compaction(170_000) is True
            assert should_trigger_compaction(180_000) is True


class TestCustomCompaction:
    """Test custom compaction detection."""

    def test_claude_no_custom_compaction_by_default(self):
        """Test Claude doesn't need custom compaction."""
        from plugins.autonomous_dev.lib.context_window_manager import needs_custom_compaction

        with patch.dict(os.environ, {"BACKEND": "claude"}, clear=True):
            assert needs_custom_compaction() is False

    def test_openai_needs_custom_compaction(self):
        """Test OpenAI needs custom compaction."""
        from plugins.autonomous_dev.lib.context_window_manager import needs_custom_compaction

        with patch.dict(os.environ, {"BACKEND": "openai"}, clear=True):
            assert needs_custom_compaction() is True

    def test_explicit_custom_compaction_override(self):
        """Test explicit CUSTOM_CONTEXT_COMPACTION overrides default."""
        from plugins.autonomous_dev.lib.context_window_manager import needs_custom_compaction

        # Override Claude's default (false -> true)
        with patch.dict(os.environ, {"BACKEND": "claude", "CUSTOM_CONTEXT_COMPACTION": "true"}):
            assert needs_custom_compaction() is True

        # Override OpenAI's default (true -> false)
        with patch.dict(os.environ, {"BACKEND": "openai", "CUSTOM_CONTEXT_COMPACTION": "false"}):
            assert needs_custom_compaction() is False


class TestCompactionStrategy:
    """Test compaction strategy selection."""

    def test_claude_default_auto_strategy(self):
        """Test Claude defaults to auto strategy."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_strategy

        with patch.dict(os.environ, {"BACKEND": "claude"}, clear=True):
            assert get_compaction_strategy() == "auto"

    def test_openai_default_summarize_strategy(self):
        """Test OpenAI defaults to summarize strategy."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_strategy

        with patch.dict(os.environ, {"BACKEND": "openai"}, clear=True):
            assert get_compaction_strategy() == "summarize"

    def test_ollama_default_truncate_strategy(self):
        """Test Ollama defaults to truncate strategy."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_strategy

        with patch.dict(os.environ, {"BACKEND": "ollama"}, clear=True):
            assert get_compaction_strategy() == "truncate"

    def test_custom_strategy_from_env(self):
        """Test custom strategy from environment."""
        from plugins.autonomous_dev.lib.context_window_manager import get_compaction_strategy

        with patch.dict(os.environ, {"COMPACTION_STRATEGY": "clustering"}):
            assert get_compaction_strategy() == "clustering"


class TestContextStatus:
    """Test context status reporting."""

    def test_get_context_status(self):
        """Test comprehensive status reporting."""
        from plugins.autonomous_dev.lib.context_window_manager import get_context_status

        with patch.dict(os.environ, {"BACKEND": "openai"}, clear=True):
            status = get_context_status()

            assert status["backend"] == "openai"
            assert status["context_window_size"] == 128_000
            assert status["compaction_threshold_pct"] == 85
            assert status["needs_custom_compaction"] is True
            assert status["compaction_strategy"] == "summarize"

    def test_checkpoint_before_compaction_default(self):
        """Test checkpoint default is True."""
        from plugins.autonomous_dev.lib.context_window_manager import get_checkpoint_before_compaction

        with patch.dict(os.environ, {}, clear=True):
            assert get_checkpoint_before_compaction() is True

    def test_checkpoint_before_compaction_disabled(self):
        """Test checkpoint can be disabled."""
        from plugins.autonomous_dev.lib.context_window_manager import get_checkpoint_before_compaction

        with patch.dict(os.environ, {"CHECKPOINT_BEFORE_COMPACTION": "false"}):
            assert get_checkpoint_before_compaction() is False
