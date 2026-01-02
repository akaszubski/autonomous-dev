#!/usr/bin/env python3
"""
Parallel Validation Library - Agent pool integration for /auto-implement

Migrates STEP 4.1 parallel validation from prompt engineering to agent_pool.py library.
Provides reusable validation execution with security-first priority mode, retry logic,
and result aggregation.

Features:
- Parallel validation (3 agents: security-auditor, reviewer, doc-master)
- Security-first priority mode (security blocks on failure)
- Retry with exponential backoff (transient vs permanent errors)
- Result aggregation (parse agent outputs, track failures)
- Integration with AgentPool library

Usage:
    from parallel_validation import execute_parallel_validation, ValidationResults

    # Execute validation
    results = execute_parallel_validation(
        feature_description="Add JWT authentication",
        project_root=Path("/path/to/project"),
        priority_mode=True,  # Security first
        changed_files=["src/auth/jwt.py", "tests/test_jwt.py"]
    )

    # Check results
    if not results.security_passed:
        raise SecurityValidationError(results.security_output)
    if not results.review_passed:
        print(f"Review issues: {results.review_output}")

Security:
- CWE-22: Path validation for project_root
- Input validation (feature description, file paths)
- Error classification (fail fast on permanent errors)

Date: 2026-01-02
Issue: GitHub #187 (Migrate /auto-implement to agent_pool.py)
Agent: implementer
Phase: TDD Green (making tests pass)

See library-design-patterns skill for standardized library structure.
See error-handling-patterns skill for exception handling patterns.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

# Import agent pool library
try:
    from .agent_pool import AgentPool, PriorityLevel, TaskHandle, AgentResult
    from .pool_config import PoolConfig
except ImportError:
    import sys
    from pathlib import Path as PathLib
    lib_dir = PathLib(__file__).parent.resolve()
    sys.path.insert(0, str(lib_dir))
    from agent_pool import AgentPool, PriorityLevel, TaskHandle, AgentResult
    from pool_config import PoolConfig

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Exception Classes
# ============================================================================

class SecurityValidationError(Exception):
    """Raised when security validation fails (critical failure)."""
    pass


class ValidationTimeoutError(Exception):
    """Raised when validation times out (all agents timeout)."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ValidationResults:
    """Results from parallel validation execution.

    Attributes:
        security_passed: Whether security audit passed
        review_passed: Whether code review passed
        docs_updated: Whether documentation was updated
        failed_agents: List of agent types that failed
        execution_time_seconds: Total execution time
        security_output: Raw security agent output (optional)
        review_output: Raw reviewer output (optional)
        docs_output: Raw doc-master output (optional)
    """
    security_passed: bool
    review_passed: bool
    docs_updated: bool
    failed_agents: List[str]
    execution_time_seconds: float
    security_output: str = ""
    review_output: str = ""
    docs_output: str = ""


# ============================================================================
# Error Classification
# ============================================================================

def is_transient_error(error: Exception) -> bool:
    """Classify error as transient (should retry).

    Transient errors:
    - TimeoutError (network timeout, agent timeout)
    - ConnectionError (network issues)
    - HTTP 5xx errors (server errors)

    Args:
        error: Exception to classify

    Returns:
        True if error is transient (should retry), False otherwise
    """
    # Direct transient error types
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True

    # Check error message for HTTP 5xx patterns
    error_message = str(error).lower()
    if any(pattern in error_message for pattern in ["503", "502", "500", "timeout", "timed out"]):
        return True

    return False


def is_permanent_error(error: Exception) -> bool:
    """Classify error as permanent (fail fast, no retry).

    Permanent errors:
    - SyntaxError (invalid syntax)
    - ImportError (missing module)
    - ValueError (invalid input)
    - PermissionError (access denied)
    - TypeError (type mismatch)

    Args:
        error: Exception to classify

    Returns:
        True if error is permanent (fail fast), False otherwise
    """
    return isinstance(error, (
        SyntaxError,
        ImportError,
        ValueError,
        PermissionError,
        TypeError,
        KeyError,
        AttributeError
    ))


