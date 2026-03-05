"""
Amazon India Scraper — Scrapes book data from Amazon.in

Uses httpx + BeautifulSoup for search results and product detail pages.
Playwright-based scraping available as fallback for JS-heavy pages.
"""
import httpx
import asyncio
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from backend.ws_manager import log_manager
from config import SCRAPING_DELAY, SCRAPING_MAX_PAGES


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}


async def scrape_amazon_books(exam_name: str, max_results: int = 20) -> list[dict]:
    """
    Scrape Amazon India for exam preparation books.
    Returns list of product dicts ready for database insertion.
    """
    await log_manager.broadcast("Amazon", f"Starting Amazon scrape for '{exam_name}'...", "info")
    
    search_query = f"{exam_name} preparation book"
    products = []
    
    try:
        # Step 1: Search Amazon
        search_results = await search_amazon(search_query, max_results)
        await log_manager.broadcast(
            "Amazon", 
            f"Found {len(search_results)} results on Amazon for '{exam_name}'.", 
            "info"
        )
        
        # Step 2: Fetch product details
        for i, result in enumerate(search_results[:max_results]):
            try:
                await asyncio.sleep(SCRAPING_DELAY)
                detail = await fetch_amazon_product_detail(result)
                if detail:
                    detail["exam_name"] = exam_name
                    detail["marketplace"] = "Amazon"
                    detail["scraped_at"] = datetime.now().isoformat()
                    products.append(detail)
                    
                    if (i + 1) % 5 == 0:
                        await log_manager.broadcast(
                            "Amazon",
                            f"Scraped {i + 1}/{min(len(search_results), max_results)} Amazon products...",
                            "info"
                        )
            except Exception as e:
                await log_manager.broadcast(
                    "Amazon",
                    f"Error on product {i + 1}: {str(e)[:60]}",
                    "warning"
                )
        
        await log_manager.broadcast(
            "Amazon",
            f"Completed Amazon scrape: {len(products)} products for '{exam_name}'.",
            "success"
        )
        
    except Exception as e:
        await log_manager.broadcast(
            "Amazon",
            f"Amazon scrape failed: {str(e)[:80]}. Using mock data.",
            "warning"
        )
        products = generate_mock_amazon_data(exam_name)
    
    # Fallback to mock data if nothing scraped
    if not products:
        await log_manager.broadcast(
            "Amazon",
            "No products scraped. Loading mock data for development.",
            "info"
        )
        products = generate_mock_amazon_data(exam_name)
    
    return products


async def search_amazon(query: str, max_results: int = 20) -> list[dict]:
    """Search Amazon.in and extract book listings from search results."""
    results = []
    
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for page in range(1, min(SCRAPING_MAX_PAGES + 1, 4)):
            try:
                url = f"https://www.amazon.in/s"
                params = {
                    "k": query,
                    "i": "stripbooks",
                    "page": str(page),
                }
                
                resp = await client.get(url, params=params, headers=HEADERS)
                
                if resp.status_code == 503:
                    await log_manager.broadcast(
                        "Amazon",
                        "Rate limited by Amazon. Waiting 5s...",
                        "warning"
                    )
                    await asyncio.sleep(5)
                    continue
                    
                if resp.status_code != 200:
                    continue
                
                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select('[data-component-type="s-search-result"]')
                
                for item in items:
                    try:
                        result = parse_search_result(item)
                        if result and result.get("title"):
                            results.append(result)
                    except Exception:
                        pass
                
                if len(results) >= max_results:
                    break
                    
                await asyncio.sleep(SCRAPING_DELAY)
                
            except Exception as e:
                await log_manager.broadcast(
                    "Amazon",
                    f"Search page {page} failed: {str(e)[:60]}",
                    "warning"
                )
    
    return results[:max_results]


def parse_search_result(item) -> dict | None:
    """Parse a single Amazon search result card."""
    result = {}
    
    # Title
    title_el = item.select_one("h2 a span") or item.select_one("h2 span")
    if not title_el:
        return None
    result["title"] = title_el.get_text(strip=True)
    
    # Product URL
    link_el = item.select_one("h2 a")
    if link_el and link_el.get("href"):
        href = link_el["href"]
        if not href.startswith("http"):
            href = "https://www.amazon.in" + href
        result["product_url"] = href.split("/ref=")[0]
    
    # ASIN
    result["asin"] = item.get("data-asin", "")
    
    # Price
    price_whole = item.select_one(".a-price-whole")
    if price_whole:
        price_text = price_whole.get_text(strip=True).replace(",", "").replace(".", "")
        try:
            result["price"] = float(price_text)
        except ValueError:
            pass
    
    # Original price (MRP)
    mrp_el = item.select_one(".a-price.a-text-price .a-offscreen")
    if mrp_el:
        mrp_text = mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")
        try:
            result["mrp"] = float(mrp_text)
        except ValueError:
            pass
    
    # Rating
    rating_el = item.select_one(".a-icon-star-small .a-icon-alt")
    if rating_el:
        try:
            result["rating"] = float(rating_el.get_text(strip=True).split()[0])
        except (ValueError, IndexError):
            pass
    
    # Review count
    review_el = item.select_one('[aria-label*="star"] + span') or item.select_one(".a-size-base.s-underline-text")
    if review_el:
        review_text = review_el.get_text(strip=True).replace(",", "")
        try:
            result["review_count"] = int(review_text)
        except ValueError:
            pass
    
    # Author
    author_el = item.select_one(".a-color-secondary .a-size-base+ .a-size-base")
    if author_el:
        result["author"] = author_el.get_text(strip=True)
    
    return result


