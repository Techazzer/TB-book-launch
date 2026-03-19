"""FastAPI main application — Product Launch Dashboard."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from backend.database import init_db
from backend.routers import exams, schedule
from backend.ws_manager import log_manager
from config import FRONTEND_DIR


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


# ── Static Files & Frontend ─────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/all-exams")
async def serve_all_exams():
    return FileResponse(str(FRONTEND_DIR / "all-exams.html"))


@app.get("/process")
async def serve_process():
    return FileResponse(str(FRONTEND_DIR / "process.html"))


# ── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Product Launch Dashboard is running"}
