"""FastAPI WebSocket & REST Gateway for NYC Taxi Real-Time Pipeline."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import ws_fleet, ws_kpis, rest_api
from services.redis_service import redis_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("api_gateway.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting FastAPI Gateway...")
    await redis_service.start()
    yield
    log.info("Shutting down FastAPI Gateway...")
    await redis_service.stop()


app = FastAPI(
    title="NYC Taxi Real-Time Gateway",
    description="High-throughput WebSocket & REST gateway for Apache Flink stream telemetry",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for React SPA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(ws_fleet.router)
app.include_router(ws_kpis.router)
app.include_router(rest_api.router)


@app.get("/healthz")
async def health_check():
    kpis = await redis_service.fetch_realtime_kpis()
    return {
        "status": "ok",
        "redis_connected": kpis.get("total_active_vehicles", 0) >= 0,
        "active_fleet_subscribers": len(redis_service.fleet_subscribers),
        "active_kpi_subscribers": len(redis_service.kpi_subscribers),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