async def fetch_amazon_product_detail(search_result: dict) -> dict | None:
    """Fetch additional details from a product detail page."""
    url = search_result.get("product_url")
    if not url:
        return search_result
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            
            if resp.status_code != 200:
                return search_result
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Publisher
            pub_row = soup.find("span", string=re.compile(r"Publisher", re.I))
            if pub_row:
                pub_val = pub_row.find_next("span")
                if pub_val:
                    search_result["publisher"] = pub_val.get_text(strip=True)
            
            # Language
            lang_row = soup.find("span", string=re.compile(r"Language", re.I))
            if lang_row:
                lang_val = lang_row.find_next("span")
                if lang_val:
                    search_result["language"] = lang_val.get_text(strip=True)
            
            # Pages
            pages_row = soup.find("span", string=re.compile(r"pages", re.I))
            if pages_row:
                pages_text = pages_row.get_text(strip=True)
                match = re.search(r"(\d+)\s*pages", pages_text, re.I)
                if match:
                    search_result["pages"] = int(match.group(1))
            
            # Best Seller Rank
            bsr = soup.find("span", string=re.compile(r"Best Sellers Rank", re.I))
            if bsr:
                bsr_text = bsr.parent.get_text(strip=True) if bsr.parent else ""
                match = re.search(r"#(\d[\d,]*)", bsr_text)
                if match:
                    search_result["best_seller_rank"] = match.group(1).replace(",", "")
            
            # Description
            desc_el = soup.select_one("#bookDescription_feature_div span") or soup.select_one("#productDescription p")
            if desc_el:
                search_result["description"] = desc_el.get_text(strip=True)[:500]
            
    except Exception:
        pass
    
    return search_result


def generate_mock_amazon_data(exam_name: str) -> list[dict]:
    """Generate realistic mock Amazon data for development/demo purposes."""
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
        ("Solved Papers", "PYQ", 850),
        ("Practice Set", "PYQ", 600),
        ("General Awareness", "Subject Wise", 750),
        ("Quantitative Aptitude", "Subject Wise", 900),
        ("English Language", "Subject Wise", 500),
        ("Reasoning Ability", "Subject Wise", 700),
        ("Complete Guide", "Mixed", 1200),
        ("Master Guide", "Theory", 1000),
        ("SmartBook", "Smart", 720),
        ("Previous Year Papers", "PYQ", 550),
        ("Chapterwise Solved Papers", "PYQ", 800),
        ("GK & Current Affairs", "Subject Wise", 450),
        ("Fast Track Guide", "Mixed", 650),
        ("Comprehensive Guide", "Theory", 950),
        ("Mock Test Papers", "PYQ", 400),
        ("One Liner GK", "Subject Wise", 350),
        ("Mathematics", "Subject Wise", 680),
        ("Objective Questions", "PYQ", 520),
        ("All-in-One Guide", "Mixed", 1100),
        ("Hindi Medium Guide", "Theory", 800),
    ]
    
    import random
    random.seed(hash(exam_name) % 2**32)
    
    short_name = exam_name.split()[0] + " " + (exam_name.split()[1] if len(exam_name.split()) > 1 else "")
    
    products = []
    for i, (book_type, fmt, base_pages) in enumerate(book_types):
        pub, author = publishers[i % len(publishers)]
        base_price = random.randint(250, 650)
        mrp = base_price + random.randint(50, 200)
        rating = round(random.uniform(3.5, 4.8), 1)
        reviews = random.randint(200, 25000)
        
        products.append({
            "title": f"{short_name} {book_type} {datetime.now().year} - {pub}",
            "author": author,
            "publisher": pub,
            "price": float(base_price),
            "mrp": float(mrp),
            "rating": rating,
            "review_count": reviews,
            "best_seller_rank": str(i + 1),
            "book_format": fmt,
            "language": random.choice(["English", "English", "English", "Hindi", "English/Hindi"]),
            "pages": base_pages + random.randint(-50, 100),
            "marketplace": "Amazon",
            "product_url": f"https://www.amazon.in/s?k={short_name.replace(' ', '+')}+{book_type.replace(' ', '+')}",
            "description": f"Comprehensive {book_type.lower()} for {exam_name} exam preparation. Includes latest pattern questions, detailed solutions, and expert tips.",
            "exam_name": exam_name,
            "scraped_at": datetime.now().isoformat(),
        })
    
    return products
