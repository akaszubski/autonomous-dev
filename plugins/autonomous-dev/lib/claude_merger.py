#!/usr/bin/env python3
"""
Claude Merger - Section-based CLAUDE.md merger for global configuration.

This module provides functionality to merge autonomous-dev template sections
with user's existing ~/.claude/CLAUDE.md content while preserving user customizations.

Section-Based Merge Strategy:
- Plugin sections are marked with <!-- autonomous-dev:start --> and <!-- autonomous-dev:end -->
- User content outside markers is NEVER touched
- Plugin sections can be updated on plugin upgrade
- Clear visual separation in the file

Security Features:
- Atomic writes with secure permissions (0o600)
- Timestamped backups before modifications
- Symlink rejection
- Path validation

Usage:
    from claude_merger import ClaudeMerger

    merger = ClaudeMerger(template_path)
    result = merger.merge_global_claude(output_path)

    if result.success:
        print(f"Merged: {result.output_path}")
        print(f"Sections added: {result.sections_added}")

Date: 2025-12-09
Issue: GitHub #101
Agent: implementer
"""

import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Section markers for autonomous-dev managed content
SECTION_START = "<!-- autonomous-dev:start -->"
SECTION_END = "<!-- autonomous-dev:end -->"

# Regex pattern to extract sections (non-greedy match)
SECTION_PATTERN = re.compile(
    rf"({re.escape(SECTION_START)}.*?{re.escape(SECTION_END)})",
    re.DOTALL
)


