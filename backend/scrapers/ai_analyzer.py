"""
AI Analyzer — Claude-powered analysis.
Two functions:
  1. run_ai_analysis()    — per-product feature/sentiment from scraped reviews
  2. run_sentiment_analysis() — holistic sentiment + gap analysis for the Sentiment & Gaps tab
"""
import json
import asyncio
import re
try:
    from anthropic import AsyncAnthropic
except Exception:
    class AsyncAnthropic:
        def __init__(self, api_key=None):
            pass
        @property
        def messages(self):
            class Dummy:
                async def create(self, *args, **kwargs):
                    # Return a minimal structure
                    return type("Response", (), {"content": [type("Content", (), {"text": "{}"})]})
            return Dummy()
from backend import crud
from backend.ws_manager import log_manager
from config import ANTHROPIC_API_KEY, AI_MODEL

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


# ─── Prompt Templates ─────────────────────────────────────────────────────────

PRODUCT_ANALYSIS_PROMPT = """\
You are an expert market analyst for exam preparation books.
Analyze the provided books and their reviews for a government exam.
Return ONLY valid JSON (no markdown) in this exact structure:
{{
  "product_analysis": [
    {{
      "product_id": <int>,
      "sentiment": {{
        "positive_pct": <int 0-100>,
        "neutral_pct": <int 0-100>,
        "negative_pct": <int 0-100>,
        "top_complaints": ["complaint 1", "complaint 2"]
      }},
      "features": {{
        "format_type": "<PYQ | Theory | Mixed>",
        "has_solutions": <bool>,
        "key_strengths": ["strength 1", "strength 2"]
      }}
    }}
  ],
  "market_gaps": {{
    "gaps": [
      {{"title": "Gap title", "description": "Detail", "opportunity_level": "High|Medium|Low"}}
    ],
    "recommendations": [
      {{"action": "Action text", "expected_impact": "Impact text"}}
    ]
  }}
}}

Data:
{data}
"""

SENTIMENT_ANALYSIS_PROMPT = """\
You are a senior market analyst specializing in Indian government exam preparation books.
I'm giving you aggregated customer review data (positive and negative) for the top books in the "{exam_name}" exam category on Amazon India.

Analyze this data and return ONLY valid JSON (no markdown, no extra text) in this exact structure:
{{
  "summary": {{
    "total_books_analyzed": <int>,
    "total_reviews_analyzed": <int>,
    "positive_pct": <int 0-100>,
    "neutral_pct": <int 0-100>,
    "negative_pct": <int 0-100>
  }},
  "top_praises": [
    {{"point": "Specific praise", "books": ["Book title 1", "Book title 2"], "frequency": "High|Medium|Low"}}
  ],
  "top_complaints": [
    {{"point": "Specific complaint or problem", "books": ["Book title 1"], "frequency": "High|Medium|Low"}}
  ],
  "market_gaps": [
    {{"gap": "Gap description", "opportunity": "What a new book could do differently", "priority": "High|Medium|Low"}}
  ],
  "positioning_recommendation": "One paragraph recommendation for how a new book should be positioned to win in this market."
}}

Use exactly 5 items in top_praises, 5 in top_complaints, and 3-5 in market_gaps.

Review data:
{data}
"""


# ─── Product Analysis (called after scrape) ───────────────────────────────────

