#!/usr/bin/env python3
"""
Unit tests for InstallationAnalyzer (TDD Red Phase - Issue #106).

Tests for GenAI-first installation system analysis and strategy recommendation.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because InstallationAnalyzer doesn't exist yet.

Test Strategy:
- Installation type detection (fresh/brownfield/upgrade)
- Conflict report generation
- Strategy recommendation
- Risk assessment

Date: 2025-12-09
Issue: #106 (GenAI-first installation system)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will FAIL until implementation exists
try:
    from installation_analyzer import InstallationAnalyzer, InstallationType
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


class TestInstallationTypeDetection:
    """Test detection of installation type."""

    def test_detect_fresh_installation_no_claude_directory(self, tmp_path):
        """Test detection of fresh installation (no .claude/ directory).

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()

        assert install_type == InstallationType.FRESH

    def test_detect_brownfield_installation_has_project_md(self, tmp_path):
        """Test detection of brownfield installation (has PROJECT.md).

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Existing project")

        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()

        assert install_type == InstallationType.BROWNFIELD

    def test_detect_upgrade_installation_has_plugin_files(self, tmp_path):
        """Test detection of upgrade installation (has existing plugin).

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Plugin files present (commands, hooks, etc.)
        commands_dir = claude_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "auto-implement.md").write_text("# Command")

        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# Hook")

        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()

        assert install_type == InstallationType.UPGRADE

    def test_detect_brownfield_with_user_artifacts(self, tmp_path):
        """Test brownfield detection with multiple user artifacts.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # User artifacts without plugin files
        (project_dir / ".env").write_text("API_KEY=secret")
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Project")
        (claude_dir / "batch_state.json").write_text("{}")

        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()

        assert install_type == InstallationType.BROWNFIELD

    def test_detect_upgrade_with_user_modifications(self, tmp_path):
        """Test upgrade detection when user has modified plugin files.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Plugin files + user modifications
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# Modified hook")
        (hooks_dir / "custom_hook.py").write_text("# Custom")

        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()

        assert install_type == InstallationType.UPGRADE


class TestConflictReportGeneration:
    """Test generation of conflict reports."""

    def test_generate_conflict_report_no_conflicts(self, tmp_path):
        """Test conflict report when no conflicts exist.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        (staging_dir / "new_file.py").write_text("content")

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_conflict_report(staging_dir)

        assert report["total_conflicts"] == 0
        assert report["conflicts"] == []

    def test_generate_conflict_report_with_conflicts(self, tmp_path):
        """Test conflict report with conflicting files.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "file.py").write_text("old content")

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        (staging_dir / "file.py").write_text("new content")

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_conflict_report(staging_dir)

        assert report["total_conflicts"] == 1
        assert len(report["conflicts"]) == 1
        assert report["conflicts"][0]["file"] == "file.py"

    def test_conflict_report_includes_file_details(self, tmp_path):
        """Test that conflict report includes detailed file information.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "file.py").write_text("old")

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        (staging_dir / "file.py").write_text("new")

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_conflict_report(staging_dir)

        conflict = report["conflicts"][0]
        assert "file" in conflict
        assert "existing_hash" in conflict
        assert "staging_hash" in conflict
        assert "category" in conflict

    def test_conflict_report_categorizes_conflicts(self, tmp_path):
        """Test that conflicts are categorized appropriately.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # User config conflict
        (claude_dir / "PROJECT.md").write_text("# User goals")

        # Modified plugin file conflict
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# Modified")

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        (staging_dir / "PROJECT.md").write_text("# Plugin template")
        (staging_dir / "hooks").mkdir()
        (staging_dir / "hooks" / "auto_format.py").write_text("# New version")

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_conflict_report(staging_dir)

        categories = [c["category"] for c in report["conflicts"]]
        assert "config" in categories
        assert "modified_plugin" in categories

    def test_conflict_report_includes_summary_statistics(self, tmp_path):
        """Test that report includes summary statistics.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "file1.py").write_text("old1")
        (claude_dir / "file2.py").write_text("old2")

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        (staging_dir / "file1.py").write_text("new1")
        (staging_dir / "file2.py").write_text("new2")

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_conflict_report(staging_dir)

        assert report["total_conflicts"] == 2
        assert "conflict_categories" in report
        assert report["total_staging_files"] > 0


class TestStrategyRecommendation:
    """Test installation strategy recommendation."""

    def test_recommend_copy_all_for_fresh_install(self, tmp_path):
        """Test recommendation for fresh installation.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        strategy = analyzer.recommend_strategy()

        assert strategy["approach"] == "copy_all"
        assert strategy["risk"] == "low"

    def test_recommend_skip_protected_for_brownfield(self, tmp_path):
        """Test recommendation for brownfield installation.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# User project")

        analyzer = InstallationAnalyzer(project_dir)
        strategy = analyzer.recommend_strategy()

        assert strategy["approach"] == "skip_protected"
        assert strategy["risk"] == "low"
        assert "protected_files" in strategy

    def test_recommend_backup_and_merge_for_upgrade_with_conflicts(
        self, tmp_path
    ):
        """Test recommendation for upgrade with conflicts.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Existing plugin with user modifications
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# User modified")

        analyzer = InstallationAnalyzer(project_dir)
        strategy = analyzer.recommend_strategy()

        assert strategy["approach"] == "backup_and_merge"
        assert strategy["risk"] in ["medium", "high"]
        assert "conflicts" in strategy

    def test_recommend_manual_review_for_high_risk(self, tmp_path):
        """Test recommendation for high-risk scenarios.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Many user modifications
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        for i in range(10):
            (hooks_dir / f"custom_hook{i}.py").write_text("# Custom")

        analyzer = InstallationAnalyzer(project_dir)
        strategy = analyzer.recommend_strategy()

        assert strategy["risk"] == "high"
        assert "manual_review_recommended" in strategy

    def test_strategy_includes_action_items(self, tmp_path):
        """Test that strategy includes actionable steps.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        strategy = analyzer.recommend_strategy()

        assert "action_items" in strategy
        assert len(strategy["action_items"]) > 0


