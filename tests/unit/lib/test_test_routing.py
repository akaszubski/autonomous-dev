"""Unit tests for smart test routing library.

Tests classification, marker expression generation, skipped tier reporting,
config loading, and the high-level route_tests API.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"))

from test_routing import (
    classify_changes,
    compute_marker_expression,
    get_changed_files,
    get_skipped_tiers,
    load_routing_config,
    route_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def routing_config():
    """Load the actual routing config from the repo."""
    config_path = (
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "config"
        / "test_routing_config.json"
    )
    return json.loads(config_path.read_text())


@pytest.fixture
def config_path():
    """Path to the actual routing config."""
    return (
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "config"
        / "test_routing_config.json"
    )


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------

class TestClassifyChanges:
    """Test file classification into routing categories."""

    def test_hook_files(self):
        files = ["plugins/autonomous-dev/hooks/unified_pre_tool.py"]
        assert classify_changes(files) == {"hook"}

    def test_hook_files_short_path(self):
        files = ["hooks/my_hook.py"]
        assert classify_changes(files) == {"hook"}

    def test_agent_prompt_files(self):
        files = ["plugins/autonomous-dev/agents/implementer.md"]
        assert classify_changes(files) == {"agent_prompt"}

    def test_command_files(self):
        files = ["plugins/autonomous-dev/commands/implement.md"]
        assert classify_changes(files) == {"command"}

    def test_lib_files(self):
        files = ["plugins/autonomous-dev/lib/test_routing.py"]
        assert classify_changes(files) == {"lib"}

    def test_config_json_files(self):
        files = ["plugins/autonomous-dev/config/settings.json"]
        assert classify_changes(files) == {"config"}

    def test_config_yaml_files(self):
        files = ["some/path/config.yaml"]
        assert classify_changes(files) == {"config"}

    def test_config_yml_files(self):
        files = ["some/path/config.yml"]
        assert classify_changes(files) == {"config"}

    def test_skill_files(self):
        files = ["plugins/autonomous-dev/skills/testing-guide/SKILL.md"]
        assert classify_changes(files) == {"skill"}

    def test_docs_only_files(self):
        files = ["docs/ARCHITECTURE.md"]
        assert classify_changes(files) == {"docs_only"}

    def test_readme_is_docs(self):
        files = ["README.md"]
        assert classify_changes(files) == {"docs_only"}

    def test_changelog_is_docs(self):
        files = ["CHANGELOG.md"]
        assert classify_changes(files) == {"docs_only"}

    def test_install_sync_files(self):
        files = ["install.sh"]
        assert classify_changes(files) == {"install_sync"}

    def test_sync_md_files(self):
        files = ["sync-plugin.md"]
        assert classify_changes(files) == {"install_sync"}

    def test_unknown_files_are_unclassified(self):
        files = ["some/random/file.txt"]
        assert classify_changes(files) == {"unclassified"}

    def test_mixed_changes(self):
        files = [
            "plugins/autonomous-dev/hooks/pre_tool.py",
            "plugins/autonomous-dev/lib/utils.py",
        ]
        result = classify_changes(files)
        assert result == {"hook", "lib"}

    def test_empty_file_list(self):
        assert classify_changes([]) == set()

    def test_mixed_with_unclassified(self):
        files = ["plugins/autonomous-dev/lib/foo.py", "random.txt"]
        result = classify_changes(files)
        assert "lib" in result
        assert "unclassified" in result


# ---------------------------------------------------------------------------
# Marker expression tests
# ---------------------------------------------------------------------------

class TestComputeMarkerExpression:
    """Test pytest marker expression generation."""

    def test_empty_categories_returns_full_suite(self, routing_config):
        expr = compute_marker_expression(set(), routing_config)
        assert expr == ""

    def test_unclassified_returns_full_suite(self, routing_config):
        expr = compute_marker_expression({"unclassified"}, routing_config)
        assert expr == ""

    def test_docs_only_returns_skip_all(self, routing_config):
        expr = compute_marker_expression({"docs_only"}, routing_config)
        assert expr == "__skip_all__"

    def test_hook_category_includes_smoke_and_hooks(self, routing_config):
        expr = compute_marker_expression({"hook"}, routing_config)
        markers = set(expr.split(" or "))
        assert "smoke" in markers
        assert "hooks" in markers
        assert "regression" in markers

    def test_lib_category_includes_expected_markers(self, routing_config):
        expr = compute_marker_expression({"lib"}, routing_config)
        markers = set(expr.split(" or "))
        assert "smoke" in markers
        assert "unit" in markers
        assert "regression" in markers
        assert "property" in markers

    def test_agent_prompt_includes_genai(self, routing_config):
        expr = compute_marker_expression({"agent_prompt"}, routing_config)
        markers = set(expr.split(" or "))
        assert "smoke" in markers
        assert "genai" in markers

    def test_mixed_categories_union_markers(self, routing_config):
        expr = compute_marker_expression({"hook", "agent_prompt"}, routing_config)
        markers = set(expr.split(" or "))
        # hook adds: smoke, hooks, regression
        # agent_prompt adds: smoke, genai
        assert "smoke" in markers
        assert "hooks" in markers
        assert "regression" in markers
        assert "genai" in markers

    def test_docs_mixed_with_code_not_skip_all(self, routing_config):
        """docs_only mixed with other categories should not skip all."""
        expr = compute_marker_expression({"docs_only", "lib"}, routing_config)
        assert expr != "__skip_all__"
        assert expr != ""


# ---------------------------------------------------------------------------
# Skipped tiers tests
# ---------------------------------------------------------------------------

class TestGetSkippedTiers:
    """Test reporting of skipped test tiers."""

    def test_empty_categories_nothing_skipped(self, routing_config):
        skipped = get_skipped_tiers(set(), routing_config)
        assert skipped == []

    def test_unclassified_nothing_skipped(self, routing_config):
        skipped = get_skipped_tiers({"unclassified"}, routing_config)
        assert skipped == []

    def test_docs_only_all_skipped(self, routing_config):
        skipped = get_skipped_tiers({"docs_only"}, routing_config)
        assert len(skipped) > 0

    def test_hook_skips_genai_and_property(self, routing_config):
        skipped = get_skipped_tiers({"hook"}, routing_config)
        assert "genai" in skipped
        assert "property" in skipped

    def test_lib_skips_genai(self, routing_config):
        skipped = get_skipped_tiers({"lib"}, routing_config)
        assert "genai" in skipped


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------

class TestLoadRoutingConfig:
    """Test configuration loading."""

    def test_loads_default_config(self, config_path):
        config = load_routing_config(config_path)
        assert "routing_rules" in config
        assert "tier_to_marker" in config

    def test_missing_config_raises(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            load_routing_config(missing)

    def test_custom_config(self, tmp_path):
        custom = tmp_path / "custom.json"
        custom.write_text(json.dumps({
            "routing_rules": {"hook": {"smoke": True}},
            "tier_to_marker": {"smoke": "smoke"},
        }))
        config = load_routing_config(custom)
        assert config["routing_rules"]["hook"]["smoke"] is True


# ---------------------------------------------------------------------------
# get_changed_files tests
# ---------------------------------------------------------------------------

class TestGetChangedFiles:
    """Test git diff integration."""

    @patch("test_routing.subprocess.run")
    def test_returns_files_from_git(self, mock_run):
        mock_run.side_effect = [
            MagicMock(stdout="file1.py\nfile2.py\n"),
            MagicMock(stdout="file3.py\n"),
        ]
        files = get_changed_files()
        assert "file1.py" in files
        assert "file2.py" in files
        assert "file3.py" in files

    @patch("test_routing.subprocess.run")
    def test_empty_diff_returns_empty(self, mock_run):
        # Three calls: git diff HEAD, git ls-files --others, git diff HEAD~1 (fallback)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout=""),  # fallback also empty
        ]
        files = get_changed_files()
        assert files == []

    @patch("test_routing.subprocess.run", side_effect=FileNotFoundError)
    def test_git_not_found_returns_empty(self, mock_run):
        files = get_changed_files()
        assert files == []

    def test_get_changed_files_falls_back_to_head_tilde_1_when_head_diff_empty(self, tmp_path):
        """HEAD~1 fallback fires when HEAD diff is empty (committed-but-no-working-changes).

        Build a real temp git repo: init, first commit, second commit modifying
        lib/foo.py. Since all changes are committed and there is no working-tree
        diff, git diff HEAD returns nothing. The fallback (git diff HEAD~1)
        should surface the files changed in the most-recent commit.
        """
        import subprocess as sp

        # Set up git repo
        sp.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

        # First commit (initial)
        readme = tmp_path / "README.md"
        readme.write_text("initial")
        sp.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, check=True, capture_output=True)

        # Second commit modifying lib/foo.py
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        foo = lib_dir / "foo.py"
        foo.write_text("def foo(): pass")
        sp.run(["git", "add", "lib/foo.py"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "commit", "-m", "add lib/foo.py"], cwd=tmp_path, check=True, capture_output=True)

        # Working tree is clean: git diff HEAD returns nothing.
        # The HEAD~1 fallback should surface lib/foo.py.
        files = get_changed_files(cwd=tmp_path)
        assert "lib/foo.py" in files, f"Expected lib/foo.py in fallback result, got: {files}"

    @patch("test_routing.subprocess.run")
    def test_get_changed_files_skips_fallback_when_head_diff_non_empty(self, mock_run):
        """No fallback invocation when git diff HEAD already has results.

        Only 2 subprocess.run calls should be made (git diff HEAD + git ls-files),
        NOT 3 (which would include the HEAD~1 fallback).
        """
        # First call (git diff HEAD) returns a file; second (git ls-files) empty.
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="lib/bar.py\n"),
            MagicMock(returncode=0, stdout=""),
        ]
        files = get_changed_files()
        assert "lib/bar.py" in files
        # Only 2 calls: no fallback needed
        assert mock_run.call_count == 2, (
            f"Expected 2 subprocess.run calls (no fallback), got {mock_run.call_count}"
        )

    def test_get_changed_files_returns_empty_when_head_tilde_1_unavailable(self, tmp_path):
        """Single-commit repo has no HEAD~1; fallback must return [] without raising.

        This simulates shallow clones and brand-new repos with only one commit.
        """
        import subprocess as sp

        # Set up git repo with only one commit (no HEAD~1)
        sp.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

        readme = tmp_path / "README.md"
        readme.write_text("only commit")
        sp.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "commit", "-m", "only commit"], cwd=tmp_path, check=True, capture_output=True)

        # Working tree is clean, HEAD~1 does not exist -> should return []
        files = get_changed_files(cwd=tmp_path)
        assert files == [], f"Expected empty list for single-commit repo, got: {files}"


# ---------------------------------------------------------------------------
# route_tests integration tests
# ---------------------------------------------------------------------------

class TestRouteTests:
    """Test the high-level route_tests API."""

    @patch("test_routing.get_changed_files")
    def test_no_changes_returns_full_suite(self, mock_files, config_path):
        mock_files.return_value = []
        result = route_tests(config_path=config_path)
        assert result["full_suite"] is True
        assert result["skip_all"] is False

    @patch("test_routing.get_changed_files")
    def test_docs_only_returns_skip_all(self, mock_files, config_path):
        mock_files.return_value = ["docs/README.md"]
        result = route_tests(config_path=config_path)
        assert result["skip_all"] is True
        assert result["full_suite"] is False

    @patch("test_routing.get_changed_files")
    def test_lib_change_returns_markers(self, mock_files, config_path):
        mock_files.return_value = ["plugins/autonomous-dev/lib/utils.py"]
        result = route_tests(config_path=config_path)
        assert result["full_suite"] is False
        assert result["skip_all"] is False
        assert result["marker_expression"] != ""
        assert "lib" in result["categories"]

    @patch("test_routing.get_changed_files")
    def test_missing_config_falls_back_to_full(self, mock_files, tmp_path):
        mock_files.return_value = ["plugins/autonomous-dev/lib/utils.py"]
        missing = tmp_path / "nope.json"
        result = route_tests(config_path=missing)
        assert result["full_suite"] is True

    def test_route_tests_categorizes_correctly_when_fallback_resolves(self, tmp_path, config_path):
        """Integration test: route_tests() works end-to-end when HEAD~1 fallback resolves.

        Builds a real temp git repo with a committed change to a lib/*.py file.
        The working tree is clean so get_changed_files() must use the HEAD~1
        fallback. route_tests() should then categorize the result as 'lib' and
        set full_suite=False.
        """
        import subprocess as sp

        sp.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

        # First commit
        readme = tmp_path / "README.md"
        readme.write_text("initial")
        sp.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, check=True, capture_output=True)

        # Second commit: add plugins/autonomous-dev/lib/repo_detector.py
        lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        detector = lib_dir / "repo_detector.py"
        detector.write_text("def detect(): pass")
        sp.run(["git", "add", str(detector.relative_to(tmp_path))], cwd=tmp_path, check=True, capture_output=True)
        sp.run(["git", "commit", "-m", "add repo_detector"], cwd=tmp_path, check=True, capture_output=True)

        result = route_tests(cwd=tmp_path, config_path=config_path)

        # Fallback should surface the lib file, classify it as 'lib', not full_suite
        assert "lib" in result["categories"], (
            f"Expected 'lib' in categories from fallback, got: {result['categories']}"
        )
        assert result["full_suite"] is False, (
            f"Expected full_suite=False for lib change, got: {result}"
        )