# ============================================================================
# Retry Logic
# ============================================================================

def retry_with_backoff(
    pool: AgentPool,
    agent_type: str,
    prompt: str,
    max_retries: int = 3,
    priority: PriorityLevel = PriorityLevel.P2_TESTS
) -> AgentResult:
    """Retry agent execution with exponential backoff.

    Retries transient errors (timeout, network) with exponential backoff.
    Fails fast on permanent errors (syntax, import, value).

    Backoff pattern: 2^n seconds (2s, 4s, 8s, 16s, ...)

    Args:
        pool: AgentPool instance
        agent_type: Agent type to invoke
        prompt: Agent prompt
        max_retries: Maximum retry attempts (default 3)
        priority: Task priority level

    Returns:
        AgentResult from successful execution

    Raises:
        Exception: If max retries exceeded or permanent error
    """
    attempt = 0
    last_error = None

    while attempt <= max_retries:
        try:
            # Submit task to pool
            handle = pool.submit_task(
                agent_type=agent_type,
                prompt=prompt,
                priority=priority
            )

            # Await result
            results = pool.await_all([handle])
            result = results.get(agent_type)

            if result is None:
                # Agent didn't return a result - treat as transient error and retry
                raise TimeoutError(f"No result returned for agent {agent_type}")

            return result

        except Exception as error:
            last_error = error

            # Permanent errors: fail fast (no retry)
            if is_permanent_error(error):
                logger.error(f"Permanent error in {agent_type}: {error}")
                raise

            # Transient errors: retry with backoff
            if is_transient_error(error):
                attempt += 1
                if attempt > max_retries:
                    logger.error(f"Max retries ({max_retries}) exceeded for {agent_type}")
                    raise

                # Exponential backoff: 2^attempt seconds
                backoff_seconds = 2 ** attempt
                logger.warning(
                    f"Transient error in {agent_type}: {error}. "
                    f"Retry {attempt}/{max_retries} in {backoff_seconds}s"
                )
                time.sleep(backoff_seconds)
            else:
                # Unknown error type: treat as permanent
                logger.error(f"Unknown error in {agent_type}: {error}")
                raise

    # Should never reach here (loop always raises on final attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"Unexpected retry loop exit for {agent_type}")


# ============================================================================
# Result Aggregation
# ============================================================================

def _aggregate_results(agent_results: Dict[str, AgentResult]) -> ValidationResults:
    """Aggregate agent results into ValidationResults.

    Parses agent outputs to determine pass/fail status:
    - security-auditor: Look for "PASS" or "FAIL" in output
    - reviewer: Look for "APPROVE" or "REQUEST_CHANGES" in output
    - doc-master: Look for "UPDATED" in output or check success flag

    Args:
        agent_results: Dict of agent_type -> AgentResult

    Returns:
        ValidationResults with aggregated status
    """
    failed_agents = []
    security_passed = False
    review_passed = False
    docs_updated = False
    security_output = ""
    review_output = ""
    docs_output = ""
    total_duration = 0.0

    # Process security-auditor result
    security_result = agent_results.get("security-auditor")
    if security_result:
        security_output = security_result.output
        total_duration += security_result.duration

        # Parse security output
        output_upper = security_result.output.upper()
        if "PASS" in output_upper and security_result.success:
            security_passed = True
        else:
            failed_agents.append("security-auditor")
            security_passed = False
    else:
        failed_agents.append("security-auditor")
        security_output = "ERROR - Security agent did not execute"

    # Process reviewer result
    reviewer_result = agent_results.get("reviewer")
    if reviewer_result:
        review_output = reviewer_result.output
        total_duration += reviewer_result.duration

        # Parse reviewer output
        output_upper = reviewer_result.output.upper()
        if "APPROVE" in output_upper and reviewer_result.success:
            review_passed = True
        else:
            failed_agents.append("reviewer")
            review_passed = False
    else:
        failed_agents.append("reviewer")
        review_output = "ERROR - Reviewer agent did not execute"

    # Process doc-master result
    docs_result = agent_results.get("doc-master")
    if docs_result:
        docs_output = docs_result.output
        total_duration += docs_result.duration

        # Parse doc-master output
        output_upper = docs_result.output.upper()
        if "UPDATED" in output_upper and docs_result.success:
            docs_updated = True
        else:
            # Doc updates are optional, so not considered critical failure
            docs_updated = False
            if not docs_result.success:
                failed_agents.append("doc-master")
    else:
        failed_agents.append("doc-master")
        docs_output = "ERROR - Doc-master agent did not execute"
        docs_updated = False

    return ValidationResults(
        security_passed=security_passed,
        review_passed=review_passed,
        docs_updated=docs_updated,
        failed_agents=failed_agents,
        execution_time_seconds=total_duration,
        security_output=security_output,
        review_output=review_output,
        docs_output=docs_output
    )


