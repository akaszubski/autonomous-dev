"""
Ideators Package - Specialized analyzers for different improvement categories

This package contains specialized analyzer modules for different categories
of improvement opportunities:

- security_ideator: Security vulnerability detection
- performance_ideator: Performance bottleneck detection
- quality_ideator: Code quality issue detection
- accessibility_ideator: Accessibility and UX issue detection
- tech_debt_ideator: Technical debt pattern detection

Each ideator implements an analyze() method that returns List[IdeationResult].
"""

from autonomous_dev.lib.ideators.security_ideator import SecurityIdeator
from autonomous_dev.lib.ideators.performance_ideator import PerformanceIdeator
from autonomous_dev.lib.ideators.quality_ideator import QualityIdeator
from autonomous_dev.lib.ideators.accessibility_ideator import AccessibilityIdeator
from autonomous_dev.lib.ideators.tech_debt_ideator import TechDebtIdeator

__all__ = [
    'SecurityIdeator',
    'PerformanceIdeator',
    'QualityIdeator',
    'AccessibilityIdeator',
    'TechDebtIdeator',
]
