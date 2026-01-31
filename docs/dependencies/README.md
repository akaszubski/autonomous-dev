# Dependency Installation Guides

Installation guides for optional and required dependencies used by autonomous-dev features.

## Quick Reference

| Dependency | Purpose | Required | Platform | Guide |
|-----------|---------|----------|----------|-------|
| `pypdf` | PDF parsing for book extraction | Optional | All | [pypdf.md](pypdf.md) |
| `ebooklib` | EPUB parsing for book extraction | Optional | All | [ebooklib.md](ebooklib.md) |
| `beautifulsoup4` | HTML/XML parsing for web content | Optional | All | [beautifulsoup.md](beautifulsoup.md) |
| `python-magic` | File type detection by content (magic bytes) | Optional* | Linux/macOS | [python-magic.md](python-magic.md) |
| `python-magic-bin` | File type detection by content (Windows variant) | Optional* | Windows | [python-magic.md](python-magic.md) |
| `chardet` | Encoding detection for text files | Optional | All | [python-magic.md](python-magic.md#encoding-detection) |

*python-magic is optional - book_parser falls back to extension-based detection if not installed.

## Installation Modes

### Quick Install (Recommended)
```bash
# Install all book parsing dependencies at once
pip install -r plugins/autonomous-dev/requirements-book-parsing.txt
```

### Selective Installation
```bash
# Only PDF support
pip install pypdf>=5.6.1

# Only EPUB support
pip install ebooklib>=0.20

# Only HTML support
pip install beautifulsoup4>=4.14.3 lxml>=4.0

# Magic-based file detection (Linux/macOS)
pip install python-magic>=0.4.27

# Magic-based file detection (Windows)
pip install python-magic-bin>=0.4.14

# Encoding detection
pip install chardet>=5.0
```

### Development Environment
```bash
# Install all development dependencies (includes book parsing)
pip install -r plugins/autonomous-dev/requirements-dev.txt
```

### Conda
```bash
# Install all dependencies via conda (handles system libraries automatically)
conda install -c conda-forge pypdf ebooklib beautifulsoup4 lxml python-magic chardet
```

## Feature Integration

### Book Parsing (Issue #274)

The book parsing infrastructure uses these dependencies:

- **pypdf** (PDF parsing): Used by `book_parser.parse_pdf()` with layout extraction mode
- **ebooklib** (EPUB parsing): Used by `book_parser.parse_epub()` with metadata extraction
- **beautifulsoup4** (HTML parsing): Used by `book_parser.parse_html()` with encoding detection
- **python-magic** (File detection): Used by `book_parser.detect_format()` with fallback to extension-based detection
- **chardet** (Encoding detection): Used by `text_cleaner.detect_encoding()` with utf-8 fallback

Related modules:
- `plugins/autonomous-dev/lib/book_parser.py` (711 lines) - PDF/EPUB/HTML parsing with security validation
- `plugins/autonomous-dev/lib/text_cleaner.py` (402 lines) - Text normalization and encoding repair
- `plugins/autonomous-dev/lib/training_metrics.py` - Extended with BookParsingQuality validation

## Troubleshooting

### Generic Issues
- If a dependency import fails, see the specific guide above
- Use `pip install --upgrade <package>` to update to latest version
- For conda environments, use `conda update <package>`

### Platform-Specific Issues
- **Linux**: Most dependencies available via apt/yum - see specific guides
- **macOS**: Use Homebrew for system libraries (libmagic)
- **Windows**: Use `python-magic-bin` instead of `python-magic`

### Version Requirements
All dependencies have specific minimum versions - see [requirements-book-parsing.txt](../../plugins/autonomous-dev/requirements-book-parsing.txt)

## References

- [Book Parsing Guide](#) - How to use the book parsing infrastructure
- [Security & File Validation](../security/file-signature-validation.md) - File signature validation details
- [Training Data Extraction](#) - Best practices for training data preparation

---

**Last Updated**: 2026-01-29
