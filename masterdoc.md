# RUSH - Dickinson College Intelligent Assistant

## 프로젝트 개요

**RUSH**는 Dickinson College 구성원(학생, 교직원)이 공식 웹사이트의 정보를 빠르고 정확하게 얻을 수 있도록 돕는 **도메인 특화 AI 챗봇**입니다. 전수 크롤링을 통해 수집된 데이터를 기반으로 일관되게 빠른 응답(1-2초)을 제공합니다.

**관련 문서**:
- [AI 코딩 컨텍스트 (구현 상세)](ai_context.md) - 개발 시 AI에게 전달할 상세 구현 지침
- [LLM 런타임 컨텍스트 (KR)](masterdoc.md) - 운영 중 모델이 따를 최소 지침
- [LLM Runtime Context (EN)](masterdocen.md) - English version of runtime guidelines

---

## 핵심 원칙

1. **도메인 제한**: 오직 `dickinson.edu` 도메인의 공식 정보만 사용
2. **일관된 속도**: 모든 쿼리에 대해 1-2초 내 응답 보장
3. **완전한 커버리지**: 전수 크롤링을 통한 웹사이트 전체 인덱싱
4. **투명성**: 모든 답변에 출처 URL 명시
5. **보안**: 개인정보 보호 및 악의적 사용 방지

---

## 시스템 아키텍처

### Phase 0: 초기 데이터 구축 (One-time Setup)

#### 전수 크롤링 전략

**목표**: Dickinson.edu 전체 사이트를 한 번에 크롤링하여 완전한 데이터베이스 구축

**크롤링 방식**: BFS(Breadth-First Search) 기반 내부 링크 탐색

```
시드 URL: https://www.dickinson.edu
↓
├─ /academics → 학과별 페이지들
├─ /admissions → 입학 정보
├─ /campus-life → 캠퍼스 생활
├─ /about → 학교 소개
└─ ... (모든 내부 링크 재귀 탐색)
```

**예상 규모**:

* 총 페이지 수: 5,000 ~ 15,000 페이지
* 유효 페이지 (중복 제거 후): 2,000 ~ 5,000 페이지
* 크롤링 시간: 2-3시간 (Rate limiting 포함)
* 저장 공간: 약 25-50MB (텍스트만)

#### Robots.txt / Sitemap 준수

* 반드시 https://www.dickinson.edu/robots.txt를 확인·준수 (Disallow, Crawl-delay 포함)
* User-Agent 식별자에 연락처 포함: 예) "RUSH Crawler (+contact@example.com)"
* 429/503 응답 시 Retry-After 헤더를 준수하며 지수 백오프 적용
* HTTP/2 또는 Keep-Alive 사용으로 연결 수 최소화, 서버 부하 방지

#### URL 필터링 규칙

**✅ 크롤링 대상 (Whitelist)**

