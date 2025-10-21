# RUSH — AI Coding Context (for prompt use)

## Project Overview

**RUSH** is a domain-specific AI chatbot that helps Dickinson College members (students, faculty, and staff) quickly and accurately obtain information from the official website. It provides consistently fast responses (1-2 seconds) based on data collected through a full-site crawl.

This document outlines the "implementation instructions + contracts" to be passed as context to an AI during development. It excludes operational aspects (costs, dashboards, deployment) and focuses on constraints, data schemas, function signatures, algorithms, and prompt templates required for coding.

## 0) Top-Level Principles

-   **Domain Restriction**: Only use and cite official, public information from `dickinson.edu`.
-   **No Real-time Web Crawling (for runtime queries)**: Use only the pre-built index and metadata to generate answers.
-   **Transparency**: Always include 1-3 normalized source URLs in the answer.
-   **No PII/Sensitive Info**: Do not generate or expose Personally Identifiable Information (email, phone, address) or sensitive data (grades, finances).
-   **Safety/Refusal**: For harmful, malicious, or inappropriate requests, respond with "Sorry, I can't assist with that." Politely decline off-domain questions.
-   **Language**: Match the user's language; default to English if unspecified.

Reference: The minimal runtime guidelines are in `masterdoc.md` (KR) and `masterdocen.md` (EN).

## 1) URL Policy

-   **Allowed Domains**: `https://dickinson.edu`, `https://www.dickinson.edu`
-   **Whitelist Sections (Examples)**: `/academics`, `/admissions`, `/campus-life`, `/about`, `/news`, `/events`
-   **Blacklist**:
    -   Authentication/Login: `/login`, `/signin`, `/my-dickinson`
    -   Directories (potential PII): `/student-directory`, `/faculty-directory`
    -   Files/Images: `*.pdf`, `*.doc`, `*.docx`, `*.xlsx`, `*.zip`, `*.jpg`, `*.png`, `*.gif`
    -   Search/Excessive Params: `/search?q=*`, `/events?date=*`, `/calendar?page=*`

### URL Normalization Rules

-   Convert to lowercase, remove `www`, remove trailing slash.
-   Remove tracking parameters: `utm_*`, `gclid`, etc.
-   Remove fragment (`#`).
-   Force `https` scheme.
-   Prioritize canonical URL if `rel=canonical` is present.

```python
def normalize_url(url: str) -> str:
    """
    Input: An arbitrary URL.
    Output: A normalized, absolute https URL.
    - lower(), strip www, strip trailing '/', drop tracking params, drop fragment.
    - Caller should handle resolving to a canonical URL if available.
    - Must be idempotent: normalize_url(normalize_url(url)) == normalize_url(url).
    """
    # ... implementation ...
```

```python
def should_crawl(url: str) -> bool:
    """Determines if a URL should be crawled based on whitelist/blacklist rules, extensions, and query parameters."""
    # ... implementation ...
```

## 2) Crawling & Extraction (Offline Build-Phase Only)

-   **Compliance**: Respect `robots.txt` from `https://www.dickinson.edu/robots.txt` (Disallow, Crawl-delay, Retry-After).
-   **Seeding**: Use `sitemap.xml` as a seed if available; expand with BFS for internal links.
-   **Connection Optimization**: Use HTTP/2 or keep-alive sessions.
-   **Error Handling**: On 429/503, respect `Retry-After` header, use exponential backoff, max 3 retries.

```python
def fetch_url(url: str, session, headers: dict) -> tuple[int, dict, str]:
    """
    Returns: (status_code, response_headers, text_content).
    - Complies with robots.txt, crawl-delay, and backoff.
    - On failure, returns (status, headers, '') and lets the caller handle retry policy.
    """
    # ... implementation ...
```

### Content Extraction

-   **Primary Method**: Use `trafilatura` to extract main content, title, and structure.
-   **Fallback**: Use `BeautifulSoup` to parse based on `<main>` tag and heading structure.

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Content:
    url: str
    title: str
    text: str            # Main body plain text
    html: Optional[str]  # Store if needed for re-processing
    headings: List[str]  # Section titles from H1/H2 tags

def extract_content(html: str, url: str) -> Content:
    # ... implementation ...
```

## 3) Chunking Strategy

-   **Unit**: Split by semantic meaning and header sections.
-   **Length**: Target 700-1000 tokens (or 3-6 paragraphs) with 10-20% overlap.
-   **Metadata**: Include `chunk_index` (order within page), `section` (e.g., from h2: "Admissions"), `title`, and `source_url`.

```python
from dataclasses import dataclass

@dataclass
class Chunk:
    id: str            # e.g., "{doc_id}_chunk_{i}"
    doc_id: str
    chunk_index: int
    text: str
    section: str       # e.g., "h2:Curriculum"
    title: str
    source_url: str

def chunk_document(content: Content) -> list[Chunk]:
    # ... implementation ...
```

## 4) Embedding

-   **Model**: `text-embedding-3-small` (1536 dims) or `all-MiniLM-L6-v2` (Sentence-Transformers).
-   **Input Cleaning**: Sanitize whitespace and control characters. Truncate if input exceeds max token limit.

```python
def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    """
    Returns a list of embeddings corresponding to the input chunks.
    Handle failures by returning an empty list or raising an exception.
    """
    # ... implementation ...
