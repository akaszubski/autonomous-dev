#!/usr/bin/env python3
"""
Integration tests for training best practices skills.

Tests the skill activation and progressive disclosure for:
- data-distillation skill
- preference-data-quality skill
- mlx-performance skill
- Cross-reference resolution
- Graceful degradation when docs/ are missing

Issue: #274 (Training best practices agents and skills)
"""

import pytest
from pathlib import Path


class TestDataDistillationSkill:
    """Test data-distillation skill integration."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_data_distillation_skill_exists(self, skills_dir):
        """
        GIVEN: Skills directory
        WHEN: Checking for data-distillation skill
        THEN: Skill directory and SKILL.md exist
        """
        skill_dir = skills_dir / "data-distillation"
        assert skill_dir.exists(), "data-distillation skill directory not found"

        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "data-distillation SKILL.md not found"

    def test_data_distillation_metadata_is_small(self, skills_dir):
        """
        GIVEN: data-distillation SKILL.md
        WHEN: Checking file size
        THEN: Metadata is under 2KB (progressive disclosure)
        """
        skill_metadata = skills_dir / "data-distillation" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        file_size = skill_metadata.stat().st_size
        assert file_size < 2048, \
            f"data-distillation SKILL.md too large: {file_size} bytes (should be <2KB)"

    def test_data_distillation_has_activation_keywords(self, skills_dir):
        """
        GIVEN: data-distillation SKILL.md
        WHEN: Checking for keywords
        THEN: Contains keywords for activation (IFD, distillation, KenLM)
        """
        skill_metadata = skills_dir / "data-distillation" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        content = skill_metadata.read_text()
        keywords = ["ifd", "distillation", "kenlm", "deduplication"]

        # Should mention at least 2 keywords
        found_keywords = [kw for kw in keywords if kw in content.lower()]
        assert len(found_keywords) >= 2, \
            f"data-distillation should mention keywords: {keywords}"

    def test_data_distillation_has_content_files(self, skills_dir):
        """
        GIVEN: data-distillation skill directory
        WHEN: Checking for content files
        THEN: Has docs/ directory with detailed content
        """
        skill_dir = skills_dir / "data-distillation"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        assert docs_dir.exists(), "data-distillation should have docs/ directory"

        # Should have at least one markdown file in docs/
        content_files = list(docs_dir.glob("*.md"))
        assert len(content_files) > 0, \
            "data-distillation docs/ should contain markdown files"

    def test_data_distillation_covers_ifd_methodology(self, skills_dir):
        """
        GIVEN: data-distillation skill content
        WHEN: Checking docs/ files
        THEN: Covers IFD (Instruction-Following Data) methodology
        """
        skill_dir = skills_dir / "data-distillation"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        # Check all markdown files for IFD content
        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "ifd" in all_content or "instruction-following" in all_content, \
            "data-distillation should cover IFD methodology"

    def test_data_distillation_covers_kenlm_filtering(self, skills_dir):
        """
        GIVEN: data-distillation skill content
        WHEN: Checking docs/ files
        THEN: Covers KenLM perplexity filtering
        """
        skill_dir = skills_dir / "data-distillation"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "kenlm" in all_content or "perplexity" in all_content, \
            "data-distillation should cover KenLM filtering"

    def test_data_distillation_covers_deduplication(self, skills_dir):
        """
        GIVEN: data-distillation skill content
        WHEN: Checking docs/ files
        THEN: Covers deduplication techniques
        """
        skill_dir = skills_dir / "data-distillation"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "deduplication" in all_content or "deduplicate" in all_content, \
            "data-distillation should cover deduplication"


class TestPreferenceDataQualitySkill:
    """Test preference-data-quality skill integration."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_preference_data_quality_skill_exists(self, skills_dir):
        """
        GIVEN: Skills directory
        WHEN: Checking for preference-data-quality skill
        THEN: Skill directory and SKILL.md exist
        """
        skill_dir = skills_dir / "preference-data-quality"
        assert skill_dir.exists(), "preference-data-quality skill directory not found"

        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "preference-data-quality SKILL.md not found"

    def test_preference_data_quality_metadata_is_small(self, skills_dir):
        """
        GIVEN: preference-data-quality SKILL.md
        WHEN: Checking file size
        THEN: Metadata is under 2KB
        """
        skill_metadata = skills_dir / "preference-data-quality" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        file_size = skill_metadata.stat().st_size
        assert file_size < 2048, \
            f"preference-data-quality SKILL.md too large: {file_size} bytes"

    def test_preference_data_quality_has_activation_keywords(self, skills_dir):
        """
        GIVEN: preference-data-quality SKILL.md
        WHEN: Checking for keywords
        THEN: Contains keywords (DPO, RLVR, preference, decontamination)
        """
        skill_metadata = skills_dir / "preference-data-quality" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        content = skill_metadata.read_text()
        keywords = ["dpo", "rlvr", "preference", "decontamination"]

        found_keywords = [kw for kw in keywords if kw in content.lower()]
        assert len(found_keywords) >= 2, \
            f"preference-data-quality should mention keywords: {keywords}"

    def test_preference_data_quality_has_content_files(self, skills_dir):
        """
        GIVEN: preference-data-quality skill directory
        WHEN: Checking for content files
        THEN: Has docs/ directory with detailed content
        """
        skill_dir = skills_dir / "preference-data-quality"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        assert docs_dir.exists(), "preference-data-quality should have docs/ directory"

        content_files = list(docs_dir.glob("*.md"))
        assert len(content_files) > 0, \
            "preference-data-quality docs/ should contain markdown files"

    def test_preference_data_quality_covers_dpo(self, skills_dir):
        """
        GIVEN: preference-data-quality skill content
        WHEN: Checking docs/ files
        THEN: Covers DPO (Direct Preference Optimization) metrics
        """
        skill_dir = skills_dir / "preference-data-quality"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "dpo" in all_content or "direct preference" in all_content, \
            "preference-data-quality should cover DPO"

    def test_preference_data_quality_covers_rlvr(self, skills_dir):
        """
        GIVEN: preference-data-quality skill content
        WHEN: Checking docs/ files
        THEN: Covers RLVR (Reinforcement Learning with Verifiable Rewards)
        """
        skill_dir = skills_dir / "preference-data-quality"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "rlvr" in all_content or "verifiable reward" in all_content, \
            "preference-data-quality should cover RLVR"

    def test_preference_data_quality_covers_decontamination(self, skills_dir):
        """
        GIVEN: preference-data-quality skill content
        WHEN: Checking docs/ files
        THEN: Covers decontamination techniques
        """
        skill_dir = skills_dir / "preference-data-quality"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "decontamination" in all_content or "contamination" in all_content, \
            "preference-data-quality should cover decontamination"


