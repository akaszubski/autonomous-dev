#!/usr/bin/env python3
"""Test for Issue #1355: /tmp exclusion in bash code-file gate.

Verifies that detect_bash_code_file_write returns ("", "") for paths
starting with /tmp/, /var/tmp/, or $TMPDIR.
"""

import os
import sys
from pathlib import Path

import pytest

# Path setup
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from edit_tier_classifier import detect_bash_code_file_write


class TestTmpExclusion:
    """Test /tmp path exclusion (Issue #1355)."""

    def test_tmp_direct_redirect(self):
        """Direct redirect to /tmp/file.py should not be detected."""
        result = detect_bash_code_file_write("cat > /tmp/test.py")
        assert result == ("", ""), f"Expected no detection for /tmp/test.py, got {result}"

    def test_var_tmp_redirect(self):
        """Redirect to /var/tmp/ should not be detected."""
        result = detect_bash_code_file_write("echo 'code' > /var/tmp/script.py")
        assert result == ("", ""), f"Expected no detection for /var/tmp/script.py, got {result}"

    def test_tmp_with_subdirs(self):
        """Redirect to /tmp/subdir/file.py should not be detected."""
        result = detect_bash_code_file_write("cat > /tmp/subdir/nested/file.py")
        assert result == ("", ""), f"Expected no detection for /tmp/subdir/nested/file.py, got {result}"

    def test_tmpdir_env_variable(self):
        """Redirect to $TMPDIR should not be detected."""
        # Set TMPDIR for this test
        old_tmpdir = os.environ.get("TMPDIR")
        try:
            os.environ["TMPDIR"] = "/custom/tmp"
            result = detect_bash_code_file_write("cat > /custom/tmp/test.py")
            assert result == ("", ""), f"Expected no detection for TMPDIR path, got {result}"
        finally:
            if old_tmpdir:
                os.environ["TMPDIR"] = old_tmpdir
            else:
                os.environ.pop("TMPDIR", None)

    def test_non_tmp_still_detected(self):
        """Non-/tmp paths should still be detected normally."""
        result = detect_bash_code_file_write("cat > /repo/src/main.py")
        assert result == ("/repo/src/main.py", "cat redirect"), \
            f"Expected detection for /repo/src/main.py, got {result}"

    def test_tmp_with_quotes(self):
        """Quoted /tmp paths should not be detected."""
        result = detect_bash_code_file_write('cat > "/tmp/test file.py"')
        assert result == ("", ""), f"Expected no detection for quoted /tmp path, got {result}"

    def test_tee_to_tmp(self):
        """tee to /tmp should not be detected."""
        result = detect_bash_code_file_write("echo 'data' | tee /tmp/output.py")
        assert result == ("", ""), f"Expected no detection for tee to /tmp, got {result}"

    def test_sed_inplace_tmp(self):
        """sed -i on /tmp file should not be detected."""
        result = detect_bash_code_file_write("sed -i 's/old/new/g' /tmp/script.py")
        assert result == ("", ""), f"Expected no detection for sed -i on /tmp, got {result}"

    def test_heredoc_to_tmp(self):
        """Heredoc redirect to /tmp should not be detected."""
        cmd = """cat > /tmp/test.py << 'EOF'
class Test:
    pass
EOF"""
        result = detect_bash_code_file_write(cmd)
        assert result == ("", ""), f"Expected no detection for heredoc to /tmp, got {result}"

    def test_python_c_write_tmp(self):
        """python -c writing to /tmp should not be detected."""
        result = detect_bash_code_file_write('python -c "open(\'/tmp/test.py\', \'w\').write(\'code\')"')
        assert result == ("", ""), f"Expected no detection for python -c to /tmp, got {result}"

    def test_base64_decode_to_tmp(self):
        """base64 decode to /tmp should not be detected."""
        result = detect_bash_code_file_write("echo 'Y29kZQ==' | base64 -d > /tmp/decoded.py")
        assert result == ("", ""), f"Expected no detection for base64 to /tmp, got {result}"

    def test_awk_to_tmp(self):
        """awk redirect to /tmp should not be detected."""
        result = detect_bash_code_file_write("awk '{print $1}' data.txt > /tmp/output.py")
        assert result == ("", ""), f"Expected no detection for awk to /tmp, got {result}"

    def test_relative_tmp_not_excluded(self):
        """Relative path tmp/file.py (not /tmp) should still be detected."""
        result = detect_bash_code_file_write("cat > tmp/file.py")
        assert result == ("tmp/file.py", "cat redirect"), \
            f"Expected detection for relative tmp/file.py, got {result}"

    def test_tmp_without_trailing_slash(self):
        """Path /tmpfile.py (no slash after /tmp) should still be detected."""
        result = detect_bash_code_file_write("cat > /tmpfile.py")
        assert result == ("/tmpfile.py", "cat redirect"), \
            f"Expected detection for /tmpfile.py (no slash), got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])