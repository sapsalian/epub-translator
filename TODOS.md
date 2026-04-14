# TODOS

## [ResultReviewPage 개선 — develop 브랜치]

### TODO-1: xhtml_path 전체 경로 정규화
**What:** chapterMap 빌드 시 basename 대신 OPF 루트 기준 전체 상대경로로 비교
**Why:** 동일 파일명이 다른 디렉토리에 있는 EPUB (`OEBPS/text/ch.xhtml`, `OEBPS/notes/ch.xhtml`)에서 잘못 매핑. 실패 시 진단 신호 없음.
**Pros:** 전혀 실패 없는 챕터 링크 이동. **Cons:** iframe 내부 href가 OPF 상대경로일 수 있어 resolve 로직 복잡도 증가.
**Context:** 현재 Item 5 구현은 basename만 비교 (`ch02.xhtml` → `JobChapter`). 실제 EPUB에서 충돌은 드물지만 silent failure. 전체 경로 비교하려면 iframe 내 href를 OPF 루트 기준으로 resolve해야 하며, OPF path를 frontend에 추가 전달해야 할 수 있음.
**Depends on / blocked by:** Item 5 완료 후

---

## [웹서비스 — 론치 후 확장]

### TODO-WEB-1: 시리즈 용어집 연동
**What:** 같은 시리즈 책 번역 시, 이전 권의 용어집을 자동 제안하거나 적용하는 기능
**Why:** 판타지 시리즈나 라이트노벨 독자는 같은 용어(고유명사, 세계관 용어)가 권별로 일관되기를 원함. 현재는 매번 새로 추출/수정해야 함.
**Pros:** 시리즈물 독자 UX 크게 향상, 재구매율 상승 기대.
**Cons:** "같은 시리즈" 판단 로직 복잡 (제목 유사도? 유저 수동 지정?). 용어집 공유 UI 추가 필요.
**Context:** Phase 1 론치 후 추가. 우선 "저장된 용어집을 수동으로 불러와서 적용" 수준으로 MVP 구현 가능.
**Effort:** M (human: ~1주 / CC: ~2시간)
**Priority:** P2
**Depends on / blocked by:** Phase 1 (Glossary DB 스키마) 완료 후

### TODO-WEB-2: 소설 특화 번역 모드
**What:** 일반 전문서적 번역과 다른 서술 스타일 프롬프트. 대화체, 묘사, 시제, 문체를 의식하고 원저 특유의 분위기가 살아남도록 최적화.
**Why:** 주요 타겟 중 하나인 소설/라이트노벨 독자들이 현재 버전으로는 문체가 딱딱하다고 느낄 수 있음. 전문서적용 프롬프트는 소설에 최적이 아님.
**Pros:** 소설 독자 만족도 상승, 재구매율 상승.
**Cons:** 프롬프트 튜닝에 상당한 A/B 테스트 필요. 효과 측정 방법 설계 필요.
**Context:** `translation_prompts` 테이블이 Phase 1에서 생기므로, 소설 모드 프롬프트는 별도 레코드로 추가 가능. UI에서 "번역 모드" 선택 드롭다운 추가.
**Effort:** M (human: ~1주 / CC: ~3시간)
**Priority:** P2
**Depends on / blocked by:** Phase 1 론치 후 유저 피드백 확인

### TODO-WEB-3: 모바일 네이티브 리딩 앱
**What:** 번역된 EPUB을 스마트폰에서 편하게 읽을 수 있는 네이티브 앱 (iOS/Android). "내 도서관"과 연동, 오프라인 읽기, 하이라이트/노트 기능.
**Why:** Phase 2의 개인 도서관 기능이 웹에서만 제공되면 모바일 독서 경험이 불편. 책 읽기는 본질적으로 모바일/태블릿 행동.
**Pros:** 리텐션 대폭 향상, 구독 모델 정당화.
**Cons:** 네이티브 앱 신규 개발 XL 규모. App Store/Play Store 심사 과정.
**Context:** Phase 1,2 론치 후 실제 사용 패턴 확인. 웹 트래픽의 모바일 비율이 높고, 유저들이 "앱 언제 나오냐"고 물어보기 시작하면 착수.
**Effort:** XL (human: ~3개월 / CC: ~2주)
**Priority:** P3
**Depends on / blocked by:** Phase 2 완료 + 유저 수요 확인

---

## [ResultReviewPage 개선 — develop 브랜치]

### TODO-2: 프론트엔드 단위 테스트 인프라 (Vitest + jsdom)
**What:** ResultReviewPage의 순수 함수(`extractStyleOptions`, `filterAllowedStyle`, `styleTextToObject`, `normalizeEditableHtml`) 및 이벤트 핸들러 로직에 대한 Vitest 단위 테스트 세팅
**Why:** Item 1-5, 7, 8은 TypeScript 로직인데 Python 수준의 테스트 커버리지가 없음. 프론트엔드 변경 시 regression 안전망 없음.
**Pros:** 프론트엔드 변경 시 즉각적인 regression 감지. **Cons:** Vitest 세팅 + jsdom 환경 + iframe DOM 모킹 복잡도. (human: ~2일 / CC: ~30분)
**Context:** 현재 `tests/` 아래는 Python 테스트만 있음. `frontend/` 디렉토리에 test infrastructure 없음. iframe 내부 DOM을 jsdom으로 모킹하는 방법 설계 필요.
**Depends on / blocked by:** 없음 (독립)
