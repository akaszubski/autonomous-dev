"""Unit tests for finding_target_classifier module."""

import pytest
import sys
from pathlib import Path

# Add lib to path for imports
lib_path = Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))

from finding_target_classifier import classify_finding_target


def test_framework_terms_classify_as_autonomous_dev():
    """Test case 1: Framework terms → 'autonomous-dev'."""
    title = "planner skipped acceptance-tests phase"
    description = "The pipeline_state shows coordinator bypassed plan-critic"
    
    result = classify_finding_target(title, description)
    assert result == "autonomous-dev"
    
    # Test with single framework term
    title2 = "Issue with /implement command"
    result2 = classify_finding_target(title2, "")
    assert result2 == "autonomous-dev"
    
    # Test with hook-related term
    title3 = "unified_pre_tool hook failed"
    result3 = classify_finding_target(title3, "")
    assert result3 == "autonomous-dev"


def test_consumer_terms_classify_as_consumer():
    """Test case 2: Consumer terms → 'consumer'."""
    title = "Gold market config drift in pricing module"
    description = "The pricing calculations are incorrect for gold futures"
    
    result = classify_finding_target(title, description)
    assert result == "consumer"
    
    # Test with no framework terms
    title2 = "Database connection timeout"
    description2 = "MySQL server is not responding"
    result2 = classify_finding_target(title2, description2)
    assert result2 == "consumer"


def test_mixed_terms_classify_as_both():
    """Test case 3: Mixed terms → 'both'."""
    title = "planner agent failed on gold market analysis"
    description = "The implementer couldn't handle pricing module changes"
    
    result = classify_finding_target(title, description)
    assert result == "both"
    
    # Another mixed example
    title2 = "/implement failed due to config drift"
    description2 = "Market pricing calculations blocked the pipeline"
    result2 = classify_finding_target(title2, description2)
    assert result2 == "both"


def test_existing_target_repo_preserved():
    """Test case 4: Pass-through - existing target_repo value is respected."""
    title = "Some random issue"
    description = "With random content"
    
    # Test with pre-classified autonomous-dev
    result = classify_finding_target(title, description, existing_target="autonomous-dev")
    assert result == "autonomous-dev"
    
    # Test with pre-classified consumer
    result2 = classify_finding_target(title, description, existing_target="consumer")
    assert result2 == "consumer"
    
    # Test with pre-classified both
    result3 = classify_finding_target(title, description, existing_target="both")
    assert result3 == "both"
    
    # Test that invalid existing_target is ignored and classification proceeds
    result4 = classify_finding_target("planner failed", "", existing_target="invalid")
    assert result4 == "autonomous-dev"


def test_no_terms_defaults_to_consumer():
    """Test case 5: Fallback - no terms and no target_repo → 'consumer'."""
    title = "Generic issue with no specific terms"
    description = "Some generic description without any keywords"
    
    result = classify_finding_target(title, description)
    assert result == "consumer"
    
    # Empty strings
    result2 = classify_finding_target("", "")
    assert result2 == "consumer"
    
    # Only whitespace
    result3 = classify_finding_target("   ", "   ")
    assert result3 == "consumer"