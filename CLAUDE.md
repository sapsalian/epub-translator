# Project Notes for Claude

## Global Workflow Dependency (Required)

- This project template is paired with global `~/.claude` config from [claude-workflow](https://github.com/sapsalian/claude-workflow).
- Keep these global files in sync: `settings.json`, `CLAUDE.md`, `hooks/auto-approve-exit-plan.sh`, `skills/develop/SKILL.md`.
- Project workflow state source of truth is `.claude/plans/*.md` in this repo.

## Coding Guidelines

- **명확한 네이밍**: 함수, 변수, 클래스 이름은 그 자체로 의미가 명확해야 함. 주석 없이도 역할을 알 수 있도록 고심해서 작명할 것.

## Workflow Guidelines

- **코드 수정/구조 변경 시**: 바로 plan 또는 CLAUDE.md에 반영
  - 새 파일/패키지 추가 → CLAUDE.md Project Structure 업데이트
  - TODO 발견 → plan에 기록
  - 완료된 항목 → plan에서 체크 표시
- **커밋 전**: 관련 문서 업데이트 확인
- **Codex CLI 활용**: MCP 도구 `mcp__codex-cli__codex`를 통해 Codex에 작업 위임 가능. Codex 결과물은 반드시 직접 검증(코드 리뷰, 테스트 실행) 후 반영할 것.

## Recent Updates (2026-03-10)

- Workflow mode 추가:
  - `classic`
  - `glossary_review` (preprocess 후 `awaiting_review` 대기)
- Jobs API 추가:
  - `GET /api/jobs/{id}/glossary`
  - `PUT /api/jobs/{id}/glossary`
  - `POST /api/jobs/{id}/continue`
- Frontend review 경로 추가:
  - `#/jobs/:id/review/glossary`
- 수동 검증 체크리스트:
  - `docs/MANUAL_SCENARIO_CHECKLIST.md`

## Recent Updates (2026-03-13)

- 읽기 전용 결과 뷰어 Phase 추가:
  - `GET /api/jobs/{id}/chapters`
  - `GET /api/jobs/{id}/chapters/{chapter_id}`
- EPUB reader 유틸 추가:
  - `src/epub_walker/reader.py`
- Frontend 결과 리뷰 경로 추가:
  - `#/jobs/:id/review/result`

## Python Environment

```bash
# Use this Python/pytest for running tests
/Users/an-yongjin/Codes/projects/epub-translate/.venv/bin/python -m pytest
```

## Test Commands

```bash
# Run all tests
.venv/bin/python -m pytest

# Run pipeline tests
.venv/bin/python -m pytest tests/pipeline/ -v

# Run specific test file
.venv/bin/python -m pytest tests/pipeline/workers/test_extraction.py -v
```

## Project Structure

```
run.py                    # CLI 번역 파이프라인 진입점 (python run.py book.epub)
main.py                   # 데스크탑 앱 진입점 (python main.py)
src/
├── epub_walker/          # EPUB 파싱
│   ├── parser.py         # get_spine_xhtml_paths_by_order(zf) -> list[PurePosixPath]
│   ├── reader.py         # get_chapter_titles(), extract_chapter_paragraphs() for result viewer
│   └── base.py           # XhtmlProcessor, FileProcessor ABCs
├── matchers/             # 요소 매칭
│   ├── base.py           # ElementMatcher ABC (match, reset)
│   ├── implementations.py # AllElementsMatcher, LeafBlockMatcher, TextEmergenceMatcher
│   └── factory.py        # MatcherFactory.create(strategy) -> ElementMatcher
├── pipeline/             # 번역 파이프라인
│   ├── config.py         # PipelineConfig (환경변수 오버라이드 지원)
│   ├── orchestrator.py   # PipelineOrchestrator (파이프라인 조율, 배치 처리)
│   ├── constants.py      # UNTRANSLATABLE_TAGS (code, math, svg, pre 등)
│   ├── filters.py        # TranslatableElementFilter (Matcher 래퍼)
│   ├── models.py         # Language, TermDict, InnerTag, TextUnit, XhtmlExtraction, ExtractionResult 등
│   ├── inner_tag_handler.py # InnerTagHandler (opaque 태그 raw_xml 보존)
│   ├── workers/
│   │   ├── base.py       # Worker[I,O], AsyncWorker[I,O], WorkerError 등
│   │   ├── extraction.py # ExtractionWorker, ExtractionInput
│   │   ├── preprocess.py # PreprocessWorker, PreprocessInput, PreprocessAPIClient
│   │   ├── translation.py # TranslationWorker, TranslationInput, TranslationAPIClient
│   │   └── insertion.py  # InsertionWorker, InsertionInput
│   ├── api/
│   │   ├── base.py       # ChunkExtraction, MergedExtraction, PreprocessClient, TranslationClient Protocols
│   │   ├── openai_client.py # OpenAIClient (Responses API + 구조화된 출력)
│   │   ├── schemas.py    # Pydantic 출력 스키마 (ChunkExtractionOutput, MergeOutput, TranslationOutput)
│   │   ├── instructions.py # 정적 인스트럭션 (캐싱용)
│   │   ├── inputs.py     # 동적 입력 빌더 함수
│   │   └── retry.py      # RetryConfig, with_retry 데코레이터
│   └── persistence/      # 체크포인트 관리
│       ├── base.py       # PersistenceBackend Protocol, PersistenceError
│       ├── models.py     # JobStage, StageProgress, JobStatus
│       ├── file_backend.py # FilePersistenceBackend (JSON 파일 기반)
│       └── manager.py    # CheckpointManager (고수준 API)
├── app/                  # FastAPI 백엔드 API 서버
│   ├── main.py           # FastAPI 앱 인스턴스, 라우터 등록, 정적 파일 서빙
│   ├── config.py         # 서버 설정 (환경변수 로딩)
│   ├── jobs/
│   │   ├── models.py     # JobState(queued|processing|awaiting_review|done|failed), JobInfo dataclass
│   │   ├── manager.py    # JobManager (asyncio.Queue + 다운로드 토큰)
│   │   └── worker.py     # 백그라운드 번역 워커 (순차 처리, glossary_review 워크플로우 지원)
│   ├── routes/
│   │   ├── health.py     # GET /api/health 헬스체크
│   │   ├── upload.py     # POST /api/upload EPUB 업로드
│   │   ├── jobs.py       # POST|GET /api/jobs, GET|DELETE /api/jobs/{id},
│   │   │                 # GET /api/jobs/stream (SSE), POST /api/jobs/{id}/retry,
│   │   │                 # GET|PUT /api/jobs/{id}/glossary, POST /api/jobs/{id}/continue,
│   │   │                 # GET /api/jobs/{id}/chapters, GET /api/jobs/{id}/chapters/{chapter_id}
│   │   ├── download.py   # GET /download/{token} 번역 결과 다운로드
│   │   ├── languages.py  # GET /api/languages 지원 언어 목록
│   │   └── settings.py   # GET/PUT /api/settings 설정 조회/변경
│   └── settings/
│       └── manager.py    # SettingsManager (설정 영속화)
└── desktop/              # pywebview 데스크탑 앱 셸
    ├── app.py            # DesktopApp (포트 탐색 → 서버 시작 → webview 윈도우)
    ├── port_finder.py    # find_free_port() 빈 포트 탐색
    ├── server.py         # uvicorn daemon thread 시작 + health 폴링
    └── downloader.py     # 네이티브 저장 다이얼로그 핸들러
frontend/                 # React + TypeScript + Vite 프론트엔드
├── src/
│   ├── App.tsx           # 루트 컴포넌트 (라우팅)
│   ├── main.tsx          # 엔트리포인트
│   ├── api/
│   │   └── client.ts     # API 클라이언트 (fetch 래퍼)
│   ├── components/
│   │   ├── UploadForm.tsx    # EPUB 업로드 폼
│   │   ├── JobList.tsx       # 작업 목록
│   │   ├── JobCard.tsx       # 개별 작업 카드 (진행률 표시)
│   │   ├── layout/
│   │   │   ├── AppShell.tsx      # 전체 레이아웃 (사이드바 + 메인 영역)
│   │   │   ├── Sidebar.tsx       # 데스크탑 사이드바 네비게이션
│   │   │   └── MobileTopNav.tsx  # 모바일 상단 네비게이션
│   │   └── ui/              # 공통 UI 컴포넌트 (Badge, Button, Progress 등)
│   └── pages/
│       ├── MainPage.tsx           # 메인 페이지 (업로드 + 작업 목록)
│       ├── SettingsPage.tsx       # 설정 페이지
│       ├── GlossaryReviewPage.tsx # 용어집 검토 페이지 (#/jobs/:id/review/glossary)
│       └── ResultReviewPage.tsx   # 결과 뷰어 페이지 (#/jobs/:id/review/result)
```

## Key APIs

### TranslatableElementFilter (pipeline/filters.py)
```python
from src.pipeline import TranslatableElementFilter
from src.matchers import TextEmergenceMatcher

# Matcher를 감싸서 번역 불가 태그(code, math, svg 등)의 하위 요소 제외
filter = TranslatableElementFilter(TextEmergenceMatcher())
filter.reset()  # 새 문서 처리 전 호출

for elem in tree.iter():
    if filter(elem):  # 조상 중 untranslatable 태그 없고 + matcher 조건 충족
        # 번역 대상 요소
        ...
```

### InnerTagHandler (pipeline/inner_tag_handler.py)
```python
handler = InnerTagHandler()
# 추출: 내부 태그 → {{n}} 플레이스홀더 (opaque 태그는 raw_xml로 통째 보존)
output = handler.extract(element)  # -> ExtractionOutput(tagged_text, inner_tags)
# 복원: {{n}} → 원래 태그 (raw_xml 있으면 그대로 반환)
restored = handler.restore(translated_text, inner_tags)  # -> str
```

### MatcherFactory (matchers/factory.py)
```python
from src.matchers import MatcherFactory, MatcherStrategy
matcher = MatcherFactory.create(MatcherStrategy.ALL_ELEMENTS)
matcher.reset()  # 새 문서 처리 전 호출
if matcher(element):  # or matcher.match(element)
    ...
```

### Worker Base (pipeline/workers/base.py)
```python
class Worker(ABC, Generic[InputT, OutputT]):
    def process(self, input_data: InputT) -> OutputT: ...

class AsyncWorker(ABC, Generic[InputT, OutputT]):
    async def process(self, input_data: InputT) -> OutputT: ...

# Exceptions: WorkerError, ExtractionError, PreprocessError, TranslationError, InsertionError
```

### OpenAIClient (pipeline/api/openai_client.py)
```python
from src.pipeline.api import OpenAIClient, RetryConfig, ChunkExtraction, MergedExtraction

# 환경변수 OPENAI_API_KEY 사용
client = OpenAIClient(model="gpt-4o", retry_config=RetryConfig(max_retries=3))

# 청크에서 요약 + 용어 추출 (통합 API 호출)
chunk_result = await client.extract_chunk(
    chunk_text, src_lang, tgt_lang, existing_terms={"term": "번역"}
)  # -> ChunkExtraction(summary, terms: TermDict)

# 여러 청크 결과 병합 (Map-Reduce 패턴)
merged = await client.merge_extractions(
    chunk_summaries=["요약1", "요약2"],
    chunk_terms=[{"a": "b"}, {"c": "d"}],
    source_language=src_lang,
    target_language=tgt_lang,
)  # -> MergedExtraction(summary, terms: TermDict)

# 번역 (ID 기반 입출력)
translations = await client.translate(text_units, src_lang, tgt_lang, term_dict, summary)
# -> list[str] (unit_id 순서 유지)
```

### Retry (pipeline/api/retry.py)
```python
from src.pipeline.api import with_retry, RetryConfig, RateLimitError, TransientAPIError

@with_retry(RetryConfig(max_retries=3, base_delay=1.0))
async def call_api():
    ...
```

### CheckpointManager (pipeline/persistence/manager.py)
```python
from src.pipeline.persistence import (
    CheckpointManager, FilePersistenceBackend, JobStage, JobStatus
)
from src.pipeline.models import Language

# 초기화
backend = FilePersistenceBackend("./checkpoints")
await backend.initialize()
manager = CheckpointManager(backend)

# 작업 생성 및 상태 관리
status = await manager.create_job(epub_id, Language.KOREAN, total_xhtmls=10)
await manager.update_job_stage(epub_id, lang, JobStage.TRANSLATING, total=10)
await manager.increment_job_progress(epub_id, lang, JobStage.TRANSLATING, count=1)

# 체크포인트 저장/로드
await manager.save_extraction(extraction_result)
extraction = await manager.load_extraction(epub_id)

await manager.save_preprocess(preprocess_result, lang)
preprocess = await manager.load_preprocess(epub_id, lang)

await manager.save_translation(translation_result)
translations = await manager.load_all_translations(epub_id, lang)

# 용어집 편집 저장/로드 (glossary_review 워크플로우)
await checkpoint_manager.save_glossary_edit(epub_id, lang, mappings)  # mappings: dict[str, str]
edited = await checkpoint_manager.load_glossary_edit(epub_id, lang)   # -> dict[str, str] | None

# 재개 지점 확인
stage, translated_ids = await manager.get_resume_point(epub_id, lang)
# -> (JobStage.TRANSLATING, {"xhtml001", "xhtml002"})

# 진행률 조회
status = await manager.get_job_status(epub_id, lang)
print(status.overall_progress)  # 0.0 ~ 1.0
print(status.overall_percentage)  # 0 ~ 100
```

### JobStatus Progress (pipeline/persistence/models.py)
```python
# Stage weights (base, weight):
# EXTRACTING:    (0.0,  0.10)  # 0-10%
# PREPROCESSING: (0.10, 0.15)  # 10-25%
# TRANSLATING:   (0.25, 0.70)  # 25-95%
# INSERTING:     (0.95, 0.05)  # 95-100%

status.overall_progress  # 현재 전체 진행률 (0.0 ~ 1.0)
status.stage  # JobStage.TRANSLATING 등
status.translating.percentage  # 현재 스테이지 진행률 (0 ~ 100)
```

### PipelineConfig (pipeline/config.py)
```python
from src.pipeline import PipelineConfig, Language

# 기본 설정
config = PipelineConfig(
    source_language=Language.ENGLISH,
    target_language=Language.KOREAN,
)

# 커스텀 설정
config = PipelineConfig(
    source_language=Language.ENGLISH,
    target_language=Language.KOREAN,
    model="gpt-4o",                     # 기본값: gpt-4.1-mini
    chunk_size=8000,                    # 전처리 청크 크기 (기본: 4000자)
    batch_size=8000,                    # 번역 배치 크기 (기본: 4000자)
    preprocess_max_concurrent=10,       # 전처리 동시 API 호출 수 (기본: 20)
    translation_max_concurrent=20,      # 번역 동시 API 호출 수 (기본: 20)
    output_dir=Path("./out"),           # 출력 디렉토리
    checkpoint_dir=Path("./ckpt"),      # 체크포인트 디렉토리
)

# 환경변수 오버라이드 지원 (PIPELINE_ 접두사)
# PIPELINE_MODEL=gpt-4o PIPELINE_TRANSLATION_MAX_CONCURRENT=20 python main.py
config = PipelineConfig.from_env(
    source_language=Language.ENGLISH,
    target_language=Language.KOREAN,
)
```

### PipelineOrchestrator (pipeline/orchestrator.py)
```python
from pathlib import Path
from src.pipeline import PipelineConfig, PipelineOrchestrator, Language

# 설정 및 초기화
config = PipelineConfig(
    source_language=Language.ENGLISH,
    target_language=Language.KOREAN,
)
orchestrator = PipelineOrchestrator(config)
await orchestrator.initialize()

# 단일 EPUB 처리 (체크포인트 자동 저장, 재개 지원)
result = await orchestrator.run(Path("book.epub"))
print(result.output_path)  # ./output/book_ko.epub

# 배치 처리 (순차)
results = await orchestrator.run_batch([
    Path("book1.epub"),
    Path("book2.epub"),
])

# 배치 처리 (병렬)
results = await orchestrator.run_batch(epub_paths, parallel=True)

# 작업 상태 조회
status = await orchestrator.get_job_status(Path("book.epub"))
if status:
    print(status.overall_percentage)  # 진행률 (0-100)

# 작업 데이터 삭제 (재시작용)
await orchestrator.clear_job(Path("book.epub"))
```
