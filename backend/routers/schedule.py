"""Exam schedule / upcoming exams API endpoints."""
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from backend import crud
from backend.models import ExamScheduleBase, ExamScheduleOut, StatusResponse
from backend.scrapers.exam_schedule import scrape_exam_schedules, get_seed_exam_data
from backend.ws_manager import log_manager
import csv
import io

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/upcoming", response_model=list[dict])
def get_upcoming_exams(limit: int = 5):
    """Get upcoming exams sorted by date. Default 5, pass limit=0 for all."""
    # Auto-seed if database is empty
    existing = crud.get_all_exam_schedules()
    if not existing:
        seed_data = get_seed_exam_data()
        for exam in seed_data:
            crud.upsert_exam_schedule(exam)

    if limit == 0:
        return crud.get_all_exam_schedules()
    return crud.get_upcoming_exams(limit=limit)


@router.get("/all", response_model=list[dict])
def get_all_schedules():
    """Get all exam schedule entries."""
    existing = crud.get_all_exam_schedules()
    if not existing:
        seed_data = get_seed_exam_data()
        for exam in seed_data:
            crud.upsert_exam_schedule(exam)
        return crud.get_all_exam_schedules()
    return existing


@router.post("/", response_model=dict)
def add_exam_schedule(data: ExamScheduleBase):
    """Add or update an exam schedule entry."""
    entry_id = crud.upsert_exam_schedule(data.model_dump())
    return {"id": entry_id, "status": "created"}


@router.post("/refresh")
async def refresh_exam_schedules():
    """Trigger a full refresh of exam schedule data (scrape + AI)."""
    await log_manager.broadcast("Schedule", "Manual refresh triggered...", "info")
    results = await scrape_exam_schedules()
    return {"status": "ok", "count": len(results), "message": f"Refreshed {len(results)} exam entries."}


@router.post("/seed")
def seed_exam_data():
    """Load seed data into the exam schedule table."""
    seed_data = get_seed_exam_data()
    count = 0
    for exam in seed_data:
        try:
            crud.upsert_exam_schedule(exam)
            count += 1
        except Exception:
            pass
    return {"status": "ok", "count": count, "message": f"Seeded {count} exam entries."}


@router.get("/csv")
def export_schedule_csv():
    """Export exam schedule as CSV."""
    schedules = crud.get_all_exam_schedules()
    if not schedules:
        raise HTTPException(status_code=404, detail="No exam schedules found.")

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["exam_name", "notification_date", "application_start",
                     "application_end", "expected_exam_date", "exam_cycle",
                     "estimated_applicants", "source_url", "source_name", "notes"],
    )
    writer.writeheader()
    for s in schedules:
        writer.writerow({k: s.get(k, "") for k in writer.fieldnames})
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=upcoming_exams.csv"},
    )
