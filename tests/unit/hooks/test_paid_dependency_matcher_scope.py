"""Lock the paid-dependency gate to write-tool scope (Issue #1639 follow-up).

The `validate_paid_dependency` sidecar shipped with `matcher: "*"` while all five
shipping settings templates bind the same gate with the narrow write-tool matcher.
`scripts/generate_hook_config.py` copies the sidecar matcher verbatim into
`config/global_settings_template.json` -- the surface `install.sh:530` consumes -- so
the wildcard would have attached a 5-second subprocess to EVERY Bash/Read/Grep/Task
call in every repo installing global settings.

Why this file exists alongside `test_ci_hook_enforcement.py`:
    `test_hook_sidecar_consistency_check` only asserts the generator reports no drift.
    It goes green under BOTH resolutions -- the correct one (narrow the sidecar) and
    the harmful one (regenerate with the wildcard). It therefore cannot protect this
    invariant. These tests fail if someone sets the sidecar matcher back to `"*"`
    and regenerates.

Both sources are read dynamically; no expected matcher string is hardcoded as the
authority (the templates are the authority).
"""

import json
import re
from pathlib import Path

import pytest

# tests/unit/hooks/test_x.py -> hooks -> unit -> tests -> repo root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_PLUGIN = _PROJECT_ROOT / "plugins" / "autonomous-dev"
_SIDECAR = _PLUGIN / "hooks" / "validate_paid_dependency.hook.json"
_GENERATED_SETTINGS = _PLUGIN / "config" / "global_settings_template.json"
_TEMPLATE_DIR = _PLUGIN / "templates"

_HOOK_SCRIPT = "validate_paid_dependency.py"

#: The five shipping settings templates that bind this gate.
_SHIPPING_TEMPLATES = (
    "settings.default.json",
    "settings.autonomous-dev.json",
    "settings.strict-mode.json",
    "settings.granular-bash.json",
    "settings.permission-batching.json",
)

#: Claude Code wildcard sentinel. NOT a valid regex -- `re.fullmatch("*", x)` raises
#: `re.error: nothing to repeat`. The generator itself treats it as a sentinel
#: (scripts/generate_hook_config.py:274 partitions on `matcher != "*"`).
_WILDCARD = "*"


def _tool_matches(matcher: str, tool_name: str) -> bool:
    """Model Claude Code matcher semantics: wildcard sentinel, else regex fullmatch.

    Args:
        matcher: Matcher string from a settings entry.
        tool_name: Tool name to test, e.g. "Write" or "Bash".

    Returns:
        True if the matcher would route `tool_name` to the hook.
    """
    if matcher in (_WILDCARD, ""):
        return True
    return re.fullmatch(matcher, tool_name) is not None


def _paid_gate_matchers(settings: dict) -> list[str]:
    """Extract every PreToolUse matcher bound to the paid-dependency hook."""
    found = []
    for entries in settings.get("hooks", {}).get("PreToolUse", []):
        for hook in entries.get("hooks", []):
            if _HOOK_SCRIPT in str(hook.get("command", "")):
                found.append(entries.get("matcher", _WILDCARD))
    return found


def _sidecar_matcher() -> str:
    data = json.loads(_SIDECAR.read_text())
    registrations = data["registrations"]
    assert len(registrations) == 1, (
        f"Expected exactly 1 registration in {_SIDECAR.name}, got {len(registrations)}. "
        "This test reads registrations[0]; update it if the sidecar gains registrations."
    )
    return registrations[0]["matcher"]


def test_instrument_control_wildcard_is_distinguishable() -> None:
    """CONTROL ON THE CONTROL: the instrument must tell the two matchers apart.

    If the wildcard did NOT admit "Bash", this instrument could not represent the
    broken state, every downstream assertion would be vacuous, and the whole file
    would be void. Assert the positive control before trusting any other cell.
    """
    # Positive control: the BROKEN matcher admits Bash. This is the harm being blocked.
    assert _tool_matches(_WILDCARD, "Bash") is True, (
        "INSTRUMENT VOID: wildcard matcher did not admit 'Bash', so this test "
        "cannot distinguish the broken sidecar from the fixed one."
    )
    assert _tool_matches(_WILDCARD, "Read") is True
    assert _tool_matches(_WILDCARD, "Write") is True

    # Negative control: a narrow matcher refuses Bash. Both arms of the instrument
    # are now observed, so a later pass is informative rather than structural.
    narrow = "Write|Edit|MultiEdit|NotebookEdit|mcp__.*"
    assert _tool_matches(narrow, "Bash") is False, (
        "INSTRUMENT VOID: narrow matcher admitted 'Bash'; instrument cannot refuse."
    )
    assert _tool_matches(narrow, "Write") is True


def test_sidecar_matcher_is_not_the_wildcard() -> None:
    """The sidecar MUST NOT bind the paid gate to every tool."""
    matcher = _sidecar_matcher()
    assert matcher != _WILDCARD, (
        "validate_paid_dependency.hook.json declares matcher '*'. Regenerating from "
        "this sidecar attaches a 5s subprocess to EVERY Bash/Read/Grep/Task call in "
        "every repo installing global settings. Use the write-tool matcher the five "
        "shipping settings templates already use."
    )


@pytest.mark.parametrize("template_name", _SHIPPING_TEMPLATES)
def test_sidecar_matcher_agrees_with_shipping_template(template_name: str) -> None:
    """Cross-validate: sidecar matcher MUST equal each shipping template's matcher.

    The templates are the authority; the sidecar is the thing that drifted.
    """
    template_path = _TEMPLATE_DIR / template_name
    template_matchers = _paid_gate_matchers(json.loads(template_path.read_text()))
    assert template_matchers, (
        f"{template_name} does not bind {_HOOK_SCRIPT} at all. Either the gate was "
        "unregistered (update this test) or a template lost its binding (fix it)."
    )
    sidecar = _sidecar_matcher()
    for template_matcher in template_matchers:
        assert sidecar == template_matcher, (
            f"Matcher drift: sidecar={sidecar!r} but {template_name}="
            f"{template_matcher!r}. The generated global_settings_template.json "
            "follows the sidecar, so this drift ships a different scope to global "
            "installs than to template installs."
        )


def test_generated_settings_matcher_admits_write_and_refuses_bash_and_read() -> None:
    """Both arms on the GENERATED surface that install.sh actually consumes.

    Regex-simulation, not payload-piping: validate_paid_dependency.py:171 opens with
    `if not is_write(tool_name, tool_input): return`, so a piped Bash payload reports
    "not intercepted" under BOTH the broken and the fixed matcher. Only the matcher
    string itself distinguishes them.
    """
    matchers = _paid_gate_matchers(json.loads(_GENERATED_SETTINGS.read_text()))
    assert len(matchers) == 1, (
        f"Expected exactly 1 paid-gate binding in {_GENERATED_SETTINGS.name}, "
        f"got {len(matchers)}: {matchers!r}"
    )
    matcher = matchers[0]

    # Positive arm: the gate must still fire on the tools it exists to police.
    assert _tool_matches(matcher, "Write") is True, (
        f"matcher {matcher!r} would not intercept Write -- the gate is dead."
    )
    assert _tool_matches(matcher, "Edit") is True

    # Negative arms: the gate must NOT fire on read-only / shell tools.
    assert _tool_matches(matcher, "Bash") is False, (
        f"matcher {matcher!r} intercepts Bash: a 5s subprocess on every shell call."
    )
    assert _tool_matches(matcher, "Read") is False, (
        f"matcher {matcher!r} intercepts Read: a 5s subprocess on every file read."
    )
