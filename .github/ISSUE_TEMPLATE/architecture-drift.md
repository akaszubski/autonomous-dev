---
name: Architectural Drift (Automated)
about: Automatically created from GenAI architectural validation
labels: architecture, genai-detected, layer-2
assignees: ''
---

## Architectural Drift Detected

**Principle**: {{ principle_name }}
**Status**: {{ drift_status }}
**Severity**: {{ severity }}
**Layer**: Layer 2 (GenAI Architectural Validation)
**Date**: {{ date }}

---

## Documented Intent (ARCHITECTURE-OVERVIEW.md)

{{ documented_intent }}

---

## Current Implementation

{{ current_implementation }}

**Drift Details**:
{{ drift_details }}

---

## Impact Analysis

**Architectural Impact**: {{ architectural_impact }}
**Risk Level**: {{ risk_level }}
**Breaking Changes**: {{ breaking_changes }}

---

## Specific Findings

{{ specific_findings }}

**Affected Components**:
{{ affected_components }}

---

## Recommended Fix

{{ recommended_fix }}

**Action Items**:
{{ action_items }}

---

## Validation

**After Fix, Verify**:
- [ ] {{ validation_step_1 }}
- [ ] {{ validation_step_2 }}
- [ ] {{ validation_step_3 }}
- [ ] Re-run: `/test architecture`
- [ ] Confirm: 100% alignment

---

## Related Principles

{{ related_principles }}

---

## Priority

{{ priority }} - {{ priority_reasoning }}

---

*Auto-created by `/test architecture --track-issues`*
*See: [ARCHITECTURE-OVERVIEW.md](../../docs/ARCHITECTURE-OVERVIEW.md)*