* [https://www.dickinson.edu/](https://www.dickinson.edu/)
* [https://dickinson.edu/](https://dickinson.edu/)
* 주요 섹션: /academics, /admissions, /campus-life, /about, /news, /events

**❌ 크롤링 제외 (Blacklist)**

* 로그인 필요 페이지: /login, /signin, /my-dickinson
* 개인정보 페이지: /student-directory, /faculty-directory (이메일/연락처 포함)
* 파일: *.pdf, *.doc, *.xlsx, *.zip
* 이미지: *.jpg, *.png, *.gif
* 동적 파라미터: /events?date=*, /calendar?page=*
* 검색 결과 페이지: /search?q=*

#### URL 정규화

중복 URL 방지를 위한 정규화 규칙:

```python
# 예시
https://www.dickinson.edu/page/  
https://dickinson.edu/page  
https://dickinson.edu/PAGE  
  ↓ 정규화  
https://dickinson.edu/page
```

**정규화 규칙**:

* `www` 제거
* Trailing slash 제거
* 소문자 변환
* 불필요한 쿼리 파라미터 제거(utm_*, gclid 등 추적 파라미터 제거)
* Fragment(#) 제거
* HTTPS 강제(
    http → https 리디렉션 URL은 정규화 단계에서 https로 통일)
* rel=canonical이 있는 경우 canonical URL을 우선 채택

---

### Phase 1: 사용자 요청 처리 (Real-time Pipeline)

**핵심**: 실시간 크롤링 없이 오직 Vector DB 조회만 수행

```
사용자 질문 입력
    ↓
Query Preprocessing
 ├─ Dickinson 관련성 검증 (LLM 기반)
 └─ 질문 카테고리 분류 (Academics/Events/Dining/etc.)
    ↓
Hybrid Search (Vector DB)
 ├─ Vector Similarity Search (의미 기반)
 ├─ Keyword Search (BM25)
 └─ Metadata Filtering (카테고리, 날짜)
    ↓
Context Retrieval
 ├─ Top 5-10 관련 청크 추출
 └─ 출처 URL 수집
    ↓
LLM Answer Generation
 ├─ Prompt: "다음 정보를 바탕으로 답변하세요..."
 ├─ 답변 생성
 └─ 출처 인용 포함
    ↓
Response (1-2초 이내)
 ├─ 답변 텍스트
 ├─ 출처 URL 리스트
 └─ 신뢰도 점수 (optional)
```

#### Cache Miss 처리

**실시간 크롤링 없음!** 대신:

```
[정보 없음 감지]
    ↓
"죄송합니다. 해당 정보를 찾을 수 없습니다.
관련 페이지를 확인해보세요: [추천 링크]
또는 IT 헬프데스크에 문의하세요."
    ↓
[백그라운드 로깅]
 - 미스된 쿼리를 로그에 기록
 - 주간 리포트로 관리자에게 전달
 - 다음 크롤링 시 해당 영역 집중 탐색
```

#### 보안 장치

* **Rate Limiting**:
    * 챗봇: 사용자당 분당 최대 10회 쿼리 제한(애플리케이션 레벨)
    * 크롤러: 도메인 전체 초당 ≤ 1요청(또는 robots.txt의 crawl-delay 우선 준수)
* **질문 검증**: Dickinson 무관한 질문 거부

  * "Who is the president of USA?" → "Dickinson College 관련 질문에만 답변합니다"
* **개인정보 보호**: 학생/교직원 개인정보 절대 노출 금지

### Phase 2: 백그라운드 동기화 (Scheduled Jobs)

**목표**: 데이터베이스를 최신 상태로 유지

---

#### 증분 업데이트 (Incremental Update)

**실행 빈도**: 우선순위 기반

| 우선순위       | 페이지 유형  | 업데이트 빈도       | 예시                                     |
| ---------- | ------- | ------------- | -------------------------------------- |
| **High**   | 동적 콘텐츠  | 매일 (3 AM)     | News, Events, Dining menu              |
| **Medium** | 반정기 콘텐츠 | 매주 (일요일 3 AM) | Admissions deadlines, Course schedules |
| **Low**    | 정적 콘텐츠  | 매월 (1일 3 AM)  | Faculty profiles, History, Buildings   |

---

#### 업데이트 프로세스

```
[매일 밤 3시 실행]
    ↓
1. DB에서 모든 URL 목록 추출 (우선순위별 필터링)
    ↓
2. 각 URL에 대해:
    ├─ (가능 시) HEAD로 ETag/Last-Modified 확인
    ├─ 조건부 GET(If-None-Match / If-Modified-Since) 사용 → 304는 변경 없음 처리
    ├─ (200인 경우) 웹페이지 크롤링
    ├─ 콘텐츠 추출 (본문만)
    ├─ SHA256 해시 생성
    └─ 기존 해시와 비교
    ↓
3. [변경 감지된 경우]
   ├─ 기존 벡터 삭제 (해당 URL의 모든 청크)
   ├─ 새 콘텐츠 청킹 (헤더 기반 분할)
   ├─ 임베딩 생성
   ├─ Vector DB에 저장
   └─ 변경 로그 기록
    ↓
4. [변경 없는 경우]
    ├─ 304 Not Modified 또는 해시 동일
    └─ 마지막 체크 시간만 업데이트
    ↓
5. 완료 리포트 생성
   ├─ 총 체크한 페이지 수
   ├─ 변경 감지된 페이지 수
   ├─ 에러 발생 페이지 수
   └─ 실행 시간
```

**예상 업데이트 규모**:

* High 우선순위: 50-100 페이지 → 5-10분
* Medium 우선순위: 200-500 페이지 → 20-30분
* Low 우선순위: 2,000-5,000 페이지 → 1-2시간

---

#### RSS Feed 활용 (선택적)

Dickinson이 RSS를 제공하는 경우:

```python
# News & Events는 RSS로 빠르게 확인
rss_feeds = [
    'https://www.dickinson.edu/rss/news',
    'https://www.dickinson.edu/rss/events'
]

# RSS 체크 (30초) → 새 글만 크롤링
# 전체 페이지 크롤링(10분)보다 훨씬 효율적
```

---

### Phase 3: 데이터 저장 계층

#### 저장소 구조 개요

시스템은 4개의 주요 저장소로 구성되며, 각각 명확한 역할을 담당합니다:

```
┌─────────────────────────────────────────┐
│         1. Vector Database              │
│           (Weaviate)                    │
│                                         │
│  - 청크 임베딩 (768 or 1536 차원)         │
│  - 메타데이터:                            │
│    · source_url                         │
│    · title                              │
│    · category (academics/events/etc)    │
│    · section (H1/H2 구조)                │
│    · content_hash (SHA256)              │
│    · last_updated (timestamp)           │
│    · chunk_index (페이지 내 순서)         │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│      2. Document Store (MongoDB)        │
│                                         │
│  - 원문 텍스트 또는 HTML 저장              │
│  - 재임베딩 필요 시 활용                   │
│  - 백업 용도                             │
│  - ETag, Last-Modified 저장             │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│          3. Redis (통합)                 │
│                                         │
│  역할 1: Celery Broker/Backend          │
│   - 비동기 작업 큐 (크롤링, 임베딩)          │
│   - 작업 결과 저장                        │
│                                         │
│  역할 2: Hash Index (콘텐츠 변경 감지)     │
│   Key: "hash:{normalized_url}"          │
│   Value: {                              │
│     content_hash: "abc123...",          │
│     last_checked: "2024-01-15T03:00",   │
│     priority: "high",                   │
│     status: "active"                    │
│   }                                     │
│   TTL: 30일                             │
│                                         │
│  역할 3: Query Cache (LLM 응답)          │
│   Key: "cache:query:{query_hash}"       │
│   Value: {                              │
│     answer: "...",                      │
│     sources: [...],                     │
│     confidence: 0.92                    │
│   }                                     │
│   TTL: 1시간                            │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│     4. Logs Database (PostgreSQL)       │
│                                         │
│  - user_queries: 사용자 쿼리 로그         │
│  - cache_misses: 정보 없던 질문들         │
│  - page_updates: 페이지 변경 이력         │
│  - crawl_errors: 크롤링 실패 로그         │
│  - system_metrics: 성능 지표             │
└─────────────────────────────────────────┘
```

#### Redis 상세 설명

**Redis의 3가지 핵심 역할:**

1. **Celery Broker/Backend (메시지 큐)**
   - 비동기 작업(크롤링, 임베딩) 큐잉
   - 작업 상태 및 결과 저장
   - Worker 간 작업 분산

2. **Hash Index (콘텐츠 변경 감지)**
   - URL별 콘텐츠 해시 저장
   - 증분 업데이트 시 변경 감지
   - TTL 30일로 자동 정리

3. **Query Cache (LLM 응답 캐싱)**
   - 동일 질문 재사용 (응답 속도 300배 향상)
   - TTL 1시간 (최신성 보장)
   - Cache Hit Rate 목표: 90% 이상
#### 데이터 모델 예시

##### 1. Weaviate Vector DB Schema

```python
{
    "class": "Chunk",
    "description": "검색 가능한 텍스트 청크",
    "vectorizer": "text2vec-transformers",
    "properties": [
        {"name": "text", "dataType": ["text"]},
        {"name": "source_url", "dataType": ["string"]},
        {"name": "title", "dataType": ["string"]},
        {"name": "category", "dataType": ["string"]},
        {"name": "section", "dataType": ["string"]},
        {"name": "chunk_index", "dataType": ["int"]},
        {"name": "last_updated", "dataType": ["date"]}
    ]
}
```

##### 2. MongoDB Document
```python
{
    "_id": ObjectId("..."),
    "url": "https://dickinson.edu/academics/computer-science",
    "normalized_url": "https://dickinson.edu/academics/computer-science",
    "title": "Computer Science Major",
    "category": "academics",
    "content": "전체 본문 텍스트 10KB...",
    "content_hash": "a3f5b8c9d2e1f4b3a7c8d9e2f1a4b5c6",
    "html": "<html>...</html>",  # 선택
    "etag": "W/\"abc123\"",
    "last_modified": "Wed, 10 Jan 2024 14:30:00 GMT",
    "crawled_at": ISODate("2024-01-15T03:00:00Z"),
    "status": "active",
    "metadata": {
        "word_count": 1234,
        "section_count": 8,
        "links_count": 45
    }
}
```

##### 3. Redis Hash Index

```python
Key: "hash:https://dickinson.edu/academics/computer-science"
Value: {
    "content_hash": "a3f5b8c9d2e1...",
    "last_checked": "2024-01-15T03:00:00Z",
    "last_modified": "2024-01-10T14:30:00Z",
    "priority": "medium",
    "check_frequency": "weekly",
    "status": "active",
    "error_count": 0
}
TTL: 2592000  # 30일
```

##### 4. Redis Query Cache

```python
Key: "cache:query:a3f5b8c9d2e1f4b3"
Value: {
    "query": "컴퓨터 과학과 필수 과목은?",
    "answer": "필수 과목은 CS101, CS102...",
    "sources": [
        "https://dickinson.edu/academics/cs"
    ],
    "confidence": 0.92,
    "cached_at": "2024-01-15T10:30:00Z"
}
TTL: 3600  # 1시간
```

### Phase 4: 콘텐츠 처리 파이프라인

이 단계는 크롤링된 원본 데이터를 검색 가능한 형태로 변환하는 과정입니다.

#### 1. 페이지 크롤링
- Trafilatura + BeautifulSoup 사용
- robots.txt 준수 및 Rate limiting
- 재시도 로직 (3회, 지수 백오프)

#### 2. 콘텐츠 추출
- 본문 텍스트 추출
- 메타데이터 수집 (제목, 카테고리, 섹션)
- HTML 구조 파싱 (H1/H2 기반)

#### 3. 청킹 전략
- 의미 단위 분할 (700~1000 토큰)
- 헤더 기반 섹션 분할
- 10~20% 오버랩으로 컨텍스트 유지

#### 4. 임베딩 생성
- text-embedding-3-small (OpenAI) 또는
- all-MiniLM-L6-v2 (Sentence-Transformers, 무료)
- Celery Worker에서 배치 처리

---

### Phase 5: 검색 & 답변 생성

#### Hybrid Search 전략
- **Vector Search**: 의미 기반 유사도 (k=8~12)
- **Keyword Search**: BM25 알고리즘 (k=10)
- **점수 결합**: 0.7 * vector_score + 0.3 * bm25_score
- **메타필터**: 카테고리, 날짜 등 조건부 필터링
- **중복 제거**: 동일 URL의 인접 청크 병합

#### LLM 프롬프트 구조

**시스템 프롬프트**:
```
당신은 Dickinson College 전용 AI 어시스턴트입니다.
- dickinson.edu의 사전 인덱스 데이터만 사용
- 추측/환상 금지, 항상 출처 URL 포함
- 개인정보/민감정보 절대 노출 금지
- 유해/악의적 요청은 정중히 거절
```

**유저 프롬프트**:
```
질문: {user_query}

컨텍스트:
{retrieved_chunks}

지침: 1~3문장으로 핵심 답변 후 필요 시 불릿 보강.
출처 1~3개를 정규화된 URL로 제시하세요.
```

---

---

## 구현 로드맵

### Week 1: 환경 설정 & 크롤러 개발

- [ ] 기술 스택 선택 및 환경 구축
- [ ] URL 정규화 함수 구현
- [ ] 콘텐츠 추출 함수 구현 (Trafilatura + BeautifulSoup)
- [ ] 블랙리스트/화이트리스트 설정
- [ ] 에러 핸들링 및 로깅

### Week 2: 테스트 크롤링

- [ ] Seed URL 설정 (예: /academics 섹션)
- [ ] 100-200 페이지 샘플 크롤링
- [ ] 콘텐츠 품질 검증
- [ ] 중복 URL 제거 확인
- [ ] Rate limiting 테스트

### Week 3: 전체 크롤링 & 데이터 구축

- [ ] Redis 설정 및 Celery 통합
- [ ] 전체 사이트 크롤링 실행 (Celery Task로 백그라운드 실행)
- [ ] 청킹 전략 적용
- [ ] 임베딩 생성 (시간 소요 예상)
- [ ] Weaviate에 저장
- [ ] MongoDB에 원문 백업
- [ ] 데이터 품질 검증 (누락 페이지 확인)

### Week 4: 검색 시스템 구축

- [ ] Weaviate 검색 함수 구현
- [ ] Hybrid Search (Vector + BM25) 구현
- [ ] 검색 품질 테스트 (샘플 쿼리 50개)
- [ ] 검색 결과 정렬 최적화

### Week 5: LLM 통합 & 답변 생성

- [ ] LLM API 연동 (GPT-4o-mini 또는 Claude)
- [ ] 프롬프트 엔지니어링
- [ ] Redis Query Cache 구현
- [ ] 답변 품질 테스트
- [ ] 출처 인용 기능 구현

### Week 6: 웹 인터페이스 개발

- [ ] 기본 채팅 UI (Next.js)
- [ ] 대화 히스토리
- [ ] 출처 링크 표시
- [ ] 로딩 상태 표시 (Cache Hit/Miss 구분)
- [ ] 모바일 반응형 디자인

### Week 7: 백그라운드 동기화 구현

- [ ] Redis Hash Index 구현
- [ ] 증분 업데이트 Celery Task 작성
- [ ] 우선순위 기반 스케줄링 (Celery Beat)
- [ ] 변경 감지 로직 (해시 비교)
- [ ] 캐시 무효화 로직 (페이지 업데이트 시)

### Week 8: 테스트 & 최적화

- [ ] 통합 테스트
- [ ] 성능 최적화 (응답 속도)
- [ ] Redis Cache Hit Rate 모니터링
- [ ] 에러 케이스 처리
- [ ] 사용자 피드백 수집 메커니즘

### Week 9: 모니터링 & 로깅

- [ ] 대시보드 구축 (Grafana 또는 자체 제작)
- [ ] 쿼리 로그 분석
- [ ] Cache miss 패턴 분석
- [ ] Celery Task 모니터링
- [ ] 알림 시스템 (크롤링 실패 시)

### Week 10: 배포 & 문서화

- [ ] Railway 배포 (FastAPI, Celery, Redis, Weaviate)
- [ ] Vercel 배포 (Next.js)
- [ ] 도메인 설정
- [ ] 사용자 가이드 작성
- [ ] 기술 문서 작성
- [ ] 학교 IT 부서 승인 및 공지

---

## 기술 스택

### 백엔드

| 컴포넌트               | 추천                            | 대안                   | 선택 이유          |
| ------------------ | ----------------------------- | -------------------- | -------------- |
| **프레임워크**          | FastAPI                       | Flask, NextJS                | 비동기 지원, 자동 문서화(Swagger), Pydantic을 통한 강력한 유효성 검사. |
| **크롤러**            | Trafilatura + BeautifulSoup   | Scrapy               | 본문 추출 정확도      |
| **Vector DB**      | Weaviate (Vector + 청크 텍스트, 셀프 호스팅) | Qdrant, Pinecone | Docker로 Railway에 배포 시 비용 절감($0). 셀프 호스팅 인프라 경험 확보.   |
| **Document Store** | MongoDB Atlas (원문 + 메타데이터, 무료)            | PostgreSQL           | 크롤링된 유연한 JSON 구조의 문서를 저장하기에 매우 편리함.       |
| **Cache & Queue**          | Redis (무료)                    | -                    | 빠른 해시 조회       |
| **스케줄러**           | Celery + Redis                 | APScheduler      | 현업 표준. API 서버와 무거운 작업(크롤링, 임베딩)을 분리하여 API 응답 속도 보장.         |

### 프론트엔드

| 컴포넌트               | 추천                            | 대안                   | 선택 이유          |
| ------------------ | ----------------------------- | -------------------- | -------------- |
| **프레임워크**    | Next.js        | React(Vite)     | 현업 표준. 라우팅, SSR, 이미지 최적화 등 상용화에 필요한 기능 기본 내장. |
| **UI 라이브러리** | Tailwind CSS | Material-UI | 커스텀 디자인 자유도가 높고 생산성이 뛰어남. |
| **상태 관리**    | React Query (TanStack Query)  | Redux       | 서버 상태(API 데이터) 관리를 위한 최고의 솔루션. |

### 임베딩 & LLM

| 컴포넌트               | 추천                                       | 비용                      | 참고                |
| ------------------ | ---------------------------------------- | ----------------------- | ----------------- |
| **Embedding**      | OpenAI text-embedding-3-small            | $0.02 / 1M tokens       | 5,000 페이지 ≈ $0.20 비용 대비 성능이 가장 우수함. |
| **Embedding (무료)** | Sentence-Transformers (all-MiniLM-L6-v2) | 무료                      | Celery 워커(로컬)에서 실행. all-MiniLM-L6-v2 모델 추천.             |
| **LLM**            | GPT-4o-mini                              | $0.15 / 1M input tokens | 속도와 비용, 성능의 밸런스가 가장 좋음.            |
| **LLM (대안)**       | Claude Sonnet                            | $3 / 1M tokens          | 더 고품질의 응답이 필요할 경우 사용.               |

### 인프라 및 배포

| 컴포넌트         | 추천                 | 비용      | 참고         |
| ------------ | ------------------ | ------- | ---------- |
| **백엔드 호스팅**      | Railway Pro         | $5-10/월 | FastAPI, Celery, Redis, Weaviate를 한곳에서 Docker로 관리. (학생 크레딧 가능)  |
| **프론트 호스팅** | Vercel (무료)   | $0   | Next.js 배포의 표준. 글로벌 CDN 자동 적용.    |
| **모니터링**     | Grafana Cloud (무료) | -       | 50GB 로그 및 메트릭 무료 제공. |

**예상 월 비용**:

* 최소 구성 (무료): $0 (Sentence-Transformers + Weaviate + Railway 무료 티어)
* 권장 구성: $20-30 (OpenAI Embeddings + GPT-4o-mini + Weaviate + Railway)

---

## Railway 배포 아키텍처

### 서비스 분리 전략

```yaml
Railway Project: "RUSH"

Service 1: FastAPI (API 서버)
  - Port: 8000
  - Environment: REDIS_URL, MONGODB_URI, WEAVIATE_URL, OPENAI_API_KEY
  - Auto-deploy from: main branch

Service 2: Celery Worker (백그라운드 작업)
  - Command: celery -A celery_app worker --loglevel=info --concurrency=2
  - Environment: Same as FastAPI
  - Replicas: 1

Service 3: Celery Beat (스케줄러)
  - Command: celery -A celery_app beat --loglevel=info
  - Environment: Same as FastAPI
  - Replicas: 1 (중요: 반드시 1개만!)

Service 4: Redis
  - Template: Redis
  - Memory: 256MB (충분)
  - Persistence: Enabled

Service 5: Weaviate
  - Docker Image: semitechnologies/weaviate:latest
  - Memory: 2GB (권장)
  - Volume: /var/lib/weaviate
  - Environment:
    - AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
    - PERSISTENCE_DATA_PATH=/var/lib/weaviate
```

### 메모리 사용 예상치

| 서비스 | 메모리 사용량 | 비고 |
|--------|--------------|------|
| FastAPI | ~200 MB | API 서버 |
| Celery Worker | ~400 MB | 임베딩 모델 로드 시 |
| Celery Beat | ~100 MB | 스케줄러 |
| Redis | ~50 MB | 캐시 + 큐 |
| Weaviate | ~600 MB | 5,000 페이지 기준 |
| **총합** | **~1.35 GB** | Railway Pro (8GB)로 충분 |

## 성능 목표

### 응답 속도

* **검색 + LLM 생성(Cache Miss)**: 1-2초 (목표)
* **검색 + LLM 생성 (Cache Hit)**: 0.01-0.05초 (300배 빠름)
* **Vector DB 조회**: < 200ms
* **LLM 생성**: 800ms - 1.5s
* **Redis 조회**: < 5ms

### 정확도

* **검색 관련성**: Top-5 정확도 > 85%
* **답변 품질**: 사용자 만족도 > 4/5점

### 가용성

* **시스템 가동률**: 99% 이상
* **크롤링 성공률**: 95% 이상

### 커버리지

* **인덱싱된 페이지**: 최소 2,000 페이지
* **업데이트 주기**: High priority 매일, Medium 매주, Low 매월

---

## 주의사항 및 리스크 관리

### 1. 학교 IT 부서와의 협의 (필수!)

**사전 공유 사항**:

* 프로젝트 목적 및 범위
* 크롤링 일정 (초기 전수 크롤링 날짜/시간)
* Rate limiting 정책 (요청 간 1초 대기)
* 연락처 정보 (문제 발생 시)

**승인 요청**:

* 크롤링 허가
* IP 화이트리스트 등록 (선택적)
* Robots.txt 예외 처리 (필요 시)

**약속 사항**:

* 학교 서버에 부하 주지 않기
* 문제 발생 시 즉시 중단
* 개인정보 절대 수집 금지

### 2. 법적 고려사항

**저작권**:

* 웹사이트 콘텐츠를 그대로 재배포하지 않음
* LLM이 요약/재구성한 답변만 제공
* 모든 답변에 출처 명시
* robots.txt, 사이트 이용 약관 준수(허용되지 않은 영역 크롤링 금지)

**개인정보 보호 (FERPA 준수)**:

* 학생/교직원 디렉토리 크롤링 금지
* 연락처, 이메일 주소 수집 금지
* 성적, 재정 정보 등 민감 정보 배제

### 3. 기술적 리스크

| 리스크                 | 완화 방안                        |
| ------------------- | ---------------------------- |
| **크롤링 실패**          | Retry 로직 (3회), 에러 로깅, 수동 재시도 |
| **웹사이트 구조 변경**      | 정기적 품질 검증, 에러 알림             |
| **Redis 메모리 부족**      | LRU 정책, TTL 설정, 모니터링             |
| **Celery Worker 다운**      | Health check, 자동 재시작             |
| **LLM API 다운타임**    | Fallback: "현재 서비스 이용 불가" 메시지 |
| **부정확한 답변**         | 신뢰도 점수 표시, 피드백 수집, 지속적 개선    |

### 4. 운영 계획

**초기 베타 테스트**:

* 소규모 사용자 그룹 (10-20명)
* 2주간 피드백 수집
* 답변 품질 검증
* Cache Hit Rate 모니터링

**정식 출시**:

* 학교 공식 채널 통한 공지 (학생 포털, 이메일)
* 사용 가이드 및 FAQ 제공
* IT 헬프데스크와 협력 체계 구축

**지속적 개선**:

* 주간 사용 통계 리뷰
* Cache miss 패턴 분석 → 누락된 정보 파악
* 사용자 피드백 기반 답변 품질 개선
* Redis 캐시 전략 최적화 (TTL 조정)
* 분기별 전체 재크롤링 (선택적)

---

## 모니터링 & 대시보드

### 핵심 지표 (KPIs)

**사용자 경험**:

* 일일 활성 사용자 (DAU)
* 평균 응답 시간
* 사용자 만족도 (피드백 점수)
* 세션당 평균 질문 수

**시스템 성능**:

* Vector DB 조회 시간
* LLM 응답 시간
* Redis Cache Hit Rate (목표: 90% 이상)
* API 성공률 / 에러율
* 시스템 가동률 (Uptime)

**데이터 품질**:

* 인덱싱된 총 페이지 수
* 최근 업데이트된 페이지 수
* Vector DB 커버리지
* 자주 미스되는 쿼리 Top 10

**크롤링 상태**:

* 마지막 크롤링 시간
* 크롤링 성공/실패 비율
* 변경 감지된 페이지 수
* 크롤링 에러 로그
* Celery Task Queue 길이
* robots.txt 정책 변화 감지, sitemap 접근 상태

**Redis 상태**:

* 메모리 사용량 (현재/최대)
* Cache Hit Rate (시간별/일별)
* Celery Queue 크기
* Hash Index 크기

### 대시보드 구성

```
┌─────────────────────────────────────────────────────────┐
│                    RUSH Dashboard                       │
├─────────────────────────────────────────────────────────┤
│  📊 Today's Stats                                       │
│  ├─ 234 queries (↑ 12% from yesterday)                  │
│  ├─ 1.2s avg response time (Cache Miss)                │
│  ├─ 0.03s avg response time (Cache Hit)                │
│  ├─ 96% cache hit rate ⭐                               │
│  └─ 4.3/5 user satisfaction                             │
├─────────────────────────────────────────────────────────┤
│  🗂️ Database Status                                     │
│  ├─ 4,523 pages indexed                                 │
│  ├─ Last updated: 2 hours ago                           │
│  ├─ 23 pages updated today                              │
│  └─ Coverage: 87% of known sitemap                      │
├─────────────────────────────────────────────────────────┤
│  🔴 Redis Status                                        │
│  ├─ Memory: 3.2 MB / 25 MB (12.8%)                      │
│  ├─ Cache Hit Rate: 96.3%                               │
│  ├─ Celery Queue: 3 tasks pending                       │
│  └─ Hash Index: 4,523 entries                           │
├─────────────────────────────────────────────────────────┤
│  ⚙️ Celery Workers                                      │
│  ├─ Worker 1: Active (processing crawl task)            │
│  ├─ Beat: Running (next run: 02:45:00)                  │
│  └─ Completed today: 1,234 tasks (98.5% success)        │
├─────────────────────────────────────────────────────────┤
│  ⚠️ Attention Required                                  │
│  ├─ 5 pages failed to crawl (view details)              │
│  ├─ 12 queries had no results (top topics: ...)         │
│  └─ LLM API usage: 73% of monthly quota                 │
├─────────────────────────────────────────────────────────┤
│  📈 Trends (Last 7 days)                                │
│  [Line chart: Daily queries, Response time, Hit rate]   │
└─────────────────────────────────────────────────────────┘
```

### 알림 시스템

**즉시 알림 (Critical)**:

* 시스템 다운 (5분 이상 무응답)
* LLM API 할당량 90% 초과
* 크롤링 실패율 > 20%
* Redis 메모리 사용률 > 80%
* Celery Worker 다운
* Cache Hit Rate < 50% (비정상)
* 403/429 급증 또는 robots 정책 변경 감지

**일일 요약 (Daily)**:

* 전날 사용 통계
* Cache Hit Rate 리포트
* 새로 발견된 Cache miss 패턴
* 변경된 페이지 목록
* Celery Task 실행 통계

**주간 리포트 (Weekly)**:

* 주간 사용 트렌드
* 답변 품질 피드백 요약
* 시스템 개선 제안
* Redis 성능 분석
* 시스템 개선 제안

---

---

## 확장 계획 (Future Enhancements)

### Phase 6: 고급 기능 (V2.0)

#### 1. 멀티모달 지원
- PDF 문서 처리 (학사 요람, 정책 문서)
- 이미지 인식 (캠퍼스 맵, 건물 사진)
- 비디오 전사 (입학 설명회 영상)

#### 2. 개인화
- 학생/교직원 구분 (익명)
- 학년별 맞춤 정보 (1학년 → 기숙사 정보 우선)
- 전공별 맞춤 정보 (CS 전공 → CS 과목 정보 우선)

#### 3. 대화형 기능
- 후속 질문 지원 ("그럼 신청 마감일은?")
- 대화 맥락 유지
- 명확화 질문 ("어떤 학과의 커리큘럼을 원하시나요?")

#### 4. Redis 캐싱 고도화
- 의미 기반 캐시 매칭 (유사 질문 재사용)
- 계층적 캐싱 (카테고리별 TTL 차등)
- 캐시 워밍 (자주 묻는 질문 사전 생성)

### Phase 7: 스케일링 (1000+ 동시 사용자)

#### 기술적 개선
- Weaviate 샤딩 (카테고리별 분산)
- Redis Cluster (캐시 분산)
- Celery Worker 수평 확장 (Auto-scaling)
- CDN 적용 (정적 자산)
- 로드 밸런싱 (백엔드 서버 복수화)

---

## 성공 지표 (Success Metrics)

### 출시 후 1개월

#### 사용자 지표

* 50명 이상 월간 활성 사용자
* 사용자당 평균 5회 이상 질문
* 평균 사용자 만족도 4/5점 이상

#### 기술 지표

* 평균 응답 시간 < 2초 (Cache Miss)
* 평균 응답 시간 < 0.1초 (Cache Hit)
* Cache hit rate > 85%
* 시스템 가동률 > 98%

#### 데이터 지표

* 2,000개 이상 페이지 인덱싱
* 크롤링 성공률 > 95%
* 주간 업데이트 정상 작동

### 출시 후 3개월

#### 사용자 지표

* 200명 이상 월간 활성 사용자
* 일일 활성 사용자 30명 이상
* 사용자 리텐션 > 40% (재방문율)

#### 커뮤니티 지표

* 학교 공식 채널에서 언급
* IT 헬프데스크와 협력 체계 구축
* 학생회/신문 등에서 긍정적 리뷰

#### 비즈니스 지표 (선택적)

* IT 헬프데스크 문의 10% 감소 (정보 접근성 향상)
* 입학처 웹사이트 FAQ 페이지 트래픽 20% 감소