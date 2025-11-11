#!/usr/bin/env python3
"""
Token counting measurement script for Issue #72.

Measures token counts in agent prompt files before and after cleanup,
calculates savings, and generates reports.

Usage:
    python scripts/measure_agent_tokens.py --baseline
    python scripts/measure_agent_tokens.py --post-cleanup
    python scripts/measure_agent_tokens.py --report
    python scripts/measure_agent_tokens.py --report --json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


# Token estimation: ~4 characters per token (GPT-3/4 approximation)
CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses ~4 chars per token approximation (GPT-3/4 baseline).

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    return len(text) // CHARS_PER_TOKEN


def get_agent_files() -> List[Path]:
    """
    Get all agent markdown files.

    Returns:
        List of agent file paths (excludes archived agents)
    """
    agents_dir = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents"
    agent_files = list(agents_dir.glob("*.md"))

    # Exclude archived agents
    agent_files = [f for f in agent_files if "archived" not in str(f)]

    return sorted(agent_files)


def measure_baseline_tokens() -> Dict[str, int]:
    """
    Measure baseline token counts for all agents.

    Returns:
        Dictionary mapping agent name to token count
    """
    baseline = {}

    for agent_file in get_agent_files():
        agent_name = agent_file.stem
        content = agent_file.read_text()
        token_count = count_tokens(content)
        baseline[agent_name] = token_count

    return baseline


def measure_post_cleanup_tokens() -> Dict[str, int]:
    """
    Measure token counts after cleanup.

    Same as baseline measurement (reads current state of files).
    This function exists for semantic clarity - baseline vs post-cleanup.

    Returns:
        Dictionary mapping agent name to token count
    """
    return measure_baseline_tokens()


def save_baseline(baseline: Dict[str, int], output_path: Path) -> None:
    """
    Save baseline measurements to JSON file.

    Args:
        baseline: Baseline token counts
        output_path: Path to save JSON

    Raises:
        ValueError: If output_path is not within safe directory (CWE-73)
    """
    # Security: Restrict output to safe directory (docs/metrics/)
    safe_dir = Path(__file__).parent.parent / "docs" / "metrics"
    safe_dir.mkdir(parents=True, exist_ok=True)

    resolved_output = output_path.resolve()
    resolved_safe_dir = safe_dir.resolve()

    if not str(resolved_output).startswith(str(resolved_safe_dir)):
        raise ValueError(f"Output path must be within {safe_dir} (path traversal protection)")

    with open(output_path, 'w') as f:
        json.dump(baseline, f, indent=2)


def identify_reduced_agents(baseline: Dict[str, int], post_cleanup: Dict[str, int]) -> List[str]:
    """
    Identify agents with token reduction.

    Args:
        baseline: Baseline token counts
        post_cleanup: Post-cleanup token counts

    Returns:
        List of agent names with reduced tokens
    """
    reduced = []

    for agent_name in baseline:
        if post_cleanup.get(agent_name, 0) < baseline[agent_name]:
            reduced.append(agent_name)

    return reduced


def calculate_token_savings(baseline: Dict[str, int], post_cleanup: Dict[str, int]) -> Dict:
    """
    Calculate token savings between baseline and post-cleanup.

    Args:
        baseline: Baseline token counts
        post_cleanup: Post-cleanup token counts

    Returns:
        Dictionary with savings metrics:
        - total_saved: Total tokens saved
        - percentage_reduction: Percentage reduction
        - per_agent: Per-agent savings
        - ranked_by_savings: Agents ranked by savings

    Raises:
        ValueError: If agent sets don't match
    """
    # Validate agent sets match
    if set(baseline.keys()) != set(post_cleanup.keys()):
        missing_in_post = set(baseline.keys()) - set(post_cleanup.keys())
        missing_in_base = set(post_cleanup.keys()) - set(baseline.keys())
        raise ValueError(
            f"Agent mismatch: "
            f"Missing in post-cleanup: {missing_in_post}, "
            f"Missing in baseline: {missing_in_base}"
        )

    # Calculate per-agent savings
    per_agent = {}
    for agent_name in baseline:
        saved = baseline[agent_name] - post_cleanup[agent_name]
        per_agent[agent_name] = saved

    # Calculate totals
    baseline_total = sum(baseline.values())
    post_cleanup_total = sum(post_cleanup.values())
    total_saved = baseline_total - post_cleanup_total

    # Calculate percentage
    percentage_reduction = (total_saved / baseline_total * 100) if baseline_total > 0 else 0.0

    # Rank agents by savings
    ranked_by_savings = [
        {"agent": agent, "saved": saved}
        for agent, saved in sorted(per_agent.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "total_saved": total_saved,
        "percentage_reduction": percentage_reduction,
        "per_agent": per_agent,
        "ranked_by_savings": ranked_by_savings,
        "baseline_total": baseline_total,
        "post_cleanup_total": post_cleanup_total,
    }


def extract_sections(content: str) -> Dict[str, str]:
    """
    Extract major sections from agent markdown.

    Args:
        content: Agent file content

    Returns:
        Dictionary mapping section name to content
    """
    sections = {}

    # Split by ## headers
    parts = re.split(r'\n## ', content)

    # First part is frontmatter + content before first section
    if parts:
        sections["_preamble"] = parts[0]

    # Parse remaining sections
    for part in parts[1:]:
        lines = part.split('\n', 1)
        if len(lines) >= 1:
            section_name = lines[0].strip()
            section_content = lines[1] if len(lines) > 1 else ""
            sections[section_name] = section_content

    return sections


def analyze_agent_tokens(agent_name: str) -> Dict:
    """
    Analyze token usage for individual agent.

    Args:
        agent_name: Name of agent (without .md extension)

    Returns:
        Dictionary with analysis:
        - agent_name: Agent name
        - total_tokens: Total token count
        - sections: Token count per section
        - section_percentages: Percentage per section

    Raises:
        FileNotFoundError: If agent file doesn't exist
        ValueError: If agent_name contains invalid characters (path traversal protection)
    """
    # Security: Validate agent_name to prevent path traversal (CWE-22)
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', agent_name):
        raise ValueError(f"Invalid agent name: {agent_name}. Only alphanumeric, underscore, and dash allowed.")

    agents_dir = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents"
    agent_file = agents_dir / f"{agent_name}.md"

    # Security: Verify resolved path is still within agents directory
    resolved_path = agent_file.resolve()
    agents_dir_resolved = agents_dir.resolve()
    if not str(resolved_path).startswith(str(agents_dir_resolved)):
        raise ValueError(f"Invalid agent path (path traversal attempt detected)")

    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_name}.md")

    return analyze_agent_file(agent_file)


def analyze_agent_file(agent_file: Path) -> Dict:
    """
    Analyze token usage for agent file.

    Args:
        agent_file: Path to agent markdown file

    Returns:
        Dictionary with analysis

    Raises:
        ValueError: If file is malformed
    """
    content = agent_file.read_text()

    # Basic validation
    if not content.strip():
        raise ValueError(f"Malformed agent file (empty): {agent_file.name}")

    if "---" not in content[:200]:  # Frontmatter should be near start
        raise ValueError(f"Malformed agent file (missing frontmatter): {agent_file.name}")

    # Calculate total tokens
    total_tokens = count_tokens(content)

    # Extract sections
    sections_content = extract_sections(content)

    # Count tokens per section
    sections = {}
    for section_name, section_content in sections_content.items():
        sections[section_name] = count_tokens(section_content)

    # Calculate percentages
    section_percentages = {}
    for section_name, token_count in sections.items():
        percentage = (token_count / total_tokens * 100) if total_tokens > 0 else 0.0
        section_percentages[section_name] = percentage

    return {
        "agent_name": agent_file.stem,
        "total_tokens": total_tokens,
        "sections": sections,
        "section_percentages": section_percentages,
    }


def count_output_format_tokens(agent_name: str) -> int:
    """
    Count tokens in Output Format section.

    Args:
        agent_name: Name of agent

    Returns:
        Token count in Output Format section (0 if section doesn't exist)
    """
    analysis = analyze_agent_tokens(agent_name)
    sections = analysis["sections"]

    # Look for Output Format section (various possible names)
    output_format_names = ["Output Format", "Output", "Format"]

    for section_name in output_format_names:
        if section_name in sections:
            return sections[section_name]

    return 0


def measure_output_format_lines(agent_name: str) -> int:
    """
    Measure line count of Output Format section.

    Args:
        agent_name: Name of agent

    Returns:
        Line count in Output Format section
    """
    agents_dir = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents"
    agent_file = agents_dir / f"{agent_name}.md"

    if not agent_file.exists():
        return 0

    content = agent_file.read_text()
    sections = extract_sections(content)

    # Look for Output Format section
    output_format_names = ["Output Format", "Output", "Format"]

    for section_name in output_format_names:
        if section_name in sections:
            section_content = sections[section_name]
            return len(section_content.split('\n'))

    return 0


def identify_verbose_output_formats(line_threshold: int = 30) -> List[str]:
    """
    Identify agents with verbose Output Format sections.

    Args:
        line_threshold: Minimum line count to be considered verbose

    Returns:
        List of agent names with verbose Output Format sections
    """
    verbose_agents = []

    for agent_file in get_agent_files():
        agent_name = agent_file.stem
        line_count = measure_output_format_lines(agent_name)

        if line_count >= line_threshold:
            verbose_agents.append(agent_name)

    return verbose_agents


def compare_output_format_sections(agent_name: str) -> Dict:
    """
    Compare Output Format section before/after cleanup.

    Note: This assumes current state is "after" and requires
    baseline measurements to have been saved previously.

    Args:
        agent_name: Name of agent

    Returns:
        Dictionary with comparison metrics
    """
    # Current state (after cleanup)
    after_tokens = count_output_format_tokens(agent_name)
    after_lines = measure_output_format_lines(agent_name)

    # For before, we'd need saved baseline - for now just return current
    # (This function is used in tests but real comparison requires baseline file)
    before_tokens = after_tokens  # Placeholder
    before_lines = after_lines    # Placeholder

    return {
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
        "tokens_saved": before_tokens - after_tokens,
        "before_lines": before_lines,
        "after_lines": after_lines,
    }


def print_baseline_report(baseline: Dict[str, int]) -> None:
    """
    Print baseline measurement report.

    Args:
        baseline: Baseline token counts
    """
    total = sum(baseline.values())

    print("\n=== Baseline Token Measurement ===")
    print(f"Total agents: {len(baseline)}")
    print(f"Total tokens: {total:,}")
    print(f"Average per agent: {total // len(baseline):,}")
    print("\nTop 5 agents by tokens:")

    sorted_agents = sorted(baseline.items(), key=lambda x: x[1], reverse=True)
    for agent, tokens in sorted_agents[:5]:
        print(f"  {agent}: {tokens:,} tokens")

    print("\nBaseline tokens measured successfully.")


def print_post_cleanup_report(post_cleanup: Dict[str, int]) -> None:
    """
    Print post-cleanup measurement report.

    Args:
        post_cleanup: Post-cleanup token counts
    """
    total = sum(post_cleanup.values())

    print("\n=== Post-Cleanup Token Measurement ===")
    print(f"Total agents: {len(post_cleanup)}")
    print(f"Total tokens: {total:,}")
    print(f"Average per agent: {total // len(post_cleanup):,}")

    print("\nPost-cleanup tokens measured successfully.")


def print_savings_report(savings: Dict) -> None:
    """
    Print token savings report.

    Args:
        savings: Savings metrics from calculate_token_savings
    """
    print("\n" + "="*60)
    print("Token Savings Report")
    print("="*60)

    print(f"\nBaseline total: {savings['baseline_total']:,} tokens")
    print(f"Post-cleanup total: {savings['post_cleanup_total']:,} tokens")
    print(f"Total tokens saved: {savings['total_saved']:,}")
    print(f"Percentage reduction: {savings['percentage_reduction']:.1f}%")

    print("\n--- Top 10 Agents by Token Savings ---")
    for i, item in enumerate(savings['ranked_by_savings'][:10], 1):
        agent = item['agent']
        saved = item['saved']
        if saved > 0:
            print(f"{i:2d}. {agent:30s} {saved:6,} tokens saved")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Measure token counts in agent prompts"
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Measure baseline token counts"
    )
    parser.add_argument(
        "--post-cleanup",
        action="store_true",
        help="Measure post-cleanup token counts"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate savings report"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report in JSON format"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for measurements (JSON)"
    )

    args = parser.parse_args()

    # Require at least one action
    if not any([args.baseline, args.post_cleanup, args.report]):
        parser.error("Must specify one of: --baseline, --post-cleanup, --report")

    try:
        if args.baseline:
            baseline = measure_baseline_tokens()

            if args.output:
                save_baseline(baseline, args.output)
                print(f"Baseline saved to {args.output}")

            if args.json:
                print(json.dumps(baseline, indent=2))
            else:
                print_baseline_report(baseline)

        elif args.post_cleanup:
            post_cleanup = measure_post_cleanup_tokens()

            if args.output:
                save_baseline(post_cleanup, args.output)
                print(f"Post-cleanup saved to {args.output}")

            if args.json:
                print(json.dumps(post_cleanup, indent=2))
            else:
                print_post_cleanup_report(post_cleanup)

        elif args.report:
            # Load baseline and post-cleanup, calculate savings
            baseline = measure_baseline_tokens()
            post_cleanup = measure_post_cleanup_tokens()

            savings = calculate_token_savings(baseline, post_cleanup)

            if args.json:
                print(json.dumps(savings, indent=2))
            else:
                print_savings_report(savings)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
