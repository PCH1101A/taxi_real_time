"""
Flink Stream Processor configuration.
"""
import os

class FlinkConfig:
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    KAFKA_TOPIC_TRIPS: str = os.getenv("KAFKA_TOPIC_TRIPS", "taxi.trips.live")
    KAFKA_GROUP_ID: str = os.getenv("KAFKA_GROUP_ID", "flink-taxi-processor-group")
    
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    DATA_PATH: str = os.getenv("DATA_PATH", "/app/data/taxi_zones.json")
    
    CHECKPOINT_INTERVAL_MS: int = int(os.getenv("CHECKPOINT_INTERVAL_MS", "10000"))
    PARALLELISM: int = int(os.getenv("FLINK_PARALLELISM", "2"))
    
    SLIDING_WINDOW_SECONDS: int = int(os.getenv("SLIDING_WINDOW_SECONDS", "60"))
    DENSITY_PUBLISH_INTERVAL: float = float(os.getenv("DENSITY_PUBLISH_INTERVAL", "2.0"))

config = FlinkConfig()