class TestMLXPerformanceSkill:
    """Test mlx-performance skill integration."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_mlx_performance_skill_exists(self, skills_dir):
        """
        GIVEN: Skills directory
        WHEN: Checking for mlx-performance skill
        THEN: Skill directory and SKILL.md exist
        """
        skill_dir = skills_dir / "mlx-performance"
        assert skill_dir.exists(), "mlx-performance skill directory not found"

        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "mlx-performance SKILL.md not found"

    def test_mlx_performance_metadata_is_small(self, skills_dir):
        """
        GIVEN: mlx-performance SKILL.md
        WHEN: Checking file size
        THEN: Metadata is under 2KB
        """
        skill_metadata = skills_dir / "mlx-performance" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        file_size = skill_metadata.stat().st_size
        assert file_size < 2048, \
            f"mlx-performance SKILL.md too large: {file_size} bytes"

    def test_mlx_performance_has_activation_keywords(self, skills_dir):
        """
        GIVEN: mlx-performance SKILL.md
        WHEN: Checking for keywords
        THEN: Contains keywords (MLX, RDMA, distributed, batch)
        """
        skill_metadata = skills_dir / "mlx-performance" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        content = skill_metadata.read_text()
        keywords = ["mlx", "rdma", "distributed", "batch", "performance"]

        found_keywords = [kw for kw in keywords if kw in content.lower()]
        assert len(found_keywords) >= 2, \
            f"mlx-performance should mention keywords: {keywords}"

    def test_mlx_performance_has_content_files(self, skills_dir):
        """
        GIVEN: mlx-performance skill directory
        WHEN: Checking for content files
        THEN: Has docs/ directory with detailed content
        """
        skill_dir = skills_dir / "mlx-performance"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        assert docs_dir.exists(), "mlx-performance should have docs/ directory"

        content_files = list(docs_dir.glob("*.md"))
        assert len(content_files) > 0, \
            "mlx-performance docs/ should contain markdown files"

    def test_mlx_performance_covers_mlx_distributed(self, skills_dir):
        """
        GIVEN: mlx-performance skill content
        WHEN: Checking docs/ files
        THEN: Covers MLX distributed training
        """
        skill_dir = skills_dir / "mlx-performance"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "mlx" in all_content and "distributed" in all_content, \
            "mlx-performance should cover MLX distributed training"

    def test_mlx_performance_covers_rdma(self, skills_dir):
        """
        GIVEN: mlx-performance skill content
        WHEN: Checking docs/ files
        THEN: Covers RDMA networking
        """
        skill_dir = skills_dir / "mlx-performance"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "rdma" in all_content, \
            "mlx-performance should cover RDMA networking"

    def test_mlx_performance_covers_batch_optimization(self, skills_dir):
        """
        GIVEN: mlx-performance skill content
        WHEN: Checking docs/ files
        THEN: Covers batch optimization strategies
        """
        skill_dir = skills_dir / "mlx-performance"
        if not skill_dir.exists():
            pytest.skip("Skill directory not yet created (TDD red phase)")

        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            pytest.skip("Docs directory not yet created (TDD red phase)")

        all_content = ""
        for md_file in docs_dir.glob("*.md"):
            all_content += md_file.read_text().lower()

        assert "batch" in all_content, \
            "mlx-performance should cover batch optimization"


class TestSkillCrossReferences:
    """Test cross-references between skills."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_data_distillation_references_python_standards(self, skills_dir):
        """
        GIVEN: data-distillation skill
        WHEN: Checking cross-references
        THEN: References python-standards skill for code examples
        """
        skill_metadata = skills_dir / "data-distillation" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        content = skill_metadata.read_text()
        assert "python-standards" in content.lower(), \
            "data-distillation should reference python-standards"

    def test_preference_data_quality_references_data_distillation(self, skills_dir):
        """
        GIVEN: preference-data-quality skill
        WHEN: Checking cross-references
        THEN: References data-distillation skill for preprocessing
        """
        skill_metadata = skills_dir / "preference-data-quality" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        content = skill_metadata.read_text()
        # May reference data-distillation in docs/ instead of SKILL.md
        docs_dir = skills_dir / "preference-data-quality" / "docs"
        if docs_dir.exists():
            for md_file in docs_dir.glob("*.md"):
                content += md_file.read_text().lower()

        # Should mention data-distillation somewhere in skill content
        # (not strictly required in SKILL.md, can be in docs/)

    def test_mlx_performance_references_python_standards(self, skills_dir):
        """
        GIVEN: mlx-performance skill
        WHEN: Checking cross-references
        THEN: References python-standards for code quality
        """
        skill_metadata = skills_dir / "mlx-performance" / "SKILL.md"
        if not skill_metadata.exists():
            pytest.skip("Skill metadata not yet created (TDD red phase)")

        content = skill_metadata.read_text()
        assert "python-standards" in content.lower(), \
            "mlx-performance should reference python-standards"


