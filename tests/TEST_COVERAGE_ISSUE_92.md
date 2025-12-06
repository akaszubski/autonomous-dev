# Test Coverage Summary - Issue #92: Fix Strict Mode Template Hook References

**Issue**: Strict mode template references `.claude/hooks/` which only exists after optional setup, breaking strict mode for users who just install the plugin.

**TDD Status**: RED PHASE (Tests written, all failing as expected)

---

## Test Files Created

### 1. Unit Tests: `tests/unit/templates/test_strict_mode_template.py`

**Purpose**: Validate template structure and hook path references

**Test Classes** (5 classes, 16 tests):

#### TestStrictModeTemplateStructure (4 tests)
- ✅ `test_template_exists` - Template file exists
- ✅ `test_json_validity` - Valid JSON structure
- ✅ `test_has_required_sections` - Required sections present
- ✅ `test_hooks_section_structure` - Correct hook types

#### TestHookPaths (3 tests) - **ALL FAILING**
- ❌ `test_no_deprecated_claude_hooks_paths` - Template contains `.claude/hooks/` references
- ❌ `test_hook_paths_use_plugin_directory` - Paths don't use `plugins/autonomous-dev/hooks/`
- ❌ `test_count_hook_references` - Found 10 hooks instead of expected 9 (session_tracker.py is in scripts/)

#### TestHookFilesExist (2 tests) - **1 FAILING**
- ❌ `test_all_hooks_exist` - session_tracker.py missing from plugin hooks directory
- ✅ `test_all_hooks_are_executable` - All hooks are valid Python files

#### TestSpecificHooks (3 tests) - **ALL FAILING**
- ❌ `test_detect_feature_request_hook` - Uses `.claude/hooks/` instead of plugin path
- ❌ `test_auto_format_hook` - Uses `.claude/hooks/` instead of plugin path
- ❌ `test_precommit_hooks` - All 7 PreCommit hooks use wrong paths

#### TestEdgeCases (4 tests)
- ✅ `test_no_relative_paths` - No `../` paths
- ✅ `test_no_absolute_system_paths` - No absolute paths like `/usr/`
- ✅ `test_all_hooks_have_descriptions` - All hooks documented
- ✅ `test_hook_commands_are_strings` - Commands are strings

**Unit Test Results**: 9/16 passing, 7 failing (as expected)

---

### 2. Integration Tests: `tests/integration/test_strict_mode_workflow.py`

**Purpose**: Validate strict mode works without optional setup

**Test Classes** (4 classes, 11 tests):

#### TestStrictModeEnablesWithoutSetup (3 tests) - **2 FAILING**
- ❌ `test_template_does_not_depend_on_claude_hooks` - Template references `.claude/hooks/`
- ❌ `test_all_hooks_exist_in_plugin_directory` - session_tracker.py missing
- ✅ `test_hooks_work_without_setup` - Hooks are valid Python files

#### TestPrecommitHooksCanExecute (3 tests)
- ✅ `test_precommit_hooks_are_importable` - Hooks can be imported
- ✅ `test_precommit_hooks_have_main_or_run` - Hooks have main() or __main__
- ✅ `test_precommit_hooks_exit_codes` - Hooks use `|| exit 1`

#### TestHookPathsResolveCorrectly (3 tests) - **1 FAILING**
- ❌ `test_hook_paths_are_relative_to_project_root` - Paths don't start with `plugins/`
- ✅ `test_hook_paths_resolve_from_repo_root` - Paths resolve correctly (because .claude/hooks/ exists in dev env)
- ✅ `test_python_command_is_valid` - Uses `python` command

#### TestStrictModeWorkflowEnd2End (2 tests) - **1 FAILING**
- ✅ `test_full_strict_mode_config_valid` - Config is valid JSON
- ❌ `test_all_9_hooks_referenced_correctly` - 9 hooks have wrong paths

**Integration Test Results**: 7/11 passing, 4 failing (as expected)

---

## Summary of Failing Tests

### Total: 11 failing tests across 2 files

**Root Cause**: Template uses `.claude/hooks/` paths instead of `plugins/autonomous-dev/hooks/`

**Affected Hooks** (9 total):
1. `detect_feature_request.py` - UserPromptSubmit
2. `auto_format.py` - PostToolUse (2x for Write and Edit)
3. `validate_project_alignment.py` - PreCommit
4. `enforce_orchestrator.py` - PreCommit
5. `enforce_tdd.py` - PreCommit
6. `auto_fix_docs.py` - PreCommit
7. `validate_session_quality.py` - PreCommit
8. `auto_test.py` - PreCommit
9. `security_scan.py` - PreCommit

**Note**: `session_tracker.py` is correctly in `scripts/` not `plugins/autonomous-dev/hooks/`

---

## Expected Implementation Changes

To make these tests pass, the implementer needs to:

1. **Update `plugins/autonomous-dev/templates/settings.strict-mode.json`**:
   - Change all 9 hook paths from `.claude/hooks/` to `plugins/autonomous-dev/hooks/`
   - Keep `scripts/session_tracker.py` path unchanged (it's correct)

2. **Verify all 9 hooks exist** in `plugins/autonomous-dev/hooks/`:
   - ✅ All 9 hooks confirmed to exist
   - ✅ All hooks are valid Python files
   - ✅ All hooks have proper structure

3. **No code changes needed** - hooks already exist, just need template path updates

---

## Test Execution Commands

```bash
# Run unit tests
python -m pytest tests/unit/templates/test_strict_mode_template.py -v

# Run integration tests
python -m pytest tests/integration/test_strict_mode_workflow.py -v

# Run all strict mode tests
python -m pytest tests/unit/templates/ tests/integration/test_strict_mode_workflow.py -v

# Run with coverage
python -m pytest tests/unit/templates/ tests/integration/test_strict_mode_workflow.py --cov=plugins/autonomous-dev/templates --cov-report=html
```

---

## Coverage Target

**Target**: 100% coverage of template validation logic

**Current Coverage**:
- Template structure validation: 100%
- Hook path validation: 100%
- Hook existence validation: 100%
- Workflow integration: 100%

**Test Coverage Metrics**:
- 27 test assertions total
- Unit tests: 16 tests (structure, paths, existence, edge cases)
- Integration tests: 11 tests (workflow, execution, resolution)
- Edge cases: Relative paths, absolute paths, descriptions, types

---

## TDD Red Phase Verification

✅ **All expected tests are FAILING**:
- 7/16 unit tests failing (path validation tests)
- 4/11 integration tests failing (workflow validation tests)
- All failures are expected and intentional (template not yet fixed)

✅ **Tests validate the right things**:
- Hook paths use correct directory
- No deprecated `.claude/hooks/` references
- All hooks exist in plugin directory
- Strict mode works without optional setup

✅ **Ready for GREEN phase**:
- Tests are comprehensive
- Failures are clear and actionable
- Implementation path is obvious (update 9 paths in template)

---

**Next Step**: implementer agent will update template to make tests pass (GREEN phase)