class TestRiskAssessment:
    """Test risk assessment for installations."""

    def test_assess_low_risk_fresh_install(self, tmp_path):
        """Test low risk assessment for fresh install.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        risk = analyzer.assess_risk()

        assert risk["level"] == "low"
        assert risk["data_loss_risk"] is False

    def test_assess_medium_risk_with_conflicts(self, tmp_path):
        """Test medium risk assessment with some conflicts.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Project")

        analyzer = InstallationAnalyzer(project_dir)
        risk = analyzer.assess_risk()

        assert risk["level"] in ["low", "medium"]
        assert risk["data_loss_risk"] is False  # Protected files preserved

    def test_assess_high_risk_with_many_modifications(self, tmp_path):
        """Test high risk assessment with many user modifications.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Many custom files
        for category in ["hooks", "commands", "agents"]:
            cat_dir = claude_dir / category
            cat_dir.mkdir()
            for i in range(5):
                (cat_dir / f"custom_{i}.py").write_text("# Custom")

        analyzer = InstallationAnalyzer(project_dir)
        risk = analyzer.assess_risk()

        assert risk["level"] == "high"

    def test_risk_assessment_includes_factors(self, tmp_path):
        """Test that risk assessment includes contributing factors.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        risk = analyzer.assess_risk()

        assert "factors" in risk
        assert "protected_files_count" in risk
        assert "conflicts_count" in risk


class TestAnalysisReport:
    """Test comprehensive analysis report generation."""

    def test_generate_full_analysis_report(self, tmp_path):
        """Test generation of complete analysis report.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Project")

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()
        (staging_dir / "PROJECT.md").write_text("# Template")

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_analysis_report(staging_dir)

        assert "installation_type" in report
        assert "conflicts" in report
        assert "strategy" in report
        assert "risk" in report

    def test_analysis_report_includes_metadata(self, tmp_path):
        """Test that analysis report includes metadata.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_analysis_report(staging_dir)

        assert "timestamp" in report
        assert "project_dir" in report
        assert "staging_dir" in report

    def test_analysis_report_serializable_to_json(self, tmp_path):
        """Test that analysis report can be serialized to JSON.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        import json

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_analysis_report(staging_dir)

        # Should serialize without error
        json_str = json.dumps(report, indent=2)
        assert json_str is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_missing_project_directory(self, tmp_path):
        """Test handling missing project directory.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="does not exist"):
            InstallationAnalyzer(nonexistent)

    def test_handles_missing_staging_directory(self, tmp_path):
        """Test handling missing staging directory.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        nonexistent_staging = tmp_path / "nonexistent"

        analyzer = InstallationAnalyzer(project_dir)

        with pytest.raises(ValueError, match="staging.*not found"):
            analyzer.generate_conflict_report(nonexistent_staging)

    def test_handles_empty_directories(self, tmp_path):
        """Test handling empty project and staging directories.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "empty-project"
        project_dir.mkdir()

        staging_dir = tmp_path / "empty-staging"
        staging_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_analysis_report(staging_dir)

        assert report["installation_type"] == InstallationType.FRESH
        assert report["conflicts"]["total_conflicts"] == 0

    def test_handles_symlinked_directories(self, tmp_path):
        """Test handling symlinked project directory.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        real_dir = tmp_path / "real-project"
        real_dir.mkdir()

        symlink_dir = tmp_path / "symlink-project"
        symlink_dir.symlink_to(real_dir)

        analyzer = InstallationAnalyzer(symlink_dir)
        install_type = analyzer.detect_installation_type()

        assert install_type == InstallationType.FRESH

    def test_performance_with_large_directories(self, tmp_path):
        """Test performance with large project directories.

        Current: FAILS - InstallationAnalyzer doesn't exist
        """
        project_dir = tmp_path / "large-project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Create many files
        for i in range(100):
            (claude_dir / f"file{i}.py").write_text(f"# File {i}")

        staging_dir = tmp_path / ".claude-staging"
        staging_dir.mkdir()

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_analysis_report(staging_dir)

        assert report is not None
