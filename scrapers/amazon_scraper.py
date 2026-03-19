"""
Amazon India Scraper — Full rewrite with:
- Inline review extraction (5 positive + 5 negative per book, during detail page fetch)
- Robust BSR extraction with multiple fallbacks
- Language/pages trimming improvements
- Bot-challenge detection
- Scrapes up to 200 books across multiple pages
"""
import httpx
import asyncio
import re
import random
from datetime import datetime
from bs4 import BeautifulSoup
from backend.ws_manager import log_manager
from config import SCRAPING_DELAY

MAX_BOOKS = 100
REVIEWS_PER_SENTIMENT = 5   # 5 positive + 5 negative per product

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
}


def _is_bot_challenge(html: str) -> bool:
    markers = ["Enter the characters you see", "Robot Check", "automated access", "api-services-support@amazon"]
    lhtml = html.lower()
    return any(m.lower() in lhtml for m in markers)


# ─── Main Entry ──────────────────────────────────────────────────────────────

async def scrape_amazon_books(exam_name: str, max_results: int = MAX_BOOKS) -> list[dict]:
    await log_manager.broadcast("Amazon", f"🔍 Searching Amazon.in for '{exam_name}' books (target: {max_results})...", "info")

    search_query = f"{exam_name} preparation book"
    stubs = await search_amazon(search_query, max_results)
    await log_manager.broadcast("Amazon", f"📄 Found {len(stubs)} search results. Fetching details...", "info")

    if not stubs:
        await log_manager.broadcast("Amazon", "No results — using mock data.", "warning")
        return generate_mock_amazon_data(exam_name, min(max_results, 20))

    products = []
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        for i, stub in enumerate(stubs):
            try:
                await asyncio.sleep(SCRAPING_DELAY + random.uniform(0.5, 1.2))
                detail = await fetch_product_detail(client, stub)
                detail["exam_name"] = exam_name
                detail["marketplace"] = "Amazon"
                detail["scraped_at"] = datetime.now().isoformat()
                products.append(detail)

                if (i + 1) % 10 == 0 or (i + 1) == len(stubs):
                    await log_manager.broadcast(
                        "Amazon",
                        f"📦 Scraped {i + 1}/{len(stubs)} books...",
                        "info"
                    )
            except Exception as e:
                await log_manager.broadcast("Amazon", f"⚠️ Book {i+1} error: {str(e)[:60]}", "warning")

    await log_manager.broadcast("Amazon", f"✅ {len(products)} products collected.", "success")
    return products


# ─── Search ──────────────────────────────────────────────────────────────────

