# PII Protection Strategies

Protect personally identifiable information (PII) in training datasets.

## Overview

Training data may contain sensitive information. PII protection prevents privacy breaches and ensures compliance.

## Common PII Types

| Type | Examples | Risk Level |
|------|----------|------------|
| Names | "John Smith" | High |
| Emails | "user@example.com" | High |
| Phone | "+1-555-0123" | High |
| SSN | "123-45-6789" | Critical |
| Credit cards | "4111-1111-1111-1111" | Critical |
| Addresses | "123 Main St" | Medium |
| IPs | "192.168.1.1" | Medium |

## Protection Methods

### 1. Format-Preserving Encryption (FPE)

Encrypt while maintaining format:

```python
# Pseudo-code
from cryptography.fernet import Fernet

def fpe_protect(text, key):
    """Encrypt PII while preserving format."""
    # Email: user@example.com → xyz@example.com
    # Phone: +1-555-0123 → +1-555-9876
    pass
```

### 2. Differential Privacy

Add noise to protect individuals:

```python
# Pseudo-code
def add_differential_privacy(dataset, epsilon=1.0):
    """Add calibrated noise for privacy."""
    # ε = 1.0: Standard privacy guarantee
    # Lower ε = stronger privacy, more noise
    pass
```

### 3. Tokenization

Replace PII with tokens:

```python
def tokenize_pii(text):
    """Replace PII with safe tokens."""
    import re

    # Emails
    text = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]', text)

    # Phone numbers
    text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[PHONE]', text)

    # SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)

    return text
```

## Best Practices

1. **Detect before training**: Scan datasets for PII
2. **Use FPE when possible**: Preserves data utility
3. **Tokenize high-risk PII**: SSN, credit cards
4. **Apply differential privacy**: For aggregated statistics
5. **Audit regularly**: Re-scan datasets periodically

## Compliance

- **GDPR**: European data protection
- **CCPA**: California privacy law
- **HIPAA**: Healthcare data (US)
- **SOC 2**: Security standards

## Related

- See `dpo-metrics.md` for data quality
- External: Presidio (Microsoft PII detection)
- External: cryptography library (Python)
