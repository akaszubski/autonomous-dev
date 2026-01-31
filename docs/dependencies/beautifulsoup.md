# BeautifulSoup Installation Guide

Installation guide for BeautifulSoup4 library (HTML/XML parsing).

## Overview

`beautifulsoup4` is a Python library for parsing HTML and XML documents. It provides easy navigation and text extraction from web content.

## Installation

```bash
# Via pip (with lxml parser)
pip install beautifulsoup4>=4.14.3 lxml

# Via conda
conda install -c conda-forge beautifulsoup4 lxml
```

## Verification

```python
from bs4 import BeautifulSoup

# Test basic functionality
html = "<html><body><p>Test</p></body></html>"
soup = BeautifulSoup(html, 'lxml')
print(soup.get_text())
```

## Version Requirements

- **beautifulsoup4**: >= 4.14.3
- **lxml**: >= 4.0 (recommended parser)

## Related Documentation

- [Dependency Installation Guides](README.md)
- [Book Parser Library](../LIBRARIES.md) - See book_parser.py entry
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

**Last Updated**: 2026-01-29
