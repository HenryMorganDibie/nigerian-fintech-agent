"""
Event-Driven Ingestion Layer
==============================
Simulates Kafka/Redis Streams transaction event pipeline.
In production: replace _queue with kafka-python or redis streams.

Flow:
  Transaction happens → event published → fraud engine consumes → decision emitted

For Railway (no Kafka): uses asyncio.Queue — same interface, swap backend later.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Callable, Awaitable
from app.models.schemas import Transaction


# ── In-memory event queue ─────────────────────────────────────────────────────
_event_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
_processed_events: list[dict] = []   # last 1000 processed events for audit


async def publish_transaction_event(transaction: Transaction, source: str = "api") -> str:
    """
    Publish a transaction to the event stream.
    Returns event_id.
    In production: publish to Kafka topic 'naija.transactions.raw'
    """
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "event_type": "transaction.created",
        "source": source,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "payload": transaction.model_dump(mode="json"),
    }
    try:
        _event_queue.put_nowait(event)
    except asyncio.QueueFull:
        # Drop oldest event (backpressure handling)
        try:
            _event_queue.get_nowait()
            _event_queue.put_nowait(event)
        except Exception:
            pass
    return event_id


async def consume_events(
    handler: Callable[[dict], Awaitable[dict]],
    max_events: int = 10,
) -> list[dict]:
    """
    Consume up to max_events from the queue.
    Each event is passed to handler(event) → fraud decision.
    In production: replace with Kafka consumer group.
    """
    results = []
    for _ in range(max_events):
        try:
            event = _event_queue.get_nowait()
            result = await handler(event)
            results.append(result)
            _processed_events.append(result)
            if len(_processed_events) > 1000:
                _processed_events.pop(0)
        except asyncio.QueueEmpty:
            break
    return results


async def stream_events(
    handler: Callable[[dict], Awaitable[dict]],
) -> AsyncGenerator[dict, None]:
    """
    Continuously stream events as they arrive.
    Used for SSE endpoint: GET /api/stream/events
    In production: Kafka consumer with auto-commit.
    """
    while True:
        try:
            event = _event_queue.get_nowait()
            result = await handler(event)
            yield result
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.1)


def get_queue_stats() -> dict:
    return {
        "queue_depth": _event_queue.qsize(),
        "queue_capacity": _event_queue.maxsize,
        "processed_total": len(_processed_events),
        "backend": "asyncio.Queue (in-memory)",
        "production_upgrade": "Replace with kafka-python or redis.streams for multi-instance",
    }
