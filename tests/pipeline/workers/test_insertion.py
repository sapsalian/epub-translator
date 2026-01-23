"""Tests for InsertionWorker."""

import tempfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.pipeline.models import (
    ExtractionResult,
    InnerTag,
    InsertionResult,
    Language,
    TextLocation,
    TextUnit,
    TranslatedUnit,
    TranslationResult,
    XhtmlExtraction,
)
from src.pipeline.workers.base import InsertionError
from src.pipeline.workers.insertion import (
    InsertionInput,
    InsertionWorker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_epub(temp_dir: Path) -> Path:
    """Create a sample EPUB for testing."""
    epub_path = temp_dir / "test.epub"

    xhtml_content = b"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test</title></head>
<body>
<p>Hello world</p>
<p>Goodbye <b>world</b></p>
</body>
</html>"""

    with ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("OEBPS/chapter1.xhtml", xhtml_content)

    return epub_path


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """Create sample extraction result."""
    return ExtractionResult(
        epub_id="test-epub-001",
        source_language=Language.ENGLISH,
        xhtml_extractions=[
            XhtmlExtraction(
                xhtml_id="xhtml-001",
                xhtml_path="OEBPS/chapter1.xhtml",
                text_units=[
                    TextUnit(
                        unit_id="unit-001",
                        location=TextLocation(
                            xhtml_path="OEBPS/chapter1.xhtml",
                            xpath="/html/body/p[1]",
                        ),
                        source_text="Hello world",
                        tagged_text="Hello world",
                        inner_tags=[],
                    ),
                    TextUnit(
                        unit_id="unit-002",
                        location=TextLocation(
                            xhtml_path="OEBPS/chapter1.xhtml",
                            xpath="/html/body/p[2]",
                        ),
                        source_text="Goodbye world",
                        tagged_text="Goodbye {{1}}world{{/1}}",
                        inner_tags=[
                            InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False),
                        ],
                    ),
                ],
                raw_text="Hello world\nGoodbye world",
            ),
        ],
    )


@pytest.fixture
def sample_translation_results() -> list[TranslationResult]:
    """Create sample translation results."""
    return [
        TranslationResult(
            epub_id="test-epub-001",
            xhtml_id="xhtml-001",
            target_language=Language.KOREAN,
            translated_units=[
                TranslatedUnit(
                    unit_id="unit-001",
                    translated_text="안녕 세계",
                ),
                TranslatedUnit(
                    unit_id="unit-002",
                    translated_text="안녕히 {{1}}세계{{/1}}",
                ),
            ],
        ),
    ]


@pytest.fixture
def insertion_input(
    sample_epub: Path,
    sample_extraction_result: ExtractionResult,
    sample_translation_results: list[TranslationResult],
    temp_dir: Path,
) -> InsertionInput:
    """Create insertion input."""
    return InsertionInput(
        epub_id="test-epub-001",
        epub_path=sample_epub,
        target_language=Language.KOREAN,
        extraction_result=sample_extraction_result,
        translation_results=sample_translation_results,
        output_dir=temp_dir / "output",
    )


@pytest.fixture
def worker() -> InsertionWorker:
    """Create InsertionWorker."""
    return InsertionWorker()


# =============================================================================
# Basic Tests
# =============================================================================


class TestInsertionWorkerBasic:
    """Basic tests for InsertionWorker."""

    def test_worker_has_logger(self, worker: InsertionWorker):
        """Worker has logger attribute."""
        assert hasattr(worker, "logger")

    def test_worker_repr(self, worker: InsertionWorker):
        """Worker has readable repr."""
        assert repr(worker) == "InsertionWorker()"


class TestInsertionInput:
    """Tests for InsertionInput model."""

    def test_input_fields(
        self,
        sample_epub: Path,
        sample_extraction_result: ExtractionResult,
        sample_translation_results: list[TranslationResult],
        temp_dir: Path,
    ):
        """Input has required fields."""
        input_data = InsertionInput(
            epub_id="test",
            epub_path=sample_epub,
            target_language=Language.KOREAN,
            extraction_result=sample_extraction_result,
            translation_results=sample_translation_results,
            output_dir=temp_dir,
        )
        assert input_data.epub_id == "test"
        assert input_data.target_language == Language.KOREAN


# =============================================================================
# Insertion Tests
# =============================================================================


class TestInsertion:
    """Tests for insertion functionality."""

    def test_generates_insertion_result(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Processing produces InsertionResult."""
        result = worker.process(insertion_input)

        assert isinstance(result, InsertionResult)
        assert result.epub_id == "test-epub-001"
        assert result.target_language == Language.KOREAN

    def test_creates_output_epub(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Output EPUB is created."""
        result = worker.process(insertion_input)

        output_path = Path(result.output_path)
        assert output_path.exists()
        assert output_path.suffix == ".epub"

    def test_output_path_includes_language(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Output path includes target language code."""
        result = worker.process(insertion_input)

        assert "_ko.epub" in result.output_path

    def test_translated_content_in_output(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Output EPUB contains translated content."""
        result = worker.process(insertion_input)

        with ZipFile(result.output_path, "r") as zf:
            content = zf.read("OEBPS/chapter1.xhtml").decode("utf-8")

        # Check translations are present
        assert "안녕 세계" in content
        assert "안녕히" in content

    def test_inner_tags_restored(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Inner tags are restored in output."""
        result = worker.process(insertion_input)

        with ZipFile(result.output_path, "r") as zf:
            content = zf.read("OEBPS/chapter1.xhtml").decode("utf-8")

        # Check <b> tag is restored (not placeholder)
        assert "<b>" in content or "<b " in content
        assert "{{1}}" not in content

    def test_success_when_all_translated(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Success is True when all translations applied."""
        result = worker.process(insertion_input)

        assert result.success is True
        assert len(result.errors) == 0

    def test_creates_output_directory(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """Output directory is created if it doesn't exist."""
        # Ensure output dir doesn't exist
        assert not insertion_input.output_dir.exists()

        result = worker.process(insertion_input)

        assert Path(result.output_path).parent.exists()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_epub_raises_error(
        self,
        sample_extraction_result: ExtractionResult,
        sample_translation_results: list[TranslationResult],
        temp_dir: Path,
    ):
        """Missing EPUB file raises InsertionError."""
        input_data = InsertionInput(
            epub_id="test",
            epub_path=temp_dir / "nonexistent.epub",
            target_language=Language.KOREAN,
            extraction_result=sample_extraction_result,
            translation_results=sample_translation_results,
            output_dir=temp_dir / "output",
        )
        worker = InsertionWorker()

        with pytest.raises(InsertionError, match="not found"):
            worker.process(input_data)

    def test_missing_translation_records_error(
        self,
        sample_epub: Path,
        sample_extraction_result: ExtractionResult,
        temp_dir: Path,
    ):
        """Missing translation for a unit is recorded as error."""
        # Only provide translation for first unit
        partial_translations = [
            TranslationResult(
                epub_id="test-epub-001",
                xhtml_id="xhtml-001",
                target_language=Language.KOREAN,
                translated_units=[
                    TranslatedUnit(
                        unit_id="unit-001",
                        translated_text="안녕 세계",
                    ),
                    # unit-002 translation missing
                ],
            ),
        ]

        input_data = InsertionInput(
            epub_id="test-epub-001",
            epub_path=sample_epub,
            target_language=Language.KOREAN,
            extraction_result=sample_extraction_result,
            translation_results=partial_translations,
            output_dir=temp_dir / "output",
        )
        worker = InsertionWorker()

        result = worker.process(input_data)

        # Should complete but with errors
        assert result.success is False
        assert any("unit-002" in error for error in result.errors)


# =============================================================================
# Preservation Tests
# =============================================================================


class TestPreservation:
    """Tests for preserving EPUB structure."""

    def test_preserves_mimetype(
        self,
        worker: InsertionWorker,
        insertion_input: InsertionInput,
    ):
        """mimetype file is preserved."""
        result = worker.process(insertion_input)

        with ZipFile(result.output_path, "r") as zf:
            mimetype = zf.read("mimetype").decode("utf-8")

        assert mimetype == "application/epub+zip"

    def test_preserves_non_xhtml_files(
        self,
        temp_dir: Path,
        sample_extraction_result: ExtractionResult,
        sample_translation_results: list[TranslationResult],
    ):
        """Non-XHTML files are preserved."""
        epub_path = temp_dir / "test.epub"

        with ZipFile(epub_path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("OEBPS/chapter1.xhtml", b"""<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<body><p>Hello world</p></body>
</html>""")
            zf.writestr("OEBPS/style.css", "body { color: black; }")
            zf.writestr("META-INF/container.xml", "<container/>")

        input_data = InsertionInput(
            epub_id="test-epub-001",
            epub_path=epub_path,
            target_language=Language.KOREAN,
            extraction_result=sample_extraction_result,
            translation_results=sample_translation_results,
            output_dir=temp_dir / "output",
        )
        worker = InsertionWorker()

        result = worker.process(input_data)

        with ZipFile(result.output_path, "r") as zf:
            css = zf.read("OEBPS/style.css").decode("utf-8")
            container = zf.read("META-INF/container.xml").decode("utf-8")

        assert "color: black" in css
        assert "<container/>" in container


# =============================================================================
# Unit Map Tests
# =============================================================================


class TestBuildMaps:
    """Tests for building lookup maps."""

    def test_build_unit_map(
        self,
        worker: InsertionWorker,
        sample_extraction_result: ExtractionResult,
    ):
        """Unit map is built correctly."""
        unit_map = worker._build_unit_map(sample_extraction_result)

        assert "unit-001" in unit_map
        assert "unit-002" in unit_map
        assert unit_map["unit-001"].source_text == "Hello world"

    def test_build_translation_map(
        self,
        worker: InsertionWorker,
        sample_translation_results: list[TranslationResult],
    ):
        """Translation map is built correctly."""
        translation_map = worker._build_translation_map(sample_translation_results)

        assert "unit-001" in translation_map
        assert "unit-002" in translation_map
        assert translation_map["unit-001"].translated_text == "안녕 세계"
