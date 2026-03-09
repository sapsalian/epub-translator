# Manual Scenario Checklist

This checklist verifies end-to-end behavior for both workflow modes:
- `classic`
- `glossary_review`

Use this after backend/frontend changes affecting job state transitions, review flow, or resume behavior.

## Preconditions

- App server is running.
- Frontend is running.
- A valid `.epub` file is available.
- API key is configured if real translation is required.

## Scenario A: classic mode

1. Upload an EPUB.
2. Select source/target language.
3. Select workflow mode: `기본 번역` (`classic`).
4. Start the job.
5. Verify job state progression in list:
   - `queued` -> `processing` -> `done`
6. Verify output:
   - download button is visible
   - file can be downloaded

Expected result:
- Job completes without review screen.
- Existing behavior is unchanged from pre-review flow.

## Scenario B: glossary_review mode

1. Upload an EPUB.
2. Select source/target language.
3. Select workflow mode: `용어 검토 후 번역` (`glossary_review`).
4. Start the job.
5. Verify job pauses after preprocess:
   - state becomes `awaiting_review`
   - card shows `검토` CTA
6. Open review screen (`/jobs/:id/review/glossary` via CTA).
7. Verify glossary load:
   - source/target term rows are shown
8. Edit glossary:
   - modify one term
   - add one term
   - delete one term
9. Save glossary.
10. Click `진행`.
11. Verify same job resumes and completes:
    - `awaiting_review` -> `queued` -> `processing` -> `done`
12. Verify output is downloadable.

Expected result:
- Review step is enforced before translation for `glossary_review`.
- Continue uses the same job ID.

## Regression checks

1. Failed-job retry still works (`POST /api/jobs/{id}/retry`).
2. Job delete still works in each state.
3. Job list/SSE updates reflect state transitions.
4. `classic` and `glossary_review` can coexist in the same job list.

## API spot checks (optional)

For a `glossary_review` job:
- `GET /api/jobs/{id}/glossary` returns `terms`, `has_edits`.
- `PUT /api/jobs/{id}/glossary` accepts full replacement list.
- `POST /api/jobs/{id}/continue` returns `ok: true` only from `awaiting_review`.
