# Test Regression Audit - 2025-12-16

## Summary

Audited 270 test files to recommend which should be moved to regression suite.

## Recommendations

### SMOKE (Tier 0 - Critical Path)

These tests protect functionality that MUST work for the plugin to function at all.
Move to: `tests/regression/smoke/`

| Current Location | Test File | Why Critical |
|------------------|-----------|--------------|
| `unit/` | `test_install_bootstrap.py` | install.sh bootstrap functions |
| `unit/` | `test_install_manifest_commands.py` | Manifest parsing |
| `unit/` | `test_install_validation.py` | Install validation |
| `unit/` | `test_health_check.py` | /health-check command |
| `unit/lib/` | `test_sync_dispatcher.py` | /sync core functionality |
| `unit/lib/` | `test_settings_generator.py` | settings.json generation |
| `unit/lib/` | `test_settings_generator_validation.py` | Settings validation |
| `unit/lib/` | `test_orphan_file_cleaner.py` | Orphan cleanup (recent fix) |
| `unit/` | `test_unified_hooks.py` | Hook system (Issue #144) |

**Total: 9 files → smoke**

---

### REGRESSION (Tier 1 - Feature Protection)

These tests protect released features from breaking. One file per feature/issue.
Move to: `tests/regression/regression/`

| Current Location | Test File | Feature/Issue Protected |
|------------------|-----------|------------------------|
| `unit/lib/` | `test_batch_state_manager.py` | Batch processing (Issue #88) |
| `unit/lib/` | `test_batch_retry_manager.py` | Batch retry (Issue #89) |
| `unit/lib/` | `test_batch_git_integration.py` | Batch git (Issue #93) |
| `unit/lib/` | `test_mcp_permission_validator.py` | MCP security (Issue #95) |
| `unit/lib/` | `test_mcp_profile_manager.py` | MCP profiles (Issue #95) |
| `unit/` | `test_skill_loader.py` | Skill loading (Issue #143) |
| `unit/` | `test_skill_compliance.py` | Skill compliance |
| `unit/` | `test_skill_allowed_tools.py` | Skill tools (Issue #146) |
| `unit/hooks/` | `test_auto_git_workflow.py` | Git automation |
| `unit/hooks/` | `test_auto_approve_tool.py` | Auto-approval (v3.40.0) |
| `unit/lib/` | `test_sync_dispatcher_marketplace.py` | Marketplace sync |
| `unit/lib/` | `test_sync_dispatcher_settings_merge.py` | Settings merge |
| `unit/lib/` | `test_user_state_manager.py` | User state persistence |
| `unit/lib/` | `test_agent_tracker_issue79.py` | Tracking portability (#79) |
| `security/` | `test_mcp_bypass_prevention.py` | MCP security |
| `security/` | `test_tool_auto_approval_security.py` | Auto-approval security |

**Total: 16 files → regression**

---

### ALREADY IN REGRESSION (Keep)

| Location | Test File | Status |
|----------|-----------|--------|
| `regression/smoke/` | `test_command_routing.py` | ✅ Keep |
| `regression/smoke/` | `test_install_sync_critical.py` | ✅ Keep |
| `regression/smoke/` | `test_plugin_loading.py` | ✅ Keep |
| `regression/regression/` | `test_claude2_compliance.py` | ✅ Keep |
| `regression/regression/` | `test_feature_v3_3_0_parallel_validation.py` | ✅ Keep |
| `regression/regression/` | `test_feature_v3_4_0_project_progress.py` | ✅ Keep |
| `regression/regression/` | `test_security_v3_4_1_race_condition.py` | ✅ Keep |

---

### KEEP AS UNIT TESTS

These are fine as unit tests - they test implementation details, not released features:
- `test_math_utils.py` - Pure utility
- `test_search_utils.py` - Internal helper
- `test_error_*.py` - Error handling internals
- `test_issue*_*.py` - Issue-specific fixes (already tested)
- `test_phase*.py` - Performance optimization phases
- `test_pipeline_*.py` - Pipeline internals
- Most skill tests (testing skill content, not loading)

---

## Migration Commands

```bash
# SMOKE (Tier 0)
mv tests/unit/test_install_bootstrap.py tests/regression/smoke/
mv tests/unit/test_install_manifest_commands.py tests/regression/smoke/
mv tests/unit/test_install_validation.py tests/regression/smoke/
mv tests/unit/test_health_check.py tests/regression/smoke/
mv tests/unit/lib/test_sync_dispatcher.py tests/regression/smoke/
mv tests/unit/lib/test_settings_generator.py tests/regression/smoke/
mv tests/unit/lib/test_settings_generator_validation.py tests/regression/smoke/
mv tests/unit/lib/test_orphan_file_cleaner.py tests/regression/smoke/
mv tests/unit/test_unified_hooks.py tests/regression/smoke/

# REGRESSION (Tier 1)
mv tests/unit/lib/test_batch_state_manager.py tests/regression/regression/test_feature_v3_24_0_batch_state.py
mv tests/unit/lib/test_batch_retry_manager.py tests/regression/regression/test_feature_v3_33_0_batch_retry.py
mv tests/unit/lib/test_batch_git_integration.py tests/regression/regression/test_feature_v3_36_0_batch_git.py
mv tests/unit/lib/test_mcp_permission_validator.py tests/regression/regression/test_feature_v3_37_0_mcp_security.py
mv tests/unit/lib/test_mcp_profile_manager.py tests/regression/regression/test_feature_v3_37_0_mcp_profiles.py
mv tests/unit/test_skill_loader.py tests/regression/regression/test_feature_v3_43_0_skill_loader.py
mv tests/unit/test_skill_compliance.py tests/regression/regression/test_feature_v3_43_0_skill_compliance.py
mv tests/unit/test_skill_allowed_tools.py tests/regression/regression/test_feature_v3_43_0_skill_tools.py
mv tests/unit/hooks/test_auto_git_workflow.py tests/regression/regression/test_feature_v3_12_0_auto_git.py
mv tests/unit/hooks/test_auto_approve_tool.py tests/regression/regression/test_feature_v3_40_0_auto_approve.py
mv tests/unit/lib/test_sync_dispatcher_marketplace.py tests/regression/regression/test_feature_v3_41_0_sync_marketplace.py
mv tests/unit/lib/test_sync_dispatcher_settings_merge.py tests/regression/regression/test_feature_v3_41_0_sync_settings.py
mv tests/unit/lib/test_user_state_manager.py tests/regression/regression/test_feature_v3_12_0_user_state.py
mv tests/unit/lib/test_agent_tracker_issue79.py tests/regression/regression/test_feature_v3_28_0_tracking.py
mv tests/security/test_mcp_bypass_prevention.py tests/regression/regression/test_security_v3_37_0_mcp_bypass.py
mv tests/security/test_tool_auto_approval_security.py tests/regression/regression/test_security_v3_40_0_approval.py
```

---

## Impact

**Before Migration:**
- Smoke: 3 files (40 tests)
- Regression: 4 files

**After Migration:**
- Smoke: 12 files (~150 tests)
- Regression: 20 files (~200 tests)

**Coverage:**
- install.sh: Protected
- /sync: Protected
- /health-check: Protected
- Settings generation: Protected
- MCP security: Protected
- Skill loading: Protected
- Batch processing: Protected
- Git automation: Protected
