import asyncio
import json
import logging
from typing import Dict, Set

logger = logging.getLogger("chat_events")

class ChatEventBroadcaster:
    """
    In-memory async pub/sub manager for Server-Sent Events (SSE).
    Distributes real-time events (incoming message, status update, reaction)
    directly to connected browser clients without polling.
    """
    def __init__(self):
        self._listeners: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._listeners.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._listeners.discard(q)

    async def broadcast(self, event_type: str, data: dict):
        if not self._listeners:
            return
        payload = {
            "event": event_type,
            "data": data
        }
        # Non-blocking broadcast to all active queues
        dead_queues = set()
        for q in self._listeners:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead_queues.add(q)
            except Exception:
                dead_queues.add(q)
        for q in dead_queues:
            self._listeners.discard(q)

    def publish_sync(self, event_type: str, data: dict):
        """Thread-safe and sync-context helper to schedule a broadcast."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(event_type, data))
        except RuntimeError:
            pass


chat_broadcaster = ChatEventBroadcaster()

