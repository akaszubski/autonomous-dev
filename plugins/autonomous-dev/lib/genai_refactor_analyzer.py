#!/usr/bin/env python3
"""GenAI semantic analysis wrapper for RefactorAnalyzer.

Hybrid static-candidate + LLM-semantic analysis for /refactor.
Wraps RefactorAnalyzer (composition). Structural detectors become candidate
generators. GenAI does all judgment about meaning, alignment, and quality.

Three analysis passes:
- Pass 1 (Docs): Read covers: frontmatter -> Haiku contradiction check
  -> Sonnet escalation for HIGH
- Pass 2 (Tests): Pair test_foo.py with foo.py -> Haiku
  MEANINGFUL/HOLLOW/UNTESTED_SOURCE -> Sonnet for HOLLOW detail
- Pass 3 (Code): AST candidates from DEAD_CODE detector -> Haiku verify
  with dynamic dispatch context -> only flag if confidence >= 0.7

Content hash caching at .claude/cache/refactor/ keyed by
SHA-256(model:prompt_hash:content_hash).

Date: 2026-03-20
"""

import ast
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).parent))

from refactor_analyzer import (
    ConfidenceLevel,
    OptimizationType,
    RefactorAnalyzer,
    RefactorCategory,
    RefactorFinding,
    RefactorReport,
)
from sweep_analyzer import SweepSeverity

# ============================================================================
# GenAI imports (graceful degradation if unavailable)
# ============================================================================

_hooks_path = Path(__file__).parent.parent / "hooks"
if _hooks_path.exists() and str(_hooks_path) not in sys.path:
    sys.path.insert(0, str(_hooks_path))

_GENAI_AVAILABLE = False
try:
    from genai_utils import (
        GenAIAnalyzer,
        _safe_wrap,
        parse_classification_response,
        should_use_genai,
    )
    from genai_prompts import (
        DOC_CODE_DRIFT_PROMPT,
        HOLLOW_TEST_PROMPT,
        DEAD_CODE_VERIFY_PROMPT,
        REFACTOR_ESCALATION_PROMPT,
        REFACTOR_BATCH_SYSTEM_PROMPT,
        DEFAULT_MODEL,
    )
    _GENAI_AVAILABLE = True
except ImportError:
    GenAIAnalyzer = None  # type: ignore[assignment,misc]
    parse_classification_response = None  # type: ignore[assignment]
    should_use_genai = None  # type: ignore[assignment]
    _safe_wrap = None  # type: ignore[assignment]
    DOC_CODE_DRIFT_PROMPT = ""  # type: ignore[assignment]
    HOLLOW_TEST_PROMPT = ""  # type: ignore[assignment]
    DEAD_CODE_VERIFY_PROMPT = ""  # type: ignore[assignment]
    REFACTOR_ESCALATION_PROMPT = ""  # type: ignore[assignment]
    REFACTOR_BATCH_SYSTEM_PROMPT = ""  # type: ignore[assignment]
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Sensitive file patterns (case-insensitive)
_SENSITIVE_PATTERNS = [
    r"\.env$",
    r"\.pem$",
    r"\.key$",
    r"secret",
    r"credential",
    r"password",
]

# Dead code confidence threshold
_DEAD_CODE_CONFIDENCE_THRESHOLD = 0.7