async def search_amazon(query: str, max_results: int) -> list[dict]:
    results = []
    pages_needed = min(14, (max_results // 15) + 2)

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for page in range(1, pages_needed + 1):
            if len(results) >= max_results:
                break
            try:
                resp = await client.get(
                    "https://www.amazon.in/s",
                    params={"k": query, "i": "stripbooks", "page": str(page)},
                    headers=HEADERS,
                )
                if resp.status_code == 503:
                    await asyncio.sleep(8)
                    continue
                if resp.status_code != 200:
                    continue
                if _is_bot_challenge(resp.text):
                    await log_manager.broadcast("Amazon", f"⚠️ Bot challenge on page {page}.", "warning")
                    await asyncio.sleep(10)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select('[data-component-type="s-search-result"]')
                for item in items:
                    stub = _parse_stub(item)
                    if stub:
                        results.append(stub)
                    if len(results) >= max_results:
                        break

                await asyncio.sleep(SCRAPING_DELAY)
            except Exception as e:
                await log_manager.broadcast("Amazon", f"Search page {page} failed: {str(e)[:50]}", "warning")

    return results[:max_results]


def _parse_stub(item) -> dict | None:
    title_el = item.select_one("h2 a span") or item.select_one("h2 span")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    if not title:
        return None

    asin = item.get("data-asin", "")
    link_el = item.select_one("h2 a")
    product_url = f"https://www.amazon.in/dp/{asin}" if asin else ""
    if not product_url and link_el and link_el.get("href"):
        href = link_el["href"]
        if not href.startswith("http"):
            href = "https://www.amazon.in" + href
        product_url = href.split("/ref=")[0]

    price = None
    price_el = item.select_one(".a-price-whole")
    if price_el:
        try:
            price = float(re.sub(r"[^\d.]", "", price_el.get_text(strip=True)))
        except ValueError:
            pass

    mrp = None
    mrp_el = item.select_one(".a-price.a-text-price .a-offscreen")
    if mrp_el:
        try:
            mrp = float(re.sub(r"[^\d.]", "", mrp_el.get_text(strip=True)))
        except ValueError:
            pass

    rating = None
    for sel in [".a-icon-star-small .a-icon-alt", ".a-icon-star .a-icon-alt"]:
        r_el = item.select_one(sel)
        if r_el:
            m = re.search(r"(\d[\d.]+)", r_el.get_text())
            if m:
                try:
                    rating = float(m.group(1))
                except ValueError:
                    pass
            break

    review_count = 0
    rev_el = item.select_one('[aria-label*=" ratings"]') or item.select_one(".a-size-base.s-underline-text")
    if rev_el:
        m = re.search(r"([\d,]+)", rev_el.get_text())
        if m:
            try:
                review_count = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

    return {"asin": asin, "title": title, "product_url": product_url,
            "price": price, "mrp": mrp, "rating": rating, "review_count": review_count}


# ─── Product Detail + Inline Reviews ─────────────────────────────────────────

async def fetch_product_detail(client: httpx.AsyncClient, stub: dict) -> dict:
    result = dict(stub)

    url = stub.get("product_url") or (
        f"https://www.amazon.in/dp/{stub['asin']}" if stub.get("asin") else None
    )
    if not url:
        return result

    try:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200 or _is_bot_challenge(resp.text):
            return result

        soup = BeautifulSoup(resp.text, "html.parser")

        # ── Title ─────────────────────────────────────────────────────────────
        t = soup.select_one("#productTitle") or soup.select_one("#title")
        if t:
            result["title"] = t.get_text(strip=True)

        # ── ASIN ──────────────────────────────────────────────────────────────
        if not result.get("asin"):
            inp = soup.find("input", {"id": "ASIN"})
            if inp:
                result["asin"] = inp.get("value", "")

        # ── Rating ────────────────────────────────────────────────────────────
        if not result.get("rating"):
            for sel in [
                "#acrPopover .a-icon-alt",
                "span[data-hook='rating-out-of-text']",
                ".a-icon-star .a-icon-alt",
            ]:
                el = soup.select_one(sel)
                if el:
                    m = re.search(r"(\d[\d.]+)", el.get_text())
                    if m:
                        try:
                            result["rating"] = float(m.group(1))
                            break
                        except ValueError:
                            pass

        # ── Review count ──────────────────────────────────────────────────────
        if not result.get("review_count"):
            for sel in ["#acrCustomerReviewText", "span[data-hook='total-review-count']"]:
                el = soup.select_one(sel)
                if el:
                    m = re.search(r"([\d,]+)", el.get_text())
                    if m:
                        try:
                            result["review_count"] = int(m.group(1).replace(",", ""))
                        except ValueError:
                            pass
                    break

        # ── Price ─────────────────────────────────────────────────────────────
        if not result.get("price"):
            for sel in [".a-price .a-offscreen", "#kindle-price", "#price"]:
                el = soup.select_one(sel)
                if el:
                    try:
                        result["price"] = float(re.sub(r"[^\d.]", "", el.get_text(strip=True)))
                        break
                    except ValueError:
                        pass

        # ── BSR ───────────────────────────────────────────────────────────────
        bsr = _extract_bsr(soup)
        if bsr:
            result["amazon_rank"] = bsr["display"]
            result["best_seller_rank"] = bsr["num"]

        # ── Detail bullets (pages, language, publisher, isbn) ─────────────────
        _parse_detail_bullets(soup, result)

        # ── Author ────────────────────────────────────────────────────────────
        if not result.get("author"):
            for sel in [".author a", "#bylineInfo .author a", ".contributorNameID"]:
                els = soup.select(sel)
                if els:
                    result["author"] = ", ".join(e.get_text(strip=True) for e in els[:2])
                    break

        # ── Format type ───────────────────────────────────────────────────────
        if not result.get("book_format"):
            title_lower = result.get("title", "").lower()
            if any(k in title_lower for k in ["previous year", "solved paper", "pyq", "past year", "question bank"]):
                result["book_format"] = "PYQ"
            elif any(k in title_lower for k in ["guide", "complete guide", "study material", "theory", "objective"]):
                result["book_format"] = "Theory"
            else:
                result["book_format"] = "Mixed"

        # ── Description ───────────────────────────────────────────────────────
        for sel in ["#bookDescription_feature_div span", "#productDescription p"]:
            el = soup.select_one(sel)
            if el:
                result["description"] = el.get_text(strip=True)[:600]
                break

        # ── Bestseller badge ──────────────────────────────────────────────────
        badges = soup.select(".a-badge-text, #acBadge_feature_div")
        if any("best seller" in b.get_text(strip=True).lower() for b in badges):
            result["is_bestseller"] = 1

        # ── Inline Reviews (5 positive + 5 negative) ──────────────────────────
        reviews = _extract_inline_reviews(soup)
        result["_inline_reviews"] = reviews

    except Exception as e:
        await log_manager.broadcast("Amazon", f"Detail error {url[:45]}: {str(e)[:60]}", "warning")

    return result


def _extract_bsr(soup: BeautifulSoup) -> dict | None:
    """
    Try multiple BSR extraction strategies.
    Returns {"num": "12345", "display": "#12,345 in Books > Exam Prep"} or None.
    """
    # Strategy 1: Find the BSR label and walk up to its container
    for tag_type in ["span", "td", "th", "li"]:
        label = soup.find(tag_type, string=re.compile(r"Best Sellers Rank", re.I))
        if label:
            container = label.find_parent(["li", "tr", "div", "ul"]) or label.parent
            if container:
                text = container.get_text(" ", strip=True)
                m = re.search(r"#([\d,]+)\s+in\s+([^(#\n,]+)", text)
                if m:
                    return {"num": m.group(1).replace(",", ""), "display": f"#{m.group(1)} in {m.group(2).strip()}"}

    # Strategy 2: scan the entire detail bullets section for BSR pattern
    for section_id in ["#detailBullets_feature_div", "#productDetails_db_sections", "#centerCol"]:
        section = soup.select_one(section_id)
        if section:
            text = section.get_text(" ", strip=True)
            m = re.search(r"#([\d,]+)\s+in\s+([A-Za-z\s&>]+)", text)
            if m and int(m.group(1).replace(",", "")) < 5_000_000:
                return {"num": m.group(1).replace(",", ""), "display": f"#{m.group(1)} in {m.group(2).strip()}"}

    # Strategy 3: any element containing a pattern like "#1,234 in"
    m = re.search(r"#([\d,]+)\s+in\s+([A-Za-z\s&>]+)", soup.get_text(" ", strip=True))
    if m and int(m.group(1).replace(",", "")) < 5_000_000:
        return {"num": m.group(1).replace(",", ""), "display": f"#{m.group(1)} in {m.group(2).strip()}"}

    return None


def _clean_value(text: str) -> str:
    """Remove label prefixes and extraneous spans from a detail value."""
    # Strip known label prefixes
    text = re.sub(r"^[^:]+:\s*", "", text).strip()
    # Strip trailing parenthetical dates like "(1 January 2024)"
    text = re.sub(r"\s*\(\d.*\)$", "", text).strip()
    return text


def _parse_detail_bullets(soup: BeautifulSoup, result: dict):
    """Extract pages, language, publisher, isbn from the detail bullets area."""
    # Try both bullet format (li) and table format (tr)
    rows = (
        soup.select("#detailBullets_feature_div li .a-list-item")
        or soup.select("#detailBullets_feature_div li")
        or soup.select("#productDetails_techSpec_section_1 tr")
        or soup.select("#productDetails_detailBullets_sections1 tr")
    )

    for row in rows:
        # For table rows, split by th/td
        header_el = row.select_one("th") or row.select_one(".a-text-bold")
        value_el = row.select_one("td") or row

        label = (header_el.get_text(strip=True) if header_el else row.get_text(" ", strip=True)).lower()
        value_raw = value_el.get_text(strip=True) if value_el else ""

        # Clean out the label part from value
        value = value_raw
        if ":" in value:
            value = value.split(":", 1)[-1].strip()

        if not value or value.lower() in ("—", "-", "n/a"):
            continue

        if "publisher" in label and not result.get("publisher"):
            result["publisher"] = re.sub(r"\s*\(.*?\)\s*$", "", value).strip()

        elif "language" in label and not result.get("language"):
            # Keep only the first language word / short phrase
            lang = re.sub(r"[^A-Za-z/,\s]", "", value).strip()
            result["language"] = lang[:30]

        elif "pages" in label and not result.get("pages"):
            m = re.search(r"([\d,]+)", value)
            if m:
                try:
                    result["pages"] = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        elif ("isbn-13" in label or "isbn13" in label) and not result.get("isbn"):
            m = re.search(r"[\d]{9,13}", value.replace("-", "").replace(" ", ""))
            if m:
                result["isbn"] = m.group(0)

    # Fallback: scan the full page text for language if still missing
    if not result.get("language"):
        page_text = soup.get_text(" ", strip=True)
        m = re.search(r"Language\s*[:\u2013]\s*([A-Za-z][A-Za-z /,]{1,25})", page_text, re.I)
        if m:
            lang = m.group(1).strip()
            if len(lang) < 30:
                result["language"] = lang


def _extract_inline_reviews(soup: BeautifulSoup) -> list[dict]:
    """
    Extract reviews embedded directly on the product detail page.
    Classify into positive (≥4★) and negative (≤2★).
    Cap: 5 positive + 5 negative.
    """
    all_reviews = []
    for rev_el in soup.select("[data-hook='review']"):
        r = _parse_review_el(rev_el)
        if r:
            all_reviews.append(r)

    positive = [r for r in all_reviews if r.get("rating") and r["rating"] >= 4]
    negative = [r for r in all_reviews if r.get("rating") and r["rating"] <= 2]
    neutral  = [r for r in all_reviews if r.get("rating") and 2 < r["rating"] < 4]

    result = (
        positive[:REVIEWS_PER_SENTIMENT]
        + negative[:REVIEWS_PER_SENTIMENT]
        + neutral[:max(0, 10 - len(positive[:REVIEWS_PER_SENTIMENT]) - len(negative[:REVIEWS_PER_SENTIMENT]))]
    )

    # If total < 10 return them all anyway
    if len(all_reviews) < 10:
        return all_reviews

    return result


def _parse_review_el(rev) -> dict | None:
    reviewer = rev.select_one("[data-hook='review-author']")
    rating_el = (
        rev.select_one("[data-hook='review-star-rating'] .a-icon-alt")
        or rev.select_one("[data-hook='cmps-review-star-rating'] .a-icon-alt")
        or rev.select_one(".a-icon-star .a-icon-alt")
    )
    title_el = rev.select_one("[data-hook='review-title'] span:not(.a-icon-alt)")
    body_el = rev.select_one("[data-hook='review-body'] span") or rev.select_one("[data-hook='review-body']")
    date_el = rev.select_one("[data-hook='review-date']")
    verified_el = rev.select_one("[data-hook='avp-badge']")
    helpful_el = rev.select_one("[data-hook='helpful-vote-statement']")

    content = body_el.get_text(strip=True) if body_el else None
    if not content:
        return None

    rating = None
    if rating_el:
        m = re.search(r"(\d[\d.]+)", rating_el.get_text())
        if m:
            try:
                rating = float(m.group(1))
            except ValueError:
                pass

    helpful_count = 0
    if helpful_el:
        m = re.search(r"(\d+)", helpful_el.get_text())
        if m:
            try:
                helpful_count = int(m.group(1))
            except ValueError:
                pass

    return {
        "reviewer_name": reviewer.get_text(strip=True) if reviewer else None,
        "rating": rating,
        "title": title_el.get_text(strip=True) if title_el else None,
        "content": content,
        "review_date": date_el.get_text(strip=True) if date_el else None,
        "verified_purchase": 1 if verified_el else 0,
        "helpful_count": helpful_count,
        "marketplace": "Amazon",
    }


# ─── Mock Data ────────────────────────────────────────────────────────────────

def generate_mock_amazon_data(exam_name: str, count: int = 20) -> list[dict]:
    publishers = [
        ("Kiran Prakashan", "Kiran Institute"),
        ("Arihant Publications", "Arihant Experts"),
        ("Lucent Publications", "Dr. Binay Karna"),
        ("Pinnacle Publications", "Pinnacle Team"),
        ("Disha Publications", "Disha Experts"),
        ("Rakesh Yadav Publications", "Rakesh Yadav"),
        ("S.Chand Publishing", "R.S. Aggarwal"),
        ("Paramount Publications", "Neetu Singh"),
        ("Adda247", "Adda247 Team"),
        ("Youth Competition Times", "Youth Competition Team"),
    ]
    book_types = [
        ("Solved Papers 2024", "PYQ", 850, "English"),
        ("Practice Set 2024", "PYQ", 600, "English"),
        ("General Awareness Guide", "Theory", 750, "English"),
        ("Quantitative Aptitude", "Theory", 900, "English"),
        ("English Grammar & Usage", "Theory", 500, "English"),
        ("Reasoning Ability", "Theory", 700, "English"),
        ("Complete Study Guide 2025", "Mixed", 1200, "English"),
        ("Master Guide Theory", "Theory", 1000, "Hindi"),
        ("SmartBook Series 2025", "Mixed", 720, "English"),
        ("Previous Year Papers 10 Sets", "PYQ", 550, "English/Hindi"),
        ("Chapterwise Solved Papers", "PYQ", 800, "English"),
        ("GK & Current Affairs 2025", "Theory", 450, "English"),
        ("Fast Track Revision Guide", "Mixed", 650, "Hindi"),
        ("Comprehensive Theory Book", "Theory", 950, "English"),
        ("Mock Test Papers 25 Sets", "PYQ", 400, "English"),
        ("One Liner GK Capsule", "Theory", 350, "English"),
        ("Maths Shortcuts & Tricks", "Theory", 680, "English"),
        ("Objective Questions Bank", "PYQ", 520, "English"),
        ("All-in-One Mega Guide", "Mixed", 1100, "English/Hindi"),
        ("Hindi Medium Complete Guide", "Theory", 800, "Hindi"),
    ]

    rng = random.Random(hash(exam_name) % 2**32)
    short_name = " ".join(exam_name.split()[:2])
    products = []

    for i in range(min(count, len(book_types))):
        bt, fmt, pages, lang = book_types[i % len(book_types)]
        pub, author = publishers[i % len(publishers)]
        price = float(rng.randint(249, 650))
        mrp = price + rng.randint(50, 250)
        rating = round(rng.uniform(3.5, 4.8), 1) if rng.random() > 0.1 else None
        reviews_count = rng.randint(200, 25000) if rating else 0
        rank = rng.randint(1, 5000)
        asin = f"B0{rng.randint(10000000, 99999999)}"

        products.append({
            "title": f"{short_name} {bt} - {pub}",
            "author": author,
            "publisher": pub,
            "price": price,
            "mrp": mrp,
            "rating": rating,
            "review_count": reviews_count,
            "best_seller_rank": str(rank),
            "amazon_rank": f"#{rank:,} in Books > Exam Preparation",
            "asin": asin,
            "book_format": fmt,
            "language": lang,
            "pages": pages + rng.randint(-50, 100),
            "marketplace": "Amazon",
            "product_url": f"https://www.amazon.in/dp/{asin}",
            "description": f"Comprehensive {bt.lower()} for {exam_name} exam. Includes latest questions and expert tips.",
            "exam_name": exam_name,
            "scraped_at": datetime.now().isoformat(),
            "_inline_reviews": [],
        })

    return products
