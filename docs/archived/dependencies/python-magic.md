# python-magic Installation Guide

Comprehensive installation guide for python-magic and libmagic dependency.

## Overview

`python-magic` is a Python wrapper for libmagic, which detects file types using "magic bytes" (file signatures). Unlike relying solely on file extensions, magic bytes provide more reliable file type detection and help prevent security issues like fake file extensions.

**Note**: python-magic is an **optional dependency** for book parsing. If not installed, the system falls back to extension-based detection.

## Platform-Specific Installation

### Linux (Debian/Ubuntu)

```bash
# Install libmagic system library
sudo apt-get update
sudo apt-get install libmagic1

# Install Python wrapper
pip install python-magic>=0.4.27
```

**Troubleshooting**:
- If you get "libmagic.so.1: cannot open shared object file", the system library wasn't installed
- Use `dpkg -l | grep libmagic` to verify installation

### Linux (RHEL/CentOS/Fedora)

```bash
# Install libmagic system library
sudo yum install file-libs

# Install Python wrapper
pip install python-magic>=0.4.27
```

**Alternative (Fedora/newer RHEL)**:
```bash
sudo dnf install file-libs
pip install python-magic>=0.4.27
```

### macOS

```bash
# Install libmagic via Homebrew
brew install libmagic

# Install Python wrapper
pip install python-magic>=0.4.27
```

**Troubleshooting**:
- If Homebrew is not installed: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- If you get "library not loaded" errors, try: `brew reinstall libmagic`

### Windows

Windows doesn't have a native libmagic library, but there's a special package that includes pre-compiled binaries:

```bash
# Install python-magic-bin (includes libmagic binaries)
pip install python-magic-bin>=0.4.14
```

**Note**: Use `python-magic-bin` instead of `python-magic` on Windows. The `-bin` variant includes the libmagic DLL files.

### Conda Environments

For conda users across all platforms:

```bash
conda install -c conda-forge python-magic
```

This automatically handles the libmagic dependency for your platform.

## Verification

After installation, verify it works:

```python
import magic

# Test basic functionality
mime_type = magic.from_file('/path/to/file.pdf', mime=True)
print(mime_type)  # Should print: application/pdf
```

## Version Requirements

- **python-magic**: >= 0.4.27
- **libmagic**: >= 5.0 (system library)

Check your version:

```python
import magic
print(magic.__version__)  # Should be >= 0.4.27
```

## Common Issues

### Issue: "No module named 'magic'"

**Solution**: Install python-magic:
```bash
pip install python-magic>=0.4.27
```

### Issue: "ImportError: failed to find libmagic"

**Cause**: Python wrapper is installed, but system library (libmagic) is missing.

**Solution**:
- **Linux**: Install `libmagic1` or `file-libs` (see platform instructions above)
- **macOS**: `brew install libmagic`
- **Windows**: Use `python-magic-bin` instead of `python-magic`

### Issue: "OSError: cannot load library 'magic'"

**Cause**: Conflicting magic packages (filemagic vs python-magic).

**Solution**:
```bash
# Uninstall all magic packages
pip uninstall magic filemagic python-magic python-magic-bin

# Reinstall correct package
pip install python-magic>=0.4.27  # Linux/macOS
pip install python-magic-bin>=0.4.14  # Windows
```

### Issue: Version mismatch

**Cause**: Old version of python-magic installed.

**Solution**:
```bash
pip install --upgrade python-magic>=0.4.27
```

## Fallback Behavior

If python-magic is not installed, book_parser falls back to extension-based detection:

```python
# With magic (preferred)
detect_format("suspicious.pdf")  # Detects actual content type

# Without magic (fallback)
detect_format("book.pdf")  # Uses .pdf extension
```

**Security Note**: Extension-based detection is less secure. A file named `malicious.pdf` could actually be an executable. Magic bytes provide content validation.

## Integration with book_parser

The `book_parser` module uses python-magic for:

1. **Format auto-detection** - `detect_format(file_path)`
2. **Security validation** - Verify file signature matches extension
3. **Mismatch detection** - Log warnings when extension != actual content

Example usage:

```python
from plugins.autonomous_dev.lib.book_parser import parse_book

# Auto-detects format using magic (if available)
book = parse_book("document.pdf")
```

## Alternative: Extension-Only Mode

If you don't need magic-based detection, you can explicitly specify the format:

```python
# Skip magic detection, use explicit format
book = parse_book("document.pdf", format="pdf")
```

This avoids the magic dependency entirely.

## Testing

The test suite handles magic gracefully:

```python
# Tests use pytest.importorskip
magic = pytest.importorskip("magic", minversion="0.4.27")
```

Tests that require magic are automatically skipped if not installed.

## Related Documentation

- [Dependency Installation Guides](README.md)
- [Book Parser Library](../LIBRARIES.md) - See book_parser.py entry
- [Optional Dependencies](../../plugins/autonomous-dev/requirements-book-parsing.txt)

## References

- **python-magic GitHub**: https://github.com/ahupp/python-magic
- **libmagic (file)**: https://www.darwinsys.com/file/
- **python-magic-bin (Windows)**: https://pypi.org/project/python-magic-bin/

**Last Updated**: 2026-01-29
