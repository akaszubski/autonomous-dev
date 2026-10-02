"""Plugin-owned native hooks migrate without erasing consumer registrations."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev"
sys.path.insert(0, str(ROOT / "scripts"))
from sync_settings_hooks import _replace_hooks  # noqa: E402 - plugin script path above
from sync_settings_hooks import _strip_plugin_owned  # noqa: E402 - plugin script path above
from sync_settings_hooks import _write_settings_transaction  # noqa: E402 - plugin script path above


def test_interrupted_transaction_marker_refuses_retry_without_mutation(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"customKey": "original"}\n')
    marker = tmp_path / ".autonomous-dev-settings-transaction"
    marker.write_text("interrupted")
    with pytest.raises(RuntimeError, match="PARTIAL or interrupted"):
        _write_settings_transaction({settings: {"customKey": "new"}})
    assert settings.read_text() == '{"customKey": "original"}\n'
    assert marker.read_text() == "interrupted"


def test_process_death_between_settings_replaces_refuses_next_install(tmp_path):
    global_settings = tmp_path / "settings.json"
    local_settings = tmp_path / "settings.local.json"
    global_settings.write_text('{"old": "global"}\n')
    local_settings.write_text('{"old": "local"}\n')
    child = """
import os
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import sync_settings_hooks as module
real_replace = module.os.replace
count = 0
def die_after_first_replace(source, target):
    global count
    real_replace(source, target)
    count += 1
    if count == 1:
        os._exit(91)