```

## 5) Vector DB Schema (with Metadata)

Recommended fields for each vector's metadata:

```json
{
  "id": "doc_123_chunk_5",
  "values": [0.123, -0.456, ...],
  "metadata": {
    "source_url": "https://dickinson.edu/academics/...",
    "title": "Computer Science Major",
    "category": "academics|admissions|events|...",
    "section": "h2:Curriculum Requirements",
    "content_hash": "sha256...",
    "last_updated": "2025-01-01T03:00:00Z",
    "chunk_index": 5
  }
}
```

### Database Contracts

```python
def upsert_vectors(points: list[dict]) -> None:
    # ... implementation ...

def delete_vectors_by_source(source_url: str) -> int:
    """Deletes all vectors associated with a source URL and returns the count of deleted items."""
    # ... implementation ...
```

## 6) Search (Hybrid)

-   **Retrieval**: Vector `k=8-12`, Keyword (BM25) `k=10`.
-   **Ranking**: Combine scores: `score = w_v * norm(vector_score) + w_k * norm(bm25_score)`. Default `w_v=0.7`, `w_k=0.3`.
-   **Filtering**: Apply meta-filters for `category`, `date`, etc., as needed.
-   **Deduplication**: Merge adjacent chunks from the same source URL.
-   **Final Selection**: Return the top 5-10 most relevant, unique contexts.

```python
from typing import TypedDict

class Retrieved(TypedDict):
    text: str
    source_url: str
    title: str
    section: str
    score: float

def hybrid_search(query: str, top_k: int = 10, filters: dict | None = None) -> list[Retrieved]:
    # ... implementation ...
```

## 7) Answer Generation Rules

-   **Grounding**: Summarize or combine only the provided context chunks. No guessing or hallucination.
-   **Structure**: Start with a 1-3 sentence core summary, then add bullet points if necessary for detail.
-   **Citations**: Provide 1-3 normalized source URLs, with tracking parameters removed.
-   **Factual Precision**: For dates, policies, or requirements, quote the original text where possible and advise the user to verify at the source.

### Prompt Templates

**System Prompt**:
```
You are a dedicated AI assistant for Dickinson College. Answer only with the pre-indexed data from dickinson.edu. Do not guess or hallucinate. Always include 1-3 source URLs. Do not include personal or sensitive information. For harmful/malicious requests, respond with "Sorry, I can't assist with that." Politely decline off-domain questions. Default to English.
```

**User Prompt (Structure for LLM call)**:
```
Question: {{user_query}}

Context:
{{retrieved_chunks}}

Instructions:
1. Based only on the context provided, answer the question concisely (1-3 sentences, then bullets if needed).
2. Under a "Sources" heading, list 1-3 normalized URLs.
3. If the information seems uncertain or time-sensitive, advise the user to check the sources for the most up-to-date details.
```

```python
def generate_answer(query: str, retrieved: list[Retrieved], user_lang: str = "en") -> dict:
    """Returns a dictionary: {"answer": str, "sources": list[str], "notes": Optional[str]}"""
    # ... implementation ...
```

## 8) Query Processing Pipeline (Runtime)

```python
def handle_query(query: str, user_lang: str = "en") -> dict:
    # 1. Relevance Check: Politely decline if unrelated to Dickinson.
    # 2. (Optional) Category Classification: Infer category for filtering.
    # 3. Search: retrieved_chunks = hybrid_search(query)
    # 4. Fallback: If no chunks found, return a "not found" message.
    # 5. Generate: result = generate_answer(query, retrieved_chunks)
    # 6. Return: {answer, sources, notes}
    ...
```

### Fallback (Information Not Found)

-   **No real-time crawling.**
-   **Template**: "Sorry, I could not find information on that topic in my pre-built data. You may find what you're looking for on one of these official pages:" + 1-3 relevant high-level links (e.g., main academics page).

## 9) Incremental Update (Offline Scheduled Job)

-   Use `HEAD` requests to check `ETag` or `Last-Modified` headers.
-   Use conditional `GET` (`If-None-Match` / `If-Modified-Since`).
-   If `304 Not Modified`, skip.
-   If `200 OK`, extract content, compare content hash.
-   If content has changed, delete all existing vectors for that URL and upsert new ones.

```python
def incremental_update(urls: list[str]) -> dict:
    """
    Performs an incremental update for a list of URLs.
    Returns a summary: {"checked": int, "changed": int, "errors": int, "duration_ms": int}
    """
    # ... implementation ...
```

## 10) Data & Type Schemas (Summary)

```python
from pydantic import BaseModel, Field
from typing import Optional

class VectorMeta(BaseModel):
    source_url: str
    title: str
    category: Optional[str] = None
    section: Optional[str] = None
    content_hash: str
    last_updated: str
    chunk_index: int

class Answer(BaseModel):
    answer: str
    sources: list[str]
    notes: Optional[str] = None

class MongoPageDocument(BaseModel):
    url: str
    normalized_url: str
    title: str
    category: str
    content: str
    content_hash: str
    html: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    crawled_at: str
    status: str = "active"
```

## 11) Edge Case Checklist

-   **Empty/Short Pages**: Skip or move to a review queue if `len(text) < N`.
-   **Duplicate URLs**: Ensure only one is processed after normalization.
-   **Redirect Chains**: Store content under the final destination URL.
-   **Parametric Pages**: Filter out calendar/event pages with volatile query params.
-   **Large Pages**: Consider splitting by major sections before chunking.
-   **Encoding/Malformed HTML**: Use a lenient parser; retry on failure.
-   **PII Detection**: On extraction, check for email/phone patterns and mask or skip if found.

---
This document provides the executable instructions for the AI during development. Use these contracts (signatures, schemas, procedures) as the source of truth when designing modules or writing tests.
