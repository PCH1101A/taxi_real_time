"""
Entrypoint forwarding to main.py to run the high-throughput multi-fleet Kafka producer (Yellow, Green, FHVHV).
"""
import asyncio
import sys
from main import _main

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