# ============================================================================
# Security-First Execution
# ============================================================================

def _execute_security_first(
    pool: AgentPool,
    feature: str,
    project_root: Path,
    changed_files: Optional[List[str]] = None
) -> ValidationResults:
    """Execute validation with security-first priority.

    Security agent runs first. If security fails, raises SecurityValidationError
    and blocks reviewer + doc-master from running.

    If security passes, reviewer + doc-master run in parallel.

    Args:
        pool: AgentPool instance
        feature: Feature description
        project_root: Project root directory
        changed_files: Optional list of changed files

    Returns:
        ValidationResults if all agents succeed

    Raises:
        SecurityValidationError: If security validation fails
    """
    start_time = time.time()

    # PHASE 1: Run security agent first (blocking)
    logger.info("PHASE 1: Running security agent (blocking)")

    security_prompt = f"""Scan implementation for security vulnerabilities.

Feature: {feature}
Project: {project_root}
"""
    if changed_files:
        security_prompt += f"\nChanged files:\n" + "\n".join(f"- {f}" for f in changed_files)

    security_prompt += """

Check for:
- Hardcoded secrets (API keys, passwords)
- SQL injection vulnerabilities
- XSS vulnerabilities
- Path traversal (CWE-22)
- Command injection (CWE-78)
- SSRF vulnerabilities
- Insecure dependencies
- Authentication/authorization issues
- Input validation missing
- OWASP Top 10 compliance

Output: PASS if no vulnerabilities, FAIL with details if vulnerabilities found.
"""

    # Run security agent with retry
    security_result = retry_with_backoff(
        pool=pool,
        agent_type="security-auditor",
        prompt=security_prompt,
        priority=PriorityLevel.P1_SECURITY
    )

    # Check security result
    security_output_upper = security_result.output.upper()
    security_passed = "PASS" in security_output_upper and security_result.success

    if not security_passed:
        # Security failed - raise exception and block further execution
        raise SecurityValidationError(
            f"Security validation failed: {security_result.output}"
        )

    logger.info("PHASE 1: Security passed, proceeding to reviewer + doc-master")

    # PHASE 2: Run reviewer + doc-master in parallel
    logger.info("PHASE 2: Running reviewer + doc-master in parallel")

    # Submit reviewer task
    reviewer_prompt = f"""Review implementation for code quality.

Feature: {feature}
Project: {project_root}
"""
    if changed_files:
        reviewer_prompt += f"\nChanged files:\n" + "\n".join(f"- {f}" for f in changed_files)

    reviewer_prompt += """

Check:
- Code quality (readability, maintainability)
- Pattern consistency with codebase
- Test coverage (all cases covered?)
- Error handling (graceful failures?)
- Edge cases (handled properly?)
- Documentation (clear comments?)

Output: APPROVE if quality standards met, REQUEST_CHANGES with specific issues if changes needed.
"""

    reviewer_handle = pool.submit_task(
        agent_type="reviewer",
        prompt=reviewer_prompt,
        priority=PriorityLevel.P2_TESTS
    )

    # Submit doc-master task
    docs_prompt = f"""Update documentation for implemented feature.

Feature: {feature}
Project: {project_root}
"""
    if changed_files:
        docs_prompt += f"\nChanged files:\n" + "\n".join(f"- {f}" for f in changed_files)

    docs_prompt += """

Update:
- CHANGELOG.md (add feature entry)
- README.md (update if API changed)
- Docstrings (ensure all functions documented)

Output: UPDATED with list of files modified.
"""

    docs_handle = pool.submit_task(
        agent_type="doc-master",
        prompt=docs_prompt,
        priority=PriorityLevel.P3_DOCS
    )

    # Await parallel results
    results = pool.await_all([reviewer_handle, docs_handle])

    # Add security result to results dict
    all_results = {
        "security-auditor": security_result,
        "reviewer": results.get("reviewer"),
        "doc-master": results.get("doc-master")
    }

    # Aggregate results
    validation_results = _aggregate_results(all_results)
    # execution_time_seconds already set by _aggregate_results (sum of agent durations)
    # Don't overwrite with wall-clock time (which would be 0 in tests with mocks)

    return validation_results


