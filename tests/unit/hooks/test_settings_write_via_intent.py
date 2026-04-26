"""Integration tests for ``_detect_settings_json_write`` post-Issue #971 migration.

Validates the 8 issue acceptance scenarios end-to-end (calling the hook
function directly, not just the classifier). These are the canonical
behaviour contracts that the migration MUST preserve.

Date: 2026-04-26
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Add hook + lib dirs to path.
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

hook = importlib.import_module("unified_pre_tool")


# ---------------------------------------------------------------------------
# TestSettingsWriteViaIntent — issue #971 acceptance scenarios
# ---------------------------------------------------------------------------


class TestSettingsWriteViaIntent:
    """End-to-end behaviour of ``_detect_settings_json_write`` after migration."""

    # Scenario 1: READ on settings.json passes (false positive fix)
    def test_python_json_load_settings_passes(self):
        cmd = """python3 -c "import json; json.load(open('settings.json'))" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_python_json_load_dot_claude_settings_passes(self):
        cmd = """python3 -c "import json; data = json.load(open('.claude/settings.json'))" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_python_path_read_text_passes(self):
        cmd = """python3 -c "from pathlib import Path; Path('settings.json').read_text()" """
        assert hook._detect_settings_json_write(cmd) is None

    # Scenario 2: WRITE on settings.json blocks
    def test_python_json_dump_settings_blocks(self):
        cmd = """python3 -c "import json; json.dump({}, open('settings.json','w'))" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_path_write_text_settings_blocks(self):
        cmd = """python3 -c "from pathlib import Path; Path('settings.json').write_text('{}')" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    # Scenario 3: sed -i blocks
    def test_sed_inplace_settings_blocks(self):
        cmd = "sed -i 's/foo/bar/' settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    # Scenario 4: cat passes
    def test_cat_settings_passes(self):
        assert hook._detect_settings_json_write("cat settings.json") is None

    def test_cat_pipe_jq_passes(self):
        cmd = "cat settings.json | jq .hooks"
        assert hook._detect_settings_json_write(cmd) is None

    # Scenario 5: heredoc redirect blocks
    def test_heredoc_redirect_settings_blocks(self):
        cmd = "cat <<EOF > settings.json\n{}\nEOF"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_simple_redirect_settings_blocks(self):
        cmd = "echo '{}' > settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    # Scenario 7: bash -c / sh -c recursion
    def test_bash_dash_c_cat_settings_passes(self):
        cmd = 'bash -c "cat settings.json"'
        assert hook._detect_settings_json_write(cmd) is None

    def test_bash_dash_c_rm_settings_blocks(self):
        cmd = 'bash -c "rm settings.json"'
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result


# ---------------------------------------------------------------------------
# TestFalsePositiveFix — the canonical Issue #971 false-positive scenarios
# ---------------------------------------------------------------------------


class TestFalsePositiveFix:
    """Read-only Python operations on settings.json must NOT block.

    These were all blocked under the legacy regex (which matched ``open\\s*\\(``
    indiscriminately). Issue #971 routes through AST and tool_intent, so
    these are now correctly classified as READ.
    """

    def test_json_load_open_settings(self):
        cmd = """python3 -c "import json; json.load(open('settings.json'))" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_json_load_with_print(self):
        cmd = """python3 -c "import json; print(json.load(open('settings.json')))" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_path_read_text_settings(self):
        cmd = """python3 -c "from pathlib import Path; print(Path('settings.json').read_text())" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_open_read_no_mode(self):
        # open(path) with no mode = read by default
        cmd = """python3 -c "data = open('settings.json').read(); print(data)" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_open_read_explicit_r_mode(self):
        cmd = """python3 -c "f = open('settings.json', 'r'); print(f.read())" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_settings_local_json_read(self):
        cmd = """python3 -c "import json; json.load(open('.claude/settings.local.json'))" """
        assert hook._detect_settings_json_write(cmd) is None
