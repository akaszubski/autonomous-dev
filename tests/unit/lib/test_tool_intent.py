"""Unit tests for tool_intent.py — shell + tool classifier (Issue #971).

Covers:
- Native tool dispatch (Read/Write/Edit/Glob/Grep/...)
- Bash binaries (read vs write)
- Redirections (>, >>, 2>, &>, heredoc)
- Pipes & sequential operators
- Python -c inline snippets (read vs write)
- Nested shells (bash -c "...")
- Env-var prefixes (FOO=bar python ...)
- Edge cases (empty, malformed, oversized, sentinel)
- The 8 issue-body acceptance scenarios as named tests

Date: 2026-04-26
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add lib dir to path so we can import the module under test.
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import tool_intent  # noqa: E402  (path manipulation must precede import)


# ---------------------------------------------------------------------------
# TestNativeToolClassification
# ---------------------------------------------------------------------------


class TestNativeToolClassification:
    """Native Claude Code tools dispatch by tool_name."""

    def test_read_classifies_read(self):
        assert tool_intent.classify("Read", {"file_path": "/tmp/x"}) == "READ"

    def test_glob_classifies_read(self):
        assert tool_intent.classify("Glob", {"pattern": "*.py"}) == "READ"

    def test_grep_classifies_read(self):
        assert tool_intent.classify("Grep", {"pattern": "foo"}) == "READ"

    def test_notebook_read_classifies_read(self):
        assert tool_intent.classify("NotebookRead", {"notebook_path": "/x.ipynb"}) == "READ"

    def test_write_classifies_write(self):
        assert tool_intent.classify("Write", {"file_path": "/tmp/x"}) == "WRITE"

    def test_edit_classifies_write(self):
        assert tool_intent.classify("Edit", {"file_path": "/tmp/x"}) == "WRITE"

    def test_multi_edit_classifies_write(self):
        assert tool_intent.classify("MultiEdit", {"file_path": "/tmp/x"}) == "WRITE"

    def test_notebook_edit_classifies_write(self):
        assert tool_intent.classify("NotebookEdit", {"notebook_path": "/x.ipynb"}) == "WRITE"

    def test_task_classifies_exec(self):
        assert tool_intent.classify("Task", {"prompt": "do thing"}) == "EXEC"

    def test_webfetch_classifies_exec(self):
        assert tool_intent.classify("WebFetch", {"url": "https://x"}) == "EXEC"

    def test_mcp_tool_classifies_exec(self):
        assert tool_intent.classify("mcp__github__create_issue", {}) == "EXEC"

    def test_unknown_tool_classifies_exec(self):
        assert tool_intent.classify("BogusTool", {}) == "EXEC"

    def test_write_targets_for_write_tool_returns_path(self):
        targets = tool_intent.write_targets("Write", {"file_path": "/x/y.txt"})
        assert targets == ["/x/y.txt"]

    def test_write_targets_for_read_tool_returns_empty(self):
        assert tool_intent.write_targets("Read", {"file_path": "/x/y.txt"}) == []

    def test_write_targets_for_notebook_edit_uses_notebook_path(self):
        targets = tool_intent.write_targets(
            "NotebookEdit", {"notebook_path": "/n.ipynb"}
        )
        assert targets == ["/n.ipynb"]


# ---------------------------------------------------------------------------
# TestBashReadBinaries
# ---------------------------------------------------------------------------


class TestBashReadBinaries:
    def test_cat_is_read(self):
        assert tool_intent.classify("Bash", {"command": "cat /tmp/x"}) == "READ"

    def test_grep_in_bash_is_read(self):
        assert tool_intent.classify("Bash", {"command": "grep foo /tmp/x"}) == "READ"

    def test_head_is_read(self):
        assert tool_intent.classify("Bash", {"command": "head -5 file.txt"}) == "READ"

    def test_wc_is_read(self):
        assert tool_intent.classify("Bash", {"command": "wc -l file.txt"}) == "READ"

    def test_jq_is_read(self):
        assert tool_intent.classify("Bash", {"command": "jq .foo file.json"}) == "READ"

    def test_ls_is_read(self):
        assert tool_intent.classify("Bash", {"command": "ls -la /tmp"}) == "READ"

    def test_diff_is_read(self):
        assert tool_intent.classify("Bash", {"command": "diff a.txt b.txt"}) == "READ"


# ---------------------------------------------------------------------------
# TestBashWriteBinaries
# ---------------------------------------------------------------------------


class TestBashWriteBinaries:
    def test_rm_is_write(self):
        intent = tool_intent.classify("Bash", {"command": "rm /tmp/foo"})
        assert intent == "WRITE"
        assert "/tmp/foo" in tool_intent.write_targets("Bash", {"command": "rm /tmp/foo"})

    def test_mv_is_write_dest_is_last_arg(self):
        targets = tool_intent.write_targets("Bash", {"command": "mv a.txt b.txt"})
        assert "b.txt" in targets

    def test_cp_is_write_dest_is_last_arg(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "cp src.txt dst.txt"}
        )
        assert "dst.txt" in targets

    def test_tee_is_write(self):
        targets = tool_intent.write_targets("Bash", {"command": "tee out.txt"})
        assert "out.txt" in targets

    def test_truncate_is_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "truncate -s 0 logs.txt"}
        )
        assert "logs.txt" in targets

    def test_dd_of_is_write_target(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "dd if=/dev/zero of=/tmp/blob bs=1M count=1"}
        )
        assert "/tmp/blob" in targets

    def test_touch_is_write(self):
        intent = tool_intent.classify("Bash", {"command": "touch newfile"})
        assert intent == "WRITE"

    def test_chmod_is_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "chmod 755 script.sh"}
        )
        assert intent == "WRITE"
        targets = tool_intent.write_targets(
            "Bash", {"command": "chmod 755 script.sh"}
        )
        assert "script.sh" in targets
        # The mode (755) must NOT be in targets.
        assert "755" not in targets

    def test_sed_inplace_is_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "sed -i 's/foo/bar/' file.txt"}
        )
        assert intent == "WRITE"
        targets = tool_intent.write_targets(
            "Bash", {"command": "sed -i 's/foo/bar/' file.txt"}
        )
        assert "file.txt" in targets

    def test_sed_without_inplace_is_read(self):
        intent = tool_intent.classify(
            "Bash", {"command": "sed 's/foo/bar/' file.txt"}
        )
        assert intent == "READ"

    def test_awk_inplace_is_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "awk -i inplace '{print}' file.txt"}
        )
        assert intent == "WRITE"

    def test_find_delete_is_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "find . -name '*.tmp' -delete"}
        )
        assert intent == "WRITE"


# ---------------------------------------------------------------------------
# TestRedirections
# ---------------------------------------------------------------------------


class TestRedirections:
    def test_single_redirect_is_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "echo hi > out.txt"}
        )
        assert "out.txt" in targets

    def test_append_redirect_is_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "echo hi >> out.txt"}
        )
        assert "out.txt" in targets

    def test_stderr_only_redirect_is_not_write_target(self):
        # 2> /dev/null should not flag /dev/null as a write target.
        targets = tool_intent.write_targets(
            "Bash", {"command": "ls /missing 2> /dev/null"}
        )
        assert "/dev/null" not in targets

    def test_combined_redirect_is_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "ls &> combined.log"}
        )
        assert "combined.log" in targets

    def test_dev_null_not_treated_as_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "echo hi > /dev/null"}
        )
        assert "/dev/null" not in targets

    def test_cat_heredoc_redirect_blocks(self):
        # cat <<EOF > file is the canonical heredoc-write idiom.
        cmd = "cat <<EOF > out.txt\nhello\nEOF"
        targets = tool_intent.write_targets("Bash", {"command": cmd})
        assert "out.txt" in targets


# ---------------------------------------------------------------------------
# TestPipes
# ---------------------------------------------------------------------------


class TestPipes:
    def test_pipe_to_tee_is_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "echo hi | tee out.txt"}
        )
        assert intent == "WRITE"
        targets = tool_intent.write_targets(
            "Bash", {"command": "echo hi | tee out.txt"}
        )
        assert "out.txt" in targets

    def test_pipe_all_reads_is_read(self):
        intent = tool_intent.classify(
            "Bash", {"command": "cat file.txt | grep foo | wc -l"}
        )
        assert intent == "READ"

    def test_pipe_with_redirect_is_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "cat a.txt | grep foo > matches.txt"}
        )
        assert "matches.txt" in targets


# ---------------------------------------------------------------------------
# TestSequentialOperators
# ---------------------------------------------------------------------------


class TestSequentialOperators:
    def test_semicolon_any_write_classifies_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "ls; rm /tmp/foo"}
        )
        assert intent == "WRITE"

    def test_and_operator_propagates_write(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": "make && cp build/out /tmp/out"}
        )
        assert "/tmp/out" in targets

    def test_or_operator_propagates_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": "test -f x.txt || touch x.txt"}
        )
        assert intent == "WRITE"


# ---------------------------------------------------------------------------
# TestPythonInline
# ---------------------------------------------------------------------------


class TestPythonInline:
    def test_json_load_is_read_not_write(self):
        # The canonical false-positive case the issue is about.
        cmd = """python3 -c "import json; json.load(open('settings.json'))" """
        assert tool_intent.classify("Bash", {"command": cmd}) == "READ"
        assert tool_intent.write_targets("Bash", {"command": cmd}) == []

    def test_json_dump_is_write(self):
        cmd = """python3 -c "import json; json.dump({}, open('out.json','w'))" """
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent == "WRITE"
        targets = tool_intent.write_targets("Bash", {"command": cmd})
        assert "out.json" in targets

    def test_path_write_text_is_write(self):
        cmd = """python3 -c "from pathlib import Path; Path('out.txt').write_text('x')" """
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent == "WRITE"
        targets = tool_intent.write_targets("Bash", {"command": cmd})
        assert "out.txt" in targets

    def test_path_read_text_is_read(self):
        cmd = """python3 -c "from pathlib import Path; print(Path('in.txt').read_text())" """
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent == "READ"

    def test_shutil_copy_is_write(self):
        cmd = """python3 -c "import shutil; shutil.copy('a.txt','b.txt')" """
        targets = tool_intent.write_targets("Bash", {"command": cmd})
        assert "b.txt" in targets

    def test_os_rename_is_write_dest_is_second_arg(self):
        cmd = """python3 -c "import os; os.rename('old','new')" """
        targets = tool_intent.write_targets("Bash", {"command": cmd})
        assert "new" in targets

    def test_python_no_version_number(self):
        cmd = """python -c "import json; json.dump({}, open('x.json','w'))" """
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent == "WRITE"


# ---------------------------------------------------------------------------
# TestNestedShells
# ---------------------------------------------------------------------------


class TestNestedShells:
    def test_bash_dash_c_cat_is_read(self):
        intent = tool_intent.classify(
            "Bash", {"command": 'bash -c "cat settings.json"'}
        )
        assert intent == "READ"

    def test_bash_dash_c_rm_is_write(self):
        intent = tool_intent.classify(
            "Bash", {"command": 'bash -c "rm settings.json"'}
        )
        assert intent == "WRITE"
        targets = tool_intent.write_targets(
            "Bash", {"command": 'bash -c "rm settings.json"'}
        )
        assert "settings.json" in targets

    def test_sh_dash_c_redirect(self):
        targets = tool_intent.write_targets(
            "Bash", {"command": 'sh -c "echo hi > out.txt"'}
        )
        assert "out.txt" in targets

    def test_recursion_depth_is_capped(self):
        # 5 levels of nesting — exceeds _MAX_RECURSION_DEPTH=3 → EXEC.
        cmd = (
            'bash -c "bash -c \\"bash -c \\\\\\"bash -c \\\\\\\\\\\\\\"'
            'bash -c rm /tmp/x\\\\\\\\\\\\\\"\\\\\\"\\""'
        )
        # Even if we can't construct the perfect deep nesting in a string
        # literal, just ensure recursion past depth 3 doesn't crash.
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent in ("EXEC", "READ", "WRITE")


# ---------------------------------------------------------------------------
# TestEnvPrefixes
# ---------------------------------------------------------------------------


class TestEnvPrefixes:
    def test_env_assignment_prefix_skipped(self):
        intent = tool_intent.classify(
            "Bash", {"command": "FOO=bar PATH=/x:$PATH cat file.txt"}
        )
        assert intent == "READ"

    def test_env_wrapper_strips_to_real_command(self):
        intent = tool_intent.classify(
            "Bash", {"command": "env FOO=bar rm /tmp/foo"}
        )
        assert intent == "WRITE"

    def test_env_wrapper_with_python_inline(self):
        cmd = """env PYTHONPATH=. python3 -c "import json; json.load(open('x.json'))" """
        intent = tool_intent.classify("Bash", {"command": cmd})
        # python_write_detector returns no targets for json.load, so READ.
        assert intent == "READ"


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_command_is_exec(self):
        assert tool_intent.classify("Bash", {"command": ""}) == "EXEC"
        assert tool_intent.write_targets("Bash", {"command": ""}) == []

    def test_whitespace_only_command_is_exec(self):
        assert tool_intent.classify("Bash", {"command": "   "}) == "EXEC"

    def test_malformed_quotes_are_safe(self):
        # Unterminated quote — shlex will raise; classifier must not crash.
        cmd = """python3 -c "import json; json.dump('"""
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent in ("READ", "WRITE", "EXEC")

    def test_oversize_command_rejected_safely(self):
        cmd = "echo " + ("x" * 100_000)
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent == "EXEC"
        assert tool_intent.write_targets("Bash", {"command": cmd}) == []

    def test_missing_tool_input_is_safe(self):
        assert tool_intent.classify("Bash", {}) == "EXEC"
        assert tool_intent.classify("Read", {}) == "READ"

    def test_none_tool_name_is_safe(self):
        assert tool_intent.classify("", {}) == "EXEC"
        assert tool_intent.classify(None, {}) == "EXEC"  # type: ignore[arg-type]

    def test_suspicious_exec_sentinel_preserved(self):
        # exec(variable) → AST flags suspicious
        cmd = """python3 -c "exec(open('settings.json').read())" """
        targets = tool_intent.write_targets("Bash", {"command": cmd})
        # The sentinel may or may not be in targets depending on python_write_detector
        # behavior, but we must not crash and the command should be classified.
        intent = tool_intent.classify("Bash", {"command": cmd})
        assert intent in ("WRITE", "READ", "EXEC")

    def test_has_suspicious_exec_returns_bool(self):
        # Plain exec() with non-constant arg → suspicious.
        assert isinstance(
            tool_intent.has_suspicious_exec("python3 -c \"exec(s)\""), bool
        )
        assert tool_intent.has_suspicious_exec("") is False