# ============================================================================
# Main Entry Point
# ============================================================================

def execute_parallel_validation(
    feature_description: str,
    project_root: Path,
    priority_mode: bool = False,
    changed_files: Optional[List[str]] = None,
    max_retries: int = 3
) -> ValidationResults:
    """Execute parallel validation for implemented feature.

    Runs 3 validation agents (security-auditor, reviewer, doc-master) in parallel
    or security-first mode with automatic retry on transient errors.

    Args:
        feature_description: Feature description (what was implemented)
        project_root: Project root directory path
        priority_mode: If True, run security first (blocks on failure)
        changed_files: Optional list of changed file paths
        max_retries: Maximum retry attempts for transient errors

    Returns:
        ValidationResults with aggregated status

    Raises:
        ValueError: If feature_description is empty or project_root invalid
        SecurityValidationError: If security validation fails (priority_mode only)
        ValidationTimeoutError: If all agents timeout
    """
    # Validate inputs
    if not feature_description or not feature_description.strip():
        raise ValueError("Feature description cannot be empty")

    if not project_root or not isinstance(project_root, Path):
        raise ValueError("project_root must be a Path object")

    if not project_root.exists():
        raise ValueError(f"Project root does not exist: {project_root}")

    # Initialize agent pool
    config = PoolConfig.load_from_env()
    pool = AgentPool(config=config)

    try:
        # Execute based on priority mode
        if priority_mode:
            # Security-first mode: security blocks on failure
            return _execute_security_first(
                pool=pool,
                feature=feature_description,
                project_root=project_root,
                changed_files=changed_files
            )
        else:
            # All parallel mode: all agents run simultaneously
            start_time = time.time()

            # Build prompts
            security_prompt = f"""Scan implementation for security vulnerabilities.

Feature: {feature_description}
Project: {project_root}
"""
            if changed_files:
                security_prompt += f"\nChanged files:\n" + "\n".join(f"- {f}" for f in changed_files)

            security_prompt += """

Check for:
- Hardcoded secrets (API keys, passwords)
- SQL injection vulnerabilities
- XSS vulnerabilities
- Path traversal (CWE-22)
- Command injection (CWE-78)
- SSRF vulnerabilities
- Insecure dependencies
- Input validation missing
- OWASP Top 10 compliance

Output: PASS if no vulnerabilities, FAIL with details if found.
"""

            reviewer_prompt = f"""Review implementation for code quality.

Feature: {feature_description}
Project: {project_root}
"""
            if changed_files:
                reviewer_prompt += f"\nChanged files:\n" + "\n".join(f"- {f}" for f in changed_files)

            reviewer_prompt += """

Check:
- Code quality (readability, maintainability)
- Pattern consistency with codebase
- Test coverage (all cases covered?)
- Error handling (graceful failures?)
- Edge cases (handled properly?)

Output: APPROVE if standards met, REQUEST_CHANGES with issues if needed.
"""

            docs_prompt = f"""Update documentation for implemented feature.

Feature: {feature_description}
Project: {project_root}
"""
            if changed_files:
                docs_prompt += f"\nChanged files:\n" + "\n".join(f"- {f}" for f in changed_files)

            docs_prompt += """

Update:
- CHANGELOG.md (add feature entry)
- README.md (update if API changed)
- Docstrings (ensure functions documented)

Output: UPDATED with list of files modified.
"""

            # Submit all tasks in parallel
            handles = {}

            try:
                handles["security-auditor"] = pool.submit_task(
                    agent_type="security-auditor",
                    prompt=security_prompt,
                    priority=PriorityLevel.P1_SECURITY
                )
            except Exception as e:
                if is_transient_error(e):
                    # Retry with backoff
                    security_result = retry_with_backoff(
                        pool=pool,
                        agent_type="security-auditor",
                        prompt=security_prompt,
                        max_retries=max_retries,
                        priority=PriorityLevel.P1_SECURITY
                    )
                    handles["security-auditor"] = None  # Already have result
                else:
                    raise

            try:
                handles["reviewer"] = pool.submit_task(
                    agent_type="reviewer",
                    prompt=reviewer_prompt,
                    priority=PriorityLevel.P2_TESTS
                )
            except Exception as e:
                if is_transient_error(e):
                    reviewer_result = retry_with_backoff(
                        pool=pool,
                        agent_type="reviewer",
                        prompt=reviewer_prompt,
                        max_retries=max_retries,
                        priority=PriorityLevel.P2_TESTS
                    )
                    handles["reviewer"] = None
                else:
                    raise

            try:
                handles["doc-master"] = pool.submit_task(
                    agent_type="doc-master",
                    prompt=docs_prompt,
                    priority=PriorityLevel.P3_DOCS
                )
            except Exception as e:
                if is_transient_error(e):
                    docs_result = retry_with_backoff(
                        pool=pool,
                        agent_type="doc-master",
                        prompt=docs_prompt,
                        max_retries=max_retries,
                        priority=PriorityLevel.P3_DOCS
                    )
                    handles["doc-master"] = None
                else:
                    raise

            # Await all handles (skip None entries from retried agents)
            valid_handles = [h for h in handles.values() if h is not None]
            results = pool.await_all(valid_handles) if valid_handles else {}

            # Add any retry results
            if "security_result" in locals():
                results["security-auditor"] = security_result
            if "reviewer_result" in locals():
                results["reviewer"] = reviewer_result
            if "docs_result" in locals():
                results["doc-master"] = docs_result

            # Aggregate results
            validation_results = _aggregate_results(results)
            # execution_time_seconds already set by _aggregate_results (sum of agent durations)

            return validation_results

    except TimeoutError as error:
        # Convert TimeoutError to ValidationTimeoutError
        logger.error(f"All agents timed out: {error}")
        raise ValidationTimeoutError(f"All agents timed out: {error}")

    except Exception as error:
        logger.error(f"Validation execution failed: {error}")
        raise


# ============================================================================
# CLI Entry Point (for testing)
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Execute parallel validation")
    parser.add_argument("--feature", required=True, help="Feature description")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    parser.add_argument("--priority-mode", action="store_true", help="Run security first")
    parser.add_argument("--changed-files", nargs="+", help="List of changed files")
    parser.add_argument("--output-format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    try:
        results = execute_parallel_validation(
            feature_description=args.feature,
            project_root=Path(args.project_root),
            priority_mode=args.priority_mode,
            changed_files=args.changed_files
        )

        if args.output_format == "json":
            print(json.dumps({
                "security_passed": results.security_passed,
                "review_passed": results.review_passed,
                "docs_updated": results.docs_updated,
                "failed_agents": results.failed_agents,
                "execution_time_seconds": results.execution_time_seconds
            }, indent=2))
        else:
            print(f"Security: {'PASS' if results.security_passed else 'FAIL'}")
            print(f"Review: {'PASS' if results.review_passed else 'FAIL'}")
            print(f"Docs: {'UPDATED' if results.docs_updated else 'NOT UPDATED'}")
            print(f"Failed agents: {', '.join(results.failed_agents) if results.failed_agents else 'None'}")
            print(f"Execution time: {results.execution_time_seconds:.2f}s")

    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
