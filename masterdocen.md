# RUSH - Dickinson College Intelligent Assistant

## Project Overview

**RUSH** is a domain-specific AI chatbot that helps Dickinson College members (students, faculty, and staff) quickly and accurately obtain information from the official website. It provides consistently fast responses (1-2 seconds) based on data collected through a full-site crawl.

**Related Documents**:
- [AI Coding Context (Implementation Details)](ai_context.md) - Detailed implementation guidelines to be provided to the AI during development.
- [LLM Runtime Context (KR)](masterdoc.md) - Minimum guidelines for the model to follow during operation.
- [LLM Runtime Context (EN)](masterdocen.md) - English version of runtime guidelines.

---

## Core Principles

1.  **Domain Restriction**: Use only official information from the `dickinson.edu` domain.
2.  **Consistent Speed**: Guarantee a response within 1-2 seconds for all queries.
3.  **Complete Coverage**: Index the entire website through a full crawl.
4.  **Transparency**: Cite the source URL for all answers.
5.  **Security**: Protect personal information and prevent malicious use.

---

## System Architecture

### Phase 0: Initial Data Build (One-time Setup)

#### Full Crawl Strategy

**Goal**: Build a complete database by crawling the entire Dickinson.edu site at once.

**Crawling Method**: BFS (Breadth-First Search) based internal link traversal.

```
Seed URL: https://www.dickinson.edu
↓
├─ /academics → Department pages
├─ /admissions → Admissions information
├─ /campus-life → Campus life
├─ /about → About the college
└─ ... (Recursive traversal of all internal links)
```

**Estimated Scale**:

*   Total pages: 5,000 ~ 15,000 pages
*   Effective pages (after deduplication): 2,000 ~ 5,000 pages
*   Crawling time: 2-3 hours (including rate limiting)
*   Storage space: Approx. 25-50MB (text only)

#### Robots.txt / Sitemap Compliance

*   Must check and comply with https://www.dickinson.edu/robots.txt (including Disallow, Crawl-delay).
*   Include contact information in the User-Agent identifier, e.g., "RUSH Crawler (+contact@example.com)".
*   On 429/503 responses, respect the Retry-After header and apply exponential backoff.
*   Use HTTP/2 or Keep-Alive to minimize connections and reduce server load.

#### URL Filtering Rules

**✅ Whitelist (Targets for crawling)**

*   `https://www.dickinson.edu/`
*   `https://dickinson.edu/`
*   Major sections: /academics, /admissions, /campus-life, /about, /news, /events

**❌ Blacklist (Exclude from crawling)**

*   Pages requiring login: /login, /signin, /my-dickinson
*   Personal information pages: /student-directory, /faculty-directory (containing emails/contacts)
*   Files: *.pdf, *.doc, *.xlsx, *.zip
*   Images: *.jpg, *.png, *.gif
*   Dynamic parameters: /events?date=*, /calendar?page=*
*   Search result pages: /search?q=*

#### URL Normalization

Rules for preventing duplicate URLs:

```python
# Example
https://www.dickinson.edu/page/  
https://dickinson.edu/page  
https://dickinson.edu/PAGE  
  ↓ Normalize  
https://dickinson.edu/page
```

**Normalization Rules**:

