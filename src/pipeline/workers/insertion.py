"""
Insertion worker for the translation pipeline.

Inserts translated text back into the original EPUB, restoring inner tags.

Input: InsertionInput (epub_path, extraction_result, translation_results, output_dir)
Output: InsertionResult

This is a CPU-bound worker that:
1. Maps translated units back to their original locations
2. Restores numbered placeholders to original inner tags
3. Generates a new EPUB with translated content
"""

import logging
import shutil
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

from lxml import etree
from pydantic import BaseModel, ConfigDict, Field

from src.pipeline.inner_tag_handler import InnerTagHandler
from src.pipeline.models import (
    ExtractionResult,
    InnerTag,
    InsertionResult,
    Language,
    TextUnit,
    TranslatedUnit,
    TranslationResult,
)

from .base import InsertionError, Worker


logger = logging.getLogger(__name__)


# =============================================================================
# Input Model
# =============================================================================


class InsertionInput(BaseModel):
    """
    Input for InsertionWorker.

    Contains all data needed to create a translated EPUB:
    - Original EPUB path
    - Extraction result (for XPath locations and inner tags)
    - Translation results (for translated text)
    - Output configuration
    """

    epub_id: str = Field(description="EPUB identifier")
    epub_path: Path = Field(description="Path to the original EPUB file")
    target_language: Language = Field(description="Target language")
    extraction_result: ExtractionResult = Field(
        description="Original extraction result with XPath and inner tags"
    )
    translation_results: list[TranslationResult] = Field(
        default_factory=list, description="Translation results for all XHTMLs"
    )
    output_dir: Path = Field(description="Directory for output EPUB")

    model_config = ConfigDict(arbitrary_types_allowed=True)


# =============================================================================
# InsertionWorker
# =============================================================================