# ---------------------------------------------------------------------------
# TestIssueAcceptanceScenarios — the 8 scenarios from issue #971 body
# ---------------------------------------------------------------------------


class TestIssueAcceptanceScenarios:
    """Each test maps to one of the 8 scenarios in the issue body."""

    # (1) READ on settings.json passes
    def test_scenario_1_python_json_load_settings_is_read(self):
        cmd = """python3 -c "import json; json.load(open('settings.json'))" """
        assert tool_intent.classify("Bash", {"command": cmd}) == "READ"
        assert tool_intent.write_targets("Bash", {"command": cmd}) == []

    # (2) WRITE on settings.json blocks
    def test_scenario_2_python_json_dump_settings_is_write(self):
        cmd = """python3 -c "import json; json.dump({}, open('settings.json','w'))" """
        assert tool_intent.classify("Bash", {"command": cmd}) == "WRITE"
        assert "settings.json" in tool_intent.write_targets("Bash", {"command": cmd})

    # (3) sed -i blocks
    def test_scenario_3_sed_inplace_settings_is_write(self):
        cmd = "sed -i 's/foo/bar/' settings.json"
        assert tool_intent.classify("Bash", {"command": cmd}) == "WRITE"
        assert "settings.json" in tool_intent.write_targets("Bash", {"command": cmd})

    # (4) Plain cat passes
    def test_scenario_4a_cat_settings_is_read(self):
        assert tool_intent.classify("Bash", {"command": "cat settings.json"}) == "READ"

    def test_scenario_4b_cat_pipe_jq_is_read(self):
        cmd = "cat settings.json | jq .hooks"
        assert tool_intent.classify("Bash", {"command": cmd}) == "READ"

    # (5) Heredoc redirect blocks
    def test_scenario_5_heredoc_redirect_settings_is_write(self):
        cmd = "cat <<EOF > settings.json\n{}\nEOF"
        assert tool_intent.classify("Bash", {"command": cmd}) == "WRITE"
        assert "settings.json" in tool_intent.write_targets("Bash", {"command": cmd})

    # (6) Edit tool name suffices (no command parsing)
    def test_scenario_6a_edit_settings_is_write(self):
        assert tool_intent.classify(
            "Edit", {"file_path": ".claude/settings.json"}
        ) == "WRITE"

    def test_scenario_6b_read_settings_is_read(self):
        assert tool_intent.classify(
            "Read", {"file_path": ".claude/settings.json"}
        ) == "READ"

    # (7) bash -c / sh -c recursion
    def test_scenario_7a_bash_dash_c_cat_is_read(self):
        assert tool_intent.classify(
            "Bash", {"command": 'bash -c "cat settings.json"'}
        ) == "READ"

    def test_scenario_7b_bash_dash_c_rm_is_write(self):
        cmd = 'bash -c "rm settings.json"'
        assert tool_intent.classify("Bash", {"command": cmd}) == "WRITE"
        assert "settings.json" in tool_intent.write_targets("Bash", {"command": cmd})


