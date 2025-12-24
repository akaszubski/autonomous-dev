# Test Summary: Issue #159 - Install Manifest Completeness Audit

## Overview

Comprehensive TDD test suite for validating install_manifest.json completeness after audit discovered orphaned files.

**Test File**: `tests/regression/smoke/test_install_manifest_completeness.py`
**Status**: RED phase (all tests failing as expected)
**Total Test Classes**: 7
**Total Test Methods**: 21

## Test Coverage

### 1. TestInstallManifestStructure (3 tests)
Tests basic manifest structure and validity.

- `test_manifest_exists` - Verifies manifest file exists
- `test_manifest_is_valid_json` - Validates JSON syntax
- `test_manifest_has_components_section` - Checks required sections exist

### 2. TestManifestAgentCompleteness (4 tests)
Tests that all 21 agent files on disk are in manifest.

- `test_manifest_has_21_agents` - Verifies count is 21 (currently 8, FAILING)
- `test_all_expected_agents_in_manifest` - Checks all expected agents present
- `test_no_extra_agents_in_manifest` - Ensures no unexpected agents
- `test_missing_13_orphaned_agents` - Validates orphaned agents added (FAILING)

**Missing Agents** (13):
- advisor.md
- alignment-analyzer.md
- alignment-validator.md
- brownfield-analyzer.md
- commit-message-generator.md
- pr-description-generator.md
- project-bootstrapper.md
- project-progress-tracker.md
- project-status-analyzer.md
- quality-validator.md
- researcher.md
- setup-wizard.md
- sync-validator.md

### 3. TestManifestCommandCompleteness (3 tests)
Tests that manifest includes correct command files.

- `test_manifest_has_8_commands` - Verifies count is 8 (PASSING)
- `test_all_expected_commands_in_manifest` - Checks all active commands present
- `test_deprecated_commands_not_in_manifest` - Ensures deprecated commands excluded

**Expected Commands** (8):
- advise.md
- align.md
- auto-implement.md
- batch-implement.md
- create-issue.md
- health-check.md
- setup.md
- sync.md

**Deprecated Commands** (should NOT be in manifest):
- align-project.md, align-claude.md, align-project-retrofit.md
- update-plugin.md, implement.md, research.md, plan.md
- review.md, test-feature.md, test.md, security-scan.md
- update-docs.md, pipeline-status.md, status.md

### 4. TestManifestHookCompleteness (3 tests)
Tests that all hook files on disk are in manifest.

- `test_missing_hooks_added_to_manifest` - Validates 6 missing hooks added (FAILING)
- `test_all_disk_hooks_in_manifest` - Checks all disk hooks present (FAILING)
- `test_no_phantom_hooks_in_manifest` - Ensures no phantom hooks

**Missing Hooks** (6):
- detect_feature_request.py
- log_agent_completion.py
- session_tracker.py
- auto_update_project_progress.py
- batch_permission_approver.py
- unified_pre_tool_use.py

### 5. TestManifestLibCompleteness (3 tests)
Tests that all library files on disk are in manifest.

- `test_missing_libs_added_to_manifest` - Validates 7 missing libs added (FAILING)
- `test_all_disk_libs_in_manifest` - Checks all disk libs present (FAILING)
- `test_no_phantom_libs_in_manifest` - Ensures no phantom libs

**Missing Libs** (7):
- genai_validate.py
- math_utils.py
- search_utils.py
- mcp_profile_manager.py
- mcp_server_detector.py
- git_hooks.py
- validate_documentation_parity.py

### 6. TestManifestVersionBump (3 tests)
Tests that manifest version is properly bumped.

- `test_version_bumped_from_3_40_0` - Verifies version > 3.40.0 (FAILING)
- `test_version_format_valid` - Validates semantic versioning format
- `test_generated_date_updated` - Checks date is current

### 7. TestManifestPathFormats (4 tests)
Tests that all manifest paths follow correct format.

- `test_agent_paths_format` - Verifies agent path format
- `test_command_paths_format` - Verifies command path format
- `test_hook_paths_format` - Verifies hook path format
- `test_lib_paths_format` - Verifies lib path format

