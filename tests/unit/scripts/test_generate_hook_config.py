#!/usr/bin/env python3
"""Unit tests for generate_hook_config.py.

Tests the hook config generator that reads .hook.json sidecar files and
produces install_manifest.json and global_settings_template.json entries.

Test Categories:
    1. discover_sidecars: finds .hook.json, excludes archived/, returns sorted
    2. load_and_validate_sidecar: valid lifecycle, valid utility, invalid JSON
    3. detect_orphans: hooks without sidecars, sidecars without hooks, clean state
    4. generate_manifest_hooks: includes all hooks + sidecars, correct extensions, sorted
    5. generate_settings_hooks: lifecycle only, excludes utility/inactive, env vars, sorted
    6. build_command_string: env sorted, no env, bash interpreter
    7. check_drift: no drift exits 0, drift exits 1
    8. write_mode: updates sections, preserves others, atomic, deterministic
    9. error handling: missing dirs, invalid sidecars
    10. Integration: end-to-end with real existing sidecars
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from generate_hook_config import (
    INTERPRETER_EXTENSIONS,
    atomic_write_json,
    build_command_string,
    check_drift,
    detect_orphans,
    discover_sidecars,
    generate_manifest_hooks,
    generate_settings_hooks,
    load_and_validate_sidecar,
    main,
    write_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_LIFECYCLE_SIDECAR = {
    "name": "session_activity_logger",
    "type": "lifecycle",
    "description": "Structured JSONL activity logging",
    "interpreter": "python3",
    "active": True,
    "env": {"ACTIVITY_LOGGING": "true"},
    "registrations": [
        {"event": "PostToolUse", "matcher": "*", "timeout": 5},
        {"event": "Stop", "matcher": "*", "timeout": 3},
    ],
}

SAMPLE_UTILITY_SIDECAR = {
    "name": "genai_utils",
    "type": "utility",
    "description": "GenAI utility functions",
    "interpreter": "python3",
    "active": True,
}

SAMPLE_PRE_TOOL_SIDECAR = {
    "name": "unified_pre_tool",
    "type": "lifecycle",
    "description": "Unified pre-tool validation",
    "interpreter": "python3",
    "active": True,
    "env": {"SANDBOX_ENABLED": "false", "MCP_AUTO_APPROVE": "true"},
    "registrations": [
        {"event": "PreToolUse", "matcher": "*", "timeout": 5},
    ],
}


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    """Create a temporary hooks directory with sample sidecars and scripts."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()

    # Create sidecar files
    (hooks / "session_activity_logger.hook.json").write_text(
        json.dumps(SAMPLE_LIFECYCLE_SIDECAR, indent=2)
    )
    (hooks / "genai_utils.hook.json").write_text(
        json.dumps(SAMPLE_UTILITY_SIDECAR, indent=2)
    )
    (hooks / "unified_pre_tool.hook.json").write_text(
        json.dumps(SAMPLE_PRE_TOOL_SIDECAR, indent=2)
    )

    # Create matching hook scripts
    (hooks / "session_activity_logger.py").write_text("# hook")
    (hooks / "genai_utils.py").write_text("# utility")
    (hooks / "unified_pre_tool.py").write_text("# hook")

    # Create archived directory with a sidecar that should be excluded
    archived = hooks / "archived"
    archived.mkdir()
    (archived / "old_hook.hook.json").write_text('{"name": "old_hook"}')

    return hooks


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with manifest and settings."""
    config = tmp_path / "config"
    config.mkdir()
    return config


@pytest.fixture
def schema_data() -> dict:
    """Return the hook metadata schema for validation tests."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name", "type", "interpreter"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "enum": ["lifecycle", "utility"]},
            "interpreter": {"type": "string", "enum": ["python3", "bash"]},
            "active": {"type": "boolean"},
            "description": {"type": "string"},
            "env": {"type": "object"},
            "registrations": {"type": "array"},
        },
    }


# ---------------------------------------------------------------------------
# 1. discover_sidecars
# ---------------------------------------------------------------------------


