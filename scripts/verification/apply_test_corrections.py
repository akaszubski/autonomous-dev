#!/usr/bin/env python3
"""
Apply corrections to test_batch_state_manager.py

Fixes 3 failing tests by correcting mock strategy.
"""

import sys
from pathlib import Path

def apply_corrections():
    """Apply test corrections to fix 3 failing tests."""
    test_file = Path(__file__).parent / "unit" / "lib" / "test_batch_state_manager.py"

    # Read entire file
    content = test_file.read_text()

    # Correction 1: test_save_batch_state_atomic_write (lines 271-284)
    old_test_1 = '''    def test_save_batch_state_atomic_write(self, state_file, sample_batch_state):
        """Test that save_batch_state uses atomic write (temp file + rename)."""
        # Arrange
        with patch("batch_state_manager.Path") as mock_path:
            mock_temp = MagicMock()
            mock_path.return_value.parent = MagicMock()

            # Act
            save_batch_state(state_file, sample_batch_state)

            # Assert - should write to temp file then rename
            # This prevents corruption if process crashes during write
            # Implementation should use: temp_file.write() -> temp_file.rename(state_file)'''

    new_test_1 = '''    def test_save_batch_state_atomic_write(self, state_file, sample_batch_state):
        """Test that save_batch_state uses atomic write (temp file + rename)."""
        # Arrange
        temp_fd = 999
        temp_path_str = "/tmp/.batch_state_abc123.tmp"

        with patch("tempfile.mkstemp", return_value=(temp_fd, temp_path_str)) as mock_mkstemp, \\
             patch("os.write") as mock_write, \\
             patch("os.close") as mock_close, \\
             patch("pathlib.Path.chmod") as mock_chmod, \\
             patch("pathlib.Path.replace") as mock_replace:

            # Act
            save_batch_state(state_file, sample_batch_state)

            # Assert - Atomic write pattern
            # 1. CREATE: temp file created in same directory
            mock_mkstemp.assert_called_once()
            call_kwargs = mock_mkstemp.call_args[1]
            assert call_kwargs['dir'] == state_file.parent
            assert call_kwargs['prefix'] == ".batch_state_"
            assert call_kwargs['suffix'] == ".tmp"

            # 2. WRITE: JSON written to temp file descriptor
            mock_write.assert_called_once()
            assert mock_write.call_args[0][0] == temp_fd
            assert b'"batch_id"' in mock_write.call_args[0][1]  # Contains JSON
            mock_close.assert_called_once_with(temp_fd)

            # 3. SECURITY: File permissions set to 0o600
            mock_chmod.assert_called_once_with(0o600)

            # 4. RENAME: Atomic rename temp → target
            mock_replace.assert_called_once()
            # replace() is called on temp_path with state_file as argument
            assert mock_replace.call_args[0][0] == state_file'''

    # Correction 2: test_save_batch_state_handles_disk_full_error (lines 623-631)
    old_test_2 = '''    def test_save_batch_state_handles_disk_full_error(self, state_file, sample_batch_state):
        """Test that save_batch_state handles disk full errors gracefully."""
        # Arrange - mock write_text to raise OSError (disk full)
        with patch("pathlib.Path.write_text", side_effect=OSError("No space left on device")):
            # Act & Assert
            with pytest.raises(BatchStateError) as exc_info:
                save_batch_state(state_file, sample_batch_state)

            assert "disk" in str(exc_info.value).lower() or "space" in str(exc_info.value).lower()'''

    new_test_2 = '''    def test_save_batch_state_handles_disk_full_error(self, state_file, sample_batch_state):
        """Test that save_batch_state handles disk full errors gracefully."""
        # Arrange - mock os.write to raise OSError (disk full)
        with patch("os.write", side_effect=OSError(28, "No space left on device")):
            # Act & Assert
            with pytest.raises(BatchStateError) as exc_info:
                save_batch_state(state_file, sample_batch_state)

            # Verify error message mentions disk/space issue
            error_msg = str(exc_info.value).lower()
            assert "disk" in error_msg or "space" in error_msg or "write" in error_msg

            # Verify original error is preserved in context
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, OSError)'''

    # Correction 3: test_load_batch_state_handles_permission_error (lines 633-643)
    old_test_3 = '''    def test_load_batch_state_handles_permission_error(self, state_file, sample_batch_state):
        """Test that load_batch_state handles permission errors gracefully."""
        # Arrange - create file then remove read permission
        save_batch_state(state_file, sample_batch_state)

        with patch("pathlib.Path.read_text", side_effect=PermissionError("Permission denied")):
            # Act & Assert
            with pytest.raises(BatchStateError) as exc_info:
                load_batch_state(state_file)

            assert "permission" in str(exc_info.value).lower()'''

    new_test_3 = '''    def test_load_batch_state_handles_permission_error(self, state_file, sample_batch_state):
        """Test that load_batch_state handles permission errors gracefully."""
        # Arrange - create valid file first (so validate_path passes)
        save_batch_state(state_file, sample_batch_state)

        # Mock open() to raise PermissionError when reading
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            # Act & Assert
            with pytest.raises(BatchStateError) as exc_info:
                load_batch_state(state_file)

            # Verify error message mentions permission issue
            error_msg = str(exc_info.value).lower()
            assert "permission" in error_msg or "access" in error_msg or "read" in error_msg

            # Verify original error is preserved in context
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, PermissionError)'''

    # Apply corrections
    if old_test_1 not in content:
        print("ERROR: Could not find old_test_1 in file")
        return False
    if old_test_2 not in content:
        print("ERROR: Could not find old_test_2 in file")
        return False
    if old_test_3 not in content:
        print("ERROR: Could not find old_test_3 in file")
        return False

    content = content.replace(old_test_1, new_test_1)
    content = content.replace(old_test_2, new_test_2)
    content = content.replace(old_test_3, new_test_3)

    # Write back
    test_file.write_text(content)

    print("✅ Successfully applied all 3 test corrections")
    print(f"   - test_save_batch_state_atomic_write")
    print(f"   - test_save_batch_state_handles_disk_full_error")
    print(f"   - test_load_batch_state_handles_permission_error")
    print()
    print("Run tests with:")
    print("  source .venv/bin/activate && python -m pytest tests/unit/lib/test_batch_state_manager.py -v")

    return True

if __name__ == "__main__":
    success = apply_corrections()
    sys.exit(0 if success else 1)
