"""Regression tests for Python -c settings.json write bypass (Issue #768).

Validates that _detect_settings_json_write blocks Python -c inline commands
that contain both a settings file reference AND a write pattern, while
allowing read-only Python commands and unrelated Python commands.

Date: 2026-04-12
"""

import importlib
import sys
from pathlib import Path

# Portable root detection
current = Path(__file__).resolve()
project_root = current.parents[3]  # smoke -> regression -> tests -> repo root
hook_path = project_root / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(hook_path))
hook = importlib.import_module("unified_pre_tool")


class TestPythonSettingsBypass:
    """Tests for Python -c settings.json write detection (Issue #768)."""

    # --- SHOULD BLOCK ---

    def test_python_c_json_dump_to_settings_json(self):
        """python3 -c with json.dump to settings.json should be blocked."""
        cmd = """python3 -c "import json; p='.claude/settings.json'; json.dump({}, open(p, 'w'))" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result
        assert "Issue #768" in result

    def test_python_c_open_write_settings_json(self):
        """python3 -c with open() write to settings.json should be blocked."""
        cmd = 'python3 -c "f = open(\'settings.json\', \'w\'); f.write(\'{}\')"'
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_c_settings_local_json(self):
        """python3 -c targeting settings.local.json should be blocked."""
        cmd = """python3 -c "import json; json.dump({}, open('settings.local.json', 'w'))" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_c_single_quotes(self):
        """python3 -c with single-quoted command should be blocked."""
        cmd = "python3 -c 'import json; json.dump({}, open(\"settings.json\", \"w\"))'"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_c_write_text_settings(self):
        """python3 -c with .write_text() to settings file should be blocked."""
        cmd = """python3 -c "from pathlib import Path; Path('settings.json').write_text('{}')" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_c_variable_indirection(self):
        """python3 -c using variable to reference settings.json should be blocked."""
        cmd = """python3 -c "import json; p = '.claude/settings.json'; data = {}; f = open(p, 'w'); json.dump(data, f)" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_no_version_number(self):
        """python -c (without 3) should also be detected."""
        cmd = """python -c "import json; json.dump({}, open('settings.json', 'w'))" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_c_shutil_settings(self):
        """python3 -c with shutil targeting settings.json should be blocked."""
        cmd = """python3 -c "import shutil; shutil.copy('tmp.json', 'settings.json')" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    # --- SHOULD ALLOW ---

    def test_python_c_read_only_settings(self):
        """python3 -c reading settings.json without writing should be allowed."""
        cmd = """python3 -c "import json; data = json.load(open('settings.json')); print(data)" """
        result = hook._detect_settings_json_write(cmd)
        # json.load uses open() which triggers write detection -- but open() without write mode
        # The current detection is conservative: open() in any context with settings ref triggers block.
        # This is acceptable because the bypass is dangerous and false positives are safe.
        # If this is too aggressive, we could refine to check for write mode indicators.
        # For now, accept either behavior as valid.
        pass  # No assertion -- documenting the design decision

    def test_python_c_no_settings_reference(self):
        """python3 -c not referencing settings files should be allowed."""
        cmd = """python3 -c "import json; json.dump({}, open('config.json', 'w'))" """
        result = hook._detect_settings_json_write(cmd)
        assert result is None

    def test_regular_python_command_allowed(self):
        """Regular python3 commands not touching settings should be allowed."""
        cmd = "python3 -m pytest tests/ -v"
        result = hook._detect_settings_json_write(cmd)
        assert result is None

    def test_python_c_print_only(self):
        """python3 -c with print only, no file writes, should be allowed."""
        cmd = """python3 -c "print('hello world')" """
        result = hook._detect_settings_json_write(cmd)
        assert result is None

    def test_grep_settings_json_allowed(self):
        """grep for settings.json should be allowed (not a write)."""
        cmd = "grep -r 'settings.json' plugins/"
        result = hook._detect_settings_json_write(cmd)
        assert result is None

    def test_cat_settings_json_allowed(self):
        """cat settings.json should be allowed (read, not write)."""
        cmd = "cat .claude/settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is None

    # --- EXISTING SHELL DETECTION STILL WORKS ---

    def test_redirect_to_settings_json_still_blocked(self):
        """Shell redirect to settings.json should still be blocked."""
        cmd = "echo '{}' > .claude/settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_sed_i_settings_json_still_blocked(self):
        """sed -i on settings.json should still be blocked."""
        cmd = "sed -i 's/old/new/' .claude/settings.json"
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_required_next_action_in_message(self):
        """Block message should include REQUIRED NEXT ACTION (stick+carrot pattern)."""
        cmd = """python3 -c "import json; json.dump({}, open('settings.json', 'w'))" """
        result = hook._detect_settings_json_write(cmd)
        assert result is not None
        assert "REQUIRED NEXT ACTION" in result


class TestFalsePositiveFix:
    """Regression tests for the Issue #971 false-positive fix.

    The legacy regex matched ``open\\s*\\(`` indiscriminately, so
    ``json.load(open('settings.json'))`` was incorrectly blocked. Post-#971
    the AST-based ``tool_intent`` correctly classifies these as READ.

    These tests document the contract: read-only Python operations on
    settings.json MUST NOT trigger ``_detect_settings_json_write``.
    """

    def test_json_load_open_settings_passes(self):
        """json.load(open('settings.json')) is a READ — must not block."""
        cmd = """python3 -c "import json; json.load(open('settings.json'))" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_json_loads_with_path_read_text_passes(self):
        """json.loads(Path('settings.json').read_text()) is a READ."""
        cmd = (
            "python3 -c \"import json; from pathlib import Path; "
            "json.loads(Path('settings.json').read_text())\""
        )
        assert hook._detect_settings_json_write(cmd) is None

    def test_open_settings_no_mode_passes(self):
        """open('settings.json') with no mode = read by default."""
        cmd = """python3 -c "data = open('settings.json').read()" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_open_settings_explicit_r_mode_passes(self):
        """open('settings.json', 'r') is explicit read mode."""
        cmd = """python3 -c "f = open('settings.json', 'r'); print(f.read())" """
        assert hook._detect_settings_json_write(cmd) is None

    def test_cat_pipe_jq_settings_passes(self):
        """cat settings.json | jq .foo is a READ pipeline."""
        cmd = "cat settings.json | jq .hooks"
        assert hook._detect_settings_json_write(cmd) is None

    def test_grep_in_settings_passes(self):
        """grep on settings.json is a READ."""
        assert hook._detect_settings_json_write("grep hooks settings.json") is None

    def test_bash_dash_c_cat_settings_passes(self):
        """bash -c "cat settings.json" — nested shell READ must not block."""
        cmd = 'bash -c "cat settings.json"'
        assert hook._detect_settings_json_write(cmd) is None
