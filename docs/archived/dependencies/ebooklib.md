# ebooklib Installation Guide

Installation guide for ebooklib library (EPUB parsing).

## Overview

`ebooklib` is a Python library for reading and writing EPUB files. It provides metadata extraction and content parsing.

## Installation

```bash
# Via pip
pip install ebooklib>=0.20

# Via conda
conda install -c conda-forge ebooklib
```

## Verification

```python
import ebooklib
from ebooklib import epub

# Test basic functionality
book = epub.read_epub("document.epub")
print(f"Title: {book.get_metadata('DC', 'title')}")
```

## Version Requirements

- **ebooklib**: >= 0.20

## Related Documentation

- [Dependency Installation Guides](README.md)
- [Book Parser Library](../LIBRARIES.md) - See book_parser.py entry
- [ebooklib Documentation](https://github.com/aerkalov/ebooklib)

**Last Updated**: 2026-01-29
