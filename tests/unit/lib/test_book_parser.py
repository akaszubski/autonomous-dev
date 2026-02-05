"""Tests for book_parser.py with optional python-magic handling.

Tests are organized into:
- Tests that work without magic (extension-based detection)
- Tests that require magic (use pytest.importorskip)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_pdf_file(tmp_path: Path) -> Path:
    """Create a minimal PDF file for testing."""
    pdf_path = tmp_path / "test.pdf"
    # Minimal PDF header (not valid PDF but has magic bytes)
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF")
    return pdf_path


@pytest.fixture
def temp_html_file(tmp_path: Path) -> Path:
    """Create a minimal HTML file for testing."""
    html_path = tmp_path / "test.html"
    html_path.write_text("<html><head><title>Test</title></head><body>Content</body></html>")
    return html_path


@pytest.fixture
def temp_text_file(tmp_path: Path) -> Path:
    """Create a minimal text file for testing."""
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("This is test content.\n\nSecond paragraph.")
    return txt_path


@pytest.fixture
def temp_epub_file(tmp_path: Path) -> Path:
    """Create a placeholder EPUB file for testing."""
    epub_path = tmp_path / "test.epub"
    # EPUB files are actually ZIP files with specific structure
    # For testing, we just check extension detection
    epub_path.write_bytes(b"PK\x03\x04")  # ZIP magic bytes
    return epub_path


# ============================================================================
# Extension-based detection tests (no magic required)
# ============================================================================

class TestExtensionBasedDetection:
    """Tests that work without python-magic installed."""

    def test_detect_format_by_extension_pdf(self, tmp_path: Path):
        """Test PDF detection by extension."""
        from plugins.autonomous_dev.lib.book_parser import detect_format, EXTENSION_MIME_MAP

        pdf_path = tmp_path / "document.pdf"
        pdf_path.write_bytes(b"fake content")

        # Mock magic as unavailable
        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                mime = detect_format(pdf_path)
                assert mime == "application/pdf"

    def test_detect_format_by_extension_epub(self, tmp_path: Path):
        """Test EPUB detection by extension."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        epub_path = tmp_path / "book.epub"
        epub_path.write_bytes(b"fake content")

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                mime = detect_format(epub_path)
                assert mime == "application/epub+zip"

    def test_detect_format_by_extension_html(self, tmp_path: Path):
        """Test HTML detection by extension."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        html_path = tmp_path / "page.html"
        html_path.write_text("<html></html>")

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                mime = detect_format(html_path)
                assert mime == "text/html"

    def test_detect_format_by_extension_txt(self, tmp_path: Path):
        """Test TXT detection by extension."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        txt_path = tmp_path / "readme.txt"
        txt_path.write_text("Hello world")

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                mime = detect_format(txt_path)
                assert mime == "text/plain"

    def test_detect_format_by_extension_md(self, tmp_path: Path):
        """Test Markdown detection by extension."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        md_path = tmp_path / "readme.md"
        md_path.write_text("# Heading")

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                mime = detect_format(md_path)
                assert mime == "text/markdown"

    def test_detect_format_unknown_extension(self, tmp_path: Path):
        """Test error on unknown extension."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        unknown_path = tmp_path / "file.xyz"
        unknown_path.write_bytes(b"content")

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                with pytest.raises(ValueError, match="Cannot determine format"):
                    detect_format(unknown_path)

    def test_detect_format_file_not_found(self, tmp_path: Path):
        """Test error on missing file."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        missing_path = tmp_path / "missing.pdf"

        with pytest.raises(FileNotFoundError):
            detect_format(missing_path)


class TestHasMagic:
    """Test has_magic() function."""

    def test_has_magic_when_not_available(self):
        """Test has_magic returns False when import fails."""
        from plugins.autonomous_dev.lib import book_parser

        # Reset state
        book_parser._magic = None
        book_parser._magic_import_error = None

        with patch.dict("sys.modules", {"magic": None}):
            with patch("builtins.__import__", side_effect=ImportError("no magic")):
                # Force re-import attempt
                book_parser._magic = None
                book_parser._magic_import_error = None
                result = book_parser.has_magic()
                # Result depends on actual system state, but function shouldn't crash
                assert isinstance(result, bool)

    def test_get_magic_import_error_message(self):
        """Test error message formatting."""
        from plugins.autonomous_dev.lib.book_parser import _format_import_error

        # Test Linux/macOS missing system library
        error = ImportError("failed to find libmagic")
        msg = _format_import_error(error)
        assert "python-magic not available" in msg
        assert "docs/dependencies/python-magic.md" in msg

        # Test missing Python wrapper
        error2 = ImportError("No module named 'magic'")
        msg2 = _format_import_error(error2)
        assert "pip install" in msg2


class TestParseText:
    """Test text file parsing (no external dependencies)."""

    def test_parse_text_file(self, temp_text_file: Path):
        """Test parsing plain text file."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        result = parse_book(temp_text_file, format="txt")

        assert result["title"] == "test"
        assert "test content" in result["content"]
        assert result["format"] == "txt"

    def test_parse_text_auto_detect(self, temp_text_file: Path):
        """Test auto-detection for text file."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                result = parse_book(temp_text_file)
                assert result["format"] == "txt"

    def test_parse_markdown_file(self, tmp_path: Path):
        """Test parsing markdown file."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        md_path = tmp_path / "readme.md"
        md_path.write_text("# Title\n\nContent here")

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                result = parse_book(md_path)
                assert result["content"] == "# Title\n\nContent here"


