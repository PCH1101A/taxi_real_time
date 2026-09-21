"""
NYC Taxi Real-Time Simulator — Entry point.

Usage:
  python main.py                  # normal run (Kafka required)
  python main.py --dry-run        # generate events, print to stdout (no Kafka)
  python main.py --dry-run -n 50  # dry-run, print 50 events then exit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SIMULATOR] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("simulator")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NYC Taxi Real-Time Simulator")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print events to stdout instead of sending to Kafka.",
    )
    p.add_argument(
        "-n", "--events",
        type=int,
        default=0,
        help="Stop after N events (0 = run forever). Applies to dry-run only.",
    )
    return p.parse_args()


async def _dry_run(max_events: int) -> None:
    """Generate events and print as JSON — no Kafka required."""
    import random
    import time

    from config import config
    from loaders.yellow_loader import YellowLoader
    from loaders.green_loader import GreenLoader
    from loaders.fhvhv_loader import FhvhvLoader
    from zones.zone_registry import ZoneRegistry
    from generator.trip_generator import TripGenerator
    from models.trip_event import DatasetSource  # noqa: F401 (used via DatasetSource(dataset))

    log.info("DRY RUN mode — events will be printed to stdout")
    zones = ZoneRegistry(json_path=config.ZONE_JSON_PATH)
    generator = TripGenerator(zones=zones)

    loaders: dict = {}
    if config.SOURCE_MODE == "PARQUET_REPLAY":
        for name, cls, rows in [
            ("YELLOW", YellowLoader, config.YELLOW_MAX_ROWS),
            ("GREEN",  GreenLoader,  config.GREEN_MAX_ROWS),
            ("FHVHV",  FhvhvLoader,  config.FHVHV_MAX_ROWS),
        ]:
            if name in config.enabled_datasets:
                loader = cls(data_dir=config.DATA_DIR, max_rows=rows)
                loader.load()
                loaders[name] = loader

    count = 0
    enabled = config.enabled_datasets
    weights = {
        "YELLOW": config.YELLOW_WEIGHT,
        "GREEN":  config.GREEN_WEIGHT,
        "FHVHV":  config.FHVHV_WEIGHT,
    }

    while max_events == 0 or count < max_events:
        active = generator.active_count
        if active < config.MAX_CONCURRENT_TRIPS and (random.random() < 0.4 or active == 0):
            ready = [d for d in enabled if loaders.get(d) and loaders[d].is_ready]
            if config.SOURCE_MODE == "PARQUET_REPLAY" and ready:
                dataset = random.choices(ready, weights=[weights[d] for d in ready], k=1)[0]
                row = loaders[dataset].next_row()
                event = generator.create_from_parquet(DatasetSource(dataset), row)
            else:
                event = generator.create_synthetic()
        else:
            trip_id = generator.random_active_trip_id()
            event = generator.step(trip_id) if trip_id else generator.create_synthetic()

        if event:
            print(json.dumps(event.to_kafka_dict(), indent=None, default=str))
            count += 1

        await asyncio.sleep(0.001)  # yield

    log.info("Dry-run complete: %d events generated.", count)


async def _main() -> None:
    args = _parse_args()

    if args.dry_run:
        await _dry_run(max_events=args.events)
    else:
        # Import here to avoid loading aiokafka in dry-run mode
        from producer.kafka_producer import run_producer  # noqa: E402
        await run_producer()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        log.info("Terminated by user.")