## Test Execution Results

**Command**: `python3 -m pytest tests/regression/smoke/test_install_manifest_completeness.py --override-ini="addopts=" --tb=line -q`

**Results**:
- Total Tests: 21
- Passing: 14
- Failing: 7

**Failing Tests** (RED phase - expected):
1. `test_manifest_has_21_agents` - Found 8 agents, expected 21
2. `test_all_expected_agents_in_manifest` - Missing 13 agents
3. `test_missing_13_orphaned_agents` - Orphaned agents not in manifest
4. `test_missing_hooks_added_to_manifest` - Missing 6 hooks
5. `test_all_disk_hooks_in_manifest` - 6 disk hooks not in manifest
6. `test_missing_libs_added_to_manifest` - Missing 7 libs
7. `test_all_disk_libs_in_manifest` - 7 disk libs not in manifest

## Implementation Requirements

To make tests pass (GREEN phase), update `plugins/autonomous-dev/config/install_manifest.json`:

1. **Add 13 missing agents** to `components.agents.files`:
   ```json
   "plugins/autonomous-dev/agents/advisor.md",
   "plugins/autonomous-dev/agents/alignment-analyzer.md",
   "plugins/autonomous-dev/agents/alignment-validator.md",
   "plugins/autonomous-dev/agents/brownfield-analyzer.md",
   "plugins/autonomous-dev/agents/commit-message-generator.md",
   "plugins/autonomous-dev/agents/pr-description-generator.md",
   "plugins/autonomous-dev/agents/project-bootstrapper.md",
   "plugins/autonomous-dev/agents/project-progress-tracker.md",
   "plugins/autonomous-dev/agents/project-status-analyzer.md",
   "plugins/autonomous-dev/agents/quality-validator.md",
   "plugins/autonomous-dev/agents/researcher.md",
   "plugins/autonomous-dev/agents/setup-wizard.md",
   "plugins/autonomous-dev/agents/sync-validator.md"
   ```

2. **Add 6 missing hooks** to `components.hooks.files`:
   ```json
   "plugins/autonomous-dev/hooks/detect_feature_request.py",
   "plugins/autonomous-dev/hooks/log_agent_completion.py",
   "plugins/autonomous-dev/hooks/session_tracker.py",
   "plugins/autonomous-dev/hooks/auto_update_project_progress.py",
   "plugins/autonomous-dev/hooks/batch_permission_approver.py",
   "plugins/autonomous-dev/hooks/unified_pre_tool_use.py"
   ```

3. **Add 7 missing libs** to `components.lib.files`:
   ```json
   "plugins/autonomous-dev/lib/genai_validate.py",
   "plugins/autonomous-dev/lib/math_utils.py",
   "plugins/autonomous-dev/lib/search_utils.py",
   "plugins/autonomous-dev/lib/mcp_profile_manager.py",
   "plugins/autonomous-dev/lib/mcp_server_detector.py",
   "plugins/autonomous-dev/lib/git_hooks.py",
   "plugins/autonomous-dev/lib/validate_documentation_parity.py"
   ```

4. **Bump version** from 3.40.0 to 3.41.0 (or higher)

5. **Update generated date** to current date (YYYY-MM-DD format)

## Edge Cases Covered

1. **Path Format Validation** - All paths must follow correct prefix pattern
2. **No Phantom Files** - Manifest shouldn't reference non-existent files
3. **No Duplicates** - Files should appear exactly once in manifest
4. **Deprecated Exclusion** - Archived commands must NOT be in manifest
5. **Version Validation** - Semantic versioning format and bump verification
6. **Date Validation** - Generated date must be valid and not in future

## Next Steps

1. implementer agent will update install_manifest.json
2. Re-run tests to verify GREEN phase
3. Verify install.sh uses updated manifest
4. Test installation on clean system

## Related Files

- **Test File**: `tests/regression/smoke/test_install_manifest_completeness.py`
- **Manifest**: `plugins/autonomous-dev/config/install_manifest.json`
- **Issue**: GitHub #159
- **Related Test**: `tests/regression/smoke/test_install_manifest_commands.py` (validates 8 commands)
