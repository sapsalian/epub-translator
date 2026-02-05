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
    sections = [
        f"Source language: {source_language.value}\n"
        f"Target language: {target_language.value}",
    ]

    if existing_terms:
        sections.append(
            f"Already identified terms (maintain consistency):\n"
            f"{_format_term_list(existing_terms)}"
        )

    if custom_instructions:
        sections.append(f"Custom Instructions:\n{custom_instructions}")

    sections.append(f"Text to analyze:\n{chunk_text}")

    return "\n\n".join(sections)


def build_meta_merge_input(
    chunk_summaries: list[str],
    chunk_terms: list[TermDict],
    source_language: Language,
    target_language: Language,
    chunk_styles: list[str] | None = None,
    custom_instructions: str = "",
) -> str:
    sections = [
        f"Source language: {source_language.value}\n"
        f"Target language: {target_language.value}",
    ]

    if custom_instructions:
        sections.append(f"Custom Instructions:\n{custom_instructions}")

    summaries_text = "\n".join(
        f"Chunk {i}:\n{summary}"
        for i, summary in enumerate(chunk_summaries, 1)
    )
    sections.append(f"--- Chunk Summaries ---\n{summaries_text}")

    all_terms = _collect_chunk_terms(chunk_terms)
    if all_terms:
        term_lines = "\n".join(
            f"  - {source} -> {targets[0]}" if len(targets) == 1
            else f"  - {source} -> {' / '.join(targets)} (conflict)"
            for source, targets in sorted(all_terms.items())
        )
        sections.append(f"--- Collected Terms ---\n{term_lines}")

    non_empty_styles = [s for s in (chunk_styles or []) if s]
    if non_empty_styles:
        style_lines = "\n".join(
            f"Chunk {i}:\n{style}"
            for i, style in enumerate(non_empty_styles, 1)
        )
        sections.append(f"--- Chunk Style Notes ---\n{style_lines}")

    return "\n\n".join(sections)


def build_translation_input(
    unit_ids: list[str],
    texts: list[str],
    source_language: Language,
    target_language: Language,
    term_dictionary: TermDict,
    context_summary: str,
    style_guidelines: str = "",
) -> str:
    sections = [
        f"Translate from {source_language.value} to {target_language.value}.",
    ]

    if term_dictionary:
        sections.append(
            f"Term Dictionary (use these translations):\n"
            f"{_format_term_list(term_dictionary, limit=100)}"
        )

    if style_guidelines:
        sections.append(f"Style Guidelines:\n{style_guidelines}")

    if context_summary:
        sections.append(f"Context:\n{context_summary}")

    text_lines = "\n".join(
        f"[{unit_id}] {text}" for unit_id, text in zip(unit_ids, texts)
    )
    sections.append(
        f"--- Texts to Translate ---\n"
        f"(Each line: [unit_id] text)\n"
        f"{text_lines}"
    )

    return "\n\n".join(sections)


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
