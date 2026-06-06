# 07 — Scalability & Performance

## 7.1 Performance Targets

| Scale | Customers | Approx Records | Target Time | Memory |
|-------|-----------|----------------|-------------|--------|
| Small | 100 | ~15K | < 15 seconds | < 200 MB |
| Medium | 1,000 | ~150K | < 2 minutes | < 500 MB |
| Large | 5,000 | ~800K | < 10 minutes | < 1 GB |
| XL | 10,000 | ~2M | < 30 minutes | < 2 GB |
| Enterprise | 50,000+ | ~10M+ | < 2 hours | < 4 GB |

## 7.2 Batch Processing Architecture

### Producer-Consumer Pattern

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Generator      │     │  Bounded Queue  │     │  DB Writer      │
│  (CPU-bound)    │────▶│  (async.Queue)  │────▶│  (I/O-bound)    │
│                 │     │  max_size=10    │     │                 │
│  Produces       │     │                 │     │  Consumes       │
│  record batches │     │  Backpressure   │     │  and bulk       │
│                 │     │  when full      │     │  inserts        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Batch Size Tuning

| Batch Size | Insert Time (1K rows) | Memory per Batch | Recommended For |
|-----------|----------------------|------------------|-----------------|
| 1,000 | ~50ms | ~2 MB | Small datasets |
| 5,000 | ~120ms | ~10 MB | Medium (default) |
| 10,000 | ~200ms | ~20 MB | Large datasets |
| 50,000 | ~800ms | ~100 MB | Enterprise |

## 7.3 Memory Management

### Streaming Generation

Records are generated in chunks and written to the database before the next chunk is generated. The system never holds the entire dataset in memory.

```python
async def generate_and_write_sales(
    profiles: list[CustomerProfile],
    engine: AsyncEngine,
    batch_size: int = 5000,
) -> int:
    """Generate sales in batches, writing each batch to DB."""

    total_written = 0
    buffer: list[dict] = []

    for profile in profiles:
        customer_sales = generate_customer_sales(profile)

        for sale in customer_sales:
            buffer.append(sale)

            if len(buffer) >= batch_size:
                await bulk_insert(engine, "raw_sales", buffer)
                total_written += len(buffer)
                buffer.clear()

    # Flush remaining
    if buffer:
        await bulk_insert(engine, "raw_sales", buffer)
        total_written += len(buffer)

    return total_written
```

### Customer-Level Processing

For very large datasets, customers are processed in groups to limit per-customer memory:

```python
CUSTOMER_CHUNK_SIZE = 100  # Process 100 customers at a time

for chunk in chunked(profiles, CUSTOMER_CHUNK_SIZE):
    sales = generate_sales_batch(chunk)
    await write_sales(sales)
    # Sales data for this chunk can now be GC'd
```

## 7.4 Database Optimization

### Bulk Insert Strategy

```python
async def bulk_insert(
    engine: AsyncEngine,
    table_name: str,
    records: list[dict],
) -> None:
    """Optimized bulk insert using executemany."""

    async with engine.begin() as conn:
        table = metadata.tables[table_name]
        await conn.execute(table.insert(), records)
```

### Connection Pool Configuration

```python
engine = create_async_engine(
    database_uri,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,      # Verify connections before use
    pool_recycle=3600,        # Recycle connections after 1 hour
    echo=False,               # Disable SQL logging in production
)
```

### Index Strategy

Indexes are created AFTER bulk data load for faster insert performance:

```python
async def initialize_schema(engine: AsyncEngine) -> None:
    # Phase 1: Create tables WITHOUT indexes
    await create_tables(engine)

    # Phase 2: After data generation, create indexes
    # (Called from orchestrator after all data is written)

async def create_indexes(engine: AsyncEngine) -> None:
    """Create indexes after bulk data load."""
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_sales_customer ON raw_sales(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_order_date ON raw_sales(order_date)",
        # ... etc
    ]
    async with engine.begin() as conn:
        for stmt in index_statements:
            await conn.execute(text(stmt))
```

## 7.5 Parallelism Strategy

### Customer-Level Parallelism

Different customers are independent. Generation can be parallelized across CPU cores:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def generate_parallel(
    profiles: list[CustomerProfile],
    num_workers: int = 4,
) -> None:
    loop = asyncio.get_event_loop()
    chunks = split_into_chunks(profiles, num_workers)

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        tasks = [
            loop.run_in_executor(executor, generate_chunk, chunk)
            for chunk in chunks
        ]
        results = await asyncio.gather(*tasks)
```

### Phase-Level Serialization

Phases MUST execute sequentially (customers → sales → payments → returns) to maintain referential integrity.

## 7.6 Progress Reporting

```python
@dataclass
class GenerationProgress:
    job_id: str
    phase: str  # "customers" | "sales" | "payments" | "returns" | "validation"
    phase_progress: float  # 0.0 to 1.0
    total_progress: float  # 0.0 to 1.0
    records_generated: int
    records_written: int
    elapsed_seconds: float
    estimated_remaining: float
```

Progress is tracked per-phase and stored in memory (or Redis for multi-worker setups). The `/api/v1/status/{job_id}` endpoint returns this data.

## 7.7 Resource Monitoring

The system monitors and logs:

- Memory usage (RSS) per generation phase
- Database connection pool utilization
- Batch write latency (p50, p95, p99)
- Records generated per second

If memory exceeds 80% of configured limit, batch sizes are automatically halved.