module.os.replace = die_after_first_replace
module._write_settings_transaction({
    Path(sys.argv[2]): {"new": "global"},
    Path(sys.argv[3]): {"new": "local"},
})
"""
    result = subprocess.run(
        [sys.executable, "-c", child, str(ROOT / "scripts"),
         str(global_settings), str(local_settings)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 91
    assert json.loads(global_settings.read_text()) == {"new": "global"}
    assert json.loads(local_settings.read_text()) == {"old": "local"}
    marker = tmp_path / ".autonomous-dev-settings-transaction"
    assert marker.exists()
    assert list(tmp_path.glob(".settings.json.restore.*"))
    with pytest.raises(RuntimeError, match="PARTIAL or interrupted"):
        _write_settings_transaction({global_settings: {"new": "retry"}})
    assert json.loads(global_settings.read_text()) == {"new": "global"}


from configure_global_settings import upgrade_existing_settings  # noqa: E402 - plugin script path above


def _commands(settings):
    return [hook.get("command") for entries in settings.get("hooks", {}).values()
            for entry in entries for hook in entry.get("hooks", [])]


def test_native_guard_migration_retires_only_exact_legacy_owner():
    legacy = {"type": "command", "command": "python3 ~/.claude/hooks/unified_pre_tool.py"}
    foreign = {"type": "command", "command": "python3 /opt/consumer/unified_pre_tool.py"}
    hooks = {"PreToolUse": [{"matcher": "*", "hooks": [legacy, foreign]}]}
    migrated, removed = _strip_plugin_owned(hooks)
    assert removed == 1
    assert migrated == {"PreToolUse": [{"matcher": "*", "hooks": [foreign]}]}
    assert hooks["PreToolUse"][0]["hooks"] == [legacy, foreign]


def test_populated_global_and_local_survive_two_installs(tmp_path):
    user = tmp_path / ".claude" / "settings.json"
    user.parent.mkdir()
    local = user.with_name("settings.local.json")
    legacy = "ACTIVITY_LOGGING=true python3 ~/.claude/hooks/session_activity_logger.py"
    custom = "python3 /opt/consumer/session_activity_logger.py"
    user.write_text(json.dumps({"permissions": {"allow": ["Read"]}, "customKey": 42,
        "hooks": {"PostToolUse": [
            {"matcher": "*", "hooks": [{"type": "command", "command": legacy}]},
            {"matcher": "*", "hooks": [{"type": "command", "command": custom}]},
        ]}}))
    local.write_text(json.dumps({"permissions": {"ask": ["Bash"]}, "localKey": True,
        "hooks": {"SubagentStop": [
            {"matcher": "*", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/unified_session_tracker.py"}]},
            {"matcher": "*", "hooks": [{"type": "command", "command": "echo local"}]},
        ]}}))
    template = ROOT / "config" / "global_settings_template.json"
    _replace_hooks(user, template)
    first_user = json.loads(user.read_text())
    first_local = json.loads(local.read_text())
    assert first_user["customKey"] == 42
    assert first_user["permissions"]["allow"] == ["Read"]
    assert custom in _commands(first_user)
    assert all(legacy not in [h.get("command") for h in entry.get("hooks", [])]
               for entry in first_user["hooks"].get("PostToolUse", []))
    assert first_local["localKey"] is True
    assert first_local["permissions"]["ask"] == ["Bash"]
    assert _commands(first_local) == ["echo local"]
    _replace_hooks(user, template)
    assert json.loads(user.read_text()) == first_user
    assert json.loads(local.read_text()) == first_local


def test_repo_template_migration_preserves_unrelated_entry(tmp_path):
    user = tmp_path / ".claude" / "settings.json"
    user.parent.mkdir()
    user.write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command": "echo consumer"}]},
        {"matcher": "Task|Agent", "hooks": [{"type": "command", "command":
            'python3 "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/session_activity_logger.py"'}]},
    ]}}))
    _replace_hooks(user, ROOT / "templates" / "settings.default.json")
    commands = _commands(json.loads(user.read_text()))
    assert "echo consumer" in commands
    assert all("session_activity_logger.py" not in h.get("command", "")
               for entry in json.loads(user.read_text())["hooks"]["PreToolUse"]
               if entry.get("matcher") != "Bash" for h in entry.get("hooks", []))


def test_shipped_registration_has_single_plugin_owner():
    plugin = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    assert len(plugin["SubagentStop"]) == 1
    assert plugin["SubagentStop"][0]["hooks"][0]["args"][-1] == "--native"
    assert len(plugin["UserPromptExpansion"]) == 1
    assert len(plugin["PostToolUse"]) == 1
    for path in (ROOT / "config" / "global_settings_template.json",
                 ROOT / "templates" / "settings.autonomous-dev.json"):
        hooks = json.loads(path.read_text())["hooks"]
        _, removed = _strip_plugin_owned(hooks)
        assert removed == 0, path


def test_global_installer_upgrade_removes_exact_legacy_and_keeps_custom(tmp_path):
    from settings_generator import SettingsGenerator
    user = tmp_path / "settings.json"
    user.write_text(json.dumps({"hooks": {"SubagentStop": [
        {"matcher": "*", "hooks": [{"type": "command", "command": "echo custom stop"}]},
    ], "PostToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command":
            "ACTIVITY_LOGGING=true python3 ~/.claude/hooks/session_activity_logger.py"}]},
        {"matcher": "*", "hooks": [{"type": "command", "command": "echo custom"}]},
    ]}, "customKey": 12}))
    generator = SettingsGenerator(project_root=tmp_path)
    generator.merge_global_settings(user, ROOT / "config" / "global_settings_template.json",
                                    create_backup=False)
    installed = json.loads(user.read_text())
    assert installed["customKey"] == 12
    assert "echo custom" in _commands(installed)
    assert "echo custom stop" in _commands(installed)
    assert all("session_activity_logger.py" not in h.get("command", "")
               for entry in installed["hooks"]["PostToolUse"] for h in entry.get("hooks", []))


def test_install_cli_twice_migrates_global_local_and_repo(tmp_path):
    home = tmp_path / "home" / ".claude"
    home.mkdir(parents=True)
    global_settings = home / "settings.json"
    global_settings.write_text(json.dumps({"permissions": {"allow": ["Read"]},
        "hooks": {"UserPromptExpansion": [{"matcher": "*", "hooks": [
            {"type": "command", "command": "python3 ~/.claude/hooks/native_run_origin.py"}]}],
                  "PreToolUse": [{"matcher": "*", "hooks": [
                      {"type": "command", "command": "echo global custom"}]}]}}))
    local = home / "settings.local.json"
    local.write_text(json.dumps({"localKey": "keep", "hooks": {"SubagentStop": [
        {"matcher": "*", "hooks": [{"type": "command", "command":
            "python3 ~/.claude/hooks/unified_session_tracker.py"}]},
        {"matcher": "*", "hooks": [{"type": "command", "command": "echo local custom"}]},
    ]}}))
    command = [sys.executable, str(ROOT / "scripts" / "configure_global_settings.py"),
               "--template", str(ROOT / "config" / "global_settings_template.json"),
               "--home", str(home)]
    for _ in range(2):
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        assert json.loads(result.stdout)["success"] is True, result.stdout
    assert "echo global custom" in _commands(json.loads(global_settings.read_text()))
    assert "echo local custom" in _commands(json.loads(local.read_text()))
    assert "native_run_origin.py" not in " ".join(_commands(json.loads(global_settings.read_text())))
    assert "unified_session_tracker.py" not in " ".join(_commands(json.loads(local.read_text())))
    repo = tmp_path / "repo"
    repo.mkdir()
    repo_settings = repo / ".claude" / "settings.json"
    repo_settings.parent.mkdir()
    repo_settings.write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command": "echo repo custom"}]},
    ]}}))
    repo_command = [sys.executable, str(ROOT / "scripts" / "sync_settings_hooks.py"),
                    "--repo", str(repo)]
    for _ in range(2):
        result = subprocess.run(repo_command, capture_output=True, text=True, check=True)
        assert json.loads(result.stdout)["success"] is True
    assert "echo repo custom" in _commands(json.loads(repo_settings.read_text()))


def test_malformed_hooks_never_replaced(tmp_path):
    user = tmp_path / "settings.json"
    local = tmp_path / "settings.local.json"
    user.write_text(json.dumps({"hooks": ["malformed"]}))
    local.write_text(json.dumps({"hooks": {"SubagentStop": []}}))
    before = (user.read_bytes(), local.read_bytes())
    with pytest.raises(ValueError, match="hooks object"):
        _replace_hooks(user, ROOT / "config" / "global_settings_template.json")
    result = upgrade_existing_settings(user, ROOT / "config" / "global_settings_template.json")
    assert result["success"] is False
    assert (user.read_bytes(), local.read_bytes()) == before


def test_second_replace_failure_rolls_back_both_settings(tmp_path, monkeypatch):
    user = tmp_path / "settings.json"
    local = tmp_path / "settings.local.json"
    user.write_text('{"user":1}')
    local.write_text('{"local":1}')
    before = (user.read_bytes(), local.read_bytes())
    replace = os.replace
    failed = False

    def fail_second(source, target):
        nonlocal failed
        if Path(target) == local and not failed:
            failed = True
            raise OSError("injected second replacement failure")
        return replace(source, target)

    monkeypatch.setattr(os, "replace", fail_second)
    with pytest.raises(OSError, match="injected"):
        _write_settings_transaction({user: {"user": 2}, local: {"local": 2}})
    assert (user.read_bytes(), local.read_bytes()) == before


def test_upgrade_second_file_failure_restores_global_and_local(tmp_path, monkeypatch):
    user = tmp_path / "settings.json"
    local = tmp_path / "settings.local.json"
    user.write_text(json.dumps({"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": "echo consumer"}]}]}, "customKey": 1}))
    local.write_text(json.dumps({"hooks": {"SubagentStop": [{"matcher": "*", "hooks": [
        {"type": "command", "command": "python3 ~/.claude/hooks/unified_session_tracker.py"}]}]}}))
    before = (user.read_bytes(), local.read_bytes())
    replace = os.replace
    failed = False

    def fail_local(source, target):
        nonlocal failed
        if Path(target) == local and not failed:
            failed = True
            raise OSError("injected local write failure")
        return replace(source, target)

    monkeypatch.setattr(os, "replace", fail_local)
    result = upgrade_existing_settings(user, ROOT / "config" / "global_settings_template.json")
    assert result["success"] is False
    assert (user.read_bytes(), local.read_bytes()) == before


def test_rollback_failure_reports_partial_and_keeps_recovery_backup(tmp_path, monkeypatch):
    user = tmp_path / "settings.json"
    local = tmp_path / "settings.local.json"
    user.write_text('{"user":1}')
    local.write_text('{"local":1}')
    replace = os.replace

    def fail_second_and_rollback(source, target):
        if Path(target) == local or ".restore." in str(source):
            raise OSError("injected permanent replacement failure")
        return replace(source, target)

    monkeypatch.setattr(os, "replace", fail_second_and_rollback)
    with pytest.raises(RuntimeError, match="PARTIAL settings update.*private recovery backups"):
        _write_settings_transaction({user: {"user": 2}, local: {"local": 2}})
    assert json.loads(local.read_text()) == {"local": 1}
    assert any("user" in path.read_text() for path in tmp_path.glob(".settings.json.restore.*"))
