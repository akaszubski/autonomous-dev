"""Regression tests - bug fixes and feature validation (< 30 seconds).

Regression tests protect against known bugs and validate features.
Each test documents the bug/feature it protects against.

Coverage:
- Security fixes (v3.4.1, v3.2.3, etc.)
- Feature implementations (v3.4.0, v3.3.0, etc.)
- Bug fixes from CHANGELOG
- Security audit findings

Organization:
- test_security_*.py - Security fixes and vulnerabilities
- test_feature_*.py - Feature implementations
- test_bugfix_*.py - Bug fixes
"""