class GenAIRefactorAnalyzer:
    """Hybrid static-candidate + LLM-semantic analysis for /refactor.

    Wraps RefactorAnalyzer (composition). Structural detectors become candidate
    generators. GenAI does all judgment about meaning, alignment, and quality.

    Args:
        project_root: Root directory of the project to analyze.
        use_genai: Whether to enable GenAI analysis (default True).
        use_batch_api: Whether to use Anthropic Batch API (default False).

    Example:
        >>> analyzer = GenAIRefactorAnalyzer(Path("."))
        >>> report = analyzer.full_analysis(deep=True)
        >>> print(report.format_report())
    """

    def __init__(
        self,
        project_root: Path,
        *,
        use_genai: bool = True,
        use_batch_api: bool = False,
    ):
        self.project_root = Path(project_root).resolve()
        self._structural = RefactorAnalyzer(self.project_root)
        self.use_batch_api = use_batch_api

        # Determine GenAI availability
        self._genai_enabled = use_genai and _GENAI_AVAILABLE
        self._analyzer: Any = None  # Lazy-initialized GenAIAnalyzer
        self._escalation_analyzer: Any = None  # Sonnet for escalation

        # Cache directory
        self._cache_dir = self.project_root / ".claude" / "cache" / "refactor"

        # Warnings collected during analysis
        self.warnings: List[str] = []

    def _ensure_genai_analyzer(self) -> bool:
        """Initialize GenAI analyzer if not yet created.

        Returns:
            True if GenAI analyzer is available and ready.
        """
        if self._analyzer is not None:
            return True
        if not self._genai_enabled:
            return False
        if GenAIAnalyzer is None:
            return False

        self._analyzer = GenAIAnalyzer(
            model=DEFAULT_MODEL,
            max_tokens=500,
            timeout=10,
            use_genai=True,
        )
        return True

    def _ensure_escalation_analyzer(self) -> bool:
        """Initialize Sonnet escalation analyzer.

        Returns:
            True if escalation analyzer is available and ready.
        """
        if self._escalation_analyzer is not None:
            return True
        if not self._genai_enabled:
            return False
        if GenAIAnalyzer is None:
            return False

        self._escalation_analyzer = GenAIAnalyzer(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            timeout=15,
            use_genai=True,
        )
        return True

    def full_analysis(
        self,
        modes: Optional[List[str]] = None,
        *,
        deep: bool = False,
    ) -> RefactorReport:
        """Run analysis with optional GenAI semantic enhancement.

        Args:
            modes: List of modes to run ("tests", "docs", "code").
                   If None, runs all three.
            deep: If True, require GenAI (raise if unavailable).
                  If False with GenAI available, still uses GenAI.

        Returns:
            RefactorReport with structural + GenAI findings.

        Raises:
            RuntimeError: If deep=True but no API key / SDK available.
        """
        if not modes:
            modes = ["tests", "docs", "code"]

        # Validate GenAI availability for --deep
        if deep and not _GENAI_AVAILABLE:
            raise RuntimeError(
                "GenAI analysis requires the Anthropic SDK.\n"
                "Install: pip install anthropic\n"
                "Set: export ANTHROPIC_API_KEY=your-key"
            )
        if deep and not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "GenAI analysis requires ANTHROPIC_API_KEY.\n"
                "Set: export ANTHROPIC_API_KEY=your-key\n"
                "Get a key at: https://console.anthropic.com/"
            )

        start = time.time()

        # Get structural analysis first
        structural_report = self._structural.full_analysis(modes)
        all_findings = list(structural_report.findings)
        modes_run = list(structural_report.modes_run)

        # Add GenAI semantic analysis if available
        if self._genai_enabled or deep:
            if "docs" in modes:
                try:
                    genai_doc_findings = self._analyze_doc_code_drift()
                    all_findings.extend(genai_doc_findings)
                except Exception as e:
                    logger.debug("Doc-code drift analysis failed: %s", e)

            if "tests" in modes:
                try:
                    genai_test_findings = self._analyze_hollow_tests()
                    all_findings.extend(genai_test_findings)
                except Exception as e:
                    logger.debug("Hollow test analysis failed: %s", e)

            if "code" in modes:
                try:
                    # Use structural dead code candidates, verify with GenAI
                    dead_code_candidates = [
                        f for f in structural_report.findings
                        if f.category == RefactorCategory.DEAD_CODE
                    ]
                    if dead_code_candidates:
                        verified = self._verify_dead_code(dead_code_candidates)
                        # Remove structural dead code findings and add verified ones
                        all_findings = [
                            f for f in all_findings
                            if f.category != RefactorCategory.DEAD_CODE
                        ]
                        all_findings.extend(verified)
                except Exception as e:
                    logger.debug("Dead code verification failed: %s", e)
        else:
            if not self._genai_enabled:
                self.warnings.append(
                    "GenAI analysis not available. "
                    "Results are structural-only. "
                    "Install anthropic SDK and set ANTHROPIC_API_KEY for semantic analysis."
                )

        elapsed_ms = int((time.time() - start) * 1000)
        return RefactorReport(
            findings=all_findings,
            scan_duration_ms=elapsed_ms,
            modes_run=modes_run,
            test_shape=structural_report.test_shape,
        )

    # =========================================================================
    # Pass 1: Doc-Code Drift Analysis
    # =========================================================================

    def _analyze_doc_code_drift(self) -> List[RefactorFinding]:
        """Analyze documentation files with covers: frontmatter for code drift.

        Reads covers: frontmatter from .md files, pairs with source files,
        and uses GenAI to detect contradictions.

        Returns:
            List of findings for doc-code contradictions.
        """
        findings: List[RefactorFinding] = []

        if not self._ensure_genai_analyzer():
            return findings

        docs_dir = self.project_root / "docs"
        if not docs_dir.is_dir():
            return findings

        for md_file in docs_dir.rglob("*.md"):
            if self._is_sensitive_file(md_file):
                continue

            try:
                doc_content = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            covered_paths = self._parse_covers_frontmatter(doc_content)
            if not covered_paths:
                continue

            for covered_path in covered_paths:
                source_file = (self.project_root / covered_path).resolve()
                # Path traversal guard: ensure file is within project root
                if not source_file.is_relative_to(self.project_root):
                    continue
                if not source_file.is_file():
                    continue
                if self._is_sensitive_file(source_file):
                    continue

                try:
                    source_content = source_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue

                # Truncate long files to avoid token limits
                doc_truncated = doc_content[:4000]
                source_truncated = source_content[:4000]

                # Check cache
                cache_key = self._get_cache_key(md_file, "doc_code_drift")
                cached = self._get_cached_result(cache_key)
                if cached is not None:
                    findings.extend(self._parse_drift_result(
                        cached, str(md_file.relative_to(self.project_root)),
                        str(source_file.relative_to(self.project_root))
                    ))
                    continue

                # Issue #1007 (Phase 3): wrap user-controlled repo content for
                # prompt-injection defense. doc_content and source_content are
                # repo-controlled; doc_path/source_path come from validated
                # filesystem traversal and are left unwrapped.
                response = self._analyzer.analyze(
                    DOC_CODE_DRIFT_PROMPT,
                    doc_path=str(md_file.relative_to(self.project_root)),
                    doc_content=_safe_wrap(doc_truncated),
                    source_path=str(source_file.relative_to(self.project_root)),
                    source_content=_safe_wrap(source_truncated),
                )

                if not response:
                    continue

                # Parse response
                result = self._parse_json_or_aligned(response)
                self._set_cached_result(cache_key, result)

                findings.extend(self._parse_drift_result(
                    result,
                    str(md_file.relative_to(self.project_root)),
                    str(source_file.relative_to(self.project_root)),
                ))

        return findings

    def _parse_covers_frontmatter(self, content: str) -> List[str]:
        """Parse covers: field from YAML frontmatter.

        Args:
            content: Full file content with optional frontmatter.

        Returns:
            List of file paths from covers: field.
        """
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return []

        frontmatter = match.group(1)
        paths: List[str] = []
        in_covers = False

        for line in frontmatter.split("\n"):
            stripped = line.strip()
            if stripped.startswith("covers:"):
                in_covers = True
                # Check for inline value
                value = stripped[len("covers:"):].strip()
                if value and value != "":
                    paths.append(value)
                continue
            if in_covers:
                if stripped.startswith("- "):
                    paths.append(stripped[2:].strip())
                elif stripped and not stripped.startswith("#"):
                    # End of covers list
                    break

        return paths

    def _parse_json_or_aligned(self, response: str) -> Dict[str, Any]:
        """Parse GenAI response as JSON or ALIGNED marker.

        Args:
            response: Raw response text.

        Returns:
            Parsed dict or {"status": "ALIGNED"}.
        """
        response = response.strip()
        if response.upper() == "ALIGNED" or response.strip('"').upper() == "ALIGNED":
            return {"status": "ALIGNED"}

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try extracting JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            return {"status": "ALIGNED"}

    def _parse_drift_result(
        self,
        result: Dict[str, Any],
        doc_path: str,
        source_path: str,
    ) -> List[RefactorFinding]:
        """Convert parsed drift result into RefactorFinding list.

        Args:
            result: Parsed JSON result from GenAI.
            doc_path: Relative path to documentation file.
            source_path: Relative path to source file.

        Returns:
            List of findings for contradictions.
        """
        findings: List[RefactorFinding] = []

        if result.get("status") == "ALIGNED":
            return findings

        contradictions = result.get("contradictions", [])
        for contradiction in contradictions:
            if not isinstance(contradiction, dict):
                continue

            severity_str = contradiction.get("severity", "MEDIUM").upper()
            severity_map = {
                "HIGH": SweepSeverity.HIGH,
                "MEDIUM": SweepSeverity.MEDIUM,
                "LOW": SweepSeverity.LOW,
            }
            severity = severity_map.get(severity_str, SweepSeverity.MEDIUM)

            doc_claim = contradiction.get("doc_claim", "unknown claim")
            code_behavior = contradiction.get("code_behavior", "unknown behavior")

            description = (
                f"[genai] Doc-code contradiction: doc says '{doc_claim}' "
                f"but code does '{code_behavior}'"
            )

            # Escalate HIGH severity to Sonnet for detail
            suggestion = f"Review {doc_path} against {source_path} and update documentation"
            if severity == SweepSeverity.HIGH and self._ensure_escalation_analyzer():
                # Issue #1007 (Phase 3): wrap user-controlled analysis text for
                # prompt-injection defense. file_path/category are validated/literal
                # constants; original_analysis is composed from repo content.
                escalation_response = self._escalation_analyzer.analyze(
                    REFACTOR_ESCALATION_PROMPT,
                    file_path=doc_path,
                    category="DOC_CODE_DRIFT",
                    original_analysis=_safe_wrap(f"{doc_claim} vs {code_behavior}"),
                )
                if escalation_response:
                    suggestion = f"[genai] {escalation_response}"

            findings.append(RefactorFinding(
                category=RefactorCategory.DOC_REDUNDANCY,
                severity=severity,
                file_path=doc_path,
                description=description,
                suggestion=suggestion,
                optimization_type=OptimizationType.OPTIMIZATION,
                confidence=ConfidenceLevel.HIGH,
            ))

        return findings

    # =========================================================================
    # Pass 2: Hollow Test Analysis
    # =========================================================================

    def _analyze_hollow_tests(self) -> List[RefactorFinding]:
        """Analyze tests for hollowness by pairing test_foo.py with foo.py.

        Returns:
            List of findings for hollow or untested source files.
        """
        findings: List[RefactorFinding] = []

        if not self._ensure_genai_analyzer():
            return findings

        test_dirs = [
            self.project_root / "tests",
            self.project_root / "test",
        ]

        for test_dir in test_dirs:
            if not test_dir.is_dir():
                continue

            for test_file in test_dir.rglob("test_*.py"):
                if self._is_sensitive_file(test_file):
                    continue

                # Find corresponding source file
                source_file = self._find_source_for_test(test_file)
                if source_file is None or not source_file.is_file():
                    continue
                if self._is_sensitive_file(source_file):
                    continue

                try:
                    test_source = test_file.read_text(encoding="utf-8")
                    source_content = source_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue

                # Truncate for token limits
                test_truncated = test_source[:4000]
                source_truncated = source_content[:4000]

                # Check cache
                cache_key = self._get_cache_key(test_file, "hollow_test")
                cached = self._get_cached_result(cache_key)
                if cached is not None:
                    finding = self._parse_hollow_result(
                        cached,
                        str(test_file.relative_to(self.project_root)),
                    )
                    if finding:
                        findings.append(finding)
                    continue

                # Issue #1007 (Phase 3): wrap user-controlled repo content for
                # prompt-injection defense. test_source/source_under_test are
                # repo-controlled; test_path comes from validated traversal.
                response = self._analyzer.analyze(
                    HOLLOW_TEST_PROMPT,
                    test_path=str(test_file.relative_to(self.project_root)),
                    test_source=_safe_wrap(test_truncated),
                    source_under_test=_safe_wrap(source_truncated),
                )

                if not response:
                    continue

                result = self._parse_json_or_aligned(response)
                self._set_cached_result(cache_key, result)

                finding = self._parse_hollow_result(
                    result,
                    str(test_file.relative_to(self.project_root)),
                )
                if finding:
                    findings.append(finding)

        return findings

    def _find_source_for_test(self, test_file: Path) -> Optional[Path]:
        """Find the source file corresponding to a test file.

        Maps test_foo.py -> foo.py by searching lib/ and src/ directories.

        Args:
            test_file: Path to test file (e.g., tests/unit/test_foo.py).

        Returns:
            Path to source file or None if not found.
        """
        # Strip test_ prefix
        test_name = test_file.stem
        if not test_name.startswith("test_"):
            return None
        source_name = test_name[5:] + ".py"

        # Search in common source directories
        search_dirs = [
            self.project_root / "src",
            self.project_root / "lib",
            self.project_root / "plugins",
        ]

        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for candidate in search_dir.rglob(source_name):
                return candidate

        return None

    def _parse_hollow_result(
        self,
        result: Dict[str, Any],
        test_path: str,
    ) -> Optional[RefactorFinding]:
        """Convert parsed hollow test result into a RefactorFinding.

        Args:
            result: Parsed JSON result from GenAI.
            test_path: Relative path to the test file.

        Returns:
            RefactorFinding if test is HOLLOW or UNTESTED_SOURCE, None otherwise.
        """
        classification = result.get("classification", "").upper()
        reason = result.get("reason", "no reason provided")
        confidence = result.get("confidence", 0.5)

        if classification == "MEANINGFUL":
            return None

        if classification == "HOLLOW":
            description = f"[genai] Hollow test detected: {reason}"
            suggestion = "Refactor tests to verify actual behavior instead of mocking everything"

            # Escalate to Sonnet for detail
            if self._ensure_escalation_analyzer():
                # Issue #1007 (Phase 3): wrap user-controlled reason for
                # prompt-injection defense. reason is composed from heuristic
                # output that may include test source snippets.
                escalation = self._escalation_analyzer.analyze(
                    REFACTOR_ESCALATION_PROMPT,
                    file_path=test_path,
                    category="HOLLOW_TEST",
                    original_analysis=_safe_wrap(reason),
                )
                if escalation:
                    suggestion = f"[genai] {escalation}"

            return RefactorFinding(
                category=RefactorCategory.TEST_WASTE,
                severity=SweepSeverity.MEDIUM,
                file_path=test_path,
                description=description,
                suggestion=suggestion,
                optimization_type=OptimizationType.OPTIMIZATION,
                confidence=ConfidenceLevel.MEDIUM if confidence < 0.8 else ConfidenceLevel.HIGH,
            )

        if classification == "UNTESTED_SOURCE":
            return RefactorFinding(
                category=RefactorCategory.TEST_WASTE,
                severity=SweepSeverity.HIGH,
                file_path=test_path,
                description=f"[genai] Untested source code: {reason}",
                suggestion="Add tests for uncovered public functions/classes",
                optimization_type=OptimizationType.OPTIMIZATION,
                confidence=ConfidenceLevel.MEDIUM if confidence < 0.8 else ConfidenceLevel.HIGH,
            )

        return None

    # =========================================================================
    # Pass 3: Dead Code Verification
    # =========================================================================

    def _verify_dead_code(
        self,
        candidates: List[RefactorFinding],
    ) -> List[RefactorFinding]:
        """Verify structural dead code candidates with GenAI analysis.

        Args:
            candidates: Dead code findings from structural analysis.

        Returns:
            Verified dead code findings (confidence >= 0.7 only).
        """
        verified: List[RefactorFinding] = []

        if not self._ensure_genai_analyzer():
            return candidates  # Return unverified if GenAI unavailable

        for candidate in candidates:
            file_path = self.project_root / candidate.file_path
            if not file_path.is_file():
                verified.append(candidate)
                continue
            if self._is_sensitive_file(file_path):
                continue

            try:
                source_content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                verified.append(candidate)
                continue

            # Extract function name from description
            func_name = self._extract_function_name(candidate.description)
            if not func_name:
                verified.append(candidate)
                continue

            # Extract function source
            func_source = self._extract_function_source(source_content, func_name)
            if not func_source:
                func_source = f"# Could not extract source for {func_name}"

            # Build references summary
            references_summary = self._build_references_summary(func_name)

            # Check cache
            cache_key = self._get_cache_key(file_path, f"dead_code_{func_name}")
            cached = self._get_cached_result(cache_key)
            if cached is not None:
                if self._is_confirmed_dead(cached):
                    verified.append(RefactorFinding(
                        category=RefactorCategory.DEAD_CODE,
                        severity=candidate.severity,
                        file_path=candidate.file_path,
                        description=f"[genai] {candidate.description}",
                        suggestion=candidate.suggestion,
                        optimization_type=candidate.optimization_type,
                        line=candidate.line,
                        confidence=ConfidenceLevel.HIGH,
                    ))
                continue

            # Truncate for token limits
            func_truncated = func_source[:2000]

            # Issue #1007 (Phase 3): wrap user-controlled repo content for
            # prompt-injection defense. function_source and references_summary are
            # repo-controlled; file_path/function_name come from AST traversal.
            response = self._analyzer.analyze(
                DEAD_CODE_VERIFY_PROMPT,
                file_path=candidate.file_path,
                function_name=func_name,
                function_source=_safe_wrap(func_truncated),
                references_summary=_safe_wrap(references_summary),
            )

            if not response:
                verified.append(candidate)
                continue

            result = self._parse_json_or_aligned(response)
            self._set_cached_result(cache_key, result)

            if self._is_confirmed_dead(result):
                verified.append(RefactorFinding(
                    category=RefactorCategory.DEAD_CODE,
                    severity=candidate.severity,
                    file_path=candidate.file_path,
                    description=f"[genai] {candidate.description}",
                    suggestion=candidate.suggestion,
                    optimization_type=candidate.optimization_type,
                    line=candidate.line,
                    confidence=ConfidenceLevel.HIGH,
                ))

        return verified

    def _is_confirmed_dead(self, result: Dict[str, Any]) -> bool:
        """Check if a dead code verification result confirms the code is dead.

        Args:
            result: Parsed JSON from GenAI verification.

        Returns:
            True if verdict is DEAD and confidence >= threshold.
        """
        verdict = result.get("verdict", "").upper()
        confidence = result.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        return verdict == "DEAD" and confidence >= _DEAD_CODE_CONFIDENCE_THRESHOLD

    def _extract_function_name(self, description: str) -> Optional[str]:
        """Extract function name from a dead code finding description.

        Args:
            description: Finding description text.

        Returns:
            Function name if found, None otherwise.
        """
        # Match patterns like "Potentially dead function: foo_bar"
        # or "dead function: foo_bar" or "dead class: FooBar"
        match = re.search(r"(?:dead\s+(?:function|class|method)):\s*(\w+)", description, re.I)
        if match:
            return match.group(1)

        # Match "function 'foo_bar'" pattern
        match = re.search(r"function\s+['\"]?(\w+)['\"]?", description, re.I)
        if match:
            return match.group(1)

        return None

    def _extract_function_source(self, source: str, func_name: str) -> Optional[str]:
        """Extract a function's source code from a file.

        Args:
            source: Full file source code.
            func_name: Name of the function to extract.

        Returns:
            Function source code or None if not found.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == func_name:
                    lines = source.split("\n")
                    end_line = getattr(node, "end_lineno", node.lineno + 10)
                    return "\n".join(lines[node.lineno - 1:end_line])

        return None

    def _build_references_summary(self, func_name: str) -> str:
        """Build a summary of references to a function across the codebase.

        Args:
            func_name: Name to search for.

        Returns:
            Summary string of where the name appears.
        """
        references: List[str] = []
        search_dirs = [
            self.project_root / "plugins",
            self.project_root / "src",
            self.project_root / "lib",
            self.project_root / "tests",
        ]

        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for py_file in search_dir.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding="utf-8")
                    if func_name in content:
                        rel = str(py_file.relative_to(self.project_root))
                        count = content.count(func_name)
                        references.append(f"{rel}: {count} reference(s)")
                except (OSError, UnicodeDecodeError):
                    continue

        if not references:
            return "No references found in .py files"
        return "\n".join(references[:20])  # Limit to 20 refs

    # =========================================================================
    # Batch API Support
    # =========================================================================

    def _submit_batch(self, requests: List[Dict[str, Any]]) -> Optional[str]:
        """Submit batch of analysis requests to Anthropic Batch API.

        Args:
            requests: List of request dicts with 'custom_id' and 'prompt'.

        Returns:
            Batch ID if submission successful, None otherwise.
        """
        if not self.use_batch_api:
            return None

        try:
            from anthropic import Anthropic

            client = Anthropic()
            batch_requests = []

            for req in requests:
                batch_requests.append({
                    "custom_id": req["custom_id"],
                    "params": {
                        "model": DEFAULT_MODEL,
                        "max_tokens": 500,
                        "messages": [{"role": "user", "content": req["prompt"]}],
                        "system": REFACTOR_BATCH_SYSTEM_PROMPT,
                    },
                })

            batch = client.batches.create(requests=batch_requests)
            return batch.id

        except Exception as e:
            logger.debug("Batch submission failed: %s", e)
            return None

    def _poll_batch(self, batch_id: str) -> Optional[List[Dict[str, Any]]]:
        """Poll for batch results.

        Args:
            batch_id: ID of the batch to poll.

        Returns:
            List of result dicts or None if not ready/failed.
        """
        try:
            from anthropic import Anthropic

            client = Anthropic()
            batch = client.batches.retrieve(batch_id)

            if batch.processing_status != "ended":
                return None

            results = []
            for result in client.batches.results(batch_id):
                results.append({
                    "custom_id": result.custom_id,
                    "response": result.result.message.content[0].text
                    if result.result and result.result.message
                    else None,
                })

            return results

        except Exception as e:
            logger.debug("Batch polling failed: %s", e)
            return None

    # =========================================================================
    # Caching
    # =========================================================================

    def _get_cache_key(self, file_path: Path, prompt_name: str) -> str:
        """Generate cache key from file content and prompt.

        Args:
            file_path: Path to the file being analyzed.
            prompt_name: Name of the prompt template used.

        Returns:
            SHA-256 hash string as cache key.
        """
        try:
            content = file_path.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()
        except OSError:
            content_hash = "unknown"

        prompt_hash = hashlib.sha256(prompt_name.encode()).hexdigest()[:16]
        model_id = DEFAULT_MODEL

        raw_key = f"{model_id}:{prompt_hash}:{content_hash}"
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis result.

        Args:
            cache_key: SHA-256 cache key.

        Returns:
            Cached result dict or None if not cached.
        """
        cache_file = self._cache_dir / f"{cache_key}.json"
        if not cache_file.is_file():
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _set_cached_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Store analysis result in cache.

        Args:
            cache_key: SHA-256 cache key.
            result: Result dict to cache.
        """
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._cache_dir / f"{cache_key}.json"
            cache_file.write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
        except OSError:
            pass  # Cache write failure is non-critical

    # =========================================================================
    # Security Filtering
    # =========================================================================

    def _is_sensitive_file(self, path: Path) -> bool:
        """Check if a file should be excluded from analysis for security.

        Excludes .env, *.pem, *.key, and files with secret/credential/password
        in their name (case-insensitive).

        Args:
            path: Path to check.

        Returns:
            True if file is sensitive and should be excluded.
        """
        name_lower = path.name.lower()
        path_str_lower = str(path).lower()

        for pattern in _SENSITIVE_PATTERNS:
            if re.search(pattern, name_lower):
                return True
            if re.search(pattern, path_str_lower):
                return True

        return False
