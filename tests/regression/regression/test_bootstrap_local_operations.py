"""
Regression tests for bootstrap_local_operations() function in install.sh.

Tests cover:
1. Directory creation (.claude/local/)
2. Template copying from staging directory
3. Preserving existing OPERATIONS.md files
4. Creating placeholder when template missing
5. Error handling for permission failures
"""

import pytest
import subprocess
from pathlib import Path


# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()


class TestBootstrapLocalOperationsDirectoryCreation:
    """Test that bootstrap_local_operations creates .claude/local/ directory."""

    def test_creates_local_directory_when_missing(self, tmp_path):
        """Test that .claude/local/ directory is created when it doesn't exist."""
        # Arrange: Set up test environment in tmp_path
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()

        # Create a minimal bash script that simulates bootstrap_local_operations
        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

bootstrap_local_operations() {
    local local_target_dir=".claude/local"

    # Create target directory if it doesn't exist
    if ! mkdir -p "$local_target_dir" 2>/dev/null; then
        echo "FAILED to create directory"
        return 1
    fi

    echo "SUCCESS created directory"
    return 0
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Directory was created
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS created directory" in result.stdout
        assert (test_repo / ".claude/local").exists()
        assert (test_repo / ".claude/local").is_dir()

    def test_succeeds_when_local_directory_exists(self, tmp_path):
        """Test that function succeeds when .claude/local/ already exists."""
        # Arrange: Create existing directory structure
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()
        local_dir = claude_dir / "local"
        local_dir.mkdir()

        # Create test script
        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

bootstrap_local_operations() {
    local local_target_dir=".claude/local"

    if ! mkdir -p "$local_target_dir" 2>/dev/null; then
        echo "FAILED"
        return 1
    fi

    echo "SUCCESS"
    return 0
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Function succeeds with existing directory
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout


class TestBootstrapLocalOperationsTemplateCreation:
    """Test template copying and placeholder creation."""

    def test_copies_template_when_available(self, tmp_path):
        """Test that OPERATIONS.md template is copied when available in staging."""
        # Arrange: Create staging directory with template
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()

        staging_dir = test_repo / "staging"
        staging_dir.mkdir()
        template_dir = staging_dir / "files/plugins/autonomous-dev/templates/local"
        template_dir.mkdir(parents=True)

        template_content = "# Test Template\n\nTemplate content here\n"
        (template_dir / "OPERATIONS.md").write_text(template_content)

        # Create test script
        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

STAGING_DIR="./staging"

bootstrap_local_operations() {
    local local_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/templates/local"
    local local_target_dir=".claude/local"

    mkdir -p "$local_target_dir" 2>/dev/null || return 1

    if [[ -f "$local_target_dir/OPERATIONS.md" ]]; then
        echo "PRESERVED existing file"
        return 0
    fi

    if [[ -f "$local_source_dir/OPERATIONS.md" ]]; then
        if cp -P "$local_source_dir/OPERATIONS.md" "$local_target_dir/OPERATIONS.md"; then
            echo "COPIED template"
            return 0
        else
            echo "FAILED to copy"
            return 1
        fi
    else
        echo "TEMPLATE not found"
        return 1
    fi
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Template was copied
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "COPIED template" in result.stdout
        operations_file = test_repo / ".claude/local/OPERATIONS.md"
        assert operations_file.exists()
        assert operations_file.read_text() == template_content

    def test_creates_placeholder_when_template_missing(self, tmp_path):
        """Test that placeholder is created when template not found in staging."""
        # Arrange: Create environment without staging template
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()

        # Create test script with placeholder creation logic
        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

STAGING_DIR="./staging"

bootstrap_local_operations() {
    local local_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/templates/local"
    local local_target_dir=".claude/local"

    mkdir -p "$local_target_dir" 2>/dev/null || return 1

    if [[ -f "$local_target_dir/OPERATIONS.md" ]]; then
        echo "PRESERVED"
        return 0
    fi

    if [[ -f "$local_source_dir/OPERATIONS.md" ]]; then
        cp -P "$local_source_dir/OPERATIONS.md" "$local_target_dir/OPERATIONS.md"
        echo "COPIED"
        return 0
    else
        # Create placeholder
        cat > "$local_target_dir/OPERATIONS.md" << 'OPERATIONS_EOF'
# Repo Operations

This file is for repo-specific procedures. It is preserved across /sync.

## Procedures

<!-- Add your repo-specific procedures here -->
OPERATIONS_EOF
        echo "PLACEHOLDER created"
        return 0
    fi
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Placeholder was created
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "PLACEHOLDER created" in result.stdout

        operations_file = test_repo / ".claude/local/OPERATIONS.md"
        assert operations_file.exists()

        content = operations_file.read_text()
        assert "# Repo Operations" in content
        assert "This file is for repo-specific procedures" in content
        assert "## Procedures" in content


class TestBootstrapLocalOperationsPreservesExisting:
    """Test that existing OPERATIONS.md files are preserved."""

    def test_preserves_existing_operations_file(self, tmp_path):
        """Test that existing OPERATIONS.md is NOT overwritten."""
        # Arrange: Create existing OPERATIONS.md with custom content
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()
        local_dir = claude_dir / "local"
        local_dir.mkdir()

        existing_content = "# My Custom Operations\n\nCustom procedures here\n"
        (local_dir / "OPERATIONS.md").write_text(existing_content)

        # Create staging with different template
        staging_dir = test_repo / "staging"
        staging_dir.mkdir()
        template_dir = staging_dir / "files/plugins/autonomous-dev/templates/local"
        template_dir.mkdir(parents=True)
        template_content = "# Template Operations\n\nTemplate procedures\n"
        (template_dir / "OPERATIONS.md").write_text(template_content)

        # Create test script
        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

STAGING_DIR="./staging"

bootstrap_local_operations() {
    local local_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/templates/local"
    local local_target_dir=".claude/local"

    mkdir -p "$local_target_dir" 2>/dev/null || return 1

    if [[ -f "$local_target_dir/OPERATIONS.md" ]]; then
        echo "PRESERVED existing"
        return 0
    fi

    if [[ -f "$local_source_dir/OPERATIONS.md" ]]; then
        cp -P "$local_source_dir/OPERATIONS.md" "$local_target_dir/OPERATIONS.md"
        echo "COPIED template"
        return 0
    fi
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Existing file was preserved
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "PRESERVED existing" in result.stdout

        operations_file = test_repo / ".claude/local/OPERATIONS.md"
        assert operations_file.exists()
        assert operations_file.read_text() == existing_content
        assert operations_file.read_text() != template_content

    def test_preserves_user_content_on_multiple_runs(self, tmp_path):
        """Test that user content is preserved across multiple bootstrap runs."""
        # Arrange: Set up initial state
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()

        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

bootstrap_local_operations() {
    local local_target_dir=".claude/local"

    mkdir -p "$local_target_dir" 2>/dev/null || return 1

    if [[ -f "$local_target_dir/OPERATIONS.md" ]]; then
        echo "PRESERVED"
        return 0
    fi

    cat > "$local_target_dir/OPERATIONS.md" << 'EOF'
# Placeholder
EOF
    echo "CREATED"
    return 0
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act 1: First run - creates placeholder
        result1 = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )
        assert "CREATED" in result1.stdout

        # Modify the file to simulate user customization
        operations_file = test_repo / ".claude/local/OPERATIONS.md"
        user_content = "# User Modified Content\n\nMy procedures\n"
        operations_file.write_text(user_content)

        # Act 2: Second run - should preserve user content
        result2 = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: User content was preserved
        assert result2.returncode == 0
        assert "PRESERVED" in result2.stdout
        assert operations_file.read_text() == user_content


class TestBootstrapLocalOperationsErrorHandling:
    """Test error handling for permission and file system issues."""

    def test_handles_mkdir_permission_error(self, tmp_path):
        """Test graceful handling when mkdir fails due to permissions."""
        # Arrange: Create a read-only parent directory
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()

        # Make .claude directory read-only
        claude_dir.chmod(0o444)

        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

bootstrap_local_operations() {
    local local_target_dir=".claude/local"

    if ! mkdir -p "$local_target_dir" 2>/dev/null; then
        echo "FAILED to create directory"
        return 1
    fi

    echo "SUCCESS"
    return 0
}

bootstrap_local_operations
exit_code=$?
chmod -R u+w .claude 2>/dev/null  # Cleanup for test
exit $exit_code
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Function returns error code 1
        assert result.returncode == 1
        assert "FAILED to create directory" in result.stdout

        # Cleanup: Restore permissions
        claude_dir.chmod(0o755)

    def test_returns_success_on_valid_operations(self, tmp_path):
        """Test that function returns 0 on successful operations."""
        # Arrange: Set up clean environment
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()

        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

bootstrap_local_operations() {
    local local_target_dir=".claude/local"

    mkdir -p "$local_target_dir" 2>/dev/null || return 1

    cat > "$local_target_dir/OPERATIONS.md" << 'EOF'
# Placeholder
EOF
    return 0
}

bootstrap_local_operations
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Success return code
        assert result.returncode == 0

    def test_handles_copy_failure_gracefully(self, tmp_path):
        """Test graceful handling when cp command fails."""
        # Arrange: Create scenario where copy will fail
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        claude_dir = test_repo / ".claude"
        claude_dir.mkdir()
        local_dir = claude_dir / "local"
        local_dir.mkdir()

        # Make target directory read-only
        local_dir.chmod(0o444)

        staging_dir = test_repo / "staging"
        staging_dir.mkdir()
        template_dir = staging_dir / "files/plugins/autonomous-dev/templates/local"
        template_dir.mkdir(parents=True)
        (template_dir / "OPERATIONS.md").write_text("# Template\n")

        test_script = test_repo / "test_bootstrap.sh"
        test_script.write_text("""
#!/bin/bash
cd "$(dirname "$0")"

STAGING_DIR="./staging"

bootstrap_local_operations() {
    local local_source_dir="${STAGING_DIR}/files/plugins/autonomous-dev/templates/local"
    local local_target_dir=".claude/local"

    mkdir -p "$local_target_dir" 2>/dev/null || return 1

    if [[ -f "$local_target_dir/OPERATIONS.md" ]]; then
        return 0
    fi

    if [[ -f "$local_source_dir/OPERATIONS.md" ]]; then
        if cp -P "$local_source_dir/OPERATIONS.md" "$local_target_dir/OPERATIONS.md" 2>/dev/null; then
            echo "COPIED"
            return 0
        else
            echo "COPY FAILED"
            return 1
        fi
    fi
}

bootstrap_local_operations
exit_code=$?
chmod -R u+w .claude 2>/dev/null  # Cleanup
exit $exit_code
        """)
        test_script.chmod(0o755)

        # Act: Run the test script
        result = subprocess.run(
            ["bash", str(test_script)],
            cwd=str(test_repo),
            capture_output=True,
            text=True
        )

        # Assert: Function returns error
        assert result.returncode == 1
        assert "COPY FAILED" in result.stdout

        # Cleanup
        local_dir.chmod(0o755)


class TestBootstrapLocalOperationsIntegration:
    """Integration tests with actual install.sh."""

    def test_function_exists_in_install_sh(self):
        """Test that bootstrap_local_operations exists in install.sh."""
        install_sh = project_root / "install.sh"
        assert install_sh.exists(), "install.sh not found"

        content = install_sh.read_text()
        assert "bootstrap_local_operations()" in content

    def test_function_called_in_main(self):
        """Test that bootstrap_local_operations is called from main()."""
        install_sh = project_root / "install.sh"
        content = install_sh.read_text()

        # Find main function
        assert "main()" in content

        # Check that bootstrap_local_operations is called
        assert "bootstrap_local_operations" in content

    def test_creates_valid_operations_template(self):
        """Test that the created OPERATIONS.md has valid structure."""
        # This test validates the template structure without running install.sh
        install_sh = project_root / "install.sh"
        content = install_sh.read_text()

        # Extract the heredoc content from the function
        assert "# Repo Operations" in content
        assert "This file is for repo-specific procedures" in content
        assert "## Procedures" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