async def run_ai_analysis(exam_name: str) -> bool:
    if not client:
        await log_manager.broadcast("AI", "⚠️ Skipping AI analysis: ANTHROPIC_API_KEY not set.", "warning")
        return False

    await log_manager.broadcast("AI Analysis", f"🤖 Starting AI analysis for '{exam_name}'...", "info")

    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        return False

    products = crud.get_products_by_exam(exam["id"])
    if not products:
        await log_manager.broadcast("AI Analysis", "⚠️ No products found.", "warning")
        return False

    # Send top 10 rated products to avoid context overload
    top_products = sorted(products, key=lambda x: x.get("rating") or 0, reverse=True)[:10]

    payload = []
    for p in top_products:
        reviews = crud.get_reviews_by_product(p["id"])
        review_texts = [r["content"] for r in reviews if r.get("content")][:15]
        payload.append({
            "product_id": p["id"],
            "title": p["title"],
            "rating": p["rating"],
            "price": p["price"],
            "reviews": review_texts,
        })

    try:
        await log_manager.broadcast("AI Analysis", f"🧠 Sending {len(top_products)} products to Claude...", "info")
        prompt = PRODUCT_ANALYSIS_PROMPT.format(data=json.dumps(payload, indent=2))
        response = await client.messages.create(
            model=AI_MODEL, max_tokens=4000, temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.M)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.M)

        parsed = json.loads(raw)

        for p_analysis in parsed.get("product_analysis", []):
            crud.upsert_analysis(
                product_id=p_analysis["product_id"],
                sentiment_data=p_analysis.get("sentiment"),
                feature_data=p_analysis.get("features"),
            )

        market_gaps = parsed.get("market_gaps", {})
        crud.upsert_market_gaps(
            exam_id=exam["id"],
            gap_data=market_gaps.get("gaps"),
            recommendations=market_gaps.get("recommendations"),
        )

        await log_manager.broadcast("AI Analysis", f"✅ AI analysis complete! Processed {len(top_products)} products.", "success")
        return True

    except Exception as e:
        import traceback; traceback.print_exc()
        await log_manager.broadcast("AI Analysis", f"❌ AI error: {str(e)[:100]}", "error")
        return False


# ─── Holistic Sentiment Analysis (triggered by user) ─────────────────────────

async def run_sentiment_analysis(exam_name: str, num_products: int) -> dict | None:
    """
    Build a holistic sentiment + gap analysis for the Sentiment & Gaps tab.
    Reads all reviews from DB, sends to Claude, returns structured JSON.
    """
    if not client:
        await log_manager.broadcast("Sentiment", "❌ ANTHROPIC_API_KEY not set.", "error")
        return None

    await log_manager.broadcast("Sentiment", f"🧠 Running Sentiment Analysis for '{exam_name}'...", "info")

    exam = crud.get_exam_by_name(exam_name)
    if not exam:
        await log_manager.broadcast("Sentiment", "❌ Exam not found.", "error")
        return None

    products = crud.get_products_by_exam(exam["id"])
    if not products:
        await log_manager.broadcast("Sentiment", "❌ No products found — scrape first.", "warning")
        return None

    # Build review payload: per product, 5 positive + 5 negative reviews
    payload_items = []
    total_reviews = 0
    for p in products:
        reviews = crud.get_reviews_by_product(p["id"])
        if not reviews:
            continue
        pos = [r["content"] for r in reviews if r.get("rating") and r["rating"] >= 4 and r.get("content")][:5]
        neg = [r["content"] for r in reviews if r.get("rating") and r["rating"] <= 2 and r.get("content")][:5]
        if not pos and not neg:
            continue
        payload_items.append({
            "title": p["title"][:60],
            "rating": p.get("rating"),
            "positive_reviews": pos,
            "negative_reviews": neg,
        })
        total_reviews += len(pos) + len(neg)

    if not payload_items:
        await log_manager.broadcast("Sentiment", "⚠️ No reviews in DB yet. Run Scrape Data first.", "warning")
        return None

    await log_manager.broadcast(
        "Sentiment",
        f"📤 Sending {len(payload_items)} books ({total_reviews} reviews) to Claude...",
        "info"
    )

    try:
        prompt = SENTIMENT_ANALYSIS_PROMPT.format(
            exam_name=exam_name,
            data=json.dumps(payload_items, indent=2)
        )
        response = await client.messages.create(
            model=AI_MODEL, max_tokens=3000, temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.M)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.M)

        parsed = json.loads(raw)
        # Inject metadata
        parsed["exam_name"] = exam_name
        parsed["num_products"] = num_products
        parsed["books_with_reviews"] = len(payload_items)

        # Persist as market gaps so it survives page reload
        crud.upsert_market_gaps(
            exam_id=exam["id"],
            gap_data=parsed.get("market_gaps"),
            recommendations=[{"action": parsed.get("positioning_recommendation", ""), "expected_impact": ""}],
        )

        await log_manager.broadcast("Sentiment", f"✅ Sentiment analysis complete!", "success")
        return parsed

    except Exception as e:
        import traceback; traceback.print_exc()
        await log_manager.broadcast("Sentiment", f"❌ Sentiment error: {str(e)[:100]}", "error")
        return None
