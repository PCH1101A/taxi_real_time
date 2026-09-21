"""Green Taxi parquet loader (TLC green_tripdata_*.parquet)."""
from __future__ import annotations

import logging
from typing import Dict, Optional

from loaders.base_loader import (
    MAX_TRIP_DISTANCE_MILES,
    MIN_TOTAL_AMOUNT,
    MAX_TOTAL_AMOUNT,
    ParquetLoader,
    _is_valid_timestamp,
)

log = logging.getLogger(__name__)


class GreenLoader(ParquetLoader):
    dataset_name = "GREEN"

    def _find_parquet(self) -> Optional[str]:
        return self._find_file("green_tripdata")

    def _quality_check(self, row: Dict) -> bool:
        dist = self._safe_float(row.get("trip_distance"), 0.0)
        amount = self._safe_float(row.get("total_amount"), 0.0)
        ts = row.get("lpep_pickup_datetime")
        pu_id = self._safe_int(row.get("PULocationID"), 0)
        do_id = self._safe_int(row.get("DOLocationID"), 0)

        # Eliminate extreme fare outliers and erroneous charges in green cabs
        if amount > 100.0 or amount < MIN_TOTAL_AMOUNT:
            return False
        if pu_id == do_id and (dist > 4.0 or amount > 40.0):
            return False
        if dist <= 0.0 or dist > 45.0:
            return False

        return (
            _is_valid_timestamp(ts)
            and pu_id > 0
            and do_id > 0
        )
