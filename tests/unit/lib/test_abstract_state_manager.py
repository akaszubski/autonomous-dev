"""Tests for StateManager.__repr__ method.

TDD Red Phase: These tests should FAIL until __repr__ is implemented.
"""

import sys
from pathlib import Path

# Add lib to path for imports
lib_path = Path(__file__).resolve().parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

from abstract_state_manager import StateManager


class ConcreteManagerWithFile(StateManager):
    """Test subclass with state_file attribute."""

    def __init__(self, state_file):
        self.state_file = state_file

    def load_state(self):
        return {}

    def save_state(self, state):
        pass

    def cleanup_state(self):
        pass


class ConcreteManagerNoFile(StateManager):
    """Test subclass without state_file attribute."""

    def load_state(self):
        return {}

    def save_state(self, state):
        pass

    def cleanup_state(self):
        pass


class CustomNamedManager(StateManager):
    """Test subclass with a distinct name for polymorphic test."""

    def __init__(self, state_file=None):
        if state_file is not None:
            self.state_file = state_file

    def load_state(self):
        return {}

    def save_state(self, state):
        pass

    def cleanup_state(self):
        pass


class TestStateManagerRepr:
    """Tests for StateManager.__repr__."""

    def test_repr_with_path_state_file(self):
        """repr includes Path state_file value."""
        mgr = ConcreteManagerWithFile(Path("/tmp/state.json"))
        result = repr(mgr)
        assert "ConcreteManagerWithFile" in result
        assert "/tmp/state.json" in result

    def test_repr_with_string_state_file(self):
        """repr works when state_file is a string."""
        mgr = ConcreteManagerWithFile("/tmp/foo.json")
        result = repr(mgr)
        assert "ConcreteManagerWithFile" in result
        assert "/tmp/foo.json" in result

    def test_repr_with_none_state_file(self):
        """repr handles None state_file - returns ClassName() format."""
        mgr = ConcreteManagerWithFile(None)
        result = repr(mgr)
        assert "ConcreteManagerWithFile()" in result

    def test_repr_without_state_file_attr(self):
        """repr works when no state_file attribute - returns ClassName() format."""
        mgr = ConcreteManagerNoFile()
        result = repr(mgr)
        assert "ConcreteManagerNoFile()" in result

    def test_repr_polymorphic_class_name(self):
        """repr uses actual subclass name, not 'StateManager'."""
        mgr = CustomNamedManager(Path("/tmp/custom.json"))
        result = repr(mgr)
        assert "CustomNamedManager" in result
        assert "StateManager" not in result
        assert "/tmp/custom.json" in result