class TestDiscoverSidecars:
    """Tests for discover_sidecars function."""

    def test_finds_all_hook_json_files(self, hooks_dir: Path) -> None:
        """Should find all .hook.json files in the hooks directory."""
        result = discover_sidecars(hooks_dir)
        names = [p.name for p in result]
        assert "genai_utils.hook.json" in names
        assert "session_activity_logger.hook.json" in names
        assert "unified_pre_tool.hook.json" in names

    def test_excludes_archived_directory(self, hooks_dir: Path) -> None:
        """Should not include sidecars from archived/ subdirectory."""
        result = discover_sidecars(hooks_dir)
        names = [p.name for p in result]
        assert "old_hook.hook.json" not in names

    def test_returns_sorted_by_name(self, hooks_dir: Path) -> None:
        """Should return sidecars sorted alphabetically by filename."""
        result = discover_sidecars(hooks_dir)
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_raises_on_missing_directory(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for non-existent directory."""
        with pytest.raises(FileNotFoundError, match="Hooks directory not found"):
            discover_sidecars(tmp_path / "nonexistent")

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Should return empty list for directory with no sidecars."""
        empty_dir = tmp_path / "empty_hooks"
        empty_dir.mkdir()
        result = discover_sidecars(empty_dir)
        assert result == []


# ---------------------------------------------------------------------------
# 2. load_and_validate_sidecar
# ---------------------------------------------------------------------------


class TestLoadAndValidateSidecar:
    """Tests for load_and_validate_sidecar function."""

    def test_valid_lifecycle_sidecar(self, tmp_path: Path) -> None:
        """Should load and return valid lifecycle sidecar data."""
        path = tmp_path / "test.hook.json"
        path.write_text(json.dumps(SAMPLE_LIFECYCLE_SIDECAR))
        result = load_and_validate_sidecar(path)
        assert result["name"] == "session_activity_logger"
        assert result["type"] == "lifecycle"
        assert len(result["registrations"]) == 2

    def test_valid_utility_sidecar(self, tmp_path: Path) -> None:
        """Should load and return valid utility sidecar data."""
        path = tmp_path / "test.hook.json"
        path.write_text(json.dumps(SAMPLE_UTILITY_SIDECAR))
        result = load_and_validate_sidecar(path)
        assert result["name"] == "genai_utils"
        assert result["type"] == "utility"
        assert "registrations" not in result

    def test_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        """Should raise ValueError for invalid JSON content."""
        path = tmp_path / "bad.hook.json"
        path.write_text("{not valid json")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_and_validate_sidecar(path)

    def test_missing_name_raises_value_error(self, tmp_path: Path) -> None:
        """Should raise ValueError when required 'name' field is missing."""
        path = tmp_path / "no_name.hook.json"
        path.write_text(json.dumps({"type": "utility", "interpreter": "python3"}))
        with pytest.raises(ValueError, match="Missing required field 'name'"):
            load_and_validate_sidecar(path)

    def test_missing_type_raises_value_error(self, tmp_path: Path) -> None:
        """Should raise ValueError when required 'type' field is missing."""
        path = tmp_path / "no_type.hook.json"
        path.write_text(json.dumps({"name": "test", "interpreter": "python3"}))
        with pytest.raises(ValueError, match="Missing required field 'type'"):
            load_and_validate_sidecar(path)

    def test_missing_interpreter_raises_value_error(self, tmp_path: Path) -> None:
        """Should raise ValueError when required 'interpreter' field is missing."""
        path = tmp_path / "no_interp.hook.json"
        path.write_text(json.dumps({"name": "test", "type": "utility"}))
        with pytest.raises(ValueError, match="Missing required field 'interpreter'"):
            load_and_validate_sidecar(path)

    def test_non_object_raises_value_error(self, tmp_path: Path) -> None:
        """Should raise ValueError when JSON root is not an object."""
        path = tmp_path / "array.hook.json"
        path.write_text("[1, 2, 3]")
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_and_validate_sidecar(path)

    def test_schema_validation_when_available(
        self, tmp_path: Path, schema_data: dict
    ) -> None:
        """Should validate against schema when jsonschema is available."""
        path = tmp_path / "test.hook.json"
        path.write_text(json.dumps(SAMPLE_UTILITY_SIDECAR))
        # Should not raise with valid data
        result = load_and_validate_sidecar(path, schema=schema_data)
        assert result["name"] == "genai_utils"

    def test_warns_when_jsonschema_not_available(
        self, tmp_path: Path, schema_data: dict, capsys: pytest.CaptureFixture
    ) -> None:
        """Should print warning when jsonschema is not installed."""
        path = tmp_path / "test.hook.json"
        path.write_text(json.dumps(SAMPLE_UTILITY_SIDECAR))
        with patch("generate_hook_config.HAS_JSONSCHEMA", False):
            result = load_and_validate_sidecar(path, schema=schema_data)
        assert result["name"] == "genai_utils"
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "jsonschema not installed" in captured.err


# ---------------------------------------------------------------------------
# 3. detect_orphans
# ---------------------------------------------------------------------------


class TestDetectOrphans:
    """Tests for detect_orphans function."""

    def test_clean_state_no_orphans(self, hooks_dir: Path) -> None:
        """Should return empty lists when all hooks have sidecars and vice versa."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]
        result = detect_orphans(hooks_dir, sidecars)
        assert result["hooks_without_sidecars"] == []
        assert result["sidecars_without_hooks"] == []

    def test_hooks_without_sidecars(self, hooks_dir: Path) -> None:
        """Should detect hook scripts that have no corresponding sidecar."""
        # Add a hook script without sidecar
        (hooks_dir / "orphan_hook.py").write_text("# orphan")
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]
        result = detect_orphans(hooks_dir, sidecars)
        assert "orphan_hook" in result["hooks_without_sidecars"]

    def test_sidecars_without_hooks(self, hooks_dir: Path) -> None:
        """Should detect sidecars that have no corresponding hook script."""
        sidecars = [
            SAMPLE_LIFECYCLE_SIDECAR,
            SAMPLE_UTILITY_SIDECAR,
            SAMPLE_PRE_TOOL_SIDECAR,
            {"name": "phantom_hook", "type": "utility", "interpreter": "python3"},
        ]
        result = detect_orphans(hooks_dir, sidecars)
        assert "phantom_hook" in result["sidecars_without_hooks"]

    def test_ignores_dunder_files(self, hooks_dir: Path) -> None:
        """Should ignore __init__.py and __pycache__ files."""
        (hooks_dir / "__init__.py").write_text("")
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]
        result = detect_orphans(hooks_dir, sidecars)
        assert "__init__" not in result["hooks_without_sidecars"]

    def test_results_are_sorted(self, hooks_dir: Path) -> None:
        """Should return sorted lists of orphan names."""
        (hooks_dir / "z_orphan.py").write_text("# orphan")
        (hooks_dir / "a_orphan.py").write_text("# orphan")
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]
        result = detect_orphans(hooks_dir, sidecars)
        assert result["hooks_without_sidecars"] == sorted(result["hooks_without_sidecars"])


# ---------------------------------------------------------------------------
# 4. generate_manifest_hooks
# ---------------------------------------------------------------------------


class TestGenerateManifestHooks:
    """Tests for generate_manifest_hooks function."""

    def test_includes_both_sidecar_and_script(self) -> None:
        """Should include both .hook.json and script files for each hook."""
        sidecars = [SAMPLE_UTILITY_SIDECAR]
        result = generate_manifest_hooks(sidecars)
        assert "plugins/autonomous-dev/hooks/genai_utils.hook.json" in result
        assert "plugins/autonomous-dev/hooks/genai_utils.py" in result

    def test_correct_extension_for_python(self) -> None:
        """Should use .py extension for python3 interpreter."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR]
        result = generate_manifest_hooks(sidecars)
        assert "plugins/autonomous-dev/hooks/session_activity_logger.py" in result

    def test_correct_extension_for_bash(self) -> None:
        """Should use .sh extension for bash interpreter."""
        bash_sidecar = {
            "name": "pre_compact_saver",
            "type": "lifecycle",
            "interpreter": "bash",
            "active": True,
            "registrations": [{"event": "PreCompact", "matcher": "*", "timeout": 5}],
        }
        result = generate_manifest_hooks([bash_sidecar])
        assert "plugins/autonomous-dev/hooks/pre_compact_saver.sh" in result
        assert "plugins/autonomous-dev/hooks/pre_compact_saver.hook.json" in result

    def test_sorted_output(self) -> None:
        """Should return alphabetically sorted file paths."""
        sidecars = [SAMPLE_PRE_TOOL_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_LIFECYCLE_SIDECAR]
        result = generate_manifest_hooks(sidecars)
        assert result == sorted(result)

    def test_includes_all_hooks_lifecycle_and_utility(self) -> None:
        """Should include both lifecycle and utility hooks."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR]
        result = generate_manifest_hooks(sidecars)
        # Both hook types should produce entries
        assert len(result) == 4  # 2 sidecars + 2 scripts

    def test_empty_sidecars_returns_empty_list(self) -> None:
        """Should return empty list when no sidecars provided."""
        result = generate_manifest_hooks([])
        assert result == []


# ---------------------------------------------------------------------------
# 5. generate_settings_hooks
# ---------------------------------------------------------------------------


class TestGenerateSettingsHooks:
    """Tests for generate_settings_hooks function."""

    def test_lifecycle_only(self) -> None:
        """Should only include lifecycle hooks, not utility hooks."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR]
        result = generate_settings_hooks(sidecars)
        # Utility hooks should not appear in settings
        for event_entries in result.values():
            for entry in event_entries:
                for hook in entry["hooks"]:
                    assert "genai_utils" not in hook["command"]

    def test_excludes_inactive_hooks(self) -> None:
        """Should exclude hooks with active=False."""
        inactive = {
            **SAMPLE_LIFECYCLE_SIDECAR,
            "name": "inactive_hook",
            "active": False,
        }
        sidecars = [inactive]
        result = generate_settings_hooks(sidecars)
        assert result == {}

    def test_dual_registration(self) -> None:
        """Should create entries for each registration of a hook."""
        result = generate_settings_hooks([SAMPLE_LIFECYCLE_SIDECAR])
        assert "PostToolUse" in result
        assert "Stop" in result

    def test_env_vars_in_command(self) -> None:
        """Should include env vars in command string."""
        result = generate_settings_hooks([SAMPLE_PRE_TOOL_SIDECAR])
        assert "PreToolUse" in result
        command = result["PreToolUse"][0]["hooks"][0]["command"]
        assert "MCP_AUTO_APPROVE=true" in command
        assert "SANDBOX_ENABLED=false" in command

    def test_events_sorted_alphabetically(self) -> None:
        """Should sort event names alphabetically."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]
        result = generate_settings_hooks(sidecars)
        events = list(result.keys())
        assert events == sorted(events)

    def test_specific_matchers_before_wildcard(self) -> None:
        """Within an event, specific matchers should come before wildcard '*'."""
        specific_sidecar = {
            "name": "plan_mode_exit_detector",
            "type": "lifecycle",
            "interpreter": "python3",
            "active": True,
            "registrations": [
                {"event": "PostToolUse", "matcher": "ExitPlanMode", "timeout": 3},
            ],
        }
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, specific_sidecar]
        result = generate_settings_hooks(sidecars)
        post_tool = result["PostToolUse"]
        # ExitPlanMode specific matcher should come before * wildcard
        assert post_tool[0]["matcher"] == "ExitPlanMode"
        assert post_tool[1]["matcher"] == "*"

    def test_output_format_matches_settings_structure(self) -> None:
        """Should produce the exact structure expected by settings template."""
        result = generate_settings_hooks([SAMPLE_PRE_TOOL_SIDECAR])
        entry = result["PreToolUse"][0]
        assert "matcher" in entry
        assert "hooks" in entry
        assert entry["hooks"][0]["type"] == "command"
        assert "command" in entry["hooks"][0]
        assert "timeout" in entry["hooks"][0]

    def test_timeout_comes_from_the_canonical_budget_not_the_registration(
        self,
    ) -> None:
        """Issue #1704: the sidecar no longer decides the timeout.

        This test previously asserted that a per-registration timeout won
        (Stop=3, PostToolUse=5). That behaviour WAS the defect: every sidecar
        and every settings surface independently re-declared the number, and
        the generator's own ``reg.get("timeout", 5)`` default seeded it. The
        budget now comes from ``config/hook_time_budgets.json`` and is uniform
        per hook, so BOTH events get the same value.

        The expected value is read from the canonical source, never hardcoded
        here -- a literal would just re-create the third copy.
        """
        budgets = {
            "default": {"budget_seconds": 11, "warning_pct": 0.8},
            "hooks": {},
            "libraries": {},
        }
        result = generate_settings_hooks([SAMPLE_LIFECYCLE_SIDECAR], budgets=budgets)
        expected = budgets["default"]["budget_seconds"]
        assert result["Stop"][0]["hooks"][0]["timeout"] == expected
        assert result["PostToolUse"][0]["hooks"][0]["timeout"] == expected

    def test_per_hook_budget_overrides_the_default(self) -> None:
        """A hook with its own entry gets it; NEGATIVE CONTROL for the above.

        Without this, the previous test alone would pass even if
        ``resolve_timeout`` ignored the per-hook table entirely and always
        returned the default.
        """
        budgets = {
            "default": {"budget_seconds": 11, "warning_pct": 0.8},
            "hooks": {SAMPLE_LIFECYCLE_SIDECAR["name"]: {"budget_seconds": 23}},
            "libraries": {},
        }
        result = generate_settings_hooks([SAMPLE_LIFECYCLE_SIDECAR], budgets=budgets)
        assert result["Stop"][0]["hooks"][0]["timeout"] == 23

    def test_empty_sidecars_returns_empty_dict(self) -> None:
        """Should return empty dict when no sidecars provided."""
        result = generate_settings_hooks([])
        assert result == {}


# ---------------------------------------------------------------------------
# 6. build_command_string
# ---------------------------------------------------------------------------


class TestBuildCommandString:
    """Tests for build_command_string function."""

    def test_env_vars_sorted_alphabetically(self) -> None:
        """Env vars should be sorted alphabetically in the command string."""
        result = build_command_string(SAMPLE_PRE_TOOL_SIDECAR)
        # MCP_AUTO_APPROVE comes before SANDBOX_ENABLED alphabetically
        mcp_pos = result.index("MCP_AUTO_APPROVE")
        sandbox_pos = result.index("SANDBOX_ENABLED")
        assert mcp_pos < sandbox_pos

    def test_no_env_vars(self) -> None:
        """Should produce clean command when no env vars are set."""
        sidecar = {
            "name": "simple_hook",
            "type": "lifecycle",
            "interpreter": "python3",
        }
        result = build_command_string(sidecar)
        assert result == "python3 ~/.claude/hooks/simple_hook.py"

    def test_bash_interpreter(self) -> None:
        """Should use bash and .sh extension for bash interpreter."""
        sidecar = {
            "name": "pre_compact_saver",
            "type": "lifecycle",
            "interpreter": "bash",
        }
        result = build_command_string(sidecar)
        assert result == "bash ~/.claude/hooks/pre_compact_saver.sh"

    def test_full_command_with_env(self) -> None:
        """Should produce full command with sorted env vars, interpreter, and path."""
        result = build_command_string(SAMPLE_PRE_TOOL_SIDECAR)
        expected = (
            "MCP_AUTO_APPROVE=true SANDBOX_ENABLED=false "
            "python3 ~/.claude/hooks/unified_pre_tool.py"
        )
        assert result == expected

    def test_single_env_var(self) -> None:
        """Should handle a single env var correctly."""
        result = build_command_string(SAMPLE_LIFECYCLE_SIDECAR)
        expected = (
            "ACTIVITY_LOGGING=true "
            "python3 ~/.claude/hooks/session_activity_logger.py"
        )
        assert result == expected


# ---------------------------------------------------------------------------
# 7. check_drift (--check mode)
# ---------------------------------------------------------------------------


class TestCheckDrift:
    """Tests for check_drift function."""

    def test_no_drift_returns_zero(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should return 0 when config matches sidecar-generated config."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]

        # Write manifest with expected hooks
        manifest = {
            "version": "1.0.0",
            "components": {
                "hooks": {
                    "target": ".claude/hooks",
                    "files": generate_manifest_hooks(sidecars),
                }
            },
        }
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

        # Write settings with expected hooks
        settings = {
            "permissions": {"allow": ["Bash"]},
            "hooks": generate_settings_hooks(sidecars),
        }
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps(settings, indent=2, sort_keys=True))

        schema_path = config_dir / "schema.json"
        schema_path.write_text("{}")

        result = check_drift(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=schema_path,
        )
        assert result == 0

    def test_drift_returns_one(self, hooks_dir: Path, config_dir: Path) -> None:
        """Should return 1 when config does not match sidecar-generated config."""
        # Write manifest with mismatched hooks
        manifest = {
            "components": {
                "hooks": {
                    "files": ["plugins/autonomous-dev/hooks/old_hook.py"],
                }
            },
        }
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        settings = {"hooks": {}}
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps(settings))

        schema_path = config_dir / "schema.json"
        schema_path.write_text("{}")

        result = check_drift(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=schema_path,
        )
        assert result == 1

    def test_missing_manifest_returns_one(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should return 1 when manifest file does not exist."""
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        result = check_drift(
            hooks_dir=hooks_dir,
            manifest_path=config_dir / "nonexistent.json",
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )
        assert result == 1

    def test_verbose_output(
        self, hooks_dir: Path, config_dir: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Should print detailed info in verbose mode."""
        manifest = {"components": {"hooks": {"files": []}}}
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        settings = {"hooks": {}}
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps(settings))

        check_drift(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
            verbose=True,
        )
        captured = capsys.readouterr()
        assert "would add" in captured.out or "DRIFT" in captured.out or "Drift" in captured.out


# ---------------------------------------------------------------------------
# 8. write_mode (--write mode)
# ---------------------------------------------------------------------------


class TestWriteConfig:
    """Tests for write_config function."""

    def test_updates_manifest_hooks_section(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should update components.hooks.files in manifest."""
        manifest = {
            "version": "1.0.0",
            "description": "Test manifest",
            "components": {
                "hooks": {
                    "target": ".claude/hooks",
                    "files": ["old/file.py"],
                },
                "agents": {"target": ".claude/agents", "files": ["agents/test.md"]},
            },
        }
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        settings = {"permissions": {"allow": ["Bash"]}, "hooks": {}}
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps(settings))

        result = write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )
        assert result == 0

        # Verify manifest was updated
        updated = json.loads(manifest_path.read_text())
        hook_files = updated["components"]["hooks"]["files"]
        assert "plugins/autonomous-dev/hooks/genai_utils.py" in hook_files
        assert "plugins/autonomous-dev/hooks/genai_utils.hook.json" in hook_files

    def test_preserves_other_manifest_sections(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should preserve version, description, other components."""
        manifest = {
            "version": "3.50.0",
            "description": "Test manifest",
            "components": {
                "hooks": {"target": ".claude/hooks", "files": []},
                "agents": {"target": ".claude/agents", "files": ["agents/test.md"]},
            },
        }
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )

        updated = json.loads(manifest_path.read_text())
        assert updated["version"] == "3.50.0"
        assert updated["description"] == "Test manifest"
        assert updated["components"]["agents"]["files"] == ["agents/test.md"]

    def test_preserves_other_settings_sections(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should preserve permissions and other settings keys."""
        settings = {
            "permissionBatching": {"enabled": True},
            "permissions": {"allow": ["Bash", "Read"], "deny": ["Bash(rm -rf /)"]},
            "hooks": {},
        }
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps(settings))

        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(
            json.dumps({"components": {"hooks": {"files": []}}})
        )

        write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )

        updated = json.loads(settings_path.read_text())
        assert updated["permissionBatching"] == {"enabled": True}
        assert updated["permissions"]["allow"] == ["Bash", "Read"]
        assert "hooks" in updated
        # Hooks should be populated now
        assert len(updated["hooks"]) > 0

    def test_deterministic_output(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Running write twice should produce identical output."""
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(
            json.dumps({"components": {"hooks": {"files": []}}})
        )
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )
        first_manifest = manifest_path.read_text()
        first_settings = settings_path.read_text()

        write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )
        second_manifest = manifest_path.read_text()
        second_settings = settings_path.read_text()

        assert first_manifest == second_manifest
        assert first_settings == second_settings

    def test_trailing_newline(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Output files should end with a trailing newline."""
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(
            json.dumps({"components": {"hooks": {"files": []}}})
        )
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )

        assert manifest_path.read_text().endswith("\n")
        assert settings_path.read_text().endswith("\n")

    def test_creates_manifest_if_missing(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should create manifest from scratch if file does not exist."""
        manifest_path = config_dir / "install_manifest.json"
        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        # manifest_path does not exist
        result = write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )
        assert result == 0
        assert manifest_path.is_file()
        updated = json.loads(manifest_path.read_text())
        assert "components" in updated
        assert "hooks" in updated["components"]

    def test_preserves_hooks_target(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should preserve the hooks.target field in manifest."""
        manifest = {
            "components": {
                "hooks": {
                    "target": ".claude/hooks",
                    "files": [],
                }
            }
        }
        manifest_path = config_dir / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        settings_path = config_dir / "global_settings_template.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        write_config(
            hooks_dir=hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )

        updated = json.loads(manifest_path.read_text())
        assert updated["components"]["hooks"]["target"] == ".claude/hooks"