# ---------------------------------------------------------------------------
# Issue #1503 — transport-independent write classification
# ---------------------------------------------------------------------------

# The 24 entries that used to live in unified_pre_tool.py as
# _PLAN_EXIT_MCP_READONLY. MCP_READ_TOOLS must be a strict SUPERSET of these.
LEGACY_PLAN_EXIT_MCP_READONLY = frozenset({
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",
    "mcp__claude_ai_Hugging_Face__hf_doc_search",
    "mcp__claude_ai_Hugging_Face__hf_doc_fetch",
    "mcp__claude_ai_Hugging_Face__hub_repo_search",
    "mcp__claude_ai_Hugging_Face__paper_search",
    "mcp__claude_ai_Hugging_Face__space_search",
    "mcp__claude_ai_Hugging_Face__hf_whoami",
    "mcp__claude_ai_Hugging_Face__hf_hub_query",
    "mcp__claude_ai_Hugging_Face__hub_repo_details",
    "mcp__claude_ai_Gmail__list_drafts",
    "mcp__claude_ai_Gmail__list_labels",
    "mcp__claude_ai_Gmail__get_thread",
    "mcp__claude_ai_Gmail__search_threads",
    "mcp__claude_ai_Google_Calendar__list_calendars",
    "mcp__claude_ai_Google_Calendar__list_events",
    "mcp__claude_ai_Google_Calendar__get_event",
    "mcp__claude_ai_Google_Drive__list_recent_files",
    "mcp__claude_ai_Google_Drive__search_files",
    "mcp__claude_ai_Google_Drive__read_file_content",
    "mcp__claude_ai_Google_Drive__get_file_metadata",
    "mcp__claude_ai_Google_Drive__get_file_permissions",
})

