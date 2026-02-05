"""
Dynamic input builders for LLM API calls.

These functions build the input data that changes per request.
Static instructions are kept separate for caching efficiency.
"""

from src.pipeline.models import Language, TermDict


def _format_term_list(terms: TermDict, limit: int = 0) -> str:
    items = sorted(terms.items())
    if limit:
        items = items[:limit]
    return "\n".join(f"  - {source} -> {target}" for source, target in items)


def build_chunk_extraction_input(
    chunk_text: str,
    source_language: Language,
    target_language: Language,
    existing_terms: TermDict | None = None,
    custom_instructions: str = "",
) -> str:
    existing_section = ""
    if existing_terms:
        existing_section = (
            f"\n\nAlready identified terms (maintain consistency):\n"
            f"{_format_term_list(existing_terms)}"
        )

    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\nCustom Instructions:\n{custom_instructions}"

    return (
        f"Source language: {source_language.value}\n"
        f"Target language: {target_language.value}"
        f"{existing_section}\n"
        f"{custom_section}\n"
        f"\nText to analyze:\n"
        f"{chunk_text}"
    )


def build_meta_merge_input(
    chunk_summaries: list[str],
    chunk_terms: list[TermDict],
    source_language: Language,
    target_language: Language,
    chunk_styles: list[str] | None = None,
    custom_instructions: str = "",
) -> str:
    summaries_section = "\n".join(
        f"\nChunk {i}:\n{summary}"
        for i, summary in enumerate(chunk_summaries, 1)
    )

    all_terms = _collect_chunk_terms(chunk_terms)
    terms_section = ""
    if all_terms:
        term_lines = "\n".join(
            f"  - {source} -> {targets[0]}" if len(targets) == 1
            else f"  - {source} -> {' / '.join(targets)} (conflict)"
            for source, targets in sorted(all_terms.items())
        )
        terms_section = f"\n\n--- Collected Terms ---\n{term_lines}"

    styles_section = ""
    non_empty_styles = [s for s in (chunk_styles or []) if s]
    if non_empty_styles:
        style_lines = "\n".join(
            f"\nChunk {i}:\n{style}"
            for i, style in enumerate(non_empty_styles, 1)
        )
        styles_section = f"\n\n--- Chunk Style Notes ---{style_lines}"

    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\nCustom Instructions:\n{custom_instructions}"

    return (
        f"Source language: {source_language.value}\n"
        f"Target language: {target_language.value}\n"
        f"{custom_section}\n"
        f"\n--- Chunk Summaries ---"
        f"{summaries_section}"
        f"{terms_section}"
        f"{styles_section}"
    )


def build_translation_input(
    unit_ids: list[str],
    texts: list[str],
    source_language: Language,
    target_language: Language,
    term_dictionary: TermDict,
    context_summary: str,
    style_guidelines: str = "",
) -> str:
    terms_section = ""
    if term_dictionary:
        terms_section = (
            f"\n\nTerm Dictionary (use these translations):\n"
            f"{_format_term_list(term_dictionary, limit=100)}"
        )

    style_section = ""
    if style_guidelines:
        style_section = f"\n\nStyle Guidelines:\n{style_guidelines}"

    context_section = ""
    if context_summary:
        context_section = f"\n\nContext:\n{context_summary}"

    text_lines = "\n".join(
        f"[{unit_id}] {text}" for unit_id, text in zip(unit_ids, texts)
    )

    return (
        f"Translate from {source_language.value} to {target_language.value}."
        f"{terms_section}"
        f"{style_section}"
        f"{context_section}\n"
        f"\n--- Texts to Translate ---\n"
        f"(Each line: [unit_id] text)\n"
        f"{text_lines}\n"
        f"\nIMPORTANT: Preserve all placeholder tags ({{{{1}}}}, {{{{/1}}}}, {{{{2/}}}}, etc.) exactly."
    )


def _collect_chunk_terms(
    chunk_terms: list[TermDict],
) -> dict[str, list[str]]:
    all_terms: dict[str, list[str]] = {}
    for terms in chunk_terms:
        for source, target in terms.items():
            if source:
                if source not in all_terms:
                    all_terms[source] = []
                if target and target not in all_terms[source]:
                    all_terms[source].append(target)
    return all_terms
