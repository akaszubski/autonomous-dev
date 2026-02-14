# GRPO Verifier Types and Implementation

Complete guide to implementing verifiers for different task types in GRPO training.

## Verifier Design Principles

### Key Properties

1. **Objective**: Deterministic correctness evaluation (no human judgment)
2. **Fast**: <1 second per verification (training efficiency)
3. **Reliable**: Low false positive rate (<5%)
4. **Comprehensive**: High coverage of correct solutions

### Verifier Interface

```python
from typing import Protocol

class Verifier(Protocol):
    """Standard verifier interface for GRPO."""

    def verify(self, prompt: str, response: str) -> float:
        """Verify response correctness.

        Args:
            prompt: Original task/question
            response: Model-generated response

        Returns:
            score: 0.0-1.0 (0.0 = wrong, 1.0 = correct)
        """
        ...
```

## 1. Symbolic Solver Verifier (Math)

**Use Case**: Algebra, calculus, symbolic math problems

**Verifiability**: 95%+ (exact symbolic comparison)

### Implementation

```python
from sympy import sympify, solve, simplify, Eq
from sympy.parsing.sympy_parser import parse_expr

class SymbolicMathVerifier:
    """Verify math answers using symbolic solver."""

    def verify(self, prompt: str, response: str) -> float:
        """Verify math answer with SymPy."""
        try:
            # Extract equation from prompt
            equation = self._extract_equation(prompt)

            # Solve symbolically
            expected_solutions = solve(equation)

            # Parse response
            provided_answer = self._parse_answer(response)

            # Check if provided answer matches any expected solution
            for expected in expected_solutions:
                if simplify(provided_answer - expected) == 0:
                    return 1.0

            return 0.0

        except Exception as e:
            # Malformed response or unparseable
            return 0.0

    def _extract_equation(self, prompt: str) -> Eq:
        """Extract equation from prompt text."""
        # Example: "Solve for x: 2x + 5 = 15"
        parts = prompt.split(":")
        equation_str = parts[1].strip()

        # Parse equation
        left, right = equation_str.split("=")
        return Eq(parse_expr(left), parse_expr(right))

    def _parse_answer(self, response: str):
        """Parse answer from response text."""
        # Extract final answer (various formats)
        # "x = 5" or "The answer is 5" or just "5"
        if "=" in response:
            answer_str = response.split("=")[-1].strip()
        else:
            # Take last line as answer
            answer_str = response.strip().split("\n")[-1]

        return sympify(answer_str)
```

### Example Usage

```python
verifier = SymbolicMathVerifier()

# Correct answer
score = verifier.verify(
    "Solve for x: 2x + 5 = 15",
    "2x + 5 = 15\n2x = 10\nx = 5"
)
assert score == 1.0

# Incorrect answer
score = verifier.verify(
    "Solve for x: 2x + 5 = 15",
    "x = 10"
)
assert score == 0.0
```

## 2. Execution Sandbox Verifier (Code)

**Use Case**: Python, JavaScript, SQL code generation

**Verifiability**: 90%+ (depends on test coverage)

### Implementation

```python
import subprocess
import tempfile
import json
from pathlib import Path

class CodeExecutionVerifier:
    """Verify code by executing test cases in sandbox."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def verify(self, prompt: str, response: str) -> float:
        """Verify code with test cases."""
        try:
            # Extract test cases from prompt
            test_cases = self._extract_tests(prompt)

            # Extract code from response
            code = self._extract_code(response)

            # Run test cases
            passed = 0
            for test_input, expected_output in test_cases:
                if self._run_test(code, test_input, expected_output):
                    passed += 1

            # Return pass rate
            return passed / len(test_cases) if test_cases else 0.0

        except Exception as e:
            return 0.0

    def _extract_tests(self, prompt: str) -> list:
        """Extract test cases from prompt."""
        # Example format:
        # Test 1: input="hello", output="olleh"
        # Test 2: input="world", output="dlrow"
        tests = []
        for line in prompt.split("\n"):
            if line.startswith("Test"):
                # Parse test case
                parts = line.split(":")
                test_data = parts[1].strip()
                # Extract input and output
                # ... (parsing logic)
                tests.append((test_input, expected_output))
        return tests

    def _extract_code(self, response: str) -> str:
        """Extract code block from response."""
        # Extract ```python ... ``` blocks
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            return response[start:end].strip()
        return response.strip()

    def _run_test(self, code: str, test_input: str, expected_output: str) -> bool:
        """Run single test case in sandbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to file
            code_file = Path(tmpdir) / "solution.py"
            code_file.write_text(code)

            # Run with test input
            result = subprocess.run(
                ["python", str(code_file)],
                input=test_input.encode(),
                capture_output=True,
                timeout=self.timeout,
                cwd=tmpdir
            )

            # Check output
            actual_output = result.stdout.decode().strip()
            return actual_output == expected_output
```

### Docker Sandbox (Production)

```python
import docker

class DockerCodeVerifier:
    """Production-grade code verifier with Docker isolation."""

    def __init__(self):
        self.client = docker.from_env()
        self.image = "python:3.11-slim"

    def verify(self, prompt: str, response: str) -> float:
        """Verify code in isolated Docker container."""
        try:
            code = self._extract_code(response)
            test_cases = self._extract_tests(prompt)

            passed = 0
            for test_input, expected_output in test_cases:
                # Run in container
                # SECURITY: Use list format to prevent command injection (CWE-94)
                container = self.client.containers.run(
                    self.image,
                    ["python", "-c", code],  # Safe: list format properly escapes
                    stdin_open=True,
                    detach=True,
                    mem_limit="256m",
                    cpu_quota=50000
                )

                # Provide input
                container.attach(stdin=True).send(test_input.encode())

                # Get output
                result = container.wait(timeout=5)
                output = container.logs().decode().strip()

                # Clean up
                container.remove()

                # Check correctness
                if output == expected_output:
                    passed += 1

            return passed / len(test_cases)

        except Exception as e:
            return 0.0
```

