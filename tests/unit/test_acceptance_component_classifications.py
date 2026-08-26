"""Acceptance tests for component classifications registry (Issue #566).

Validates the harness evolution tracking system that classifies enforcement
components as model-limitation or process-requirement.

GitHub Issue: #566
"""

import json
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

REGISTRY_PATH = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "config" / "component_classifications.json"
)
SCHEMA_PATH = (
    PROJECT_ROOT
    / "plugins"
    / "autonomous-dev"
    / "config"
    / "component_classifications.schema.json"
)
EVOLUTION_DOC = PROJECT_ROOT / "docs" / "HARNESS-EVOLUTION.md"
VALIDATION_SCRIPT = PROJECT_ROOT / "scripts" / "validate_component_classifications.py"


@pytest.mark.genai
class TestRegistryExists:
    """Core registry files must exist."""

    def test_registry_file_exists(self):
        """component_classifications.json must exist."""
        assert REGISTRY_PATH.exists(), f"Missing registry: {REGISTRY_PATH}"

    def test_schema_file_exists(self):
        """component_classifications.schema.json must exist."""
        assert SCHEMA_PATH.exists(), f"Missing schema: {SCHEMA_PATH}"

    def test_evolution_doc_exists(self):
        """HARNESS-EVOLUTION.md must exist."""
        assert EVOLUTION_DOC.exists(), f"Missing doc: {EVOLUTION_DOC}"

    def test_validation_script_exists(self):
        """validate_component_classifications.py must exist."""
        assert VALIDATION_SCRIPT.exists(), f"Missing script: {VALIDATION_SCRIPT}"


@pytest.mark.genai
class TestRegistryCompleteness:
    """Registry must cover all active enforcement components."""

    def test_registry_has_all_three_sections(self):
        """Registry must have hooks, hard_gates, and forbidden_lists."""
        data = json.loads(REGISTRY_PATH.read_text())
        classifications = data.get("classifications", {})
        assert "hooks" in classifications
        assert "hard_gates" in classifications
        assert "forbidden_lists" in classifications

    def test_registry_has_minimum_hook_entries(self):
        """Registry must classify at least 15 hooks."""
        data = json.loads(REGISTRY_PATH.read_text())
        hooks = data["classifications"]["hooks"]
        assert len(hooks) >= 15, (
            f"Registry has only {len(hooks)} hook entries; expected at least 15"
        )

    def test_registry_has_minimum_gate_entries(self):
        """Registry must classify at least 15 hard gates."""
        data = json.loads(REGISTRY_PATH.read_text())
        gates = data["classifications"]["hard_gates"]
        assert len(gates) >= 15, (
            f"Registry has only {len(gates)} hard gate entries; expected at least 15"
        )

    def test_registry_has_forbidden_list_entries(self):
        """Registry must classify at least 3 forbidden lists."""
        data = json.loads(REGISTRY_PATH.read_text())
        forbidden = data["classifications"]["forbidden_lists"]
        assert len(forbidden) >= 3, (
            f"Registry has only {len(forbidden)} forbidden list entries; expected at least 3"
        )


@pytest.mark.genai
class TestClassificationBalance:
    """Both classification types must be represented."""

    def test_has_model_limitation_entries(self):
        """At least some entries must be classified as model-limitation."""
        data = json.loads(REGISTRY_PATH.read_text())
        model_lim = 0
        for section in data["classifications"].values():
            for entry in section.values():
                if entry.get("classification") == "model-limitation":
                    model_lim += 1
        assert model_lim >= 5, (
            f"Only {model_lim} model-limitation entries; expected at least 5"
        )

    def test_has_process_requirement_entries(self):
        """At least some entries must be classified as process-requirement."""
        data = json.loads(REGISTRY_PATH.read_text())
        process_req = 0
        for section in data["classifications"].values():
            for entry in section.values():
                if entry.get("classification") == "process-requirement":
                    process_req += 1
        assert process_req >= 5, (
            f"Only {process_req} process-requirement entries; expected at least 5"
        )


@pytest.mark.genai
class TestEvolutionDocQuality:
    """HARNESS-EVOLUTION.md must document the review process."""

    def test_doc_has_covers_frontmatter(self):
        """Evolution doc should reference the registry in frontmatter."""
        content = EVOLUTION_DOC.read_text()
        assert "covers:" in content or "component_classifications" in content, (
            "HARNESS-EVOLUTION.md should reference component_classifications.json"
        )

    def test_doc_has_classification_explanation(self):
        """Doc must explain what model-limitation and process-requirement mean."""
        content = EVOLUTION_DOC.read_text()
        assert "model-limitation" in content, "Doc must explain model-limitation"
        assert "process-requirement" in content, "Doc must explain process-requirement"

    def test_doc_has_review_checklist(self):
        """Doc must include a model upgrade review checklist."""
        content = EVOLUTION_DOC.read_text().lower()
        assert "checklist" in content or "review" in content, (
            "Doc must include review guidance for model upgrades"
        )
