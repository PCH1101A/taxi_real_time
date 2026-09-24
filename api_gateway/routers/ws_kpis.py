"""WebSocket endpoint for real-time KPIs and pipeline telemetry."""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.redis_service import redis_service

router = APIRouter()
log = logging.getLogger("api_gateway.ws_kpis")


@router.websocket("/ws/kpis")
async def websocket_kpis_endpoint(websocket: WebSocket):
    await websocket.accept()
    log.info("Client connected to /ws/kpis")

    try:
        # Immediately send current KPI frame
        await websocket.send_text(json.dumps(redis_service.last_kpi_frame))
    except Exception as e:
        log.warning(f"Error sending initial kpi snapshot: {e}")

    await redis_service.register_kpi_ws(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        log.info("Client disconnected from /ws/kpis")
    except Exception as e:
        log.warning(f"WebSocket error in /ws/kpis: {e}")
    finally:
        await redis_service.unregister_kpi_ws(websocket)