*   Remove `www`
*   Remove trailing slash
*   Convert to lowercase
*   Remove unnecessary query parameters (e.g., utm_*, gclid tracking parameters)
*   Remove fragment (#)
*   Force HTTPS (http → https redirection URLs are unified to https during normalization)
*   Prioritize the canonical URL if `rel=canonical` is present.

---

### Phase 1: User Request Processing (Real-time Pipeline)

**Core**: No real-time crawling; only queries the Vector DB.

```
User question input
    ↓
Query Preprocessing
 ├─ Dickinson relevance check (LLM-based)
 └─ Question categorization (Academics/Events/Dining/etc.)
    ↓
Hybrid Search (Vector DB)
 ├─ Vector Similarity Search (semantic-based)
 ├─ Keyword Search (BM25)
 └─ Metadata Filtering (category, date)
    ↓
Context Retrieval
 ├─ Extract Top 5-10 relevant chunks
 └─ Collect source URLs
    ↓
LLM Answer Generation
 ├─ Prompt: "Based on the following information, provide an answer..."
 ├─ Generate answer
 └─ Include source citations
    ↓
Response (within 1-2 seconds)
 ├─ Answer text
 ├─ List of source URLs
 └─ Confidence score (optional)
```

#### Cache Miss Handling

**No real-time crawling!** Instead:

```
[Information not found detected]
    ↓
"Sorry, I could not find the requested information.
Please check the relevant pages: [Recommended Links]
Or contact the IT Help Desk."
    ↓
[Background Logging]
 - Log the missed query
 - Forward to administrators in a weekly report
 - Focus on this area in the next crawl
```

#### Security Measures

*   **Rate Limiting**:
    *   Chatbot: Max 10 queries per user per minute (application level).
    *   Crawler: ≤ 1 request per second for the entire domain (or prioritize crawl-delay from robots.txt).
*   **Question Validation**: Reject questions unrelated to Dickinson.
    *   "Who is the president of the USA?" → "I only answer questions related to Dickinson College."
*   **Privacy Protection**: Absolutely no exposure of student/faculty personal information.

### Phase 2: Background Synchronization (Scheduled Jobs)

**Goal**: Keep the database up to date.

---

#### Incremental Update

**Execution Frequency**: Priority-based

| Priority | Page Type          | Update Frequency      | Examples                                 |
|----------|--------------------|-----------------------|------------------------------------------|
| **High** | Dynamic Content    | Daily (3 AM)          | News, Events, Dining menu                |
| **Medium** | Semi-static Content| Weekly (Sunday 3 AM)  | Admissions deadlines, Course schedules   |
| **Low**    | Static Content     | Monthly (1st of month 3 AM) | Faculty profiles, History, Buildings     |

---

#### Update Process

```
[Runs every night at 3 AM]
    ↓
1. Extract all URLs from the DB (filtered by priority)
    ↓
2. For each URL:
   ├─ (If possible) Check ETag/Last-Modified with a HEAD request
   ├─ Use conditional GET (If-None-Match / If-Modified-Since) → 304 means no change
   ├─ (If 200) Crawl the webpage
   ├─ Extract content (main body only)
   ├─ Generate SHA256 hash
   └─ Compare with the existing hash
    ↓
3. [If change is detected]
   ├─ Delete existing vectors (all chunks for that URL)
   ├─ Chunk new content (header-based splitting)
   ├─ Generate embeddings
   ├─ Save to Vector DB
   └─ Record change log
    ↓
4. [If no change]
   ├─ 304 Not Modified or hash is identical
   └─ Update only the last checked time
    ↓
5. Generate completion report
   ├─ Total pages checked
   ├─ Number of pages with changes detected
   ├─ Number of pages with errors
   └─ Execution time
```

**Estimated Update Scale**:

*   High priority: 50-100 pages → 5-10 minutes
*   Medium priority: 200-500 pages → 20-30 minutes
*   Low priority: 2,000-5,000 pages → 1-2 hours

---

#### RSS Feed Utilization (Optional)

If Dickinson provides RSS feeds:

```python
# Quickly check News & Events via RSS
rss_feeds = [
    'https://www.dickinson.edu/rss/news',
    'https://www.dickinson.edu/rss/events'
]

# Check RSS (30 seconds) → Crawl only new articles
# Much more efficient than a full page crawl (10 minutes)
```

---

### Phase 3: Data Storage Layer

#### Storage Structure Overview

The system consists of four main storage components, each with a clear role:

```
┌─────────────────────────────────────────┐
│         1. Vector Database              │
│           (Weaviate)                    │
│                                         │
│  - Chunk embeddings (768 or 1536 dims)  │
│  - Metadata:                            │
│    · source_url                         │
│    · title                              │
│    · category (academics/events/etc)    │
│    · section (H1/H2 structure)          │
│    · content_hash (SHA256)              │
│    · last_updated (timestamp)           │
│    · chunk_index (order within page)    │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│      2. Document Store (MongoDB)        │
│                                         │
│  - Store original text or HTML          │
│  - Use for re-embedding if needed       │
│  - Backup purposes                      │
│  - Store ETag, Last-Modified            │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│          3. Redis (Integrated)          │
│                                         │
│  Role 1: Celery Broker/Backend          │
│   - Async task queue (crawling, embedding)│
│   - Store task results                  │
│                                         │
│  Role 2: Hash Index (Content change detection)│
│   Key: "hash:{normalized_url}"          │
│   Value: {                              │
│     content_hash: "abc123...",          │
│     last_checked: "2024-01-15T03:00",   │
│     priority: "high",                   │
│     status: "active"                    │
│   }                                     │
│   TTL: 30 days                          │
│                                         │
│  Role 3: Query Cache (LLM responses)    │
│   Key: "cache:query:{query_hash}"       │
│   Value: {                              │
│     answer: "...",                      │
│     sources: [...],                     │
│     confidence: 0.92                    │
│   }                                     │
│   TTL: 1 hour                           │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│     4. Logs Database (PostgreSQL)       │
│                                         │
│  - user_queries: User query logs        │
│  - cache_misses: Questions with no info │
│  - page_updates: Page change history    │
│  - crawl_errors: Crawling failure logs  │
│  - system_metrics: Performance metrics  │
└─────────────────────────────────────────┘
```

#### Redis Details

**Redis's 3 Core Roles:**

1.  **Celery Broker/Backend (Message Queue)**
    *   Queues asynchronous tasks (crawling, embedding).
    *   Stores task states and results.
    *   Distributes tasks among workers.

2.  **Hash Index (Content Change Detection)**
    *   Stores content hash per URL.
    *   Detects changes during incremental updates.
    *   Automatically cleans up with a 30-day TTL.

3.  **Query Cache (LLM Response Caching)**
    *   Reuses answers for identical questions (300x faster response).
    *   Ensures freshness with a 1-hour TTL.
    *   Target Cache Hit Rate: 90%+.

#### Data Model Examples

##### 1. Weaviate Vector DB Schema

```json
{
    "class": "Chunk",
    "description": "Searchable text chunks",
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

```json
{
    "_id": ObjectId("..."),
    "url": "https://dickinson.edu/academics/computer-science",
    "normalized_url": "https://dickinson.edu/academics/computer-science",
    "title": "Computer Science Major",
    "category": "academics",
    "content": "Full body text 10KB...",
    "content_hash": "a3f5b8c9d2e1f4b3a7c8d9e2f1a4b5c6",
    "html": "<html>...</html>",  // Optional
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

```
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
TTL: 2592000  # 30 days
```

##### 4. Redis Query Cache

```
Key: "cache:query:a3f5b8c9d2e1f4b3"
Value: {
    "query": "What are the required courses for Computer Science?",
    "answer": "The required courses are CS101, CS102...",
    "sources": [
        "https://dickinson.edu/academics/cs"
    ],
    "confidence": 0.92,
    "cached_at": "2024-01-15T10:30:00Z"
}
TTL: 3600  # 1 hour
```

### Phase 4: Content Processing Pipeline

This phase transforms raw crawled data into a searchable format.

#### 1. Page Crawling
- Use Trafilatura + BeautifulSoup.
- Comply with robots.txt and rate limiting.
- Retry logic (3 times, exponential backoff).

#### 2. Content Extraction
- Extract main body text.
- Collect metadata (title, category, section).
- Parse HTML structure (based on H1/H2).

#### 3. Chunking Strategy
- Semantic unit splitting (700-1000 tokens).
- Header-based section splitting.
- 10-20% overlap to maintain context.

#### 4. Embedding Generation
- `text-embedding-3-small` (OpenAI) or
- `all-MiniLM-L6-v2` (Sentence-Transformers, free).
- Batch processing in a Celery Worker.

---

### Phase 5: Search & Answer Generation

#### Hybrid Search Strategy
- **Vector Search**: Semantic similarity (k=8~12).
- **Keyword Search**: BM25 algorithm (k=10).
- **Score Combination**: 0.7 * vector_score + 0.3 * bm25_score.
- **Meta-filtering**: Conditional filtering by category, date, etc.
- **Deduplication**: Merge adjacent chunks from the same URL.

#### LLM Prompt Structure

**System Prompt**:
```
You are a dedicated AI assistant for Dickinson College.
- Use only pre-indexed data from dickinson.edu.
- No guessing/hallucination; always include source URLs.
- Never expose personal/sensitive information.
- Politely decline harmful/malicious requests.
```

**User Prompt**:
```
Question: {user_query}

Context:
{retrieved_chunks}

Instructions: Provide a core answer in 1-3 sentences, then add bullets if needed.
Cite 1-3 normalized URLs as sources.
```

---

## Implementation Roadmap

### Week 1: Environment Setup & Crawler Development

- [ ] Choose tech stack and set up environment.
- [ ] Implement URL normalization function.
- [ ] Implement content extraction function (Trafilatura + BeautifulSoup).
- [ ] Configure blacklist/whitelist.
- [ ] Implement error handling and logging.

### Week 2: Test Crawl

- [ ] Set seed URLs (e.g., /academics section).
- [ ] Crawl a sample of 100-200 pages.
- [ ] Verify content quality.
- [ ] Confirm duplicate URL removal.
- [ ] Test rate limiting.

### Week 3: Full Crawl & Data Build

- [ ] Set up Redis and integrate Celery.
- [ ] Run full site crawl (as a background Celery task).
- [ ] Apply chunking strategy.
- [ ] Generate embeddings (expect time consumption).
- [ ] Store in Weaviate.
- [ ] Back up original content in MongoDB.
- [ ] Verify data quality (check for missing pages).

### Week 4: Search System Build

- [ ] Implement Weaviate search function.
- [ ] Implement Hybrid Search (Vector + BM25).
- [ ] Test search quality (50 sample queries).
- [ ] Optimize search result ranking.

### Week 5: LLM Integration & Answer Generation

- [ ] Integrate LLM API (GPT-4o-mini or Claude).
- [ ] Perform prompt engineering.
- [ ] Implement Redis Query Cache.
- [ ] Test answer quality.
- [ ] Implement source citation feature.

### Week 6: Web Interface Development

- [ ] Build basic chat UI (Next.js).
- [ ] Implement conversation history.
- [ ] Display source links.
- [ ] Show loading status (distinguishing Cache Hit/Miss).
- [ ] Implement responsive design for mobile.

### Week 7: Background Synchronization Implementation

- [ ] Implement Redis Hash Index.
- [ ] Create incremental update Celery Task.
- [ ] Set up priority-based scheduling (Celery Beat).
- [ ] Implement change detection logic (hash comparison).
- [ ] Implement cache invalidation logic (on page update).

### Week 8: Testing & Optimization

- [ ] Conduct integration testing.
- [ ] Optimize performance (response speed).
- [ ] Monitor Redis Cache Hit Rate.
- [ ] Handle error cases.
- [ ] Implement user feedback collection mechanism.

### Week 9: Monitoring & Logging

- [ ] Build a dashboard (Grafana or custom).
- [ ] Analyze query logs.
- [ ] Analyze cache miss patterns.
- [ ] Monitor Celery tasks.
- [ ] Set up alert system (for crawling failures).

### Week 10: Deployment & Documentation

- [ ] Deploy to Railway (FastAPI, Celery, Redis, Weaviate).
- [ ] Deploy to Vercel (Next.js).
- [ ] Configure domain.
- [ ] Write user guide.
- [ ] Write technical documentation.
- [ ] Get approval from and notify the school's IT department.

---

## Tech Stack

### Backend

| Component        | Recommendation                               | Alternatives         | Rationale                                                              |
|------------------|----------------------------------------------|----------------------|------------------------------------------------------------------------|
| **Framework**    | FastAPI                                      | Flask, Next.js       | Async support, auto-docs (Swagger), strong validation with Pydantic.   |
| **Crawler**      | Trafilatura + BeautifulSoup                  | Scrapy               | High accuracy in main content extraction.                              |
| **Vector DB**    | Weaviate (Vector + chunk text, self-hosted)  | Qdrant, Pinecone     | Cost savings ($0) when deployed on Railway with Docker. Self-hosting experience. |
| **Document Store** | MongoDB Atlas (raw content + metadata, free) | PostgreSQL           | Very convenient for storing flexible JSON documents from crawls.       |
| **Cache & Queue**| Redis (free)                                 | -                    | Fast hash lookups.                                                     |
| **Scheduler**    | Celery + Redis                               | APScheduler          | Industry standard. Decouples heavy tasks (crawling, embedding) from the API server to ensure API responsiveness. |

### Frontend

| Component         | Recommendation                 | Alternatives  | Rationale                                                              |
|-------------------|--------------------------------|---------------|------------------------------------------------------------------------|
| **Framework**     | Next.js                        | React (Vite)  | Industry standard. Built-in features for routing, SSR, image optimization. |
| **UI Library**    | Tailwind CSS                   | Material-UI   | High productivity and freedom for custom designs.                      |
| **State Management**| React Query (TanStack Query)   | Redux         | The best solution for managing server state (API data).                |

### Embedding & LLM

| Component            | Recommendation                                 | Cost                    | Notes                                                                  |
|----------------------|------------------------------------------------|-------------------------|------------------------------------------------------------------------|
| **Embedding**        | OpenAI `text-embedding-3-small`                | $0.02 / 1M tokens       | Best performance for the cost. 5,000 pages ≈ $0.20.                    |
| **Embedding (Free)** | Sentence-Transformers (`all-MiniLM-L6-v2`)     | Free                    | Run in a Celery worker (local). `all-MiniLM-L6-v2` model recommended.  |
| **LLM**              | GPT-4o-mini                                    | $0.15 / 1M input tokens | Best balance of speed, cost, and performance.                          |
| **LLM (Alternative)**| Claude Sonnet                                  | $3 / 1M tokens          | Use when higher quality responses are needed.                          |

### Infrastructure & Deployment

| Component           | Recommendation               | Cost       | Notes                                                                    |
|---------------------|------------------------------|------------|--------------------------------------------------------------------------|
| **Backend Hosting** | Railway Pro                  | $5-10/month| Manage FastAPI, Celery, Redis, Weaviate in one place with Docker. (Student credits available) |
| **Frontend Hosting**| Vercel (Free)                | $0         | Standard for Next.js deployment. Global CDN applied automatically.       |
| **Monitoring**      | Grafana Cloud (Free)         | -          | 50GB of logs and metrics for free.                                       |

**Estimated Monthly Cost**:

*   **Minimum Config (Free)**: $0 (Sentence-Transformers + Weaviate + Railway Free Tier)
*   **Recommended Config**: $20-30 (OpenAI Embeddings + GPT-4o-mini + Weaviate + Railway)

---

## Railway Deployment Architecture

### Service Separation Strategy

```yaml
Railway Project: "RUSH"

Service 1: FastAPI (API Server)
  - Port: 8000
  - Environment: REDIS_URL, MONGODB_URI, WEAVIATE_URL, OPENAI_API_KEY
  - Auto-deploy from: main branch

Service 2: Celery Worker (Background Tasks)
  - Command: celery -A celery_app worker --loglevel=info --concurrency=2
  - Environment: Same as FastAPI
  - Replicas: 1

Service 3: Celery Beat (Scheduler)
  - Command: celery -A celery_app beat --loglevel=info
  - Environment: Same as FastAPI
  - Replicas: 1 (Important: must be exactly 1!)

Service 4: Redis
  - Template: Redis
  - Memory: 256MB (sufficient)
  - Persistence: Enabled

Service 5: Weaviate
  - Docker Image: semitechnologies/weaviate:latest
  - Memory: 2GB (recommended)
  - Volume: /var/lib/weaviate
  - Environment:
    - AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
    - PERSISTENCE_DATA_PATH=/var/lib/weaviate
```

### Estimated Memory Usage

| Service       | Memory Usage | Notes                       |
|---------------|--------------|-----------------------------|
| FastAPI       | ~200 MB      | API Server                  |
| Celery Worker | ~400 MB      | When loading embedding model|
| Celery Beat   | ~100 MB      | Scheduler                   |
| Redis         | ~50 MB       | Cache + Queue               |
| Weaviate      | ~600 MB      | Based on 5,000 pages        |
| **Total**     | **~1.35 GB** | Sufficient on Railway Pro (8GB) |

## Performance Goals

### Response Time

*   **Search + LLM Gen (Cache Miss)**: 1-2 seconds (Target)
*   **Search + LLM Gen (Cache Hit)**: 0.01-0.05 seconds (300x faster)
*   **Vector DB Query**: < 200ms
*   **LLM Generation**: 800ms - 1.5s
*   **Redis Query**: < 5ms

### Accuracy

*   **Search Relevance**: Top-5 accuracy > 85%
*   **Answer Quality**: User satisfaction > 4/5

### Availability

*   **System Uptime**: > 99%
*   **Crawling Success Rate**: > 95%

### Coverage

*   **Indexed Pages**: At least 2,000 pages
*   **Update Frequency**: High priority daily, Medium weekly, Low monthly

---

## Precautions and Risk Management

### 1. Consultation with School IT Department (Required!)

**Items to share in advance**:

*   Project purpose and scope
*   Crawling schedule (date/time of initial full crawl)
*   Rate limiting policy (1-second wait between requests)
*   Contact information (in case of issues)

**Approval requests**:

*   Permission to crawl
*   IP whitelisting (optional)
*   Exception for Robots.txt (if necessary)

**Commitments**:

*   Do not overload the school's servers.
*   Immediately halt on any issue.
*   Absolutely no collection of personal information.

### 2. Legal Considerations

**Copyright**:

*   Do not redistribute website content as is.
*   Provide only answers summarized/reconstructed by the LLM.
*   Cite sources for all answers.
*   Comply with robots.txt and site terms of use (do not crawl disallowed areas).

**Privacy (FERPA Compliance)**:

*   Do not crawl student/faculty directories.
*   Do not collect contact info, email addresses.
*   Exclude sensitive information like grades, financial data.

### 3. Technical Risks

| Risk                    | Mitigation Plan                                       |
|-------------------------|-------------------------------------------------------|
| **Crawling Failure**    | Retry logic (3 times), error logging, manual retry    |
| **Website Structure Change**| Regular quality checks, error alerts                |
| **Redis Memory Exhaustion**| LRU policy, TTL settings, monitoring                |
| **Celery Worker Down**  | Health checks, auto-restart                           |
| **LLM API Downtime**    | Fallback: "Service currently unavailable" message     |
| **Inaccurate Answers**  | Display confidence score, collect feedback, continuous improvement |

### 4. Operational Plan

**Initial Beta Test**:

*   Small user group (10-20 people)
*   Collect feedback for 2 weeks
*   Verify answer quality
*   Monitor Cache Hit Rate

**Official Launch**:

*   Announce through official school channels (student portal, email)
*   Provide user guide and FAQ
*   Establish cooperation with IT Help Desk

**Continuous Improvement**:

*   Weekly review of usage statistics
*   Analyze cache miss patterns → identify missing information
*   Improve answer quality based on user feedback
*   Optimize Redis cache strategy (adjust TTLs)
*   Quarterly full re-crawl (optional)

---

## Monitoring & Dashboard

### Key Performance Indicators (KPIs)

**User Experience**:

*   Daily Active Users (DAU)
*   Average Response Time
*   User Satisfaction (feedback score)
*   Average questions per session

**System Performance**:

*   Vector DB Query Time
*   LLM Response Time
*   Redis Cache Hit Rate (Target: > 90%)
*   API Success/Error Rate
*   System Uptime

**Data Quality**:

*   Total Indexed Pages
*   Recently Updated Pages
*   Vector DB Coverage
*   Top 10 Most Frequent Missed Queries

**Crawling Status**:

*   Last Crawl Time
*   Crawl Success/Failure Ratio
*   Number of Pages with Detected Changes
*   Crawl Error Logs
*   Celery Task Queue Length
*   robots.txt policy change detection, sitemap access status

**Redis Status**:

*   Memory Usage (current/max)
*   Cache Hit Rate (hourly/daily)
*   Celery Queue Size
*   Hash Index Size

### Dashboard Layout

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

### Alert System

**Immediate Alerts (Critical)**:

*   System down (unresponsive for > 5 mins)
*   LLM API quota > 90%
*   Crawling failure rate > 20%
*   Redis memory usage > 80%
*   Celery Worker down
*   Cache Hit Rate < 50% (abnormal)
*   Spike in 403/429 errors or robots.txt policy change detected

**Daily Summary**:

*   Previous day's usage statistics
*   Cache Hit Rate report
*   Newly discovered cache miss patterns
*   List of changed pages
*   Celery task execution statistics

**Weekly Report**:

*   Weekly usage trends
*   Summary of answer quality feedback
*   System improvement suggestions
*   Redis performance analysis

---

## Future Enhancements

### Phase 6: Advanced Features (V2.0)

#### 1. Multimodal Support
- PDF document processing (academic catalogs, policy documents)
- Image recognition (campus maps, building photos)
- Video transcription (admissions info sessions)

#### 2. Personalization
- Differentiate between students/faculty (anonymously)
- Tailored information by year (e.g., housing info for first-years)
- Major-specific information (e.g., CS course info for CS majors)

#### 3. Conversational Features
- Follow-up question support ("What about the application deadline?")
- Maintain conversation context
- Clarification questions ("Which department's curriculum are you interested in?")

#### 4. Advanced Redis Caching
- Semantic cache matching (reuse answers for similar questions)
- Hierarchical caching (different TTLs per category)
- Cache warming (pre-generate answers for frequent questions)

### Phase 7: Scaling (1000+ Concurrent Users)

#### Technical Improvements
- Weaviate sharding (distribute by category)
- Redis Cluster (distribute cache)
- Horizontal scaling of Celery Workers (Auto-scaling)
- CDN for static assets
- Load balancing for backend servers

---

## Success Metrics

### 1 Month Post-Launch

#### User Metrics
*   50+ Monthly Active Users
*   Average of 5+ questions per user
*   Average user satisfaction > 4/5

#### Technical Metrics
*   Average response time < 2s (Cache Miss)
*   Average response time < 0.1s (Cache Hit)
*   Cache hit rate > 85%
*   System uptime > 98%

#### Data Metrics
*   2,000+ pages indexed
*   Crawling success rate > 95%
*   Weekly updates functioning correctly

### 3 Months Post-Launch

#### User Metrics
*   200+ Monthly Active Users
*   30+ Daily Active Users
*   User retention > 40% (re-visit rate)

#### Community Metrics
*   Mentioned in official school channels
*   Collaboration with IT Help Desk established
*   Positive reviews from student government/newspaper

#### Business Metrics (Optional)
*   10% reduction in IT Help Desk inquiries (improved information access)
*   20% reduction in traffic to admissions FAQ page
