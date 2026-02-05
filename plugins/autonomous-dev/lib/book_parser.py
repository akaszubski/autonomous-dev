"""Book parsing library with optional python-magic support.

This module provides file format detection and book parsing capabilities.
python-magic is optional - without it, detection falls back to file extensions.

Usage:
    from plugins.autonomous_dev.lib.book_parser import parse_book, detect_format

    # With magic (if installed): uses file signatures
    # Without magic: uses file extension
    format = detect_format("document.pdf")
    book = parse_book("document.pdf")
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import magic

# Lazy-load magic to avoid import errors
_magic: Optional["magic"] = None
_magic_import_error: Optional[str] = None

def _try_import_magic() -> bool:
    """Try to import python-magic.

    Returns:
        bool: True if magic is available, False otherwise.
    """
    global _magic, _magic_import_error

    if _magic is not None:
        return True

    if _magic_import_error is not None:
        return False

    try:
        import magic as magic_module
        _magic = magic_module
        return True
    except ImportError as e:
        _magic_import_error = _format_import_error(e)
        return False


def _format_import_error(error: ImportError) -> str:
    """Format a helpful error message with platform-specific instructions.

    Args:
        error: The ImportError that occurred.

    Returns:
        str: Formatted error message with installation instructions.
    """
    platform = sys.platform

    if "libmagic" in str(error).lower() or "failed to find" in str(error).lower():
        # Python wrapper installed but system library missing
        if platform == "darwin":
            install_cmd = "brew install libmagic"
        elif platform == "win32":
            install_cmd = "pip install python-magic-bin>=0.4.14"
        else:  # Linux
            install_cmd = "sudo apt-get install libmagic1  # Debian/Ubuntu\n       sudo yum install file-libs  # RHEL/CentOS"
    else:
        # Python wrapper not installed
        if platform == "win32":
            install_cmd = "pip install python-magic-bin>=0.4.14"
        else:
            install_cmd = "pip install python-magic>=0.4.27"

    return (
        f"python-magic not available: {error}\n\n"
        f"To install python-magic (optional, enables magic byte detection):\n"
        f"    {install_cmd}\n\n"
        f"For detailed instructions: docs/dependencies/python-magic.md\n"
        f"Without magic, file type detection will use file extensions only."
    )


def has_magic() -> bool:
    """Check if python-magic is available.

    Returns:
        bool: True if magic is available, False otherwise.
    """
    return _try_import_magic()


def get_magic_import_error() -> Optional[str]:
    """Get the magic import error message, if any.

    Returns:
        Optional[str]: Error message if magic import failed, None if available.
    """
    _try_import_magic()
    return _magic_import_error


# Format detection mapping (extension -> MIME type)
EXTENSION_MIME_MAP = {
    ".pdf": "application/pdf",
    ".epub": "application/epub+zip",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".rtf": "application/rtf",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw": "application/vnd.amazon.ebook",
    ".azw3": "application/vnd.amazon.ebook",
}


def detect_format(file_path: str | Path, require_magic: bool = False) -> str:
    """Detect file format using magic bytes (preferred) or extension (fallback).

    Args:
        file_path: Path to the file to detect.
        require_magic: If True, raise error if magic not available.

    Returns:
        str: MIME type of the file.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ImportError: If require_magic=True and magic not available.
        ValueError: If format cannot be determined.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Try magic-based detection
    if _try_import_magic():
        try:
            mime_type = _magic.from_file(str(path), mime=True)
            if mime_type:
                # Check for extension mismatch (security warning)
                ext_mime = EXTENSION_MIME_MAP.get(path.suffix.lower())
                if ext_mime and ext_mime != mime_type:
                    import logging
                    logging.warning(
                        f"File extension mismatch: {path.name} has extension "
                        f"'{path.suffix}' ({ext_mime}) but content is {mime_type}"
                    )
                return mime_type
        except Exception as e:
            # Fall through to extension-based detection
            import logging
            logging.debug(f"Magic detection failed, using extension: {e}")
    elif require_magic:
        raise ImportError(get_magic_import_error())

    # Extension-based fallback
    ext = path.suffix.lower()
    mime_type = EXTENSION_MIME_MAP.get(ext)

    if not mime_type:
        raise ValueError(
            f"Cannot determine format for: {file_path}\n"
            f"Unknown extension: {ext}\n"
            f"Supported formats: {', '.join(EXTENSION_MIME_MAP.keys())}"
        )

    return mime_type


