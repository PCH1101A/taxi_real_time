"""
High-throughput async Kafka producer.

Architecture:
  Task A: _event_generator → fills asyncio.Queue with TripEvent objects
  Task B: _batch_sender    → drains queue in batches → Kafka (fire-and-forget)

This decouples event generation from I/O, enabling 100–500+ event/s on a single machine.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import List, Optional

from aiokafka import AIOKafkaProducer

from config import config
from generator.trip_generator import TripGenerator
from loaders.fhvhv_loader import FhvhvLoader
from loaders.green_loader import GreenLoader
from loaders.yellow_loader import YellowLoader
from models.trip_event import DatasetSource, TripEvent
from zones.zone_registry import ZoneRegistry

log = logging.getLogger(__name__)

# ── Dataset weights for mixed-source replay ────────────────────────────────────
_DATASET_WEIGHTS: dict[str, float] = {
    "YELLOW": config.YELLOW_WEIGHT,
    "GREEN": config.GREEN_WEIGHT,
    "FHVHV": config.FHVHV_WEIGHT,
}


def _pick_dataset(enabled: List[str]) -> str:
    weights = [_DATASET_WEIGHTS.get(d, 0.33) for d in enabled]
    return random.choices(enabled, weights=weights, k=1)[0]


async def _event_generator(
    queue: asyncio.Queue,
    generator: TripGenerator,
    loaders: dict,
    parquet_indices: dict,
) -> None:
    """Continuously generate TripEvent objects and put them in the queue."""
    enabled = config.enabled_datasets
    spawn_probability = 0.40  # chance to start a new trip vs advance existing

    while True:
        active_count = generator.active_count

        if active_count < config.MAX_CONCURRENT_TRIPS and (
            random.random() < spawn_probability or active_count == 0
        ):
            # ── Start a new trip ──────────────────────────────────────────────
            if config.SOURCE_MODE == "PARQUET_REPLAY" and loaders:
                dataset = _pick_dataset([d for d in enabled if loaders.get(d) and loaders[d].is_ready])
                if not dataset:
                    dataset = _pick_dataset(enabled)

                loader = loaders.get(dataset)
                if loader and loader.is_ready:
                    row = loader.next_row()
                    event = generator.create_from_parquet(DatasetSource(dataset), row)
                else:
                    event = generator.create_synthetic()
            else:
                event = generator.create_synthetic()

            await queue.put(event)

        else:
            # ── Advance an existing trip ──────────────────────────────────────
            trip_id = generator.random_active_trip_id()
            if trip_id:
                event = generator.step(trip_id)
                if event:
                    await queue.put(event)

        # Small yield to prevent CPU spin — generator is fast, sender is the bottleneck
        await asyncio.sleep(0)


async def _batch_sender(
    queue: asyncio.Queue,
    producer: AIOKafkaProducer,
    topic: str,
    batch_size: int,
    interval: float,
) -> None:
    """
    Drain queue in batches and send to Kafka.
    Uses fire-and-forget send() (not send_and_wait) for max throughput.
    """
    total_sent = 0
    last_log_time = time.time()
    last_log_count = 0

    while True:
        batch: List[TripEvent] = []

        # Collect up to batch_size events (non-blocking drain)
        try:
            while len(batch) < batch_size:
                event = queue.get_nowait()
                batch.append(event)
        except asyncio.QueueEmpty:
            pass

        if not batch:
            await asyncio.sleep(interval)
            continue

        # Send batch (fire-and-forget)
        for event in batch:
            try:
                await producer.send(topic, event.to_kafka_dict())
                total_sent += 1
            except Exception as exc:
                log.error("Kafka send error: %s", exc)

        # Throughput log every 5 seconds
        now = time.time()
        if now - last_log_time >= 5.0:
            rate = (total_sent - last_log_count) / max(0.1, now - last_log_time)
            log.info(
                "📊 Throughput: %.0f event/s | Total: %d | Queue: %d | Active trips: will_show_in_generator",
                rate, total_sent, queue.qsize(),
            )
            last_log_time = now
            last_log_count = total_sent

        await asyncio.sleep(interval)


async def run_producer() -> None:
    """Main entrypoint for the Kafka producer."""
    log.info("NYC Taxi Simulator starting...")
    log.info("Kafka: %s → topic: %s", config.KAFKA_BOOTSTRAP_SERVERS, config.KAFKA_TOPIC_TRIPS)
    log.info(
        "Mode: %s | Datasets: %s | Target: %.0f event/s | Batch: %d",
        config.SOURCE_MODE, config.ENABLED_DATASETS,
        config.EVENTS_PER_SECOND, config.BATCH_SIZE,
    )

    # ── Zone registry ─────────────────────────────────────────────────────────
    zones = ZoneRegistry(json_path=config.ZONE_JSON_PATH)

    # ── Load parquet datasets ─────────────────────────────────────────────────
    loaders: dict = {}
    parquet_indices: dict = {}
    if config.SOURCE_MODE == "PARQUET_REPLAY":
        loader_classes = {
            "YELLOW": (YellowLoader, config.YELLOW_MAX_ROWS),
            "GREEN":  (GreenLoader,  config.GREEN_MAX_ROWS),
            "FHVHV":  (FhvhvLoader,  config.FHVHV_MAX_ROWS),
        }
        for dataset in config.enabled_datasets:
            cls, max_rows = loader_classes[dataset]
            loader = cls(data_dir=config.DATA_DIR, max_rows=max_rows)
            loader.load()
            loaders[dataset] = loader
            parquet_indices[dataset] = 0

    # ── Generator ─────────────────────────────────────────────────────────────
    generator = TripGenerator(zones=zones)

    # ── Kafka producer with retry ─────────────────────────────────────────────
    producer: Optional[AIOKafkaProducer] = None
    retry = 0
    while producer is None:
        try:
            producer = AIOKafkaProducer(
                bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                compression_type="gzip",
                linger_ms=5,         # micro-batching at Kafka level
                acks=1,              # leader ack — balanced durability/speed
            )
            await producer.start()
            log.info("✅ Connected to Kafka")
        except Exception as exc:
            retry += 1
            log.warning("Kafka connection failed (attempt %d): %s — retrying in 3s", retry, exc)
            producer = None
            await asyncio.sleep(3)

    # ── Async queue ───────────────────────────────────────────────────────────
    queue: asyncio.Queue[TripEvent] = asyncio.Queue(maxsize=config.QUEUE_MAX_SIZE)

    # Batch interval: how often sender flushes (not 1/eps — generator fills queue freely)
    batch_interval = config.BATCH_SIZE / max(1.0, config.EVENTS_PER_SECOND)

    try:
        await asyncio.gather(
            _event_generator(queue, generator, loaders, parquet_indices),
            _batch_sender(queue, producer, config.KAFKA_TOPIC_TRIPS, config.BATCH_SIZE, batch_interval),
        )
    except asyncio.CancelledError:
        log.info("Simulator cancelled.")
    except Exception as exc:
        log.error("Fatal error: %s", exc, exc_info=True)
    finally:
        if producer:
            await producer.stop()
            log.info("Kafka producer stopped.")
