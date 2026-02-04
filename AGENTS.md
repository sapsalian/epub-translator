# AGENTS.md

Purpose: help Codex/agents quickly understand project structure, workflows, and house rules.

## Golden Rules
- Use clear, self-explanatory names (functions/variables/classes).
- When changing structure or adding files, update docs (this file and/or CLAUDE.md).
- Keep checkpoints/resume behavior intact; avoid breaking persistence formats.
- Prefer small, testable changes and run relevant tests.

## Quick Commands
- Tests (all): `.venv/bin/python -m pytest`
- Tests (pipeline): `.venv/bin/python -m pytest tests/pipeline/ -v`
- Tests (single file): `.venv/bin/python -m pytest tests/pipeline/workers/test_extraction.py -v`

## Project Layout (Summary)
- `src/epub_walker/`: EPUB parsing
- `src/matchers/`: element matchers
- `src/pipeline/`: translation pipeline (config, orchestrator, workers, API, persistence)
- `tests/`: pipeline + integration tests

## Pipeline Stages (High-Level)
1. Extraction (CPU): parse XHTML, extract text units, preserve inner tags.
2. Preprocess (IO): chunk summaries + term dictionary + style notes.
3. Translation (IO): translate text units using term dictionary and style guidelines.
4. Insertion (CPU): restore tags and write translated EPUB.

## Style/Prompting Notes
- Placeholders: `{{n}}`, `{{/n}}`, `{{n/}}` must be preserved exactly.
- Style notes are extracted during preprocess and merged into EPUB-level style.
- XHTML-specific style is used first; if missing, fallback to EPUB style.
- `PIPELINE_CUSTOM_INSTRUCTIONS` can further guide style.

## Docs to Keep in Sync
- `CLAUDE.md`: project notes and structure
- `docs/ARCHITECTURE.md`: pipeline data flow
- `docs/STYLE_GUIDE.md`: conventions and patterns

## Current Plan Reference
- See `/Users/an-yongjin/.claude/plans/serialized-inventing-lamport.md` for ongoing roadmap.
