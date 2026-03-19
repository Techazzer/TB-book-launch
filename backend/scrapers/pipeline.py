"""
Pipeline Orchestrator — Scrape + inline review save.
- Deletes old products & reviews for the exam before re-scraping (prevents duplicates).
- Does NOT auto-run AI analysis — user triggers that manually via Sentiment Check button.
"""
import asyncio
from datetime import datetime
from backend.scrapers.amazon_scraper import scrape_amazon_books
from backend import crud
from backend.ws_manager import log_manager

MAX_BOOKS = 100


async def run_scraping_pipeline(exam_name: str, max_per_source: int = MAX_BOOKS) -> dict:
    start = datetime.now()
    await log_manager.broadcast("Pipeline", f"🚀 Starting pipeline for '{exam_name}' ({max_per_source} books)...", "info")

    results = {
        "exam_name": exam_name,
        "amazon_count": 0,
        "reviews_count": 0,
        "total_saved": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    # ── Step 0: Clear old data to prevent duplicates ─────────────────────────
    exam = crud.get_exam_by_name(exam_name)
    if exam:
        old_products = crud.get_products_by_exam(exam["id"])
        if old_products:
            await log_manager.broadcast("Pipeline", f"🗑 Clearing {len(old_products)} old products & their reviews...", "info")
            # Delete reviews for each old product first
            for p in old_products:
                crud.delete_reviews_by_product(p["id"])
            crud.delete_products_by_exam(exam["id"])

    # ── Step 1: Scrape Amazon ────────────────────────────────────────────────
    await log_manager.broadcast("Pipeline", f"Scraping up to {max_per_source} books from Amazon India...", "info")

    saved_products = 0
    total_reviews = 0
    try:
        amazon_products = await scrape_amazon_books(exam_name, max_per_source)
        results["amazon_count"] = len(amazon_products)

        for product in amazon_products:
            try:
                inline_reviews = product.pop("_inline_reviews", [])
                pid = crud.upsert_product(product)
                saved_products += 1

                for rev in inline_reviews:
                    try:
                        crud.insert_review(pid, rev)
                        total_reviews += 1
                    except Exception:
                        pass

            except Exception as e:
                results["errors"].append(f"Save error: {str(e)[:60]}")

        await log_manager.broadcast(
            "Pipeline",
            f"✅ {saved_products} products saved | {total_reviews} reviews saved.",
            "success"
        )
    except Exception as e:
        error_msg = f"Amazon scrape error: {str(e)[:80]}"
        results["errors"].append(error_msg)
        await log_manager.broadcast("Pipeline", f"❌ {error_msg}", "error")

    results["reviews_count"] = total_reviews
    results["total_saved"] = saved_products

    elapsed = round((datetime.now() - start).total_seconds(), 1)
    results["duration_seconds"] = elapsed

    await log_manager.broadcast(
        "Pipeline",
        f"🎉 Done! {saved_products} products, {total_reviews} reviews in {elapsed}s.",
        "success"
    )
    return results
