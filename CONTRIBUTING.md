# Contributing

## Environment
- Python: use project venv
- Tests: `.venv/bin/python -m pytest`

## Workflow
1. Make small, focused changes.
2. Update docs if structure or behavior changes:
   - `CLAUDE.md`
   - `AGENTS.md`
   - `docs/ARCHITECTURE.md`
   - `docs/STYLE_GUIDE.md`
3. Add/adjust tests for new behavior.
4. Run relevant tests before commit.

## Commit Style
- Use conventional-ish prefixes already in repo, e.g.:
  - `feat(scope): ...`
  - `fix(scope): ...`
- Provide a short, specific subject; add bullet body if needed.

## Tests
- All tests: `.venv/bin/python -m pytest`
- Pipeline tests: `.venv/bin/python -m pytest tests/pipeline/ -v`
- Specific file: `.venv/bin/python -m pytest tests/pipeline/workers/test_extraction.py -v`

## Notes
- Checkpoints are user data; preserve backwards compatibility when possible.
- Placeholder tags must remain stable (see `docs/STYLE_GUIDE.md`).
