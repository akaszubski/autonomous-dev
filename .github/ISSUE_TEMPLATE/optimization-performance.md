---
name: System Optimization (Automated)
about: Automatically created from system performance analysis
labels: optimization, cost-reduction, layer-3
assignees: ''
---

## Optimization Opportunity

**Component**: {{ component_name }}
**Type**: {{ optimization_type }}
**Layer**: Layer 3 (System Performance)
**Date**: {{ date }}

---

## Current State

{{ current_state }}

**Metrics**:
- **Model**: {{ current_model }}
- **Avg Tokens**: {{ avg_tokens }}/invocation
- **Avg Cost**: ${{ avg_cost }}/invocation
- **Monthly Cost**: ${{ monthly_cost }} ({{ monthly_invocations }} invocations)
- **Annual Cost**: ${{ annual_cost }}

---

## Proposed Change

{{ proposed_change }}

**New Metrics**:
- **Model**: {{ proposed_model }}
- **Avg Tokens**: {{ proposed_tokens }}/invocation
- **Avg Cost**: ${{ proposed_cost }}/invocation
- **Monthly Cost**: ${{ proposed_monthly_cost }}
- **Annual Cost**: ${{ proposed_annual_cost }}

---

## Cost-Benefit Analysis

**Savings**:
- **Per Invocation**: ${{ savings_per_invocation }} ({{ savings_percent }}%)
- **Monthly**: ${{ monthly_savings }}
- **Annual**: ${{ annual_savings }}

**Implementation**:
- **Time Required**: {{ implementation_time }}
- **Complexity**: {{ complexity }}
- **ROI**: {{ roi }}

---

## Risk Assessment

**Risk Level**: {{ risk_level }}

**Reasoning**: {{ risk_reasoning }}

**Mitigation**:
{{ risk_mitigation }}

---

## Action Items

1. {{ action_item_1 }}
2. {{ action_item_2 }}
3. {{ action_item_3 }}
4. {{ action_item_4 }}

---

## Testing Plan

**Validation Steps**:
- [ ] {{ test_step_1 }}
- [ ] {{ test_step_2 }}
- [ ] {{ test_step_3 }}
- [ ] Monitor quality for {{ monitoring_period }}
- [ ] Roll back if quality degrades

**Success Criteria**:
- ✅ {{ success_criterion_1 }}
- ✅ {{ success_criterion_2 }}
- ✅ {{ success_criterion_3 }}

---

## Expected Outcome

{{ expected_outcome }}

**Metrics After Implementation**:
- Cost reduction: {{ cost_reduction }}%
- Time impact: {{ time_impact }}
- Quality impact: {{ quality_impact }}

---

## Priority

{{ priority }} - {{ priority_reasoning }}

**Category**: {{ category }}

---

*Auto-created by `/test system-performance --track-issues`*
*See: [SYSTEM-PERFORMANCE-GUIDE.md](docs/SYSTEM-PERFORMANCE-GUIDE.md)*