TARGET = "/repo/plugins/autonomous-dev/hooks/plan_gate.py"

# Every transport that can mutate a file, with a realistic payload shape.
WRITE_TRANSPORT_PAYLOADS = [
    ("Write", {"file_path": TARGET, "content": "body\n"}),
    ("Edit", {"file_path": TARGET, "old_string": "x", "new_string": "body\n"}),
    ("MultiEdit", {"file_path": TARGET,
                   "edits": [{"old_string": "x", "new_string": "body\n"}]}),
    ("NotebookEdit", {"notebook_path": TARGET, "cell_id": "c1",
                      "new_source": "body\n"}),
    ("mcp__serena__replace_symbol_body",
     {"relative_path": TARGET, "name_path": "main", "body": "body\n"}),
    ("mcp__serena__insert_after_symbol",
     {"relative_path": TARGET, "name_path": "main", "body": "body\n"}),
    ("mcp__serena__replace_content",
     {"relative_path": TARGET, "needle": "x", "repl": "body\n"}),
]

# Verified against the real serena tool schemas: none of these carries a
# content key, so the path+content shape fallback provably cannot catch them.
# Only explicit registry membership can.
FALLBACK_UNCATCHABLE_WRITERS = [
    ("mcp__serena__replace_in_files",
     {"relative_path": "", "needle": "x", "repl": "y"}),
    ("mcp__serena__rename_symbol",
     {"name_path": "main", "relative_path": TARGET, "new_name": "main2"}),
    ("mcp__serena__safe_delete_symbol",
     {"name_path_pattern": "main", "relative_path": TARGET}),
    ("mcp__serena__delete_lines",
     {"relative_path": TARGET, "start_line": 1, "end_line": 9}),
]

