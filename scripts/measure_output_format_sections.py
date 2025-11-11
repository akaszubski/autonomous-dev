#!/usr/bin/env python3
"""
Helper utilities for measuring Output Format section lengths.

Used by test suite to validate section cleanup progress.
"""

from pathlib import Path
from typing import Optional, List
import re


def extract_output_format_section(agent_file: Path) -> Optional[str]:
    """
    Extract Output Format section text from agent file.

    Args:
        agent_file: Path to agent markdown file

    Returns:
        Output Format section text, or None if not found
    """
    if not agent_file.exists():
        return None

    content = agent_file.read_text()

    # Find ## Output Format section
    match = re.search(r'^## Output Format\s*$', content, re.MULTILINE)
    if not match:
        # Try alternative headings
        match = re.search(r'^## Output\s*$', content, re.MULTILINE)

    if not match:
        return None

    # Extract from match to next ## heading or end of file
    start = match.start()
    next_section = re.search(r'\n## [A-Z]', content[start + 1:])

    if next_section:
        end = start + 1 + next_section.start()
        section_text = content[start:end]
    else:
        section_text = content[start:]

    return section_text


def count_output_format_lines(agent_file: Path) -> int:
    """
    Count non-empty lines in Output Format section.

    Args:
        agent_file: Path to agent markdown file

    Returns:
        Number of non-empty lines in Output Format section
    """
    section_text = extract_output_format_section(agent_file)

    if section_text is None:
        return 0

    # Split into lines
    lines = section_text.split('\n')

    # Count non-empty lines (excluding section header)
    non_empty_count = 0
    in_code_block = False

    for line in lines[1:]:  # Skip section header
        stripped = line.strip()

        # Track code blocks
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue

        # Count non-empty lines
        if stripped and not in_code_block:
            non_empty_count += 1

    return non_empty_count


def identify_verbose_sections(agent_file: Path) -> List[str]:
    """
    Identify verbose subsections within Output Format.

    Args:
        agent_file: Path to agent markdown file

    Returns:
        List of subsection names that are verbose
    """
    section_text = extract_output_format_section(agent_file)

    if section_text is None:
        return []

    verbose_subsections = []

    # Find ### subsections
    subsections = re.findall(r'### (.+?)$', section_text, re.MULTILINE)

    for subsection in subsections:
        # Check if subsection has >20 lines
        subsection_pattern = f'### {re.escape(subsection)}'
        match = re.search(subsection_pattern, section_text)

        if match:
            start = match.end()
            # Find next ### or end
            next_sub = re.search(r'\n###', section_text[start:])

            if next_sub:
                subsection_content = section_text[start:start + next_sub.start()]
            else:
                subsection_content = section_text[start:]

            # Count lines
            lines = [l for l in subsection_content.split('\n') if l.strip()]
            if len(lines) > 20:
                verbose_subsections.append(subsection)

    return verbose_subsections
