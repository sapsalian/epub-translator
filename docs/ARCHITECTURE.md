# Architecture

## Pipeline Overview
EPUB translation is a four-stage pipeline with checkpointing:

1. Extraction (CPU)
   - Parse EPUB XHTML
   - Extract translatable elements
   - Replace inner tags with placeholders
2. Preprocess (IO)
   - Summaries, term dictionary, style notes
   - Chunk-level extraction + merge into XHTML/EPUB results
3. Translation (IO)
   - Translate text units with term dictionary and style guidelines
4. Insertion (CPU)
   - Restore tags and write translated EPUB

## Data Flow
```
EPUB -> ExtractionResult -> PreprocessResult -> TranslationResult -> InsertionResult
```

## Key Models
- `TextUnit`: translated unit with placeholders and inner tag metadata
- `ExtractionResult`: per-XHTML extracted units + raw text
- `PreprocessResult`: term dictionary, summaries, style notes
- `TranslationResult`: translated units per XHTML

## Style Notes
- Preprocess extracts style notes per chunk.
- Chunk styles are merged into XHTML style; XHTML styles are merged into EPUB style.
- Translation uses XHTML style if present; otherwise EPUB style.
- `PIPELINE_CUSTOM_INSTRUCTIONS` can inject additional guidance.

## Checkpointing
- Stored in `checkpoints/` by default via `FilePersistenceBackend`.
- Resume point determined by `CheckpointManager.get_resume_point`.

## Parsing/Placeholders
- Inner tags use placeholders: `{{n}}`, `{{/n}}`, `{{n/}}`.
- `InnerTagHandler` restores placeholders back to XML.