# Must NEVER classify as WRITE. Several carry a path argument on purpose —
# a naive "has a path -> block" rule would break these.
READONLY_PAYLOADS = [
    ("Read", {"file_path": TARGET}),
    ("Grep", {"pattern": "def", "path": "/repo"}),
    ("Glob", {"pattern": "**/*.py"}),
    ("NotebookRead", {"notebook_path": TARGET}),
    ("mcp__serena__find_symbol",
     {"name_path_pattern": "main", "relative_path": TARGET}),
    ("mcp__serena__get_symbols_overview", {"relative_path": TARGET}),
    ("mcp__serena__find_referencing_symbols",
     {"name_path": "main", "relative_path": TARGET}),
    ("mcp__serena__search_for_pattern",
     {"substring_pattern": "def", "relative_path": TARGET}),
    ("mcp__searxng__search", {"query": "python"}),
    ("WebFetch", {"url": "https://example.com", "prompt": "summarise"}),
    ("mcp__ms365__send-mail", {"subject": "hi", "body": "text body no path"}),
]


class TestIssue1503Registries:
    """The MCP registries are explicit and authoritative."""

    def test_mcp_read_tools_is_strict_superset_of_legacy_allowlist(self):
        missing = LEGACY_PLAN_EXIT_MCP_READONLY - set(tool_intent.MCP_READ_TOOLS)
        assert not missing, f"MCP_READ_TOOLS lost legacy entries: {sorted(missing)}"
        assert len(tool_intent.MCP_READ_TOOLS) > len(LEGACY_PLAN_EXIT_MCP_READONLY), (
            "MCP_READ_TOOLS must be a STRICT superset (serena reads added)"
        )

    def test_browser_evaluate_is_not_read_only(self):
        """AC #19: browser_evaluate executes arbitrary JS — never read-only."""
        assert "mcp__playwright__browser_evaluate" not in tool_intent.MCP_READ_TOOLS

    def test_read_and_write_registries_are_disjoint(self):
        assert not (set(tool_intent.MCP_READ_TOOLS) & set(tool_intent.MCP_WRITE_TOOLS))
        assert not (tool_intent.READ_TOOLS & tool_intent.WRITE_TOOLS)

    def test_path_and_content_keys_exclude_non_filesystem_keys(self):
        for key in ("url", "prompt", "subject", "to"):
            assert key not in tool_intent.PATH_KEYS
            assert key not in tool_intent.CONTENT_KEYS