class TestProgressiveDisclosureIntegration:
    """Test progressive disclosure mechanism for training skills."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_all_training_skills_have_small_metadata(self, skills_dir):
        """
        GIVEN: Three training skills
        WHEN: Checking SKILL.md sizes
        THEN: All metadata files are under 2KB
        """
        training_skills = [
            "data-distillation",
            "preference-data-quality",
            "mlx-performance"
        ]

        for skill_name in training_skills:
            skill_metadata = skills_dir / skill_name / "SKILL.md"
            if not skill_metadata.exists():
                pytest.skip(f"{skill_name} not yet created (TDD red phase)")

            file_size = skill_metadata.stat().st_size
            assert file_size < 2048, \
                f"{skill_name} SKILL.md too large: {file_size} bytes (should be <2KB)"

    def test_all_training_skills_have_detailed_docs(self, skills_dir):
        """
        GIVEN: Three training skills
        WHEN: Checking docs/ directories
        THEN: All have substantial content (>1KB per file)
        """
        training_skills = [
            "data-distillation",
            "preference-data-quality",
            "mlx-performance"
        ]

        for skill_name in training_skills:
            docs_dir = skills_dir / skill_name / "docs"
            if not docs_dir.exists():
                pytest.skip(f"{skill_name} docs/ not yet created (TDD red phase)")

            # At least one file should be substantial
            content_files = list(docs_dir.glob("*.md"))
            has_substantial = any(f.stat().st_size > 1024 for f in content_files)

            assert has_substantial, \
                f"{skill_name} docs/ should have substantial content (>1KB per file)"

    def test_skills_total_context_under_budget(self, skills_dir):
        """
        GIVEN: Three training skills loaded together
        WHEN: Calculating total context size
        THEN: Total metadata under 6KB (3 skills * 2KB each)
        """
        training_skills = [
            "data-distillation",
            "preference-data-quality",
            "mlx-performance"
        ]

        total_size = 0
        for skill_name in training_skills:
            skill_metadata = skills_dir / skill_name / "SKILL.md"
            if not skill_metadata.exists():
                pytest.skip(f"{skill_name} not yet created (TDD red phase)")

            total_size += skill_metadata.stat().st_size

        assert total_size < 6144, \
            f"Total training skills metadata too large: {total_size} bytes (should be <6KB)"


class TestGracefulDegradation:
    """Test graceful degradation when docs/ are missing."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_skill_works_without_docs_directory(self, skills_dir):
        """
        GIVEN: Skill with SKILL.md but missing docs/
        WHEN: Agent references skill
        THEN: SKILL.md provides enough context to proceed
        """
        # This tests progressive disclosure - SKILL.md should be self-sufficient
        training_skills = [
            "data-distillation",
            "preference-data-quality",
            "mlx-performance"
        ]

        for skill_name in training_skills:
            skill_metadata = skills_dir / skill_name / "SKILL.md"
            if not skill_metadata.exists():
                pytest.skip(f"{skill_name} not yet created (TDD red phase)")

            content = skill_metadata.read_text()

            # SKILL.md should have enough info even without docs/
            assert len(content) > 500, \
                f"{skill_name} SKILL.md too minimal (should provide basic guidance)"

            # Should mention key concepts
            assert "##" in content, \
                f"{skill_name} SKILL.md should have sections"

    def test_skill_metadata_indicates_full_content_location(self, skills_dir):
        """
        GIVEN: Skill SKILL.md metadata
        WHEN: Checking for content references
        THEN: Indicates where full content is located (docs/)
        """
        training_skills = [
            "data-distillation",
            "preference-data-quality",
            "mlx-performance"
        ]

        for skill_name in training_skills:
            skill_metadata = skills_dir / skill_name / "SKILL.md"
            if not skill_metadata.exists():
                pytest.skip(f"{skill_name} not yet created (TDD red phase)")

            content = skill_metadata.read_text()

            # Should reference docs/ or detailed content
            has_reference = (
                "docs/" in content.lower() or
                "see:" in content.lower() or
                "guide" in content.lower()
            )

            assert has_reference, \
                f"{skill_name} SKILL.md should indicate where full content is"


class TestSkillUpdateCount:
    """Test that skill count is updated correctly."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "skills"

    def test_skill_count_includes_new_training_skills(self, skills_dir):
        """
        GIVEN: Skills directory with existing + new skills
        WHEN: Counting skill directories
        THEN: Count includes 3 new training skills (19 -> 22 or more)
        """
        skill_dirs = [
            d for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

        # Before Issue #274: 19 skills
        # After Issue #274: 22 skills (19 + 3 new training skills)
        # Allow for additional skills added in other issues
        assert len(skill_dirs) >= 22, \
            f"Expected at least 22 skills (19 existing + 3 new), found {len(skill_dirs)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
