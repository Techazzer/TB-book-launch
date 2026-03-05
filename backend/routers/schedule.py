"""Exam schedule / upcoming exams API endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend import crud
from backend.models import ExamScheduleBase, ExamScheduleOut
import csv
import io

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/upcoming", response_model=list[dict])
def get_upcoming_exams(limit: int = 5):
    """Get upcoming exams sorted by date. Default 5, pass limit=0 for all."""
    if limit == 0:
        return crud.get_all_exam_schedules()
    return crud.get_upcoming_exams(limit=limit)


@router.get("/all", response_model=list[dict])
def get_all_schedules():
    """Get all exam schedule entries."""
    return crud.get_all_exam_schedules()


@router.post("/", response_model=dict)
def add_exam_schedule(data: ExamScheduleBase):
    """Add or update an exam schedule entry."""
    entry_id = crud.upsert_exam_schedule(data.model_dump())
    return {"id": entry_id, "status": "created"}


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