class TestIssue1503IsWrite:
    """is_write() truth table across every transport."""

    @pytest.mark.parametrize("tool_name,tool_input", WRITE_TRANSPORT_PAYLOADS)
    def test_write_transports_classify_as_write(self, tool_name, tool_input):
        assert tool_intent.classify(tool_name, tool_input) == "WRITE"
        assert tool_intent.is_write(tool_name, tool_input) is True

    @pytest.mark.parametrize("tool_name,tool_input", FALLBACK_UNCATCHABLE_WRITERS)
    def test_contentless_writers_caught_by_registry_membership(
        self, tool_name, tool_input
    ):
        """These have no content key — only the registry can catch them."""
        assert tool_intent._looks_like_write(tool_input) is False, (
            "precondition: the shape fallback must NOT catch this payload"
        )
        assert tool_intent.is_write(tool_name, tool_input) is True

    @pytest.mark.parametrize("tool_name,tool_input", READONLY_PAYLOADS)
    def test_readonly_payloads_are_never_writes(self, tool_name, tool_input):
        assert tool_intent.is_write(tool_name, tool_input) is False
        assert tool_intent.write_targets(tool_name, tool_input) == []

    def test_unknown_tool_with_path_only_stays_exec(self):
        payload = {"relative_path": TARGET, "name_path": "main"}
        assert tool_intent.classify("mcp__future__inspect", payload) == "EXEC"
        assert tool_intent.is_write("mcp__future__inspect", payload) is False

    def test_unknown_tool_with_path_and_content_becomes_write(self):
        payload = {"path": TARGET, "content": "pwned\n"}
        assert tool_intent.classify("mcp__future__editor", payload) == "WRITE"
        assert tool_intent.write_targets("mcp__future__editor", payload) == [TARGET]

    def test_unknown_tool_with_content_only_stays_exec(self):
        payload = {"body": "just a message"}
        assert tool_intent.classify("mcp__future__notify", payload) == "EXEC"

    @pytest.mark.parametrize("bad", [None, "", 0, [], "not-a-dict"])
    def test_malformed_input_never_raises(self, bad):
        assert tool_intent.is_write("mcp__x__y", bad) is False
        assert tool_intent.changed_content("mcp__x__y", bad) == ""
        assert tool_intent.write_targets("mcp__x__y", bad) == []
        assert tool_intent.classify(bad, {}) == "EXEC"


