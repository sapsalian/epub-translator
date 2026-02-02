"""
JSON schemas for OpenAI Responses API structured outputs.

Uses array-of-objects instead of dynamic-key dicts because OpenAI's
json_schema format requires additionalProperties: false on all objects,
making dict[str, str] (additionalProperties: {"type": "string"}) impossible.
"""

_TERM_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "source": {"type": "string", "description": "Source language term"},
        "target": {"type": "string", "description": "Target language translation"},
    },
    "required": ["source", "target"],
    "additionalProperties": False,
}

_TRANSLATION_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "unit_id": {"type": "string", "description": "Text unit identifier"},
        "text": {"type": "string", "description": "Translated text"},
    },
    "required": ["unit_id", "text"],
    "additionalProperties": False,
}

CHUNK_EXTRACTION_SCHEMA: dict = {
    "type": "json_schema",
    "name": "ChunkExtractionOutput",
    "schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of the chunk content (2-3 sentences)",
            },
            "terms": {
                "type": "array",
                "description": "Key terms with target language translations",
                "items": _TERM_ENTRY_SCHEMA,
            },
        },
        "required": ["summary", "terms"],
        "additionalProperties": False,
    },
    "strict": True,
}

MERGE_SCHEMA: dict = {
    "type": "json_schema",
    "name": "MergeOutput",
    "schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Combined summary of all chunks (3-5 sentences)",
            },
            "terms": {
                "type": "array",
                "description": "Consolidated term dictionary",
                "items": _TERM_ENTRY_SCHEMA,
            },
        },
        "required": ["summary", "terms"],
        "additionalProperties": False,
    },
    "strict": True,
}

TRANSLATION_SCHEMA: dict = {
    "type": "json_schema",
    "name": "TranslationOutput",
    "schema": {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "description": "Translated text units",
                "items": _TRANSLATION_ENTRY_SCHEMA,
            },
        },
        "required": ["translations"],
        "additionalProperties": False,
    },
    "strict": True,
}