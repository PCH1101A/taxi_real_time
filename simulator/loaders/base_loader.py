"""Abstract base class for all dataset parquet loaders."""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional

import pyarrow.parquet as pq

log = logging.getLogger(__name__)

# Data quality bounds (shared across all datasets)
MAX_TRIP_DISTANCE_MILES = 75.0
MIN_TOTAL_AMOUNT = 2.5
MAX_TOTAL_AMOUNT = 200.0

# Accept timestamps within a generous window around April 2026
_TS_MIN = datetime(2026, 3, 31, tzinfo=timezone.utc)
_TS_MAX = datetime(2026, 5, 2, tzinfo=timezone.utc)


def _is_valid_timestamp(ts: Optional[datetime]) -> bool:
    if ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return _TS_MIN <= ts <= _TS_MAX


class ParquetLoader(ABC):
    """Load a parquet file and yield clean raw-row dicts one by one (cycling)."""

    dataset_name: str = "UNKNOWN"

    def __init__(self, data_dir: str, max_rows: int = 150_000) -> None:
        self._data_dir = data_dir
        self._max_rows = max_rows
        self._records: List[Dict] = []
        self._cursor = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Read parquet file into memory, apply DQ filters. Call once at startup."""
        path = self._find_parquet()
        if not path:
            log.warning("[%s] Parquet file not found in %s", self.dataset_name, self._data_dir)
            return
        try:
            table = pq.read_table(path)
            total = table.num_rows
            sample = table.slice(0, min(self._max_rows, total))
            raw = sample.to_pylist()
            self._records = [r for r in raw if self._quality_check(r)]
            log.info(
                "[%s] Loaded %d/%d rows (after DQ filter, from %s)",
                self.dataset_name, len(self._records), total, os.path.basename(path),
            )
        except Exception as exc:
            log.error("[%s] Failed to load parquet: %s", self.dataset_name, exc)

    def next_row(self) -> Optional[Dict]:
        """Return next raw row (cycling). Returns None if no data loaded."""
        if not self._records:
            return None
        row = self._records[self._cursor % len(self._records)]
        self._cursor += 1
        return row

    @property
    def is_ready(self) -> bool:
        return len(self._records) > 0

    # ── Subclass contract ──────────────────────────────────────────────────────

    @abstractmethod
    def _find_parquet(self) -> Optional[str]:
        """Return absolute path to the parquet file, or None if not found."""

    @abstractmethod
    def _quality_check(self, row: Dict) -> bool:
        """Return True if this row passes data quality rules."""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _find_file(self, pattern: str) -> Optional[str]:
        """Find first parquet file in data_dir whose name contains pattern."""
        candidates = [
            self._data_dir,
            os.path.join(self._data_dir, ".."),
        ]
        for d in candidates:
            d = os.path.abspath(d)
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if fname.endswith(".parquet") and pattern.lower() in fname.lower():
                    return os.path.join(d, fname)
        return None

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        try:
            return float(val or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(val, default: int = 0) -> int:
        try:
            return int(val or default)
        except (TypeError, ValueError):
            return default