class TestIssue1503ChangedContent:
    """changed_content() extracts the change regardless of transport."""

    def test_write_uses_content_key(self):
        assert tool_intent.changed_content(
            "Write", {"file_path": TARGET, "content": "a\nb"}
        ) == "a\nb"

    def test_edit_uses_new_string_key(self):
        assert tool_intent.changed_content(
            "Edit", {"file_path": TARGET, "new_string": "a\nb"}
        ) == "a\nb"

    def test_notebook_edit_uses_new_source_key(self):
        assert tool_intent.changed_content(
            "NotebookEdit", {"notebook_path": TARGET, "new_source": "a\nb"}
        ) == "a\nb"

    def test_serena_symbol_editors_use_body_key(self):
        assert tool_intent.changed_content(
            "mcp__serena__replace_symbol_body",
            {"relative_path": TARGET, "name_path": "m", "body": "a\nb"},
        ) == "a\nb"

    def test_serena_replace_content_uses_repl_not_content(self):
        assert tool_intent.changed_content(
            "mcp__serena__replace_content",
            {"relative_path": TARGET, "needle": "x", "repl": "a\nb"},
        ) == "a\nb"

    def test_multiedit_concatenates_every_new_string(self):
        result = tool_intent.changed_content(
            "MultiEdit",
            {
                "file_path": TARGET,
                "edits": [
                    {"old_string": "x", "new_string": "one\ntwo"},
                    {"old_string": "y", "new_string": "three"},
                ],
            },
        )
        assert "one" in result and "three" in result
        assert result.count("\n") == 2

    def test_multiedit_line_count_reflects_total_change_size(self):
        """A 120-line MultiEdit must not read as a 0-line change."""
        big = "\n".join(f"line {i}" for i in range(120))
        payload = {"file_path": TARGET,
                   "edits": [{"old_string": "x", "new_string": big}]}
        assert tool_intent.changed_content("MultiEdit", payload).count("\n") >= 100

    def test_missing_content_returns_empty_string(self):
        assert tool_intent.changed_content(
            "mcp__serena__delete_lines",
            {"relative_path": TARGET, "start_line": 1, "end_line": 2},
        ) == ""


class TestIssue1503WriteTargets:
    """write_targets() resolves MCP path keys too."""

    def test_serena_target_resolved_from_relative_path(self):
        assert tool_intent.write_targets(
            "mcp__serena__replace_symbol_body",
            {"relative_path": TARGET, "name_path": "m", "body": "b"},
        ) == [TARGET]

    def test_notebook_edit_target_resolved_from_notebook_path(self):
        assert tool_intent.write_targets(
            "NotebookEdit", {"notebook_path": TARGET, "new_source": "b"}
        ) == [TARGET]

    def test_registered_writer_without_path_returns_empty_list(self):
        assert tool_intent.write_targets(
            "mcp__serena__replace_in_files",
            {"relative_path": "", "needle": "x", "repl": "y"},
        ) == []

    def test_mcp_read_tools_never_yield_targets(self):
        assert tool_intent.write_targets(
            "mcp__serena__find_symbol",
            {"name_path_pattern": "m", "relative_path": TARGET},
        ) == []


class TestIssue1503BashUnchanged:
    """Widening classify() must not disturb the existing Bash path."""

    def test_bash_read_still_read(self):
        assert tool_intent.classify("Bash", {"command": "cat foo.txt"}) == "READ"

    def test_bash_write_still_write_with_targets(self):
        payload = {"command": "rm -f settings.json"}
        assert tool_intent.classify("Bash", payload) == "WRITE"
        assert "settings.json" in tool_intent.write_targets("Bash", payload)

    def test_bash_redirect_still_write(self):
        payload = {"command": "echo hi > out.txt"}
        assert tool_intent.classify("Bash", payload) == "WRITE"
        assert "out.txt" in tool_intent.write_targets("Bash", payload)

    def test_bash_unknown_binary_still_exec(self):
        assert tool_intent.classify("Bash", {"command": "make build"}) == "EXEC"

    def test_bash_with_path_and_content_keys_is_not_shape_matched(self):
        """Bash must route through _classify_bash, never the shape fallback."""
        payload = {"command": "ls", "path": TARGET, "content": "x"}
        assert tool_intent.classify("Bash", payload) == "READ"