class InsertionWorker(Worker[InsertionInput, InsertionResult]):
    """
    Inserts translations back into EPUB files.

    Uses XPath to locate elements and InnerTagHandler to restore
    the original inner tags from numbered placeholders.
    """

    def __init__(self) -> None:
        """Initialize InsertionWorker."""
        super().__init__()
        self._handler = InnerTagHandler()

    def process(self, input_data: InsertionInput) -> InsertionResult:
        """
        Create a translated EPUB by inserting translations.

        Args:
            input_data: Insertion input with EPUB, extraction, and translations.

        Returns:
            InsertionResult with output path and status.

        Raises:
            InsertionError: If insertion fails.
        """
        self.logger.info(
            "Starting insertion for EPUB: %s (target: %s)",
            input_data.epub_id,
            input_data.target_language.value,
        )

        if not input_data.epub_path.exists():
            raise InsertionError(f"EPUB file not found: {input_data.epub_path}")

        # Build lookup maps
        unit_map = self._build_unit_map(input_data.extraction_result)
        translation_map = self._build_translation_map(input_data.translation_results)

        # Create output path
        output_path = self._create_output_path(input_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []

        try:
            self._create_translated_epub(
                input_path=input_data.epub_path,
                output_path=output_path,
                unit_map=unit_map,
                translation_map=translation_map,
                errors=errors,
            )

            success = len(errors) == 0

            result = InsertionResult(
                epub_id=input_data.epub_id,
                target_language=input_data.target_language,
                output_path=str(output_path),
                success=success,
                errors=errors,
            )

            if success:
                self.logger.info(
                    "Insertion complete: %s",
                    output_path,
                )
            else:
                self.logger.warning(
                    "Insertion completed with %d errors: %s",
                    len(errors),
                    output_path,
                )

            return result

        except InsertionError:
            raise
        except Exception as e:
            self.logger.error("Insertion failed: %s", e)
            raise InsertionError(f"Insertion failed: {e}") from e

    def _build_unit_map(
        self, extraction: ExtractionResult
    ) -> dict[str, TextUnit]:
        """
        Build a map from unit_id to TextUnit.

        Args:
            extraction: Extraction result.

        Returns:
            Dict mapping unit_id to TextUnit.
        """
        unit_map: dict[str, TextUnit] = {}
        for xhtml in extraction.xhtml_extractions:
            for unit in xhtml.text_units:
                unit_map[unit.unit_id] = unit
        return unit_map

    def _build_translation_map(
        self, results: list[TranslationResult]
    ) -> dict[str, TranslatedUnit]:
        """
        Build a map from unit_id to TranslatedUnit.

        Args:
            results: List of translation results.

        Returns:
            Dict mapping unit_id to TranslatedUnit.
        """
        translation_map: dict[str, TranslatedUnit] = {}
        for result in results:
            for unit in result.translated_units:
                translation_map[unit.unit_id] = unit
        return translation_map

    def _create_output_path(self, input_data: InsertionInput) -> Path:
        """
        Create output path for translated EPUB.

        Args:
            input_data: Insertion input.

        Returns:
            Path for output EPUB.
        """
        original_name = input_data.epub_path.stem
        lang_code = input_data.target_language.value
        output_name = f"{original_name}_{lang_code}.epub"
        return input_data.output_dir / output_name

    def _create_translated_epub(
        self,
        input_path: Path,
        output_path: Path,
        unit_map: dict[str, TextUnit],
        translation_map: dict[str, TranslatedUnit],
        errors: list[str],
    ) -> None:
        """
        Create the translated EPUB file.

        Args:
            input_path: Original EPUB path.
            output_path: Output EPUB path.
            unit_map: Map from unit_id to TextUnit.
            translation_map: Map from unit_id to TranslatedUnit.
            errors: List to collect error messages.
        """
        # Build xhtml_path -> [(xpath, unit_id)] map
        xpath_map: dict[str, list[tuple[str, str]]] = {}
        for unit_id, unit in unit_map.items():
            xhtml_path = unit.location.xhtml_path
            if xhtml_path not in xpath_map:
                xpath_map[xhtml_path] = []
            xpath_map[xhtml_path].append((unit.location.xpath, unit_id))

        with ZipFile(input_path, "r") as zin, ZipFile(output_path, "w") as zout:
            # Write mimetype first without compression (EPUB spec)
            if "mimetype" in zin.namelist():
                zout.writestr(
                    "mimetype", zin.read("mimetype"), compress_type=ZIP_STORED
                )

            for item in zin.infolist():
                if item.filename == "mimetype":
                    continue

                content: bytes = zin.read(item.filename)

                if item.filename.endswith((".xhtml", ".html", ".htm")):
                    # Check if this XHTML has translations
                    if item.filename in xpath_map:
                        new_content = self._process_xhtml(
                            content=content,
                            xhtml_path=item.filename,
                            xpath_entries=xpath_map[item.filename],
                            unit_map=unit_map,
                            translation_map=translation_map,
                            errors=errors,
                        )
                        zout.writestr(
                            item.filename, new_content, compress_type=ZIP_DEFLATED
                        )
                    else:
                        zout.writestr(
                            item.filename, content, compress_type=ZIP_DEFLATED
                        )
                else:
                    zout.writestr(item.filename, content, compress_type=ZIP_DEFLATED)

    def _process_xhtml(
        self,
        content: bytes,
        xhtml_path: str,
        xpath_entries: list[tuple[str, str]],
        unit_map: dict[str, TextUnit],
        translation_map: dict[str, TranslatedUnit],
        errors: list[str],
    ) -> bytes:
        """
        Process a single XHTML file to insert translations.

        Args:
            content: Original XHTML content.
            xhtml_path: Path within EPUB.
            xpath_entries: List of (xpath, unit_id) tuples for this XHTML.
            unit_map: Map from unit_id to TextUnit.
            translation_map: Map from unit_id to TranslatedUnit.
            errors: List to collect error messages.

        Returns:
            Modified XHTML content as bytes.
        """
        parser = etree.XMLParser(encoding="utf-8", recover=True)
        root = etree.fromstring(content, parser=parser)
        tree = etree.ElementTree(root)

        for xpath, unit_id in xpath_entries:
            try:
                # Find element by XPath using local-name matching for namespace-agnostic query
                # This handles both namespaced and non-namespaced documents
                local_xpath = self._convert_to_local_name_xpath(xpath)
                elements = root.xpath(local_xpath)
                if not elements:
                    errors.append(f"Element not found: {xhtml_path}:{xpath}")
                    continue

                elem = elements[0]

                # Get translation
                if unit_id not in translation_map:
                    errors.append(f"Translation not found for unit: {unit_id}")
                    continue

                translated_unit = translation_map[unit_id]
                original_unit = unit_map[unit_id]

                # Skip empty translations - keep original content
                if not translated_unit.translated_text.strip():
                    self.logger.warning(
                        "Empty translation for unit %s at %s - keeping original",
                        unit_id,
                        f"{xhtml_path}:{xpath}",
                    )
                    continue

                # Restore inner tags and update element
                self._update_element(
                    elem=elem,
                    translated_text=translated_unit.translated_text,
                    inner_tags=original_unit.inner_tags,
                    errors=errors,
                    context=f"{xhtml_path}:{xpath}",
                )

            except Exception as e:
                errors.append(f"Error processing {xhtml_path}:{xpath}: {e}")

        return etree.tostring(root, encoding="utf-8", xml_declaration=True)

    def _convert_to_local_name_xpath(self, xpath: str) -> str:
        """
        Convert an XPath to use local-name() for namespace-agnostic matching.

        Args:
            xpath: Original XPath like /html/body/p[1]

        Returns:
            XPath using local-name() like /*[local-name()='html']/*[local-name()='body']/*[local-name()='p'][1]
        """
        import re

        # Pattern to match path segments like /tagname or /tagname[n]
        pattern = r"/([a-zA-Z][a-zA-Z0-9]*)(\[[^\]]+\])?"

        def replace_segment(match: re.Match) -> str:
            tag = match.group(1)
            predicate = match.group(2) or ""
            return f"/*[local-name()='{tag}']{predicate}"

        return re.sub(pattern, replace_segment, xpath)

    def _update_element(
        self,
        elem: etree._Element,
        translated_text: str,
        inner_tags: list[InnerTag],
        errors: list[str],
        context: str,
    ) -> None:
        """
        Update an element with translated content.

        Args:
            elem: Element to update.
            translated_text: Translated text with placeholders.
            inner_tags: Original inner tag metadata.
            errors: List to collect error messages.
            context: Context string for error messages.
        """
        try:
            # Get element info
            tag = etree.QName(elem.tag).localname
            attributes = dict(elem.attrib)
            nsmap = elem.nsmap if hasattr(elem, "nsmap") else None

            # Create new element with restored content
            new_elem = self._handler.restore_to_element(
                parent_tag=tag,
                translated_text=translated_text,
                inner_tags=inner_tags,
                parent_attributes=attributes,
                nsmap=nsmap,
            )

            # Replace element content (keep original tail)
            original_tail = elem.tail
            elem.text = new_elem.text

            # Clear and copy children
            for child in list(elem):
                elem.remove(child)
            for child in new_elem:
                elem.append(child)

            # Preserve tail
            elem.tail = original_tail

        except Exception as e:
            errors.append(f"Failed to restore tags at {context}: {e}")