## 3. Knowledge Base Verifier (Factual QA)

**Use Case**: Factual questions with known answers

**Verifiability**: 85%+ (depends on KB coverage)

### Implementation

```python
import json
from typing import Dict

class KnowledgeBaseVerifier:
    """Verify factual answers against knowledge base."""

    def __init__(self, kb_path: str):
        with open(kb_path) as f:
            self.kb = json.load(f)

    def verify(self, prompt: str, response: str) -> float:
        """Verify factual answer against KB."""
        try:
            # Normalize question
            question = self._normalize_question(prompt)

            # Lookup correct answer
            correct_answer = self.kb.get(question)

            if not correct_answer:
                # Unknown question (return neutral score)
                return 0.5

            # Normalize response
            provided_answer = self._normalize_answer(response)

            # Exact match
            if provided_answer == correct_answer["exact"]:
                return 1.0

            # Fuzzy match (aliases)
            if provided_answer in correct_answer.get("aliases", []):
                return 1.0

            # Partial match (contains key terms)
            if all(term in provided_answer for term in correct_answer.get("key_terms", [])):
                return 0.8

            return 0.0

        except Exception as e:
            return 0.0

    def _normalize_question(self, prompt: str) -> str:
        """Normalize question for KB lookup."""
        # Remove "What is", "Who is", etc.
        prompt = prompt.lower().strip()
        for prefix in ["what is", "who is", "when was", "where is"]:
            if prompt.startswith(prefix):
                prompt = prompt[len(prefix):].strip()
        return prompt.rstrip("?")

    def _normalize_answer(self, response: str) -> str:
        """Normalize answer for comparison."""
        # Extract main answer (remove explanation)
        answer = response.split(".")[0].strip()
        return answer.lower()
```

### Knowledge Base Format

```json
{
  "capital of france": {
    "exact": "paris",
    "aliases": ["paris, france", "city of paris"],
    "key_terms": ["paris"]
  },
  "president of the united states in 2024": {
    "exact": "joe biden",
    "aliases": ["biden", "joseph biden"],
    "key_terms": ["biden"]
  }
}
```

## 4. Regex/Parser Verifier (Format Compliance)

**Use Case**: JSON, XML, email, structured output validation

**Verifiability**: 95%+ (deterministic parsing)

### Implementation

```python
import json
import re
from typing import Optional

class FormatComplianceVerifier:
    """Verify output matches required format."""

    def verify(self, prompt: str, response: str) -> float:
        """Verify format compliance."""
        # Extract required format from prompt
        format_type = self._extract_format(prompt)

        # Verify based on format type
        if format_type == "json":
            return self._verify_json(response)
        elif format_type == "email":
            return self._verify_email(response)
        elif format_type == "xml":
            return self._verify_xml(response)
        elif format_type == "csv":
            return self._verify_csv(response)
        else:
            return 0.0

    def _verify_json(self, response: str) -> float:
        """Verify valid JSON."""
        try:
            json.loads(response)
            return 1.0
        except json.JSONDecodeError:
            return 0.0

    def _verify_email(self, response: str) -> float:
        """Verify valid email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, response.strip()):
            return 1.0
        return 0.0

    def _verify_xml(self, response: str) -> float:
        """Verify valid XML."""
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(response)
            return 1.0
        except ET.ParseError:
            return 0.0

    def _verify_csv(self, response: str) -> float:
        """Verify valid CSV."""
        try:
            import csv
            from io import StringIO
            reader = csv.reader(StringIO(response))
            rows = list(reader)
            # Check all rows have same column count
            if rows and all(len(row) == len(rows[0]) for row in rows):
                return 1.0
            return 0.0
        except:
            return 0.0
```

## Verifier Selection Guide

| Task | Verifier Type | Implementation Complexity | Verifiability |
|------|---------------|---------------------------|---------------|
| Algebra | Symbolic Solver | Medium | 95%+ |
| Calculus | Symbolic Solver | Medium | 90%+ |
| Python code | Execution Sandbox | High | 95%+ |
| JavaScript code | Execution Sandbox | High | 90%+ |
| SQL queries | Execution Sandbox | High | 85%+ |
| Factual QA | Knowledge Base | Low | 85%+ |
| Email format | Regex | Low | 99%+ |
| JSON format | Parser | Low | 99%+ |
| XML format | Parser | Low | 99%+ |

## Best Practices

1. **Start simple**: Use regex/parser for format tasks before complex verifiers
2. **Timeout protection**: Always set execution timeouts (prevent infinite loops)
3. **Error handling**: Return 0.0 on verification errors (conservative)
4. **Test coverage**: More test cases = higher verifiability
5. **Sandbox isolation**: Use Docker/containers for untrusted code
6. **False positive monitoring**: Track and minimize (<5% target)

## Common Issues

| Issue | Detection | Solution |
|-------|-----------|----------|
| **Slow verification** | >1s per response | Optimize verifier, use caching |
| **False positives** | High score, low quality | Add more test cases, stricter logic |
| **False negatives** | Low score, high quality | Support answer variations, aliases |
| **Timeout errors** | Verification hangs | Add timeout, kill stuck processes |
| **Security issues** | Code escapes sandbox | Use Docker, restrict permissions |

## References

1. SymPy documentation: https://docs.sympy.org
2. Docker Python SDK: https://docker-py.readthedocs.io
3. Python subprocess security: https://docs.python.org/3/library/subprocess.html