# ---------------------------------------------------------------------------
# 9. Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_missing_hooks_dir(self, config_dir: Path) -> None:
        """Should return error when hooks directory does not exist."""
        result = check_drift(
            hooks_dir=config_dir / "nonexistent",
            manifest_path=config_dir / "manifest.json",
            settings_path=config_dir / "settings.json",
            schema_path=config_dir / "schema.json",
        )
        # Should get FileNotFoundError propagated or return 1
        assert result == 1

    def test_invalid_sidecar_in_check_mode(
        self, tmp_path: Path, config_dir: Path
    ) -> None:
        """Should return 1 when a sidecar has invalid content."""
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "bad.hook.json").write_text("{invalid json")

        result = check_drift(
            hooks_dir=hooks,
            manifest_path=config_dir / "manifest.json",
            settings_path=config_dir / "settings.json",
            schema_path=config_dir / "schema.json",
        )
        assert result == 1

    def test_invalid_sidecar_in_write_mode(
        self, tmp_path: Path, config_dir: Path
    ) -> None:
        """Should return 1 when a sidecar has invalid content in write mode."""
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "bad.hook.json").write_text("{invalid json")

        manifest_path = config_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"components": {"hooks": {"files": []}}}))

        settings_path = config_dir / "settings.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        result = write_config(
            hooks_dir=hooks,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=config_dir / "schema.json",
        )
        assert result == 1


