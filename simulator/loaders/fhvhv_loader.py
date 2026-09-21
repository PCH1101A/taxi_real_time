"""FHVHV (Uber/Lyft) parquet loader (TLC fhvhv_tripdata_*.parquet)."""
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

# FHVHV license numbers → operator name
LICENSE_TO_PROVIDER = {
    "HV0003": "Uber",
    "HV0005": "Lyft",
}


class FhvhvLoader(ParquetLoader):
    dataset_name = "FHVHV"

    def _find_parquet(self) -> Optional[str]:
        return self._find_file("fhvhv_tripdata")

    def _quality_check(self, row: Dict) -> bool:
        miles = self._safe_float(row.get("trip_miles"), 0.0)
        fare = self._safe_float(row.get("base_passenger_fare"), 0.0)
        ts = row.get("pickup_datetime")
        pu_id = self._safe_int(row.get("PULocationID"), 0)
        do_id = self._safe_int(row.get("DOLocationID"), 0)

        if fare > 180.0 or fare < MIN_TOTAL_AMOUNT:
            return False
        if pu_id == do_id and (miles > 6.0 or fare > 50.0):
            return False
        if miles <= 0.0 or miles > MAX_TRIP_DISTANCE_MILES:
            return False

        return (
            _is_valid_timestamp(ts)
            and pu_id > 0
            and do_id > 0
        )

    @staticmethod
    def provider_name(row: Dict) -> str:
        return LICENSE_TO_PROVIDER.get(row.get("hvfhs_license_num", ""), "FHVHV")
