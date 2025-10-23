"""
Test Framework for autonomous-dev v2.0
Provides utilities for testing agent behavior, artifact validation, and workflow integrity.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Create mock pytest.fixture decorator
    class _MockPytest:
        @staticmethod
        def fixture(func):
            return func
    pytest = _MockPytest()


class MockArtifact:
    """Mock artifact for testing agents in isolation"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.data.setdefault('version', '2.0')
        self.data.setdefault('created_at', datetime.utcnow().isoformat())

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.data, indent=2)

    def write_to(self, path: Path):
        """Write artifact to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def from_file(cls, path: Path) -> 'MockArtifact':
        """Load artifact from file"""
        data = json.loads(path.read_text())
        return cls(data)


class MockProjectMd:
    """Mock PROJECT.md for testing alignment validation"""

    def __init__(
        self,
        goals: Optional[list] = None,
        scope_included: Optional[list] = None,
        scope_excluded: Optional[list] = None,
        constraints: Optional[list] = None
    ):
        self.goals = goals or ["Test goal"]
        self.scope_included = scope_included or ["Test feature"]
        self.scope_excluded = scope_excluded or []
        self.constraints = constraints or []

    def to_markdown(self) -> str:
        """Convert to PROJECT.md markdown format"""
        md = "# PROJECT.md\n\n"

        md += "## GOALS\n\n"
        for goal in self.goals:
            md += f"- {goal}\n"

        md += "\n## SCOPE\n\n"
        md += "### In Scope\n"
        for item in self.scope_included:
            md += f"- {item}\n"

        if self.scope_excluded:
            md += "\n### Out of Scope\n"
            for item in self.scope_excluded:
                md += f"- {item}\n"

        md += "\n## CONSTRAINTS\n\n"
        for constraint in self.constraints:
            md += f"- {constraint}\n"

        return md

    def write_to(self, path: Path):
        """Write PROJECT.md to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown())


class ArtifactValidator:
    """Validate artifacts against schemas"""

    REQUIRED_FIELDS = ['version', 'agent', 'workflow_id', 'status']

    @classmethod
    def validate(cls, artifact_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate artifact has required fields
        Returns: (is_valid, error_message)
        """
        for field in cls.REQUIRED_FIELDS:
            if field not in artifact_data:
                return False, f"Missing required field: {field}"

        # Validate version format
        if not artifact_data['version'].startswith('2.'):
            return False, f"Invalid version: {artifact_data['version']} (expected 2.x)"

        # Validate status values
        valid_statuses = ['pending', 'in_progress', 'completed', 'failed']
        if artifact_data['status'] not in valid_statuses:
            return False, f"Invalid status: {artifact_data['status']} (expected: {valid_statuses})"

        return True, None


# Pytest fixtures for common test scenarios

@pytest.fixture
def tmp_workflow_dir(tmp_path):
    """Create temporary workflow directory structure"""
    workflow_id = f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    workflow_dir = tmp_path / ".claude" / "artifacts" / workflow_id
    workflow_dir.mkdir(parents=True)
    return workflow_dir


@pytest.fixture
def mock_project_md(tmp_path):
    """Create mock PROJECT.md"""
    project_md = MockProjectMd(
        goals=["Improve developer productivity"],
        scope_included=["Automation", "Testing"],
        scope_excluded=["Manual processes"],
        constraints=["Must use Python 3.8+", "No external API dependencies"]
    )
    project_md_path = tmp_path / ".claude" / "PROJECT.md"
    project_md.write_to(project_md_path)
    return project_md_path


@pytest.fixture
def mock_manifest_artifact(tmp_workflow_dir):
    """Create mock workflow manifest artifact"""
    manifest = MockArtifact({
        'version': '2.0',
        'agent': 'orchestrator',
        'workflow_id': tmp_workflow_dir.name,
        'status': 'in_progress',
        'request': 'Implement user authentication',
        'alignment': {
            'validated': True,
            'matches_goals': ['Improve security'],
            'within_scope': True,
            'respects_constraints': True
        }
    })
    manifest_path = tmp_workflow_dir / "manifest.json"
    manifest.write_to(manifest_path)
    return manifest_path


# Example tests (to be expanded)

def test_artifact_validator_requires_fields():
    """Test artifact validator catches missing required fields"""
    artifact = {'version': '2.0'}  # Missing agent, workflow_id, status

    is_valid, error = ArtifactValidator.validate(artifact)

    assert not is_valid
    assert 'Missing required field' in error


def test_artifact_validator_accepts_valid():
    """Test artifact validator accepts valid artifacts"""
    artifact = {
        'version': '2.0',
        'agent': 'orchestrator',
        'workflow_id': 'test_123',
        'status': 'completed'
    }

    is_valid, error = ArtifactValidator.validate(artifact)

    assert is_valid
    assert error is None


def test_mock_project_md_format():
    """Test PROJECT.md mock generates correct format"""
    project_md = MockProjectMd(
        goals=["Goal 1", "Goal 2"],
        scope_included=["Feature A"],
        constraints=["Constraint 1"]
    )

    md_text = project_md.to_markdown()

    assert "# PROJECT.md" in md_text
    assert "## GOALS" in md_text
    assert "Goal 1" in md_text
    assert "## SCOPE" in md_text
    assert "Feature A" in md_text
    assert "## CONSTRAINTS" in md_text
    assert "Constraint 1" in md_text


if __name__ == '__main__':
    # Run basic tests
    pytest.main([__file__, '-v'])
