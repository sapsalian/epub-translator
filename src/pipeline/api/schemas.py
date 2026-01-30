"""
Pydantic schemas for structured API outputs.

These models are used with OpenAI's Responses API to ensure
type-safe, validated responses from the LLM.
"""

from pydantic import BaseModel, Field

from src.pipeline.models import TermDict


class ChunkExtractionOutput(BaseModel):
    """Output schema for chunk extraction (summary + terms)."""

    summary: str = Field(description="Brief summary of the chunk content (2-3 sentences)")
    terms: TermDict = Field(
        default_factory=dict,
        description="Term dictionary mapping source terms to target translations (proper nouns, technical terms only)",
    )


class MergeOutput(BaseModel):
    """Output schema for merging multiple chunk extractions."""

    summary: str = Field(description="Combined summary of all chunks (3-5 sentences)")
    terms: TermDict = Field(
        default_factory=dict,
        description="Merged and curated term dictionary (source -> target, common words filtered out)",
    )


class TranslationOutput(BaseModel):
    """Output schema for translation responses."""

    translations: dict[str, str] = Field(
        description="Mapping of unit_id to translated text"
    )