def parse_book(
    file_path: str | Path,
    format: Optional[str] = None,
    encoding: str = "utf-8"
) -> dict[str, Any]:
    """Parse a book file and extract content.

    Args:
        file_path: Path to the book file.
        format: Explicit format (pdf, epub, html, txt). If None, auto-detect.
        encoding: Text encoding for text-based formats.

    Returns:
        dict: Parsed book content with keys:
            - title: Book title (if available)
            - content: Full text content
            - metadata: Format-specific metadata
            - format: Detected/specified format

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If format not supported.
        ImportError: If required parser library not installed.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Determine format
    if format is None:
        mime_type = detect_format(path)
        format = _mime_to_format(mime_type)

    # Parse based on format
    if format == "pdf":
        return _parse_pdf(path)
    elif format == "epub":
        return _parse_epub(path)
    elif format in ("html", "htm"):
        return _parse_html(path, encoding)
    elif format in ("txt", "text", "md", "markdown"):
        return _parse_text(path, encoding)
    else:
        raise ValueError(
            f"Unsupported format: {format}\n"
            f"Supported formats: pdf, epub, html, txt, md"
        )


def _mime_to_format(mime_type: str) -> str:
    """Convert MIME type to format name.

    Args:
        mime_type: MIME type string.

    Returns:
        str: Format name.
    """
    mapping = {
        "application/pdf": "pdf",
        "application/epub+zip": "epub",
        "text/html": "html",
        "text/plain": "txt",
        "text/markdown": "md",
    }
    return mapping.get(mime_type, "txt")


def _parse_pdf(path: Path) -> dict[str, Any]:
    """Parse PDF file.

    Args:
        path: Path to PDF file.

    Returns:
        dict: Parsed PDF content.

    Raises:
        ImportError: If pypdf not installed.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf not installed. Install with:\n"
            "    pip install pypdf>=5.6.1\n"
            "Or: pip install -r requirements-book-parsing.txt"
        )

    reader = PdfReader(str(path))

    # Extract text from all pages
    content_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            content_parts.append(text)

    # Extract metadata
    metadata = {}
    if reader.metadata:
        metadata = {
            "author": reader.metadata.author,
            "creator": reader.metadata.creator,
            "producer": reader.metadata.producer,
            "subject": reader.metadata.subject,
            "title": reader.metadata.title,
        }

    return {
        "title": metadata.get("title") or path.stem,
        "content": "\n\n".join(content_parts),
        "metadata": metadata,
        "format": "pdf",
        "page_count": len(reader.pages),
    }


def _parse_epub(path: Path) -> dict[str, Any]:
    """Parse EPUB file.

    Args:
        path: Path to EPUB file.

    Returns:
        dict: Parsed EPUB content.

    Raises:
        ImportError: If ebooklib not installed.
    """
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        raise ImportError(
            "ebooklib not installed. Install with:\n"
            "    pip install ebooklib>=0.20\n"
            "Or: pip install -r requirements-book-parsing.txt"
        )

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError(
            "beautifulsoup4 not installed. Install with:\n"
            "    pip install beautifulsoup4>=4.14.3\n"
            "Or: pip install -r requirements-book-parsing.txt"
        )

    book = epub.read_epub(str(path))

    # Extract text from all chapters
    content_parts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if text:
                content_parts.append(text)

    # Extract metadata
    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else path.stem

    author = book.get_metadata("DC", "creator")
    author = author[0][0] if author else None

    return {
        "title": title,
        "content": "\n\n".join(content_parts),
        "metadata": {
            "author": author,
            "language": book.get_metadata("DC", "language"),
        },
        "format": "epub",
        "chapter_count": len(content_parts),
    }


def _parse_html(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    """Parse HTML file.

    Args:
        path: Path to HTML file.
        encoding: Text encoding.

    Returns:
        dict: Parsed HTML content.

    Raises:
        ImportError: If beautifulsoup4 not installed.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError(
            "beautifulsoup4 not installed. Install with:\n"
            "    pip install beautifulsoup4>=4.14.3\n"
            "Or: pip install -r requirements-book-parsing.txt"
        )

    html_content = path.read_text(encoding=encoding)
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else path.stem

    # Extract body text
    body = soup.find("body")
    content = body.get_text(separator="\n", strip=True) if body else soup.get_text()

    return {
        "title": title,
        "content": content,
        "metadata": {},
        "format": "html",
    }


def _parse_text(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    """Parse plain text file.

    Args:
        path: Path to text file.
        encoding: Text encoding.

    Returns:
        dict: Parsed text content.
    """
    content = path.read_text(encoding=encoding)

    return {
        "title": path.stem,
        "content": content,
        "metadata": {},
        "format": "txt",
    }
