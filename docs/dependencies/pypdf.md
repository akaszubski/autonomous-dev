# pypdf Installation Guide

Installation guide for pypdf library (PDF parsing).

## Overview

`pypdf` is a pure Python PDF library for reading and extracting text from PDF files. It supports layout-aware text extraction and metadata parsing.

## Installation

```bash
# Via pip
pip install pypdf>=5.6.1

# Via conda
conda install -c conda-forge pypdf
```

## Verification

```python
import pypdf

# Test basic functionality
reader = pypdf.PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")
```

## Version Requirements

- **pypdf**: >= 5.6.1

## Related Documentation

- [Dependency Installation Guides](README.md)
- [Book Parser Library](../LIBRARIES.md) - See book_parser.py entry
- [pypdf Documentation](https://pypdf.readthedocs.io/)

**Last Updated**: 2026-01-29
