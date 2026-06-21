"""Tests for file path extraction in session_activity_logger hook (Issue #1280)."""

import sys
import importlib.util
from pathlib import Path

# Load the hook module directly (it's a script, not a regular package)
hook_path = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks" / "session_activity_logger.py"
spec = importlib.util.spec_from_file_location("session_activity_logger", hook_path)
sal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sal)


def test_extract_file_paths_basic():
    """Test extraction of file paths with various extensions."""
    text = """
    We edited foo.py and updated bar.md for documentation.
    The config.json needs review, and settings.yaml is correct.
    Also check deploy.sh and alternative.yml files.
    """
    paths = sal._extract_file_paths(text)
    assert len(paths) == 6
    assert "foo.py" in paths
    assert "bar.md" in paths
    assert "config.json" in paths
    assert "settings.yaml" in paths
    assert "deploy.sh" in paths
    assert "alternative.yml" in paths


def test_extract_file_paths_dedup():
    """Test that duplicate paths appear only once."""
    text = "Modified main.py, then updated main.py again, and main.py once more"
    paths = sal._extract_file_paths(text)
    assert paths == ["main.py"]
    assert len(paths) == 1


def test_extract_file_paths_empty():
    """Test that empty/invalid input returns empty list."""
    assert sal._extract_file_paths("") == []
    assert sal._extract_file_paths(None) == []
    assert sal._extract_file_paths(123) == []
    assert sal._extract_file_paths([]) == []


def test_extract_file_paths_no_matches():
    """Test that text with no file paths returns empty list."""
    text = "This is a regular sentence with no file references."
    paths = sal._extract_file_paths(text)
    assert paths == []
    
    # Extensions we don't track
    text2 = "Has image.png and video.mp4 and document.txt"
    paths2 = sal._extract_file_paths(text2)
    assert paths2 == []


def test_summarize_input_security_auditor_gets_file_fields():
    """Test that security-auditor subagent gets file extraction fields."""
    tool_input = {
        "subagent_type": "security-auditor",
        "prompt": "Review the changes in auth.py and permissions.md",
        "description": "Security audit"
    }
    
    summary = sal._summarize_input("Task", tool_input)
    
    assert "prompt_file_count" in summary
    assert summary["prompt_file_count"] == 2
    assert "prompt_file_paths" in summary
    assert summary["prompt_file_paths"] == ["auth.py", "permissions.md"]
    assert summary["subagent_type"] == "security-auditor"


def test_summarize_input_doc_master_gets_file_fields():
    """Test that doc-master subagent gets file extraction fields."""
    tool_input = {
        "subagent_type": "doc-master",
        "prompt": "Document the API changes in api.py, update README.md, and review config.json",
        "description": "Documentation update"
    }
    
    summary = sal._summarize_input("Agent", tool_input)
    
    assert "prompt_file_count" in summary
    assert summary["prompt_file_count"] == 3
    assert "prompt_file_paths" in summary
    assert set(summary["prompt_file_paths"]) == {"api.py", "README.md", "config.json"}
    assert summary["subagent_type"] == "doc-master"


def test_summarize_input_other_agent_no_file_fields():
    """Test that other agent types don't get file extraction fields."""
    tool_input = {
        "subagent_type": "planner",
        "prompt": "Create a plan for implementing feature.py and updating docs.md",
        "description": "Planning task"
    }
    
    summary = sal._summarize_input("Task", tool_input)
    
    # These fields should NOT be present for non-targeted agents
    assert "prompt_file_count" not in summary
    assert "prompt_file_paths" not in summary
    assert summary["subagent_type"] == "planner"
    # But basic fields should still be there
    assert "prompt_word_count" in summary