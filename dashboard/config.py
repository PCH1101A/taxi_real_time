import os
from pydantic_settings import BaseSettings

class DashboardConfig(BaseSettings):
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REFRESH_INTERVAL_MS: int = int(os.getenv("REFRESH_INTERVAL_MS", "2000"))
    MAPBOX_STYLE: str = os.getenv("MAPBOX_STYLE", "dark")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

config = DashboardConfig()
