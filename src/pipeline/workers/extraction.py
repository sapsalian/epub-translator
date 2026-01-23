"""
Extraction worker for the translation pipeline.

Extracts translatable text from EPUB files, replacing inner tags with
numbered placeholders for translation.

Input: ExtractionInput (epub_id, epub_path, source_language, matcher_strategy)
Output: ExtractionResult

This is a CPU-bound worker that:
1. Parses all XHTML files in spine order
2. Filters elements using the specified matcher strategy
3. Extracts inner tags and replaces them with placeholders
4. Generates unique IDs for each text unit
"""

import hashlib
import logging
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pydantic import BaseModel, ConfigDict, Field

from src.epub_walker.parser import get_spine_xhtml_paths_by_order
from src.matchers import MatcherFactory, MatcherStrategy
from src.pipeline.inner_tag_handler import InnerTagHandler
from src.pipeline.models import (
    ExtractionResult,
    Language,
    TextLocation,
    TextUnit,
    XhtmlExtraction,
)

from .base import ExtractionError, Worker


logger = logging.getLogger(__name__)


# =============================================================================
# Input Model
# =============================================================================


class ExtractionInput(BaseModel):
    """Input for ExtractionWorker."""

    epub_id: str = Field(description="Unique EPUB identifier")
    epub_path: Path = Field(description="Path to the EPUB file")
    source_language: Language = Field(description="Source language of the EPUB")
    matcher_strategy: MatcherStrategy = Field(
        default=MatcherStrategy.ALL_ELEMENTS,
        description="Strategy for matching elements to translate",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


# =============================================================================
# ExtractionWorker
# =============================================================================


class ExtractionWorker(Worker[ExtractionInput, ExtractionResult]):
    """
    Extracts translatable text from EPUB files.

    Processes all XHTML files in spine order, filtering elements with
    the specified matcher strategy, and replacing inner tags with
    numbered placeholders.
    """

    def __init__(self) -> None:
        super().__init__()
        self._handler = InnerTagHandler()

    def process(self, input_data: ExtractionInput) -> ExtractionResult:
        """
        Extract translatable text from an EPUB file.

        Args:
            input_data: Extraction input containing epub_id, path, language, and strategy.

        Returns:
            ExtractionResult with all extracted text units.

        Raises:
            ExtractionError: If extraction fails.
        """
        self.logger.info(
            "Starting extraction for EPUB: %s (strategy: %s)",
            input_data.epub_id,
            input_data.matcher_strategy.value,
        )

        if not input_data.epub_path.exists():
            raise ExtractionError(f"EPUB file not found: {input_data.epub_path}")

        try:
            xhtml_extractions = self._extract_all_xhtml(input_data)

            result = ExtractionResult(
                epub_id=input_data.epub_id,
                source_language=input_data.source_language,
                xhtml_extractions=xhtml_extractions,
            )

            self.logger.info(
                "Extraction complete: %d XHTML files, %d text units",
                len(xhtml_extractions),
                sum(len(x.text_units) for x in xhtml_extractions),
            )

            return result

        except ExtractionError:
            raise
        except Exception as e:
            self.logger.error("Extraction failed: %s", e)
            raise ExtractionError(f"Extraction failed: {e}") from e

    def _extract_all_xhtml(
        self, input_data: ExtractionInput
    ) -> list[XhtmlExtraction]:
        """
        Extract text from all XHTML files in the EPUB.

        Args:
            input_data: Extraction input.

        Returns:
            List of XhtmlExtraction objects.
        """
        xhtml_extractions: list[XhtmlExtraction] = []
        matcher = MatcherFactory.create(input_data.matcher_strategy)

        with ZipFile(input_data.epub_path, "r") as zf:
            ordered_paths = get_spine_xhtml_paths_by_order(zf)

            for xhtml_path in ordered_paths:
                matcher.reset()

                try:
                    extraction = self._extract_single_xhtml(
                        zf=zf,
                        xhtml_path=xhtml_path.as_posix(),
                        epub_id=input_data.epub_id,
                        matcher=matcher,
                    )
                    xhtml_extractions.append(extraction)

                except Exception as e:
                    self.logger.warning(
                        "Failed to extract XHTML %s: %s", xhtml_path, e
                    )
                    # Continue with other files

        return xhtml_extractions

    def _extract_single_xhtml(
        self,
        zf: ZipFile,
        xhtml_path: str,
        epub_id: str,
        matcher,
    ) -> XhtmlExtraction:
        """
        Extract text from a single XHTML file.

        Args:
            zf: Open ZipFile object.
            xhtml_path: Path to the XHTML file within the EPUB.
            epub_id: EPUB identifier.
            matcher: Element matcher.

        Returns:
            XhtmlExtraction for this XHTML file.
        """
        xhtml_id = self._generate_xhtml_id(epub_id, xhtml_path)

        with zf.open(xhtml_path) as f:
            tree = etree.parse(f)
            root = tree.getroot()

        text_units: list[TextUnit] = []
        raw_texts: list[str] = []

        for elem in root.iter():
            if not matcher(elem):
                continue

            xpath = tree.getpath(elem)
            unit_id = self._generate_unit_id(xhtml_id, xpath)

            # Extract inner tags
            extraction_output = self._handler.extract(elem)

            # Skip empty extractions
            if not extraction_output.tagged_text.strip():
                continue

            # Get plain text for raw_text (remove placeholders)
            source_text = self._get_plain_text(elem)
            raw_texts.append(source_text)

            text_unit = TextUnit(
                unit_id=unit_id,
                location=TextLocation(xhtml_path=xhtml_path, xpath=xpath),
                source_text=source_text,
                tagged_text=extraction_output.tagged_text,
                inner_tags=extraction_output.inner_tags,
            )
            text_units.append(text_unit)

        self.logger.debug(
            "Extracted %d text units from %s", len(text_units), xhtml_path
        )

        return XhtmlExtraction(
            xhtml_id=xhtml_id,
            xhtml_path=xhtml_path,
            text_units=text_units,
            raw_text="\n".join(raw_texts),
        )

    def _get_plain_text(self, elem: etree._Element) -> str:
        """
        Get plain text content from an element (without tags).

        Args:
            elem: The element.

        Returns:
            Plain text content.
        """
        return "".join(elem.itertext())

    def _generate_xhtml_id(self, epub_id: str, xhtml_path: str) -> str:
        """
        Generate a unique ID for an XHTML file.

        Args:
            epub_id: EPUB identifier.
            xhtml_path: Path to the XHTML file.

        Returns:
            Unique xhtml_id (hash of epub_id + xhtml_path).
        """
        combined = f"{epub_id}:{xhtml_path}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _generate_unit_id(self, xhtml_id: str, xpath: str) -> str:
        """
        Generate a unique ID for a text unit.

        Args:
            xhtml_id: XHTML identifier.
            xpath: XPath to the element.

        Returns:
            Unique unit_id (hash of xhtml_id + xpath).
        """
        combined = f"{xhtml_id}:{xpath}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
