# Style Guide

## Naming
- Prefer explicit, self-describing names.
- Avoid abbreviations unless domain-standard (e.g., EPUB, XHTML).

## Python
- Use type hints for public interfaces.
- Keep functions focused; prefer smaller helpers over long methods.

## Logging
- Use `logger.info` for stage-level events.
- Use `logger.warning` for recoverable issues.
- Use `logger.error` for failed stage transitions.

## Placeholders
- Placeholder format: `{{n}}`, `{{/n}}`, `{{n/}}`.
- Do not add spaces inside placeholders.
- Preserve placeholder order and structure.

## Style Notes & Instructions
- `style_notes` are extracted during preprocess (chunk -> XHTML -> EPUB).
- Translation uses XHTML style when available; falls back to EPUB style.
- `custom_instructions` are appended to style guidelines.

## Tests
- Add tests for new parsing/format rules.
- Prefer unit tests for worker behavior + integration tests for pipeline flow.
