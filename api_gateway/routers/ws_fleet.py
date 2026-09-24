"""WebSocket endpoint for real-time fleet positions and zones."""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.redis_service import redis_service

router = APIRouter()
log = logging.getLogger("api_gateway.ws_fleet")


@router.websocket("/ws/fleet")
async def websocket_fleet_endpoint(websocket: WebSocket):
    await websocket.accept()
    log.info("Client connected to /ws/fleet")

    # Send initial snapshot immediately so client does not wait for next 2s tick
    try:
        if redis_service.last_fleet_frame.get("vehicles"):
            await websocket.send_text(json.dumps(redis_service.last_fleet_frame))
        else:
            # First fetch if poller hasn't run yet
            density = await redis_service.fetch_density_metrics()
            if density:
                vehicles = density.get("active_vehicles_sample", [])
                initial_frame = {
                    "timestamp": density.get("timestamp", 0.0),
                    "total_active_vehicles": density.get("total_active_vehicles", len(vehicles)),
                    "taxi_type_distribution": density.get("taxi_type_distribution", {}),
                    "borough_distribution": density.get("borough_distribution", {}),
                    "vehicles": vehicles,
                    "top_congested_zones": density.get("top_congested_zones", []),
                    "all_zones": density.get("all_zones", []),
                    "territory_counts": density.get("territory_counts", {}),
                    "invasion_zones": density.get("invasion_zones", []),
                    "total_fare_in_flight": density.get("total_fare_in_flight", 0.0),
                    "average_speed_mph": density.get("average_speed_mph", 0.0),
                }
                await websocket.send_text(json.dumps(initial_frame))
    except Exception as e:
        log.warning(f"Error sending initial fleet snapshot: {e}")

    await redis_service.register_fleet_ws(websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages (e.g. heartbeat ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        log.info("Client disconnected from /ws/fleet")
    except Exception as e:
        log.warning(f"WebSocket error in /ws/fleet: {e}")
    finally:
        await redis_service.unregister_fleet_ws(websocket)
