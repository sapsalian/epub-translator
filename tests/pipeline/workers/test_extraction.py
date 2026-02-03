"""Tests for ExtractionWorker."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from src.matchers import MatcherStrategy
from src.pipeline.models import Language, ExtractionResult, XhtmlExtraction, TextUnit
from src.pipeline.workers.base import ExtractionError
from src.pipeline.workers.extraction import ExtractionWorker, ExtractionInput


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_epub_path() -> Path:
    """Path to sample EPUB file."""
    return Path(__file__).parents[3] / "demo_files" / "sample.epub"


@pytest.fixture
def worker() -> ExtractionWorker:
    """Create ExtractionWorker instance."""
    return ExtractionWorker()


@pytest.fixture
def extraction_input(sample_epub_path: Path) -> ExtractionInput:
    """Create basic extraction input."""
    return ExtractionInput(
        epub_id="test-epub-001",
        epub_path=sample_epub_path,
        source_language=Language.ENGLISH,
        matcher_strategy=MatcherStrategy.ALL_ELEMENTS,
    )


# =============================================================================
# Basic Tests
# =============================================================================


class TestExtractionWorkerBasic:
    """Basic tests for ExtractionWorker."""

    def test_worker_has_logger(self, worker: ExtractionWorker):
        """Worker has logger attribute."""
        assert hasattr(worker, "logger")

    def test_worker_repr(self, worker: ExtractionWorker):
        """Worker has readable repr."""
        assert repr(worker) == "ExtractionWorker()"


class TestExtractionInput:
    """Tests for ExtractionInput model."""

    def test_default_matcher_strategy(self, sample_epub_path: Path):
        """Default matcher strategy is TEXT_EMERGENCE."""
        input_data = ExtractionInput(
            epub_id="test",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
        )
        assert input_data.matcher_strategy == MatcherStrategy.TEXT_EMERGENCE

    def test_custom_matcher_strategy(self, sample_epub_path: Path):
        """Can specify custom matcher strategy."""
        input_data = ExtractionInput(
            epub_id="test",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
            matcher_strategy=MatcherStrategy.LEAF_BLOCK,
        )
        assert input_data.matcher_strategy == MatcherStrategy.LEAF_BLOCK


# =============================================================================
# Extraction Tests
# =============================================================================


class TestExtraction:
    """Tests for extraction functionality."""

    def test_extracts_from_sample_epub(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Extraction produces result from sample EPUB."""
        result = worker.process(extraction_input)

        assert isinstance(result, ExtractionResult)
        assert result.epub_id == "test-epub-001"
        assert result.source_language == Language.ENGLISH

    def test_extracts_xhtml_files(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Extracts from multiple XHTML files."""
        result = worker.process(extraction_input)

        assert len(result.xhtml_extractions) > 0

        for xhtml_extraction in result.xhtml_extractions:
            assert isinstance(xhtml_extraction, XhtmlExtraction)
            assert xhtml_extraction.xhtml_id
            assert xhtml_extraction.xhtml_path

    def test_extracts_text_units(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Extracts text units from XHTML files."""
        result = worker.process(extraction_input)

        # Find any XHTML with text units
        xhtml_with_units = [x for x in result.xhtml_extractions if x.text_units]
        assert len(xhtml_with_units) > 0

    def test_handles_html_named_entities(self, worker: ExtractionWorker, tmp_path: Path):
        """Extraction succeeds when XHTML contains HTML named entities like &nbsp;."""
        epub_path = tmp_path / "entity.epub"
        container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
        content_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test</dc:title>
  </metadata>
  <manifest>
    <item id="item1" href="Text/ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="item1"/>
  </spine>
</package>
"""
        xhtml = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Test</title></head>
  <body><p>Hello&nbsp;world</p></body>
</html>
"""

        with ZipFile(epub_path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("META-INF/container.xml", container_xml)
            zf.writestr("OEBPS/content.opf", content_opf)
            zf.writestr("OEBPS/Text/ch1.xhtml", xhtml)

        input_data = ExtractionInput(
            epub_id="entity-epub",
            epub_path=epub_path,
            source_language=Language.ENGLISH,
            matcher_strategy=MatcherStrategy.ALL_ELEMENTS,
        )
        result = worker.process(input_data)

        assert isinstance(result, ExtractionResult)
        assert len(result.xhtml_extractions) == 1
        text_units = result.xhtml_extractions[0].text_units
        assert len(text_units) > 0
        assert "Hello" in text_units[0].source_text
        assert "world" in text_units[0].source_text

    def test_generates_unique_xhtml_ids(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Each XHTML file has a unique ID."""
        result = worker.process(extraction_input)

        xhtml_ids = [x.xhtml_id for x in result.xhtml_extractions]
        assert len(xhtml_ids) == len(set(xhtml_ids))

    def test_generates_unique_unit_ids(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Each text unit has a unique ID."""
        result = worker.process(extraction_input)

        all_unit_ids = []
        for xhtml_extraction in result.xhtml_extractions:
            for text_unit in xhtml_extraction.text_units:
                all_unit_ids.append(text_unit.unit_id)

        assert len(all_unit_ids) == len(set(all_unit_ids))

    def test_preserves_inner_tags_as_placeholders(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Inner tags are converted to numbered placeholders."""
        result = worker.process(extraction_input)

        # Find units with inner tags
        units_with_tags = []
        for xhtml_extraction in result.xhtml_extractions:
            for text_unit in xhtml_extraction.text_units:
                if text_unit.inner_tags:
                    units_with_tags.append(text_unit)

        if units_with_tags:
            for unit in units_with_tags:
                # Check that placeholders exist in tagged_text
                for inner_tag in unit.inner_tags:
                    idx = inner_tag.index
                    # Opaque tags (with raw_xml) and self-closing tags use {{n/}} format
                    if inner_tag.is_self_closing or inner_tag.raw_xml is not None:
                        assert f"{{{{{idx}/}}}}" in unit.tagged_text
                    else:
                        assert f"{{{{{idx}}}}}" in unit.tagged_text

    def test_extracts_raw_text(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """raw_text is collected for each XHTML."""
        result = worker.process(extraction_input)

        xhtml_with_text = [
            x for x in result.xhtml_extractions
            if x.text_units
        ]

        for xhtml_extraction in xhtml_with_text:
            assert xhtml_extraction.raw_text


# =============================================================================
# Matcher Strategy Tests
# =============================================================================


class TestMatcherStrategies:
    """Tests for different matcher strategies."""

    def test_all_elements_extracts_most(
        self, worker: ExtractionWorker, sample_epub_path: Path
    ):
        """ALL_ELEMENTS strategy extracts many elements."""
        input_data = ExtractionInput(
            epub_id="test",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
            matcher_strategy=MatcherStrategy.ALL_ELEMENTS,
        )
        result = worker.process(input_data)

        all_count = sum(len(x.text_units) for x in result.xhtml_extractions)
        assert all_count > 0

    def test_leaf_block_extracts_fewer(
        self, worker: ExtractionWorker, sample_epub_path: Path
    ):
        """LEAF_BLOCK strategy extracts fewer elements than ALL_ELEMENTS."""
        all_input = ExtractionInput(
            epub_id="test",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
            matcher_strategy=MatcherStrategy.ALL_ELEMENTS,
        )
        leaf_input = ExtractionInput(
            epub_id="test",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
            matcher_strategy=MatcherStrategy.LEAF_BLOCK,
        )

        all_result = worker.process(all_input)
        leaf_result = worker.process(leaf_input)

        all_count = sum(len(x.text_units) for x in all_result.xhtml_extractions)
        leaf_count = sum(len(x.text_units) for x in leaf_result.xhtml_extractions)

        # LEAF_BLOCK should be more selective (fewer or equal extractions)
        assert leaf_count <= all_count


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_raises_for_missing_file(self, worker: ExtractionWorker):
        """Raises ExtractionError for missing EPUB file."""
        input_data = ExtractionInput(
            epub_id="test",
            epub_path=Path("/nonexistent/file.epub"),
            source_language=Language.ENGLISH,
        )

        with pytest.raises(ExtractionError, match="not found"):
            worker.process(input_data)


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for result serialization."""

    def test_result_to_json(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """ExtractionResult can be serialized to JSON."""
        result = worker.process(extraction_input)

        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "test-epub-001" in json_str

    def test_result_from_json(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """ExtractionResult can be deserialized from JSON."""
        result = worker.process(extraction_input)

        json_str = result.to_json()
        restored = ExtractionResult.from_json(json_str)

        assert restored.epub_id == result.epub_id
        assert restored.source_language == result.source_language
        assert len(restored.xhtml_extractions) == len(result.xhtml_extractions)


# =============================================================================
# ID Generation Tests
# =============================================================================


class TestIdGeneration:
    """Tests for ID generation."""

    def test_xhtml_id_is_deterministic(
        self, worker: ExtractionWorker, extraction_input: ExtractionInput
    ):
        """Same input produces same xhtml_ids."""
        result1 = worker.process(extraction_input)
        result2 = worker.process(extraction_input)

        ids1 = [x.xhtml_id for x in result1.xhtml_extractions]
        ids2 = [x.xhtml_id for x in result2.xhtml_extractions]

        assert ids1 == ids2

    def test_different_epub_id_produces_different_xhtml_ids(
        self, worker: ExtractionWorker, sample_epub_path: Path
    ):
        """Different epub_id produces different xhtml_ids."""
        input1 = ExtractionInput(
            epub_id="epub-001",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
        )
        input2 = ExtractionInput(
            epub_id="epub-002",
            epub_path=sample_epub_path,
            source_language=Language.ENGLISH,
        )

        result1 = worker.process(input1)
        result2 = worker.process(input2)

        ids1 = set(x.xhtml_id for x in result1.xhtml_extractions)
        ids2 = set(x.xhtml_id for x in result2.xhtml_extractions)

        # No overlap between IDs
        assert not ids1.intersection(ids2)
