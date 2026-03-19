"""FastAPI main application — Product Launch Dashboard — API ONLY for Vercel."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

from database import init_db
from routers import exams, schedule
from ws_manager import log_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup (safe fail mode)."""
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Startup init_db failed, likely missing DATABASE_URL. {e}")
    yield


app = FastAPI(
    title="Product Launch Dashboard",
    description="Exam Book Market Intelligence & Launch Analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# ── API Routers ──────────────────────────────────────────────────────────────
app.include_router(exams.router)
app.include_router(schedule.router)


# ── WebSocket for Activity Log ───────────────────────────────────────────────
@app.websocket("/ws/activity-log")
async def websocket_activity_log(websocket: WebSocket):
    await log_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        log_manager.disconnect(websocket)


# ── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Product Launch Dashboard is running"}
