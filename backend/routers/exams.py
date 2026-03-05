"""Exam-related API endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend import crud
from backend.models import ExamBase, ExamOut, ExamOverview, StatusResponse
from config import EXAM_LIST
import csv
import io

router = APIRouter(prefix="/api/exams", tags=["exams"])


@router.get("/list", response_model=list[str])
def list_available_exams():
    """Return the full list of supported exam names."""
    return EXAM_LIST


@router.get("/active", response_model=list[ExamOut])
def list_active_exams():
    """Return exams that have been scraped (exist in db)."""
    return crud.get_all_exams()


@router.get("/{exam_name}/overview")
def get_exam_overview(exam_name: str):
    """Get overview stats for a specific exam."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found. Run a scrape first.")
    stats = crud.get_exam_stats(exam["id"])
    return {
        "exam": exam,
        "total_products": stats.get("total_products", 0),
        "avg_price": round(stats["avg_price"], 2) if stats.get("avg_price") else None,
        "avg_rating": round(stats["avg_rating"], 2) if stats.get("avg_rating") else None,
        "bestseller_count": stats.get("bestseller_count", 0),
        "amazon_count": stats.get("amazon_count", 0),
        "flipkart_count": stats.get("flipkart_count", 0),
        "total_reviews": stats.get("total_reviews", 0),
    }


@router.get("/{exam_name}/products")
def get_exam_products(exam_name: str):
    """Get all products for a specific exam."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    return crud.get_products_by_exam(exam["id"])


@router.get("/{exam_name}/products/csv")
def export_exam_products_csv(exam_name: str):
    """Export products for a specific exam as CSV."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    products = crud.get_products_by_exam(exam["id"])
    if not products:
        raise HTTPException(status_code=404, detail="No products found for this exam.")

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["title", "author", "publisher", "marketplace", "price", "mrp",
                     "rating", "review_count", "best_seller_rank", "book_format",
                     "language", "is_bestseller", "product_url"],
    )
    writer.writeheader()
    for p in products:
        writer.writerow({k: p.get(k, "") for k in writer.fieldnames})
    output.seek(0)

    filename = f"{exam_name.replace(' ', '_')}_products.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{exam_name}/reviews")
def get_exam_reviews(exam_name: str, product_id: int = None):
    """Get reviews for a specific exam, optionally filtered by product."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    if product_id:
        return crud.get_reviews_by_product(product_id)
    # Get reviews for all products in this exam
    products = crud.get_products_by_exam(exam["id"])
    all_reviews = []
    for p in products:
        reviews = crud.get_reviews_by_product(p["id"])
        for r in reviews:
            r["product_title"] = p["title"]
        all_reviews.extend(reviews)
    return all_reviews


@router.get("/{exam_name}/analysis")
def get_exam_analysis(exam_name: str):
    """Get AI analysis results for all products in an exam."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    return crud.get_analyses_by_exam(exam["id"])


@router.get("/{exam_name}/gaps")
def get_exam_gaps(exam_name: str):
    """Get market gap analysis for an exam."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    gaps = crud.get_market_gaps(exam["id"])
    if not gaps:
        raise HTTPException(status_code=404, detail="No gap analysis found. Run AI analysis first.")
    return gaps
