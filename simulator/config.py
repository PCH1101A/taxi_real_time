import os
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class SimulatorConfig(BaseSettings):
    # ── Kafka ─────────────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_TRIPS: str = "taxi.trips.live"

    # ── Source mode ───────────────────────────────────────────────────────────
    # 'PARQUET_REPLAY' | 'SYNTHETIC_STREAM'
    SOURCE_MODE: str = "PARQUET_REPLAY"

    # Which datasets to include (comma-separated: YELLOW,GREEN,FHVHV)
    ENABLED_DATASETS: str = "YELLOW,GREEN,FHVHV"

    # Local data directory (mounted as /app/data in Docker)
    DATA_DIR: str = "/app/data"

    # Zone lookup JSON (converted from shapefile — all 263 zones)
    ZONE_JSON_PATH: str = "/app/data/taxi_zones.json"

    # ── Throughput ────────────────────────────────────────────────────────────
    EVENTS_PER_SECOND: float = 100.0       # target throughput
    BATCH_SIZE: int = 50                   # events per Kafka batch
    MAX_CONCURRENT_TRIPS: int = 500        # max in-flight simulated trips
    QUEUE_MAX_SIZE: int = 2000             # internal async queue buffer

    # ── Dataset mix weights (PARQUET_REPLAY only) ─────────────────────────────
    # Proportion of new trips to start from each dataset. Must sum to ~1.0.
    YELLOW_WEIGHT: float = 0.40
    GREEN_WEIGHT: float = 0.10
    FHVHV_WEIGHT: float = 0.50

    # Max rows to load from each parquet file into memory
    YELLOW_MAX_ROWS: int = 150_000
    GREEN_MAX_ROWS: int = 44_238   # full file (small)
    FHVHV_MAX_ROWS: int = 200_000

    @field_validator("EVENTS_PER_SECOND", mode="before")
    @classmethod
    def clamp_eps(cls, v: float) -> float:
        return max(1.0, min(float(v), 2000.0))

    @property
    def enabled_datasets(self) -> List[str]:
        return [d.strip().upper() for d in self.ENABLED_DATASETS.split(",") if d.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


config = SimulatorConfig()
