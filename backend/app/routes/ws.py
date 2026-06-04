from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..pipeline import STATE

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/api/ws")
async def ws_progress(ws: WebSocket) -> None:
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    STATE.subscribers.add(queue)
    try:
        if STATE.last_progress:
            await ws.send_json(STATE.last_progress.model_dump())
        while True:
            progress = await queue.get()
            await ws.send_json(progress.model_dump())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WS error: %s", e)
    finally:
        STATE.subscribers.discard(queue)
