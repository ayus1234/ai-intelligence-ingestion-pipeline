# AI Data Intelligence Platform: System Architecture & Design

> **Production Systems Architecture Document**  
> *Target Scale: 500,000+ Records/Day | Multi-Provider LLM Orchestration | 24h Verified Freshness*

---

## Page 1: System Architecture Diagram & Data Flow

```text
                                 +-----------------------------------+
                                 |    Data Sources & Crawling        |
                                 |  arXiv, YC, Product Hunt, RSS,    |
                                 |  AIJobs, Wellfound, RemoteOK, etc.|
                                 +-----------------+-----------------+
                                                   |
                                                   v
                                 +-----------------+-----------------+
                                 |  Redis Work Lease Coordinator     |
                                 |  Distributed locks, Heartbeats,   |
                                 |  Dead-Worker Recovery             |
                                 +-----------------+-----------------+
                                                   |
                                                   v
                                 +-----------------+-----------------+
                                 |  LLM Extraction Engine            |
                                 |  Gemini -> Groq -> DeepSeek       |
                                 |  Circuit Breakers, Jitter,        |
                                 |  Chunk Replay Protection, Cache   |
                                 +-----------------+-----------------+
                                                   |
                                                   v
                                 +-----------------+-----------------+
                                 |  Hardened Entity Resolver         |
                                 |  Canonical IDs (ent_startup_*),   |
                                 |  Alias Graph, 6-Signal Engine     |
                                 +-----------------+-----------------+
                                                   |
                                                   v
                                 +-----------------+-----------------+
                                 |  PostgreSQL Source of Truth       |
                                 |  Batch Upserts, Atomic Runs,      |
                                 |  Canonical Records, Metrics       |
                                 +-----------------+-----------------+
                                                   |
                                                   v
                                 +-----------------+-----------------+
                                 |  Export & Quality Audit Engine    |
                                 |  Data Quality Report, Prometheus, |
                                 |  6-Tab Google Sheets / Manifests  |
                                 +-----------------------------------+
```

### End-to-End Data Pipeline Flow

1. **Discovery & Distributed Leasing**: Workers pull targets from source registries and claim atomic TTL leases via Redis (`SET lock:target:<id> worker_id NX EX 60`).
2. **Freshness Verification**: Raw documents are checked against 24-hour cutoff windows before parsing.
3. **Adaptive LLM Extraction**: Large documents pass through semantic chunking and provider fallback chains with circuit breakers.
4. **Hardened Entity Resolution**: Entities map through a 6-signal resolver engine to stable canonical IDs (`ent_startup_openai`).
5. **PostgreSQL Persistence**: Normalized records are written in high-throughput batch transactions (`ON CONFLICT DO UPDATE`).
6. **Data Quality Audit & Export**: Automated quality report validates record completeness and exports 6-tab manifests to Google Sheets / CSV.

---

## Page 2: Scalability, Rate Limits (429), Payloads (413), & Freshness

### 1. Scaling to 500,000+ Records Strategy
- **Horizontal Async Worker Scaling**: Workers process independent queue partitions without lock contention via Redis TTL leases.
- **Batch Processing**: Database writes execute as atomic multi-row batch upserts (`batch_upsert_*`), reducing I/O overhead.
- **Incremental Crawling (`--since`)**: Minimizes bandwidth by querying only new delta windows.
- **Chunk Replay Protection**: Avoids redundant LLM token consumption by caching and retrying *only* failed payload chunks.

### 2. Handling 429 Rate Limits & 413 Payload Errors

```text
Request ---> Provider Semaphore ---> Circuit Breaker Check ---> LLM Invocation
                 |                                                |
                 v (If 429 Rate Limit)                            v (If 413 Payload Error)
         Extract Retry-After                                   Semantic Adaptive Chunker
         + Full Random Jitter                                 + Chunk Replay Protection
                 |                                                |
                 v                                                v
         Retry Fallback Provider                          Replay ONLY Failed Chunk
```

- **Provider Semaphores**: Independent concurrency bounds (`asyncio.Semaphore`): Gemini Flash (10), Groq Llama (20), DeepSeek (8), Mock (50).
- **Circuit Breakers**: `CLOSED` -> `OPEN` (after 3 failures, 60s cooldown) -> `HALF_OPEN`. Skips degraded providers during cooldown.
- **429 Jitter**: Extracts `Retry-After` HTTP headers and applies exponential backoff with full random jitter (`random.uniform(0, min(max_delay, base * 2^attempt))`).
- **413 Chunk Replay Protection**: Caches individual chunk extraction payloads. If chunk 3 fails or triggers 413, retries *only* chunk 3 without re-processing chunks 1 and 2, then merges successful chunk payloads.

### 3. 24-Hour Freshness Guarantee Strategy
- **2-Layer News Architecture**: Fast RSS feed discovery + Layer 2 full HTML article parsing.
- **7-Tier Date Extraction Priority Engine**: `json_ld` -> `meta_article` -> `meta_og` -> `rss` -> `html_time` -> `visible_date` -> `relative_date`.
- **Dual Job Timestamps**: Distinguishes `posted_date` from `first_seen_at` to prevent stale job reposts.

---

## Page 3: Deduplication, Storage, Entity Resolution, & Audit

### 1. Deduplication & Natural Key Hierarchy
Enforces a 4-level natural key hierarchy across job listings:
1. `job:company:<domain>:role:<norm_role>`
2. `job:company:<comp>:role:<norm_role>`
3. `job:source:<src>:id:<id>`
4. `job:url:<url>`

### 2. Storage Rationale: PostgreSQL + Redis
- **PostgreSQL**: Serves as the relational source of truth with strong schema enforcement, JSONB metadata flexibility, foreign key constraints, and index support.
- **Redis**: Handles transient in-memory work queues, distributed worker lease locks (`SET NX EX`), and real-time state expiration without database lock contention.

### 3. 6-Signal Entity Resolution & Alias Graph

```text
Raw Entity Input ("OpenAI Inc.")
            |
            v
   [ 1. Domain Match (openai.com) ]  ---------------------> Confidence 1.0 (Tier: domain)
            |
            v (No match)
   [ 2. Alias Graph Network ]       ---------------------> Confidence 0.98 (Tier: alias)
            |
            v (No match)
   [ 3. GitHub Org Match ]           ---------------------> Confidence 0.95 (Tier: github_org)
            |
            v (No match)
   [ 4. YC Slug Match ]              ---------------------> Confidence 0.95 (Tier: yc_slug)
            |
            v (No match)
   [ 5. Fuzzy Jaro-Winkler >= 0.85 ] ---------------------> Confidence 0.85 (Tier: fuzzy)
            |
            v (No match)
   [ 6. Unresolved Fallback ]        ---------------------> Confidence 0.0 (Tier: unresolved)
```

- **Canonical IDs**: Stable entity IDs (e.g. `ent_startup_openai`).
- **Alias Graph**: Bi-directional alias network mapping raw variants to canonical entity nodes.
- **Audit Logs**: Every resolution logs decision tier, confidence score, and evaluated signals in `EntityMappingLog`.
