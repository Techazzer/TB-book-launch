"""Exam-related API endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend import crud
from backend.models import ExamBase, ExamOut, ExamOverview, StatusResponse
from backend.scrapers.pipeline import run_scraping_pipeline
from backend.scrapers.ai_analyzer import run_sentiment_analysis
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
        "total_reviews": stats.get("total_reviews", 0),
        "estimated_applicants": stats.get("estimated_applicants"),
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
    # Get reviews for all products in this exam, enriched with product info
    products = crud.get_products_by_exam(exam["id"])
    all_reviews = []
    for p in products:
        reviews = crud.get_reviews_by_product(p["id"])
        for r in reviews:
            r["product_title"] = p["title"]
            r["author"] = p.get("author")
            r["asin"] = p.get("asin")
            r["product_url"] = p.get("product_url")
        all_reviews.extend(reviews)
    return all_reviews


@router.get("/{exam_name}/reviews/csv")
def export_exam_reviews_csv(exam_name: str):
    """Export all reviews for a specific exam as CSV."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")

    products = crud.get_products_by_exam(exam["id"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Product Title", "Amazon Link", "Reviewer", "Rating",
        "Review Title", "Content", "Date", "Verified", "Helpful Votes"
    ])
    for p in products:
        reviews = crud.get_reviews_by_product(p["id"])
        asin = p.get("asin")
        link = f"https://www.amazon.in/dp/{asin}" if asin else p.get("product_url", "")
        for r in reviews:
            writer.writerow([
                p["title"],
                link,
                r.get("reviewer_name", ""),
                r.get("rating", ""),
                r.get("title", ""),
                r.get("content", ""),
                r.get("review_date", ""),
                "Yes" if r.get("verified_purchase") else "No",
                r.get("helpful_count", 0),
            ])
    output.seek(0)
    filename = f"{exam_name.replace(' ', '_')}_reviews.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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


@router.get("/{exam_name}/analysis/csv")
def export_exam_analysis_csv(exam_name: str):
    """Export AI sentiment analysis for a specific exam as CSV."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    analyses = crud.get_analyses_by_exam(exam["id"])
    if not analyses:
        raise HTTPException(status_code=404, detail="No AI analysis found for this exam.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Marketplace", "Positive %", "Neutral %", "Negative %", "Top Complaint", "Key Strengths"])
    
    for a in analyses:
        s = a.get("sentiment_data") or {}
        f = a.get("feature_data") or {}
        complaints = s.get("top_complaints", [])
        top_complaint = complaints[0] if complaints else ""
        strengths = f.get("key_strengths", [])
        strengths_str = " | ".join(strengths) if strengths else ""
        
        writer.writerow([
            a.get("title", ""),
            a.get("marketplace", ""),
            s.get("positive_pct", ""),
            s.get("neutral_pct", ""),
            s.get("negative_pct", ""),
            top_complaint,
            strengths_str
        ])
    
    output.seek(0)
    filename = f"{exam_name.replace(' ', '_')}_sentiment.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{exam_name}/gaps/csv")
def export_exam_gaps_csv(exam_name: str):
    """Export market gaps for a specific exam as CSV."""
    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        raise HTTPException(status_code=404, detail=f"Exam '{exam_name}' not found.")
    gaps_obj = crud.get_market_gaps(exam["id"])
    if not gaps_obj or not gaps_obj.get("gap_data"):
        raise HTTPException(status_code=404, detail="No gap analysis found.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Gap Title", "Description", "Opportunity Level"])
    
    for g in gaps_obj.get("gap_data", []):
        writer.writerow([
            g.get("title", ""),
            g.get("description", ""),
            g.get("opportunity_level", "")
        ])
    
    # Add a spacer and recommendations
    writer.writerow([])
    writer.writerow(["Recommendation Action", "Expected Impact", ""])
    for r in gaps_obj.get("recommendations", []):
         writer.writerow([
            r.get("action", ""),
            r.get("expected_impact", ""),
            ""
         ])
         
    output.seek(0)
    filename = f"{exam_name.replace(' ', '_')}_market_gaps.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{exam_name}/scrape")
async def scrape_exam_data(exam_name: str, max_results: int = 20):
    """Run the full scraping pipeline for an exam."""
    # Validate max_results to prevent resource exhaustion
    if max_results < 1 or max_results > 200:
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 200")
    results = await run_scraping_pipeline(exam_name, max_per_source=max_results)
    return results


@router.post("/{exam_name}/sentiment-check")
async def run_exam_sentiment_check(exam_name: str, num_products: int = 20):
    """Run Claude-powered holistic sentiment + gap analysis on all stored reviews."""
    result = await run_sentiment_analysis(exam_name, num_products=num_products)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Sentiment analysis failed. Check logs — ANTHROPIC_API_KEY may not be set or no reviews exist yet."
        )
    return result

