"""Tests for feature_flags library (opt-out and opt-in semantics).

The feature_flags module exposes two functions with INVERSE default behavior:

- ``is_feature_enabled``: opt-OUT semantics. Missing file/key/error -> True.
  Used for features that should be enabled-by-default in fresh repos
  (conflict_resolver, auto_git_workflow).

- ``is_feature_explicitly_enabled``: opt-IN semantics. Returns True ONLY if
  the file exists AND the key is present AND ``enabled=true`` explicitly.
  Used for features that MUST be off-by-default in fresh repos (semantic_gate).

Remediation context: spec-validator FAILURE on Issue Phase-1 semantic gate
required adding opt-in semantics without changing existing opt-out callers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Bridge sys.path: lib.
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import feature_flags  # noqa: E402
from feature_flags import (  # noqa: E402
    is_feature_enabled,
    is_feature_explicitly_enabled,
)


# =============================================================================
# is_feature_explicitly_enabled — opt-IN semantics (default OFF)
# =============================================================================


def test_explicitly_enabled_returns_false_when_config_file_missing(tmp_path):
    """No feature_flags.json file anywhere -> False (default OFF)."""
    nonexistent = tmp_path / "does_not_exist" / "feature_flags.json"
    assert not nonexistent.exists()

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=nonexistent
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_false_when_path_resolver_returns_none(tmp_path):
    """When _get_feature_flags_path returns None (no project root) -> False."""
    with patch.object(feature_flags, "_get_feature_flags_path", return_value=None):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_false_when_feature_key_absent(tmp_path):
    """File exists but lacks the feature key -> False (default OFF)."""
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(
        json.dumps({"conflict_resolver": {"enabled": True}})
    )

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_false_when_enabled_is_false(tmp_path):
    """Feature present with enabled=false -> False (explicit OFF)."""
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(
        json.dumps({"semantic_gate": {"enabled": False}})
    )

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_true_when_enabled_is_true(tmp_path):
    """Feature present with enabled=true -> True (explicit ON)."""
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(
        json.dumps({"semantic_gate": {"enabled": True}})
    )

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is True


def test_explicitly_enabled_returns_false_for_malformed_feature_config(tmp_path):
    """Feature value not a dict (e.g. bare True) -> False (fail-safe OFF).

    Contrast: ``is_feature_enabled`` returns True here (graceful degradation
    to opt-out default). Explicit variant MUST refuse anything malformed.
    """
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(json.dumps({"semantic_gate": True}))

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_false_when_enabled_key_missing(tmp_path):
    """Feature key present but lacks ``enabled`` field -> False.

    Contrast: ``is_feature_enabled`` returns True (uses ``.get("enabled",
    True)`` opt-out default). Explicit variant MUST require the field.
    """
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(
        json.dumps({"semantic_gate": {"confidence_threshold": 0.8}})
    )

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_false_for_truthy_non_boolean(tmp_path):
    """``enabled: 1`` is truthy but NOT identical to True -> False.

    The check uses ``enabled is True`` (identity), so only the JSON literal
    ``true`` qualifies. This prevents accidental enablement via stringly-typed
    or coerced values in user-edited config.
    """
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(
        json.dumps({"semantic_gate": {"enabled": 1}})
    )

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


def test_explicitly_enabled_returns_false_when_config_invalid_json(tmp_path):
    """Malformed JSON -> False (fail-safe OFF). _load_feature_flags returns
    empty dict on JSONDecodeError; absent key then yields False."""
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text("{not valid json")

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_explicitly_enabled("semantic_gate") is False


# =============================================================================
# Non-regression: is_feature_enabled (opt-OUT) UNCHANGED
# =============================================================================


def test_enabled_optout_still_returns_true_when_file_missing(tmp_path):
    """The legacy opt-out path MUST continue defaulting to True when the
    config file is absent. 40+ callers (conflict_resolver, auto_git_workflow,
    etc.) depend on this behavior.
    """
    nonexistent = tmp_path / "does_not_exist" / "feature_flags.json"

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=nonexistent
    ):
        assert is_feature_enabled("conflict_resolver") is True
        assert is_feature_enabled("any_unknown_feature") is True


def test_enabled_optout_still_returns_true_when_key_missing(tmp_path):
    """Opt-out path: missing feature key in present file -> still True."""
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(json.dumps({"other_feature": {"enabled": False}}))

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_enabled("conflict_resolver") is True


def test_enabled_optout_returns_false_only_when_explicitly_disabled(tmp_path):
    """Opt-out path returns False only when key present with enabled=false."""
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(
        json.dumps({"conflict_resolver": {"enabled": False}})
    )

    with patch.object(
        feature_flags, "_get_feature_flags_path", return_value=flags_path
    ):
        assert is_feature_enabled("conflict_resolver") is False
