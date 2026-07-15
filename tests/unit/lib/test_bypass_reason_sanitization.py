#!/usr/bin/env python3
"""
Tests for bypass_reason sanitization in pipeline_completion_state.

Ensures that control characters are stripped and text is truncated
before storage to prevent log injection and excessive storage.

Issue: #1380
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))
from pipeline_completion_state import (
    _sanitize_bypass_reason,
    record_plan_critic_skipped,
    write_coordinator_bypass_verdict,
    _read_state
)


class TestSanitizeBypassReason:
    """Test the _sanitize_bypass_reason utility function."""
    
    def test_strips_control_characters(self):
        """Control characters (except newline/tab) should be stripped."""
        # Test various control characters
        input_text = "Normal text\x00with\x01null\x02and\x03other\x04control\x05chars\x1f"
        result = _sanitize_bypass_reason(input_text)
        assert result == "Normal textwithnullandothercontrolchars"
        
        # Test bell, backspace, form feed, etc.
        input_text = "Text\x07bell\x08backspace\x0cformfeed\x0dcarriage"
        result = _sanitize_bypass_reason(input_text)
        assert result == "Textbellbackspaceformfeedcarriage"
    
    def test_preserves_newline_and_tab(self):
        """Newline and tab characters should be preserved."""
        input_text = "Line one\nLine two\tTabbed"
        result = _sanitize_bypass_reason(input_text)
        assert result == "Line one\nLine two\tTabbed"
        
        # Mix with control chars that should be stripped
        input_text = "Line\x00one\nLine\x01two\tTabbed\x02"
        result = _sanitize_bypass_reason(input_text)
        assert result == "Lineone\nLinetwo\tTabbed"
    
    def test_truncates_to_2048_chars(self):
        """Text longer than 2048 chars should be truncated."""
        # Generate text longer than 2048 chars
        long_text = "A" * 3000
        result = _sanitize_bypass_reason(long_text)
        assert len(result) == 2048
        assert result == "A" * 2048
        
        # Text with control chars that gets truncated after stripping
        long_text_with_control = ("B" * 2000) + "\x00" + ("C" * 1000)
        result = _sanitize_bypass_reason(long_text_with_control)
        assert len(result) == 2048
        assert result == ("B" * 2000) + ("C" * 48)
    
    def test_handles_none(self):
        """None input should return None."""
        result = _sanitize_bypass_reason(None)
        assert result is None
    
    def test_handles_empty_string(self):
        """Empty string should pass through unchanged."""
        result = _sanitize_bypass_reason("")
        assert result == ""
    
    def test_normal_text_unchanged(self):
        """Normal printable text should pass through unchanged."""
        normal_text = "This is a normal bypass reason with punctuation! And numbers: 123."
        result = _sanitize_bypass_reason(normal_text)
        assert result == normal_text
    
    def test_unicode_preserved(self):
        """Unicode characters should be preserved if printable."""
        unicode_text = "Unicode text: émoji 🎉 and symbols ™ © ® µ π"
        result = _sanitize_bypass_reason(unicode_text)
        assert result == unicode_text
    
    def test_mixed_content(self):
        """Mixed content with printable, newlines, tabs, and control chars."""
        mixed = "Normal\nText\twith\x00null\x01and\nnewlines\ttabs\x1fend"
        result = _sanitize_bypass_reason(mixed)
        assert result == "Normal\nText\twithnulland\nnewlines\ttabsend"


class TestRecordPlanCriticSkippedSanitization:
    """Test that record_plan_critic_skipped sanitizes bypass_reason."""
    
    @patch('pipeline_completion_state._write_state')
    @patch('pipeline_completion_state._read_state')
    def test_sanitizes_bypass_reason_with_control_chars(self, mock_read, mock_write):
        """bypass_reason with control chars should be sanitized before storage."""
        mock_read.return_value = {}
        
        # Call with bypass_reason containing control chars
        dirty_reason = "Skipping\x00because\x01of\x02mechanical\x03extension"
        record_plan_critic_skipped(
            "test-session",
            issue_number=123,
            bypass_reason=dirty_reason
        )
        
        # Verify the sanitized version was written
        mock_write.assert_called_once()
        written_state = mock_write.call_args[0][1]
        assert "plan_critic_bypass_reason" in written_state
        
        # Check both issue keys (123 and 0) have sanitized text
        assert written_state["plan_critic_bypass_reason"]["123"] == "Skippingbecauseofmechanicalextension"
        assert written_state["plan_critic_bypass_reason"]["0"] == "Skippingbecauseofmechanicalextension"
    
    @patch('pipeline_completion_state._write_state')
    @patch('pipeline_completion_state._read_state')
    def test_truncates_long_bypass_reason(self, mock_read, mock_write):
        """Long bypass_reason should be truncated to 2048 chars."""
        mock_read.return_value = {}
        
        # Call with very long bypass_reason
        long_reason = "X" * 3000
        record_plan_critic_skipped(
            "test-session",
            issue_number=456,
            bypass_reason=long_reason
        )
        
        # Verify truncated version was written
        mock_write.assert_called_once()
        written_state = mock_write.call_args[0][1]
        stored_reason = written_state["plan_critic_bypass_reason"]["456"]
        assert len(stored_reason) == 2048
        assert stored_reason == "X" * 2048
    
    @patch('pipeline_completion_state._write_state')
    @patch('pipeline_completion_state._read_state')
    def test_handles_none_bypass_reason(self, mock_read, mock_write):
        """None bypass_reason should not crash or store anything."""
        mock_read.return_value = {}
        
        # Call with None bypass_reason
        record_plan_critic_skipped(
            "test-session",
            issue_number=789,
            bypass_reason=None
        )
        
        # Verify state was written but no bypass_reason stored
        mock_write.assert_called_once()
        written_state = mock_write.call_args[0][1]
        assert "plan_critic_bypass_reason" not in written_state
    
    @patch('pipeline_completion_state._write_state')
    @patch('pipeline_completion_state._read_state')
    def test_preserves_newlines_and_tabs(self, mock_read, mock_write):
        """Newlines and tabs in bypass_reason should be preserved."""
        mock_read.return_value = {}
        
        # Call with bypass_reason containing newlines and tabs
        reason_with_formatting = "Line 1\nLine 2\tTabbed section"
        record_plan_critic_skipped(
            "test-session",
            issue_number=234,
            bypass_reason=reason_with_formatting
        )
        
        # Verify formatting was preserved
        mock_write.assert_called_once()
        written_state = mock_write.call_args[0][1]
        stored_reason = written_state["plan_critic_bypass_reason"]["234"]
        assert stored_reason == "Line 1\nLine 2\tTabbed section"


class TestWriteCoordinatorBypassVerdictSanitization:
    """Test that write_coordinator_bypass_verdict sanitizes bypass_reason."""
    
    def test_sanitizes_bypass_reason_with_control_chars(self):
        """bypass_reason with control chars should be sanitized in verdict file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            # Change to temp dir for test
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Call with bypass_reason containing control chars
                dirty_reason = "Mechanical\x00extension\x01issue\x02detected"
                write_coordinator_bypass_verdict(
                    issue_number=999,
                    bypass_reason=dirty_reason,
                    plan_summary="Test summary"
                )
                
                # Read the verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                assert verdict_file.exists()
                
                with open(verdict_file) as f:
                    verdict_data = json.load(f)
                
                # Verify control chars were stripped
                assert "\x00" not in verdict_data["reasoning"]
                assert "\x01" not in verdict_data["reasoning"]
                assert "\x02" not in verdict_data["reasoning"]
                assert "Mechanicalextensionissuedetected" in verdict_data["reasoning"]
                
            finally:
                os.chdir(original_cwd)
    
    def test_truncates_long_bypass_reason(self):
        """Long bypass_reason should be truncated in verdict file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            # Change to temp dir for test
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Call with very long bypass_reason
                long_reason = "Y" * 3000
                write_coordinator_bypass_verdict(
                    issue_number=888,
                    bypass_reason=long_reason
                )
                
                # Read the verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                assert verdict_file.exists()
                
                with open(verdict_file) as f:
                    verdict_data = json.load(f)
                
                # The reasoning should contain truncated version
                # Note: It's wrapped with "Coordinator bypass: " prefix
                # so we check the bypass part is truncated
                assert verdict_data["reasoning"].startswith("Coordinator bypass: ")
                # Extract just the bypass reason part (after "Coordinator bypass: " and before the ".")
                bypass_part = verdict_data["reasoning"].split("Coordinator bypass: ")[1].split(".")[0]
                assert len(bypass_part) == 2048
                assert bypass_part == "Y" * 2048
                
            finally:
                os.chdir(original_cwd)
    
    def test_handles_empty_bypass_reason_after_sanitization(self):
        """Empty bypass_reason after sanitization should not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            # Change to temp dir for test
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Call with bypass_reason that becomes empty after sanitization
                # (all control chars)
                control_only_reason = "\x00\x01\x02\x03\x04"
                write_coordinator_bypass_verdict(
                    issue_number=777,
                    bypass_reason=control_only_reason
                )
                
                # Read the verdict file - should not crash
                verdict_file = claude_dir / "plan_critic_verdict.json"
                assert verdict_file.exists()
                
                with open(verdict_file) as f:
                    verdict_data = json.load(f)
                
                # Should have minimal reasoning
                assert "Coordinator bypass: ." in verdict_data["reasoning"]
                
            finally:
                os.chdir(original_cwd)
    
    def test_preserves_newlines_and_tabs_in_verdict(self):
        """Newlines and tabs should be preserved in verdict file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            # Change to temp dir for test
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Call with bypass_reason containing newlines and tabs
                formatted_reason = "Line 1\nLine 2\tWith tab"
                write_coordinator_bypass_verdict(
                    issue_number=666,
                    bypass_reason=formatted_reason
                )
                
                # Read the verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                assert verdict_file.exists()
                
                with open(verdict_file) as f:
                    verdict_data = json.load(f)
                
                # Verify formatting preserved
                assert "Line 1\nLine 2\tWith tab" in verdict_data["reasoning"]
                
            finally:
                os.chdir(original_cwd)


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""
    
    @patch('pipeline_completion_state._write_state')
    @patch('pipeline_completion_state._read_state')
    def test_ansi_escape_sequences_stripped(self, mock_read, mock_write):
        """ANSI escape sequences should be stripped as control chars."""
        mock_read.return_value = {}
        
        # ANSI color codes and cursor movements
        ansi_text = "\x1b[31mRed text\x1b[0m and \x1b[1mBold\x1b[0m"
        record_plan_critic_skipped(
            "test-session",
            issue_number=555,
            bypass_reason=ansi_text
        )
        
        # Verify ANSI sequences stripped
        mock_write.assert_called_once()
        written_state = mock_write.call_args[0][1]
        stored_reason = written_state["plan_critic_bypass_reason"]["555"]
        assert stored_reason == "[31mRed text[0m and [1mBold[0m"
        # Note: ESC (\x1b) is stripped but the rest of the sequence remains
    
    @patch('pipeline_completion_state._write_state')
    @patch('pipeline_completion_state._read_state')
    def test_terminal_bell_and_backspace_stripped(self, mock_read, mock_write):
        """Terminal control chars like bell and backspace should be stripped."""
        mock_read.return_value = {}
        
        # Bell (\x07), backspace (\x08), etc.
        terminal_text = "Alert\x07\x07\x07 and typo\x08\x08fixed"
        record_plan_critic_skipped(
            "test-session",
            issue_number=444,
            bypass_reason=terminal_text
        )
        
        # Verify control chars stripped
        mock_write.assert_called_once()
        written_state = mock_write.call_args[0][1]
        stored_reason = written_state["plan_critic_bypass_reason"]["444"]
        assert stored_reason == "Alert and typofixed"
    
    def test_multiline_reasoning_preserved(self):
        """Multi-line bypass reasons should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            # Change to temp dir for test
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Multi-line bypass reason
                multiline = """This is a mechanical extension because:
                1. It only adds a new field
                2. No logic changes
                3. Simple validation update"""
                
                write_coordinator_bypass_verdict(
                    issue_number=333,
                    bypass_reason=multiline
                )
                
                # Read the verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                with open(verdict_file) as f:
                    verdict_data = json.load(f)
                
                # Verify multiline structure preserved
                assert "1. It only adds a new field" in verdict_data["reasoning"]
                assert "2. No logic changes" in verdict_data["reasoning"]
                assert "3. Simple validation update" in verdict_data["reasoning"]
                
            finally:
                os.chdir(original_cwd)
    
    def test_combined_edge_cases(self):
        """Test combination of truncation, control chars, and formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            # Change to temp dir for test
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Generate text with control chars that's also too long
                # Start with normal text, add control chars, then pad to >2048
                complex_text = "Start\x00with\nnormal\ttext\x01then" + ("Z" * 2100)
                
                write_coordinator_bypass_verdict(
                    issue_number=222,
                    bypass_reason=complex_text
                )
                
                # Read the verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                with open(verdict_file) as f:
                    verdict_data = json.load(f)
                
                # Extract the bypass part
                bypass_part = verdict_data["reasoning"].split("Coordinator bypass: ")[1].split(".")[0]
                
                # Should be sanitized AND truncated
                assert "\x00" not in bypass_part
                assert "\x01" not in bypass_part
                assert len(bypass_part) == 2048
                assert bypass_part.startswith("Startwith\nnormal\ttextthen")
                assert bypass_part.endswith("Z" * (2048 - len("Startwith\nnormal\ttextthen")))
                
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])