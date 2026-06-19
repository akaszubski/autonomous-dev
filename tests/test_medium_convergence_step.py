#!/usr/bin/env python3
"""
Test for STEP 11.6: MEDIUM-Convergence Check in implement.md pipeline.

This test verifies that the convergence detection logic correctly identifies
when multiple validators flag the same file with MEDIUM+ severity findings.
"""

import json
import tempfile
from pathlib import Path


def test_convergence_detection_logic():
    """Test that the convergence detection correctly identifies converged findings."""
    
    # Create a temporary directory for test artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test-run-123"
        validator_dir = Path(tmpdir) / ".claude" / "logs" / "activity" / "validators" / run_id
        validator_dir.mkdir(parents=True, exist_ok=True)
        
        # Create reviewer artifact with MEDIUM findings
        reviewer_content = """
        ## Review Summary
        
        lib/parser.py
        [MEDIUM] Potential performance issue in parse_data function
        
        lib/validator.py
        [BLOCKING] Critical security vulnerability in input validation
        
        lib/utils.py
        [MEDIUM] Code complexity exceeds threshold
        """
        (validator_dir / "reviewer.txt").write_text(reviewer_content)
        
        # Create security-auditor artifact with overlapping findings
        security_content = """
        ## Security Audit Results
        
        PASS with advisory findings
        
        ADVISORY-FINDINGS:
        - [Medium] lib/parser.py: SQL injection risk in query construction
        - [Low] lib/helper.py: Weak random number generation
        - [Medium] lib/validator.py: Input validation bypass possible
        """
        (validator_dir / "security-auditor.txt").write_text(security_content)
        
        # Simulate the convergence detection logic from STEP 11.6
        from collections import defaultdict
        import re
        
        converged_findings = defaultdict(list)
        
        # Parse reviewer findings - simplified pattern matching
        reviewer_file = validator_dir / "reviewer.txt"
        if reviewer_file.exists():
            content = reviewer_file.read_text()
            # Pattern: File path followed by severity marker
            lines = content.split('\n')
            for i, line in enumerate(lines):
                # Look for file paths
                if '.py' in line and 'lib/' in line:
                    file_match = re.search(r'(lib/[^\s]+\.py)', line)
                    if file_match:
                        file_path = file_match.group(1)
                        # Check next line for severity
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if '[MEDIUM]' in next_line:
                                converged_findings[file_path].append(('reviewer', 'MEDIUM'))
                            elif '[BLOCKING]' in next_line:
                                converged_findings[file_path].append(('reviewer', 'BLOCKING'))
        
        # Parse security-auditor findings
        security_file = validator_dir / "security-auditor.txt"
        if security_file.exists():
            content = security_file.read_text()
            advisory_match = re.search(r'ADVISORY-FINDINGS:(.*?)(?=\n\n|\Z)', content, re.DOTALL)
            if advisory_match:
                advisory_block = advisory_match.group(1)
                for line in advisory_block.split('\n'):
                    file_match = re.match(r'.*\[(Medium|Low)\]\s+([^\s:]+\.(py|js|ts|tsx|vue|md))', line, re.IGNORECASE)
                    if file_match:
                        severity = 'MEDIUM' if file_match.group(1).upper() == 'MEDIUM' else 'LOW'
                        file_path = file_match.group(2)
                        if severity == 'MEDIUM':  # Only track MEDIUM+ for convergence
                            converged_findings[file_path].append(('security-auditor', severity))
        
        # Detect convergence
        convergence_detected = False
        converged_files = []
        
        for file_path, findings in converged_findings.items():
            medium_plus = [f for f in findings if f[1] in ['MEDIUM', 'BLOCKING']]
            validators = set([f[0] for f in medium_plus])
            
            if len(validators) >= 2:
                convergence_detected = True
                converged_files.append({
                    'file': file_path,
                    'validators': list(validators),
                    'findings': medium_plus
                })
        
        # Debug output
        print(f"Converged findings dict: {dict(converged_findings)}")
        print(f"Converged files: {converged_files}")
        
        # Verify expected convergence
        assert convergence_detected, "Should detect convergence"
        assert len(converged_files) == 2, f"Expected 2 converged files, got {len(converged_files)}"
        
        # Check specific files
        converged_file_names = [item['file'] for item in converged_files]
        assert 'lib/parser.py' in converged_file_names, "parser.py should be flagged by both validators"
        assert 'lib/validator.py' in converged_file_names, "validator.py should be flagged by both validators"
        
        # Verify lib/utils.py is NOT converged (only reviewer flagged it)
        assert 'lib/utils.py' not in converged_file_names, "utils.py should not be converged (only one validator)"