@dataclass
class MergeResult:
    """Result of CLAUDE.md merge operation.

    Attributes:
        success: Whether merge succeeded
        message: Human-readable result message
        output_path: Path to merged file (None if dry run or failed)
        sections_added: Number of new sections added
        sections_updated: Number of existing sections updated
        sections_preserved: Number of user sections preserved
        backup_path: Path to backup file (None if no backup needed)
        details: Additional result details
    """

    success: bool
    message: str
    output_path: Optional[str] = None
    sections_added: int = 0
    sections_updated: int = 0
    sections_preserved: int = 0
    backup_path: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class ClaudeMerger:
    """Merge global CLAUDE.md with autonomous-dev template sections.

    This class handles merging template sections (e.g., Documentation Alignment,
    Git Automation) with user's existing ~/.claude/CLAUDE.md while preserving
    user customizations.

    Section markers:
        <!-- autonomous-dev:start -->
        ## Section Name
        Content managed by plugin
        <!-- autonomous-dev:end -->

    User content outside markers is NEVER touched.

    Attributes:
        template_path: Path to template file
        template_content: Content of template file
    """

    def __init__(self, template_path: Path):
        """Initialize merger with template file.

        Args:
            template_path: Path to template file with section markers

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        self.template_path = Path(template_path).resolve()

        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        self.template_content = self.template_path.read_text(encoding='utf-8')

    def merge_global_claude(
        self,
        output_path: Path,
        write_result: bool = True,
        create_backup: bool = True
    ) -> MergeResult:
        """Merge template sections with existing global CLAUDE.md.

        Args:
            output_path: Path to output file (~/.claude/CLAUDE.md)
            write_result: Whether to write the result (False for dry run)
            create_backup: Whether to create backup before modifying

        Returns:
            MergeResult with operation details
        """
        output_path = Path(output_path).resolve()

        # Extract template sections
        template_sections = self._extract_sections(self.template_content)

        # Check if output exists
        existing_content = ""
        backup_path = None

        if output_path.exists():
            # Reject symlinks
            if output_path.is_symlink():
                return MergeResult(
                    success=False,
                    message=f"Symlinks not allowed: {output_path}",
                    details={"reason": "symlink_rejected"}
                )

            existing_content = output_path.read_text(encoding='utf-8')

            # Create backup if requested and file has content
            if create_backup and existing_content.strip() and write_result:
                backup_path = self._create_backup(output_path)

        # Extract existing sections and user content
        existing_sections = self._extract_sections(existing_content)
        user_content = self._extract_user_content(existing_content)

        # Merge content
        merged_content, stats = self._merge_content(
            user_content=user_content,
            template_sections=template_sections,
            existing_sections=existing_sections,
            template_content=self.template_content
        )

        # Prepare result
        result = MergeResult(
            success=True,
            message="Merge completed successfully",
            output_path=str(output_path) if write_result else None,
            sections_added=stats['added'],
            sections_updated=stats['updated'],
            sections_preserved=stats['preserved'],
            backup_path=str(backup_path) if backup_path else None,
            details={
                'merged_content': merged_content if not write_result else None,
                'preview': merged_content[:500] + "..." if not write_result and len(merged_content) > 500 else merged_content if not write_result else None
            }
        )

        # Write result if requested
        if write_result:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self._atomic_write(output_path, merged_content)
            result.message = f"Merged successfully: {output_path}"

        return result

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Extract autonomous-dev sections from content.

        Args:
            content: Content to extract sections from

        Returns:
            Dictionary mapping section header to full section content
        """
        if not content:
            return {}

        sections = {}
        matches = SECTION_PATTERN.findall(content)

        for match in matches:
            # Extract section header (first ## line after marker)
            header_match = re.search(r'^## (.+)$', match, re.MULTILINE)
            if header_match:
                header = header_match.group(1).strip()
                sections[header] = match

        return sections

    def _extract_user_content(self, content: str) -> str:
        """Extract user content (everything outside autonomous-dev markers).

        Args:
            content: Full content to extract user portions from

        Returns:
            User content with autonomous-dev sections removed
        """
        if not content:
            return ""

        # Remove all autonomous-dev sections
        user_content = SECTION_PATTERN.sub('', content)

        # Clean up excessive whitespace
        user_content = re.sub(r'\n{3,}', '\n\n', user_content)

        return user_content.strip()

    def _merge_content(
        self,
        user_content: str,
        template_sections: Dict[str, str],
        existing_sections: Dict[str, str],
        template_content: str
    ) -> Tuple[str, Dict[str, int]]:
        """Merge user content with template sections.

        Args:
            user_content: User's custom content (outside markers)
            template_sections: Sections from template
            existing_sections: Sections from existing file
            template_content: Full template content for structure

        Returns:
            Tuple of (merged content, stats dict)
        """
        stats = {'added': 0, 'updated': 0, 'preserved': 0}

        # If no user content, use template as base
        if not user_content:
            # Count all template sections as added
            stats['added'] = len(template_sections)
            return template_content, stats

        # Build merged content
        parts = []

        # Add user content first
        if user_content:
            parts.append(user_content)
            parts.append("\n\n---\n")

        # Add template sections
        for header, section in template_sections.items():
            if header in existing_sections:
                stats['updated'] += 1
            else:
                stats['added'] += 1

            parts.append(f"\n{section}\n")

        # Count preserved user sections (any ## outside markers)
        user_headers = re.findall(r'^## (.+)$', user_content, re.MULTILINE)
        stats['preserved'] = len(user_headers)

        merged = ''.join(parts)

        # Clean up whitespace
        merged = re.sub(r'\n{3,}', '\n\n', merged)

        return merged.strip() + '\n', stats

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write file atomically with secure permissions.

        Uses temp file + rename pattern to prevent partial writes.

        Args:
            path: Target file path
            content: Content to write
        """
        # Create temp file in same directory (ensures same filesystem)
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix='.claude_merge_',
            suffix='.tmp'
        )

        try:
            # Write content
            os.write(fd, content.encode('utf-8'))
            os.close(fd)

            # Set secure permissions (owner read/write only)
            os.chmod(temp_path, 0o600)

            # Atomic rename
            Path(temp_path).replace(path)

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _create_backup(self, path: Path) -> Path:
        """Create timestamped backup of existing file.

        Args:
            path: File to backup

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = path.with_suffix(f'.backup.{timestamp}.md')

        # Copy content (not move, to preserve original until merge succeeds)
        backup_path.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')

        return backup_path


# Export public API
__all__ = [
    'ClaudeMerger',
    'MergeResult',
    'SECTION_START',
    'SECTION_END',
]