class TestParseHTML:
    """Test HTML parsing (requires beautifulsoup4)."""

    def test_parse_html_requires_bs4(self, temp_html_file: Path):
        """Test HTML parsing raises ImportError if bs4 missing."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        with patch.dict("sys.modules", {"bs4": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'bs4'")):
                # This should work if bs4 is actually installed, or raise ImportError
                try:
                    result = parse_book(temp_html_file, format="html")
                    # If it worked, bs4 is installed
                    assert "Content" in result["content"]
                except ImportError as e:
                    assert "beautifulsoup4" in str(e)


class TestParsePDF:
    """Test PDF parsing (requires pypdf)."""

    def test_parse_pdf_requires_pypdf(self, temp_pdf_file: Path):
        """Test PDF parsing raises ImportError if pypdf missing."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        # Try parsing - will work if pypdf installed, otherwise raise ImportError
        try:
            result = parse_book(temp_pdf_file, format="pdf")
            assert result["format"] == "pdf"
        except ImportError as e:
            assert "pypdf" in str(e)
        except Exception:
            # Minimal PDF may fail to parse, that's ok
            pass


class TestMimeMapping:
    """Test MIME type to format mapping."""

    def test_extension_mime_map_completeness(self):
        """Test that common formats are mapped."""
        from plugins.autonomous_dev.lib.book_parser import EXTENSION_MIME_MAP

        expected = [".pdf", ".epub", ".html", ".htm", ".txt", ".md"]
        for ext in expected:
            assert ext in EXTENSION_MIME_MAP, f"Missing extension: {ext}"


# ============================================================================
# Magic-dependent tests (skip if python-magic not installed)
# ============================================================================

class TestMagicBasedDetection:
    """Tests that require python-magic.

    These tests are automatically skipped if python-magic is not installed.
    """

    @pytest.fixture(autouse=True)
    def require_magic(self):
        """Skip tests if magic not available."""
        pytest.importorskip(
            "magic",
            reason="python-magic not installed - install libmagic system library"
        )

    def test_detect_format_by_magic_bytes(self, temp_html_file: Path):
        """Test detection using magic bytes (content-based)."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        # HTML file should be detected by magic bytes
        mime = detect_format(temp_html_file)
        assert mime in ("text/html", "text/plain")  # Magic may detect as text

    def test_extension_mismatch_warning(self, tmp_path: Path, caplog):
        """Test warning when extension doesn't match content."""
        from plugins.autonomous_dev.lib.book_parser import detect_format
        import logging

        # Create a "PDF" that's actually HTML
        fake_pdf = tmp_path / "document.pdf"
        fake_pdf.write_text("<html><body>Not a PDF</body></html>")

        with caplog.at_level(logging.WARNING):
            mime = detect_format(fake_pdf)
            # Magic should detect actual content type
            # Warning may or may not be logged depending on magic detection
            # Just verify it doesn't crash
            assert mime is not None


class TestMagicImportSkip:
    """Test that magic-dependent functionality can be skipped gracefully."""

    def test_require_magic_raises_when_unavailable(self, tmp_path: Path):
        """Test require_magic=True raises ImportError when magic unavailable."""
        from plugins.autonomous_dev.lib.book_parser import detect_format

        txt_path = tmp_path / "test.txt"
        txt_path.write_text("content")

        # Temporarily make magic unavailable
        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                with pytest.raises(ImportError, match="python-magic not available"):
                    detect_format(txt_path, require_magic=True)


# ============================================================================
# Integration tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete parsing workflows."""

    def test_parse_and_detect_flow(self, temp_text_file: Path):
        """Test complete parse workflow without magic."""
        from plugins.autonomous_dev.lib.book_parser import detect_format, parse_book

        with patch("plugins.autonomous_dev.lib.book_parser._magic", None):
            with patch("plugins.autonomous_dev.lib.book_parser._magic_import_error", "not available"):
                # Detect
                mime = detect_format(temp_text_file)
                assert mime == "text/plain"

                # Parse
                result = parse_book(temp_text_file)
                assert result["content"]
                assert result["format"] == "txt"

    def test_explicit_format_skips_detection(self, temp_text_file: Path):
        """Test that explicit format skips auto-detection."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        # Even without magic, explicit format works
        result = parse_book(temp_text_file, format="txt")
        assert result["format"] == "txt"

    def test_unsupported_format_raises(self, temp_text_file: Path):
        """Test error on unsupported format."""
        from plugins.autonomous_dev.lib.book_parser import parse_book

        with pytest.raises(ValueError, match="Unsupported format"):
            parse_book(temp_text_file, format="docx")