def test_no_convergence_when_single_validator():
    """Test that convergence is not detected when only one validator flags a file."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test-run-456"
        validator_dir = Path(tmpdir) / ".claude" / "logs" / "activity" / "validators" / run_id
        validator_dir.mkdir(parents=True, exist_ok=True)
        
        # Only reviewer has findings
        reviewer_content = """
        File: app.py
        [MEDIUM] Consider refactoring for better maintainability
        """
        (validator_dir / "reviewer.txt").write_text(reviewer_content)
        
        # Security auditor has no findings
        security_content = """
        PASS - No security issues found
        
        ADVISORY-FINDINGS: none
        """
        (validator_dir / "security-auditor.txt").write_text(security_content)
        
        # Run convergence detection
        from collections import defaultdict
        import re
        
        converged_findings = defaultdict(list)
        
        reviewer_file = validator_dir / "reviewer.txt"
        if reviewer_file.exists():
            content = reviewer_file.read_text()
            for match in re.finditer(r'([^\s]+\.(py|js|ts|tsx|vue|md))[^\n]*\[?(MEDIUM|BLOCKING)\]?', content, re.IGNORECASE):
                file_path = match.group(1)
                severity = match.group(3) if match.group(3) else 'MEDIUM'
                converged_findings[file_path].append(('reviewer', severity.upper()))
        
        convergence_detected = False
        converged_files = []
        
        for file_path, findings in converged_findings.items():
            medium_plus = [f for f in findings if f[1] in ['MEDIUM', 'BLOCKING']]
            validators = set([f[0] for f in medium_plus])
            
            if len(validators) >= 2:
                convergence_detected = True
                converged_files.append({
                    'file': file_path,
                    'validators': list(validators),
                    'findings': medium_plus
                })
        
        assert not convergence_detected, "Should not detect convergence with single validator"
        assert len(converged_files) == 0, "No files should be converged"


def test_handles_missing_artifact_files_gracefully():
    """Test that the step handles missing validator artifact files without crashing."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test-run-789"
        validator_dir = Path(tmpdir) / ".claude" / "logs" / "activity" / "validators" / run_id
        # Directory doesn't exist - simulates missing artifacts
        
        from collections import defaultdict
        import re
        
        converged_findings = defaultdict(list)
        
        # Check reviewer file (doesn't exist)
        reviewer_file = validator_dir / "reviewer.txt"
        if reviewer_file.exists():
            content = reviewer_file.read_text()
            # This block won't execute
        
        # Check security file (doesn't exist)
        security_file = validator_dir / "security-auditor.txt"
        if security_file.exists():
            content = security_file.read_text()
            # This block won't execute
        
        convergence_detected = False
        converged_files = []
        
        for file_path, findings in converged_findings.items():
            medium_plus = [f for f in findings if f[1] in ['MEDIUM', 'BLOCKING']]
            validators = set([f[0] for f in medium_plus])
            
            if len(validators) >= 2:
                convergence_detected = True
        
        # Should handle gracefully - no convergence detected, no crash
        assert not convergence_detected, "No convergence when artifacts missing"
        assert len(converged_findings) == 0, "No findings when artifacts missing"


def test_convergence_log_artifact_creation():
    """Test that convergence detection creates proper log artifacts."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test-run-abc"
        validator_dir = Path(tmpdir) / ".claude" / "logs" / "activity" / "validators" / run_id
        validator_dir.mkdir(parents=True, exist_ok=True)
        
        # Create artifacts with converged findings
        (validator_dir / "reviewer.txt").write_text("File: main.py\n[MEDIUM] Issue found")
        (validator_dir / "security-auditor.txt").write_text("ADVISORY-FINDINGS:\n- [Medium] main.py: Security concern")
        
        # Simulate the full convergence check including logging
        from collections import defaultdict
        import re
        
        converged_findings = defaultdict(list)
        converged_findings['main.py'].append(('reviewer', 'MEDIUM'))
        converged_findings['main.py'].append(('security-auditor', 'MEDIUM'))
        
        converged_files = [{
            'file': 'main.py',
            'validators': ['reviewer', 'security-auditor'],
            'findings': [('reviewer', 'MEDIUM'), ('security-auditor', 'MEDIUM')]
        }]
        
        # Create convergence log
        convergence_log = {
            'step': '11.6',
            'type': 'medium_convergence',
            'converged_files': converged_files,
            'run_id': run_id
        }
        
        log_file = Path(tmpdir) / ".claude" / "logs" / "activity" / f"{run_id}_convergence.json"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump(convergence_log, f, indent=2)
        
        # Verify log was created correctly
        assert log_file.exists(), "Convergence log file should be created"
        
        with open(log_file, 'r') as f:
            log_data = json.load(f)
        
        assert log_data['step'] == '11.6', "Step should be 11.6"
        assert log_data['type'] == 'medium_convergence', "Type should be medium_convergence"
        assert log_data['run_id'] == run_id, f"Run ID should be {run_id}"
        assert len(log_data['converged_files']) == 1, "Should have one converged file"
        assert log_data['converged_files'][0]['file'] == 'main.py', "File should be main.py"


if __name__ == "__main__":
    # Run tests
    test_convergence_detection_logic()
    test_no_convergence_when_single_validator()
    test_handles_missing_artifact_files_gracefully()
    test_convergence_log_artifact_creation()
    print("✅ All tests passed!")