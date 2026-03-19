"""WebSocket manager for live activity log."""
from fastapi import WebSocket
from datetime import datetime
import json
import asyncio
from typing import List


class ActivityLogManager:
    """Manages WebSocket connections and broadcasts log entries."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.log_history: List[dict] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send history to new connection
        for entry in self.log_history[-50:]:
            try:
                await websocket.send_json(entry)
            except Exception:
                pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, step: str, message: str, level: str = "info"):
        """Broadcast a log entry to all connected clients."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "step": step,
            "message": message,
            "level": level,
        }
        self.log_history.append(entry)
        # Keep only last 200 entries
        if len(self.log_history) > 200:
            self.log_history = self.log_history[-200:]

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(entry))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    def log_sync(self, step: str, message: str, level: str = "info"):
        """Synchronous log entry (stores in history, broadcasts on next await)."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "step": step,
            "message": message,
            "level": level,
        }
        self.log_history.append(entry)
        if len(self.log_history) > 200:
            self.log_history = self.log_history[-200:]

    def clear(self):
        """Clear log history."""
        self.log_history.clear()


# Singleton instance
log_manager = ActivityLogManager()