# ---------------------------------------------------------------------------
# 10. atomic_write_json
# ---------------------------------------------------------------------------


class TestAtomicWriteJson:
    """Tests for atomic_write_json function."""

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        """Should write valid JSON with indent=2 and sort_keys=True."""
        path = tmp_path / "test.json"
        data = {"z_key": 1, "a_key": 2}
        atomic_write_json(path, data)
        content = path.read_text()
        parsed = json.loads(content)
        assert parsed == data
        # Keys should be sorted in output
        assert content.index('"a_key"') < content.index('"z_key"')

    def test_trailing_newline(self, tmp_path: Path) -> None:
        """Written file should end with a newline."""
        path = tmp_path / "test.json"
        atomic_write_json(path, {"key": "value"})
        assert path.read_text().endswith("\n")

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Should overwrite existing file content."""
        path = tmp_path / "test.json"
        path.write_text('{"old": "data"}')
        atomic_write_json(path, {"new": "data"})
        assert json.loads(path.read_text()) == {"new": "data"}


# ---------------------------------------------------------------------------
# 11. CLI / main()
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for CLI argument parsing and main entry point."""

    def test_check_mode_via_main(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should run check mode when --check is passed."""
        sidecars = [SAMPLE_LIFECYCLE_SIDECAR, SAMPLE_UTILITY_SIDECAR, SAMPLE_PRE_TOOL_SIDECAR]
        manifest = {"components": {"hooks": {"files": generate_manifest_hooks(sidecars)}}}
        manifest_path = config_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

        settings = {"hooks": generate_settings_hooks(sidecars)}
        settings_path = config_dir / "settings.json"
        settings_path.write_text(json.dumps(settings, indent=2, sort_keys=True))

        result = main([
            "--check",
            "--hooks-dir", str(hooks_dir),
            "--manifest-path", str(manifest_path),
            "--settings-path", str(settings_path),
            "--schema-path", str(config_dir / "schema.json"),
        ])
        assert result == 0

    def test_write_mode_via_main(
        self, hooks_dir: Path, config_dir: Path
    ) -> None:
        """Should run write mode when --write is passed."""
        manifest_path = config_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps({"components": {"hooks": {"files": []}}})
        )
        settings_path = config_dir / "settings.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        result = main([
            "--write",
            "--hooks-dir", str(hooks_dir),
            "--manifest-path", str(manifest_path),
            "--settings-path", str(settings_path),
            "--schema-path", str(config_dir / "schema.json"),
        ])
        assert result == 0

    def test_mutually_exclusive_check_and_write(self) -> None:
        """Should return exit code 2 when both --check and --write are passed."""
        result = main(["--check", "--write"])
        assert result == 2

    def test_no_mode_returns_error(self) -> None:
        """Should return exit code 2 when neither --check nor --write is passed."""
        result = main([])
        assert result == 2


# ---------------------------------------------------------------------------
# 12. Integration: end-to-end with real existing sidecars
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end integration tests using real sidecar files."""

    @pytest.fixture
    def real_hooks_dir(self) -> Path:
        """Return the real hooks directory from the project."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        hooks_dir = project_root / "plugins/autonomous-dev/hooks"
        if not hooks_dir.is_dir():
            pytest.skip("Real hooks directory not found")
        return hooks_dir

    @pytest.fixture
    def real_schema_path(self) -> Path:
        """Return the real schema file path."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        return project_root / "plugins/autonomous-dev/config/hook-metadata.schema.json"

    def test_discover_real_sidecars(self, real_hooks_dir: Path) -> None:
        """Should discover the known sidecar files in the real hooks directory."""
        result = discover_sidecars(real_hooks_dir)
        names = [p.stem.replace(".hook", "") for p in result]
        assert "genai_utils" in names
        assert "session_activity_logger" in names
        assert "unified_pre_tool" in names

    def test_load_real_sidecars(
        self, real_hooks_dir: Path, real_schema_path: Path
    ) -> None:
        """Should successfully load and validate all real sidecar files."""
        schema = json.loads(real_schema_path.read_text()) if real_schema_path.is_file() else None
        sidecar_paths = discover_sidecars(real_hooks_dir)
        assert len(sidecar_paths) >= 3, "Expected at least 3 sidecar files"

        sidecars = []
        for path in sidecar_paths:
            data = load_and_validate_sidecar(path, schema)
            sidecars.append(data)

        # Verify known hooks are present
        names = {s["name"] for s in sidecars}
        assert "genai_utils" in names
        assert "session_activity_logger" in names
        assert "unified_pre_tool" in names

    def test_generate_real_manifest_hooks(
        self, real_hooks_dir: Path, real_schema_path: Path
    ) -> None:
        """Should generate valid manifest hooks from real sidecars."""
        schema = json.loads(real_schema_path.read_text()) if real_schema_path.is_file() else None
        sidecar_paths = discover_sidecars(real_hooks_dir)
        sidecars = [load_and_validate_sidecar(p, schema) for p in sidecar_paths]

        result = generate_manifest_hooks(sidecars)
        assert len(result) >= 6  # At least 3 hooks * 2 files each
        # All should be properly formatted paths
        for path in result:
            assert path.startswith("plugins/autonomous-dev/hooks/")

    def test_generate_real_settings_hooks(
        self, real_hooks_dir: Path, real_schema_path: Path
    ) -> None:
        """Should generate valid settings hooks from real sidecars."""
        schema = json.loads(real_schema_path.read_text()) if real_schema_path.is_file() else None
        sidecar_paths = discover_sidecars(real_hooks_dir)
        sidecars = [load_and_validate_sidecar(p, schema) for p in sidecar_paths]

        result = generate_settings_hooks(sidecars)
        # Should have at least PreToolUse and PostToolUse from known hooks
        assert "PreToolUse" in result
        assert "PostToolUse" in result
        assert "Stop" in result

    def test_end_to_end_write_and_check(
        self, real_hooks_dir: Path, real_schema_path: Path, tmp_path: Path
    ) -> None:
        """Should write config then check shows no drift."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(
            json.dumps({"components": {"hooks": {"files": []}}})
        )
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        # Write
        write_result = write_config(
            hooks_dir=real_hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=real_schema_path,
        )
        assert write_result == 0

        # Check should show no drift
        check_result = check_drift(
            hooks_dir=real_hooks_dir,
            manifest_path=manifest_path,
            settings_path=settings_path,
            schema_path=real_schema_path,
        )
        assert check_result == 0
