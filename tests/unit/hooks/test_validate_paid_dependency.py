"""Regression tests for the PROJECT.md paid-dependency alignment gate (Issue #1639).

The gate this replaces (``validate_project_alignment.py``) refused nothing in
11,872 opportunities because it was a ``"type": "utility"`` CLI markdown linter
bound in none of the 9 settings surfaces and emitting zero deny decisions.

Every arm below drives the hook END TO END as a subprocess with real JSON on
stdin -- the transport the runtime actually uses -- so a guard that can only be
proven by importing a helper cannot pass these.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# tests/unit/hooks/test_x.py -> hooks[0] -> unit[1] -> tests[2] -> repo root[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "plugins/autonomous-dev/hooks/validate_paid_dependency.py"
HOOK_MANIFEST = REPO_ROOT / "plugins/autonomous-dev/hooks/validate_paid_dependency.hook.json"

# Every settings template that ships a PreToolUse chain. settings.local.json is
# deliberately excluded: hooks there double-fire against settings.json (#1183).
BOUND_TEMPLATES = [
    "settings.autonomous-dev.json",
    "settings.default.json",
    "settings.granular-bash.json",
    "settings.permission-batching.json",
    "settings.strict-mode.json",
]


def run_hook(payload: dict) -> str:
    """Drive the hook as a subprocess and return its permissionDecision.

    Args:
        payload: A PreToolUse envelope written to the hook's stdin.

    Returns:
        ``"deny"`` when the hook refuses, otherwise ``"allow"``.
    """
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert proc.returncode == 0, f"hook must never crash the tool call: {proc.stderr}"
    if not proc.stdout.strip():
        return "allow"
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


# --------------------------------------------------------------------------
# ARM 1 -- REFUSES. The arm that had never happened before Issue #1639.
# --------------------------------------------------------------------------


def test_refuses_paid_client_construction_in_production_code() -> None:
    """A Write introducing Anthropic(api_key=...) into production code is denied."""
    decision = run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "scripts/new_benchmark.py",
                "content": "from anthropic import Anthropic\nclient = Anthropic(api_key=api_key)\n",
            },
        }
    )
    assert decision == "deny", "paid-API client in production code must be refused"


def test_refuses_the_real_live_violation_in_the_tree() -> None:
    """The real scripts/run_reviewer_benchmark.py content is refused as a new write.

    This is the real-world REFUSES case named in Issue #1639, not a synthetic
    string. Whether that file is deleted is Issue #1688's call -- this test only
    asserts the gate would refuse it as a NEW introduction.
    """
    real = REPO_ROOT / "scripts/run_reviewer_benchmark.py"
    # If #1688 deletes the file, the gate must still refuse re-introducing it,
    # so fall back to the exact offending construction rather than skipping.
    content = (
        real.read_text(encoding="utf-8")
        if real.exists()
        else "from anthropic import Anthropic\n\nclient = Anthropic(api_key=api_key)\n"
    )
    decision = run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "scripts/run_reviewer_benchmark.py",
                "content": content,
            },
        }
    )
    assert decision == "deny", "the live positive case must be refused"


# --------------------------------------------------------------------------
# ARM 2 -- PERMITS. A guard that cannot permit is not a guard.
# --------------------------------------------------------------------------


def test_permits_ordinary_production_write() -> None:
    """Production code with no credential-bearing construction passes through."""
    decision = run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "plugins/autonomous-dev/lib/adder.py",
                "content": "def add(a: int, b: int) -> int:\n    return a + b\n",
            },
        }
    )
    assert decision == "allow", "ordinary production code must not be refused"


def test_permits_function_signature_with_api_key_default() -> None:
    """`def helper(api_key=None)` DECLARES a parameter; it constructs nothing.

    False-positive control: without the def-stripping the naive regex reads a
    signature as a call and the gate cries wolf on every credential-passing
    helper in the repo.
    """
    decision = run_hook(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "plugins/autonomous-dev/lib/helper.py",
                "content": "def helper(api_key=None):\n    return api_key\n",
            },
        }
    )
    assert decision == "allow", "a parameter default is not a client construction"


# --------------------------------------------------------------------------
# ARM 3 -- NEGATIVE CONTROLS OF A DIFFERENT SHAPE.
# The gate must key on the construction in production code, not on a vendor
# name appearing anywhere in the tree.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file_path,content",
    [
        # A test fixture may legitimately construct a client behind a mock.
        (
            "tests/unit/test_bench.py",
            "from anthropic import Anthropic\nclient = Anthropic(api_key='x')\n",
        ),
        ("tests/conftest.py", "client = Anthropic(api_key='x')\n"),
        # Documentation describing the API is prose, not a dependency.
        ("docs/guides/llm.md", "Call `Anthropic(api_key=KEY)` to reach the API.\n"),
        ("README.md", "Anthropic(api_key=...) is used by the optional benchmark.\n"),
    ],
)
def test_permits_paid_client_string_outside_production_python(
    file_path: str, content: str
) -> None:
    """The same offending shape in a test or docs file is allowed."""
    decision = run_hook(
        {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}
    )
    assert decision == "allow", f"{file_path} is not production Python; must not be refused"


# --------------------------------------------------------------------------
# ARM 4 -- NOVEL SHAPES. The rule is shape-based, so a vendor nobody enumerated
# is caught. This is the anti-allowlist arm (#1682): remove the category, do not
# list its members.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vendor_snippet",
    [
        "c = AcmeQuantumLLM(\n    api_token=os.environ['ACME'],\n)",  # novel vendor, multiline
        "c = VoltCloud(access_token=T)",  # novel vendor, novel kwarg
        "c = zeta.Client(secret_key=S)",  # dotted module factory
        "c = make_client(subscription_key=K)",  # lowercase factory, not a class
    ],
)
def test_refuses_novel_paid_client_shapes_never_enumerated(vendor_snippet: str) -> None:
    """Vendors and kwargs that appear nowhere in the hook source are still caught."""
    hook_source = HOOK.read_text(encoding="utf-8")
    callee = vendor_snippet.split("(")[0].split("=")[-1].strip()
    assert callee not in hook_source, (
        f"{callee!r} must NOT be enumerated in the hook -- if it is, this arm proves "
        "an allowlist rather than a shape rule"
    )
    decision = run_hook(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/service.py",
                "old_string": "pass",
                "new_string": vendor_snippet,
            },
        }
    )
    assert decision == "deny", f"novel paid-client shape must be refused: {vendor_snippet}"


def test_refuses_paid_client_via_mcp_write_transport() -> None:
    """Transport independence: an MCP editor write is classified and refused too.

    Keys on tool_intent.is_write (#1503), so a new write transport does not
    become a hole in this gate.
    """
    decision = run_hook(
        {
            "tool_name": "mcp__serena__replace_symbol_body",
            "tool_input": {
                "relative_path": "src/deep.py",
                "name_path": "f",
                "body": "def f():\n    return VoltCloud(access_token=T)\n",
            },
        }
    )
    assert decision == "deny", "MCP write transports must not bypass the gate"


# --------------------------------------------------------------------------
# SURFACE BINDING -- the failure mode that made the old gate inert.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("template_name", BOUND_TEMPLATES)
def test_gate_is_bound_in_every_shipping_template(template_name: str) -> None:
    """A hook bound in no settings surface never runs. Consumer templates included.

    A self-only binding in settings.autonomous-dev.json reaches no consumer --
    that is #1679's measured blind spot.
    """
    template = REPO_ROOT / "plugins/autonomous-dev/templates" / template_name
    settings = json.loads(template.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for block in settings.get("hooks", {}).get("PreToolUse", [])
        for hook in block["hooks"]
    ]
    assert any("validate_paid_dependency.py" in c for c in commands), (
        f"{template_name} does not bind the paid-dependency gate on PreToolUse"
    )


def test_local_template_stays_hook_free() -> None:
    """Negative control: settings.local.json must NOT bind it (double-fire, #1183)."""
    template = REPO_ROOT / "plugins/autonomous-dev/templates/settings.local.json"
    assert "validate_paid_dependency" not in template.read_text(encoding="utf-8"), (
        "hooks in settings.local.json double-fire against settings.json (#1183)"
    )


def test_hook_manifest_declares_a_lifecycle_registration() -> None:
    """The old gate's manifest said "type": "utility" -- so it was never an event."""
    manifest = json.loads(HOOK_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["type"] == "lifecycle", "a utility manifest binds to no event"
    events = [r["event"] for r in manifest["registrations"]]
    assert "PreToolUse" in events, f"must register on PreToolUse, got {events}"


def test_hook_is_listed_in_the_install_manifest() -> None:
    """An unshipped hook cannot reach a consumer repo."""
    manifest = json.loads(
        (REPO_ROOT / "plugins/autonomous-dev/config/install_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    files = manifest["components"]["hooks"]["files"]
    assert any(f.endswith("validate_paid_dependency.py") for f in files)
    assert any(f.endswith("validate_paid_dependency.hook.json") for f in files)


# --------------------------------------------------------------------------
# FAIL-CLOSED -- a guard that evaporates when the stack is damaged is not a guard.
# --------------------------------------------------------------------------

_FAULT_RUNNER = '''
import sys, runpy
FAULT = {fault!r}
if FAULT:
    class _Blocker:
        def find_spec(self, name, path=None, target=None):
            if name == "tool_intent":
                raise ImportError("injected fault: tool_intent")
            return None
    sys.meta_path.insert(0, _Blocker())
sys.argv = [{hook!r}]
runpy.run_path({hook!r}, run_name="__main__")
'''


def _run_with_fault(tmp_path: Path, *, fault: bool, payload: dict) -> str:
    """Run the hook with tool_intent import optionally sabotaged.

    A sys.path shadow does NOT work here: the hook's own preamble inserts the
    real lib dir at position 0 afterwards, so the fault silently never lands
    and the probe reports a false REFUSES. meta_path cannot be outranked.
    """
    runner = tmp_path / f"runner_{fault}.py"
    runner.write_text(_FAULT_RUNNER.format(fault=fault, hook=str(HOOK)))
    proc = subprocess.run(
        [sys.executable, str(runner)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    if fault:
        assert "injected fault" in proc.stderr or proc.stdout.strip(), (
            "positive control: the fault must actually land, else this arm proves nothing"
        )
    if not proc.stdout.strip():
        return "allow"
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


_OFFENDING = {
    "tool_name": "Write",
    "tool_input": {"file_path": "src/pay.py", "content": "c = Anthropic(api_key=k)\n"},
}
_CLEAN = {
    "tool_name": "Write",
    "tool_input": {"file_path": "src/ok.py", "content": "def f():\n    return 1\n"},
}


def test_control_unfaulted_run_still_permits_and_refuses(tmp_path: Path) -> None:
    """Negative controls for the fault harness: without the fault, both arms hold."""
    assert _run_with_fault(tmp_path, fault=False, payload=_CLEAN) == "allow"
    assert _run_with_fault(tmp_path, fault=False, payload=_OFFENDING) == "deny"


def test_refuses_when_the_classifier_cannot_be_imported(tmp_path: Path) -> None:
    """With tool_intent unimportable the gate denies instead of failing open.

    Before this, hook_safety turned the ImportError into a LOUD fail-open, so
    the gate vanished precisely when the enforcement stack was broken.
    """
    assert _run_with_fault(tmp_path, fault=True, payload=_OFFENDING) == "deny", (
        "classifier loss must fail CLOSED, matching the 8 guards in proof_of_block.py"
    )


def test_gate_emits_an_actionable_next_action_on_refusal() -> None:
    """Stick+carrot: a block the model cannot act on trains it to retry blindly."""
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "src/pay.py",
                    "content": "c = Anthropic(api_key=k)\n",
                },
            }
        ),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "REQUIRED NEXT ACTION" in reason
    assert "PROJECT.md" in reason, "the refusal must cite the rule it enforces"
