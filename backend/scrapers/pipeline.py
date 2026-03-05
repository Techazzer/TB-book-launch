"""
Pipeline Orchestrator — Coordinates the full scraping + analysis pipeline.

For a given exam:
1. Scrape Amazon India for top books
2. Scrape Flipkart for top books
3. Save all products to database
4. Broadcast progress via WebSocket activity log
"""
import asyncio
from datetime import datetime
from backend.scrapers.amazon_scraper import scrape_amazon_books
from backend.scrapers.flipkart_scraper import scrape_flipkart_books
from backend.crud import upsert_product, get_products_by_exam
from backend.ws_manager import log_manager


async def run_scraping_pipeline(exam_name: str, max_per_source: int = 20) -> dict:
    """
    Run the full scraping pipeline for an exam.
    Returns summary dict with counts and status.
    """
    start = datetime.now()
    
    await log_manager.broadcast(
        "Pipeline",
        f"🚀 Starting pipeline for '{exam_name}'...",
        "info"
    )
    
    results = {
        "exam_name": exam_name,
        "amazon_count": 0,
        "flipkart_count": 0,
        "total_saved": 0,
        "errors": [],
        "duration_seconds": 0,
    }
    
    # ── Step 1: Scrape Amazon ────────────────────────────────────────
    await log_manager.broadcast("Pipeline", "Step 1/3: Scraping Amazon India...", "info")
    
    try:
        amazon_products = await scrape_amazon_books(exam_name, max_per_source)
        results["amazon_count"] = len(amazon_products)
        
        saved = 0
        for product in amazon_products:
            try:
                upsert_product(product)
                saved += 1
            except Exception as e:
                results["errors"].append(f"Amazon save error: {str(e)[:60]}")
        
        await log_manager.broadcast(
            "Pipeline",
            f"✅ Amazon: {saved} products saved to database.",
            "success"
        )
    except Exception as e:
        error_msg = f"Amazon pipeline error: {str(e)[:80]}"
        results["errors"].append(error_msg)
        await log_manager.broadcast("Pipeline", f"❌ {error_msg}", "error")
    
    # ── Step 2: Scrape Flipkart ──────────────────────────────────────
    await log_manager.broadcast("Pipeline", "Step 2/3: Scraping Flipkart...", "info")
    
    try:
        flipkart_products = await scrape_flipkart_books(exam_name, max_per_source)
        results["flipkart_count"] = len(flipkart_products)
        
        saved = 0
        for product in flipkart_products:
            try:
                upsert_product(product)
                saved += 1
            except Exception as e:
                results["errors"].append(f"Flipkart save error: {str(e)[:60]}")
        
        await log_manager.broadcast(
            "Pipeline",
            f"✅ Flipkart: {saved} products saved to database.",
            "success"
        )
    except Exception as e:
        error_msg = f"Flipkart pipeline error: {str(e)[:80]}"
        results["errors"].append(error_msg)
        await log_manager.broadcast("Pipeline", f"❌ {error_msg}", "error")
    
    # ── Step 3: Summary ──────────────────────────────────────────────
    elapsed = (datetime.now() - start).total_seconds()
    results["duration_seconds"] = round(elapsed, 1)
    results["total_saved"] = results["amazon_count"] + results["flipkart_count"]
    
    total_in_db = len(get_products_by_exam(exam_name))
    
    await log_manager.broadcast(
        "Pipeline",
        f"🎉 Pipeline complete for '{exam_name}': "
        f"{results['total_saved']} products scraped, "
        f"{total_in_db} total in database. "
        f"Took {results['duration_seconds']}s.",
        "success"
    )
    
    return results
