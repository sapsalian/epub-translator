"""
Data models for the translation pipeline.

All models are Pydantic BaseModels for JSON serialization support.
This enables checkpointing, inter-process communication, and distributed processing.

Identifier scheme:
- epub_id: UUID or hash identifying the EPUB
- xhtml_id: Hash of (epub_id + xhtml_path)
- unit_id: Hash of (xhtml_id + xpath)
"""

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    """Supported languages for translation."""

    KOREAN = "ko"
    ENGLISH = "en"
    JAPANESE = "ja"
    CHINESE_SIMPLIFIED = "zh-CN"
    CHINESE_TRADITIONAL = "zh-TW"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"


# =============================================================================
# Core Models (used across all workers)
# =============================================================================


class InnerTag(BaseModel):
    """
    Metadata for a tag inside a translation target element.

    Inner tags are any tags (block or inline) found within the element
    being translated. They are replaced with numbered placeholders during
    extraction and restored during insertion.

    Example:
        <p>Hello <b>world</b>!</p>
        -> InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)
    """

    index: int = Field(description="Placeholder number (1, 2, 3...)")
    tag_name: str = Field(description="Original tag name (b, em, a, div, etc.)")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Tag attributes"
    )
    is_self_closing: bool = Field(
        default=False, description="Whether tag is self-closing (br, img, etc.)"
    )


class TextLocation(BaseModel):
    """Location information for inserting translated text back into EPUB."""

    xhtml_path: str = Field(description="Path to XHTML file within EPUB")
    xpath: str = Field(description="XPath to the element")


class TextUnit(BaseModel):
    """
    A single unit of text to be translated.

    Contains the original text with inner tags replaced by numbered placeholders,
    along with metadata needed to restore the original structure after translation.
    """

    unit_id: str = Field(description="Unique ID (hash of xhtml_id + xpath)")
    location: TextLocation = Field(description="Location for insertion")
    source_text: str = Field(description="Original text (for reference)")
    tagged_text: str = Field(description="Text with inner tags replaced by numbers")
    inner_tags: list[InnerTag] = Field(
        default_factory=list, description="Inner tag metadata for restoration"
    )


# Note: TermCandidate removed - term extraction now done by LLM directly


# =============================================================================
# Extraction Models (ExtractionWorker output)
# =============================================================================


class XhtmlExtraction(BaseModel):
    """Extraction result for a single XHTML file."""

    xhtml_id: str = Field(description="Unique ID (hash of epub_id + xhtml_path)")
    xhtml_path: str = Field(description="Path to XHTML file within EPUB")
    text_units: list[TextUnit] = Field(
        default_factory=list, description="Extracted text units"
    )
    raw_text: str = Field(default="", description="Raw text for generating summary")


class ExtractionResult(BaseModel):
    """
    Complete extraction result for an EPUB file.

    This is the output of ExtractionWorker.
    Can be serialized to JSON for checkpointing.
    """

    epub_id: str = Field(description="Unique EPUB identifier")
    source_language: Language = Field(description="Source language of the EPUB")
    xhtml_extractions: list[XhtmlExtraction] = Field(
        default_factory=list, description="Per-XHTML extraction results"
    )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ExtractionResult":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


# =============================================================================
# Preprocess Models (PreprocessWorker output)
# =============================================================================


class TermMapping(BaseModel):
    """A single term mapping in the dictionary."""

    source: str = Field(description="Source term")
    target: str = Field(description="Translated term")


class TermDictionary(BaseModel):
    """Dictionary of term translations for a specific language pair."""

    source_language: Language = Field(description="Source language")
    target_language: Language = Field(description="Target language")
    mappings: list[TermMapping] = Field(
        default_factory=list, description="Term mappings"
    )


class PreprocessResult(BaseModel):
    """
    Preprocessing result containing term dictionary and summaries.

    This is the output of PreprocessWorker.
    """

    epub_id: str = Field(description="EPUB identifier")
    term_dictionary: TermDictionary = Field(description="Finalized term dictionary")
    summaries: dict[str, str] = Field(
        default_factory=dict, description="xhtml_id -> summary mapping"
    )
    epub_summary: str = Field(
        default="", description="Overall EPUB summary for context"
    )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PreprocessResult":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


# =============================================================================
# Translation Models (TranslationWorker input/output)
# =============================================================================


class TranslationTask(BaseModel):
    """
    Input for TranslationWorker.

    Minimal data unit to reduce network overhead.
    Worker fetches term_dictionary and summary from DB using epub_id and xhtml_id.
    """

    epub_id: str = Field(description="EPUB identifier")
    xhtml_id: str = Field(description="XHTML identifier")
    target_language: Language = Field(description="Target language for translation")
    text_units: list[TextUnit] = Field(description="Text units to translate")


class TranslatedUnit(BaseModel):
    """A translated text unit."""

    unit_id: str = Field(description="ID of the source TextUnit")
    translated_text: str = Field(
        description="Translated text (with numbered placeholders preserved)"
    )


class TranslationResult(BaseModel):
    """
    Translation result for a single XHTML.

    This is the output of TranslationWorker.
    """

    epub_id: str = Field(description="EPUB identifier")
    xhtml_id: str = Field(description="XHTML identifier")
    target_language: Language = Field(description="Target language")
    translated_units: list[TranslatedUnit] = Field(
        default_factory=list, description="Translated text units"
    )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TranslationResult":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


# =============================================================================
# Insertion Models (InsertionWorker output)
# =============================================================================


class InsertionResult(BaseModel):
    """Result of inserting translations back into EPUB."""

    epub_id: str = Field(description="EPUB identifier")
    target_language: Language = Field(description="Target language")
    output_path: str = Field(description="Path to the generated EPUB")
    success: bool = Field(default=True, description="Whether insertion succeeded")
    errors: list[str] = Field(
        default_factory=list, description="Error messages if any"
    )
