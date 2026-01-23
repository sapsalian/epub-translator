"""
Prompt templates for LLM API calls.

Contains system prompts and user prompt templates for:
- Chunk extraction (summary + terms in one call)
- Meta merge (combine chunk results)
- Translation
"""

from src.pipeline.models import Language

# =============================================================================
# Chunk Extraction Prompts (Summary + Terms)
# =============================================================================

CHUNK_EXTRACTION_SYSTEM_PROMPT = """You are a professional text analyst and translator. Your task is to analyze a text chunk and extract:

1. **Summary**: A brief summary (2-3 sentences) capturing the main content, key entities, and tone.
2. **Terms**: Important terms that need consistent translation - proper nouns (names, places, organizations), technical terms, and domain-specific vocabulary.

Guidelines for terms:
- Focus on proper nouns and specialized vocabulary, NOT common words
- Include character names, place names, organization names
- Include technical or domain-specific terms
- For each term, provide an accurate translation

Output as JSON:
{
    "summary": "Brief summary of the chunk...",
    "terms": [
        {"source": "term1", "target": "translation1"},
        {"source": "term2", "target": "translation2"}
    ]
}"""


def build_chunk_extraction_user_prompt(
    chunk_text: str,
    source_language: Language,
    target_language: Language,
    existing_terms: dict[str, str] | None = None,
) -> str:
    """
    Build user prompt for chunk extraction (summary + terms).

    Args:
        chunk_text: Text chunk to analyze.
        source_language: Source language.
        target_language: Target language.
        existing_terms: Already extracted terms for consistency.

    Returns:
        Formatted user prompt.
    """
    existing_str = ""
    if existing_terms:
        existing_str = "\n\nAlready identified terms (maintain consistency):\n"
        for source, target in list(existing_terms.items())[:50]:
            existing_str += f"- {source} → {target}\n"

    return f"""Analyze this {source_language.value} text chunk and extract summary and terms.
Translate terms to {target_language.value}.
{existing_str}
Text chunk:
{chunk_text}

Output JSON with "summary" and "terms" fields."""


# =============================================================================
# Meta Merge Prompts
# =============================================================================

META_MERGE_SYSTEM_PROMPT = """You are a professional editor and translator. Your task is to merge multiple chunk analyses into a coherent whole:

1. **Summary**: Combine chunk summaries into a single coherent summary (3-5 sentences) that captures the overall content.
2. **Terms**: Merge term dictionaries, resolving any conflicts:
   - If the same source term has different translations, choose the most appropriate one based on context
   - Remove duplicates
   - Keep only important terms

Output as JSON:
{
    "summary": "Combined summary...",
    "terms": [
        {"source": "term1", "target": "translation1"},
        ...
    ]
}"""


def build_meta_merge_user_prompt(
    chunk_summaries: list[str],
    chunk_terms: list[list[dict[str, str]]],
    source_language: Language,
    target_language: Language,
) -> str:
    """
    Build user prompt for merging chunk results.

    Args:
        chunk_summaries: List of summaries from each chunk.
        chunk_terms: List of term lists from each chunk.
        source_language: Source language.
        target_language: Target language.

    Returns:
        Formatted user prompt.
    """
    # Format summaries
    summaries_str = "\n\n".join(
        f"Chunk {i+1} summary:\n{summary}"
        for i, summary in enumerate(chunk_summaries)
    )

    # Collect and format all terms
    all_terms: dict[str, list[str]] = {}
    for terms in chunk_terms:
        for term in terms:
            source = term.get("source", "")
            target = term.get("target", "")
            if source:
                if source not in all_terms:
                    all_terms[source] = []
                if target and target not in all_terms[source]:
                    all_terms[source].append(target)

    terms_str = ""
    if all_terms:
        terms_str = "\n\nCollected terms (may have conflicts):\n"
        for source, targets in all_terms.items():
            if len(targets) == 1:
                terms_str += f"- {source} → {targets[0]}\n"
            else:
                terms_str += f"- {source} → {' / '.join(targets)} (conflict)\n"

    return f"""Merge these {source_language.value} chunk analyses into a unified result.
Target language for terms: {target_language.value}

{summaries_str}
{terms_str}
Create a combined summary and resolve any term conflicts.
Output JSON with "summary" and "terms" fields."""


# =============================================================================
# Translation Prompts
# =============================================================================

TRANSLATION_SYSTEM_PROMPT = """You are a professional translator. Translate the provided text while preserving:

1. **Placeholder tags**: Text contains numbered placeholders like {{1}}, {{/1}}, {{2/}} etc.
   - {{n}} = opening tag
   - {{/n}} = closing tag
   - {{n/}} = self-closing tag
   These MUST be preserved exactly in the translation.

2. **Meaning and tone**: Maintain the original meaning, style, and emotional tone.

3. **Term consistency**: Use the provided term dictionary for consistent translations.

4. **Natural flow**: The translation should read naturally in the target language.

Output translations as a JSON object mapping unit IDs to translated strings."""


def build_translation_user_prompt(
    unit_ids: list[str],
    texts: list[str],
    source_language: Language,
    target_language: Language,
    term_dictionary: dict[str, str],
    context_summary: str,
) -> str:
    """
    Build user prompt for translation.

    Args:
        unit_ids: IDs for each text unit.
        texts: Texts to translate (with placeholder tags).
        source_language: Source language.
        target_language: Target language.
        term_dictionary: Term mappings to use.
        context_summary: Summary for context.

    Returns:
        Formatted user prompt.
    """
    # Format term dictionary
    terms_str = ""
    if term_dictionary:
        terms_str = "\n\nTerm Dictionary (use these translations):\n"
        for source, target in list(term_dictionary.items())[:100]:
            terms_str += f"- {source} → {target}\n"

    # Format texts with IDs
    texts_str = "\n".join(
        f"[{unit_id}] {text}"
        for unit_id, text in zip(unit_ids, texts)
    )

    context_str = ""
    if context_summary:
        context_str = f"\n\nContext:\n{context_summary}"

    return f"""Translate from {source_language.value} to {target_language.value}.
{terms_str}{context_str}

Texts to translate (each prefixed with [unit_id]):
{texts_str}

IMPORTANT: Preserve all placeholder tags ({{1}}, {{/1}}, {{2/}}, etc.) exactly.

Output as a JSON object mapping unit IDs to translations:
{{"unit_id_1": "translation1", "unit_id_2": "translation2", ...}}"""
