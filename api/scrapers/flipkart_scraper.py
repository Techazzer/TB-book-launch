"""
Flipkart Scraper — Scrapes book data from Flipkart.com

Uses httpx + BeautifulSoup for search results and product pages.
Flipkart has different HTML structure from Amazon.
"""
import httpx
import asyncio
import re
from datetime import datetime
from bs4 import BeautifulSoup
from ws_manager import log_manager
from config import SCRAPING_DELAY, SCRAPING_MAX_PAGES


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


async def scrape_flipkart_books(exam_name: str, max_results: int = 20) -> list[dict]:
    """
    Scrape Flipkart for exam preparation books.
    Returns list of product dicts ready for database insertion.
    """
    await log_manager.broadcast("Flipkart", f"Starting Flipkart scrape for '{exam_name}'...", "info")
    
    search_query = f"{exam_name} preparation book"
    products = []
    
    try:
        search_results = await search_flipkart(search_query, max_results)
        await log_manager.broadcast(
            "Flipkart",
            f"Found {len(search_results)} results on Flipkart for '{exam_name}'.",
            "info"
        )
        
        for i, result in enumerate(search_results[:max_results]):
            try:
                await asyncio.sleep(SCRAPING_DELAY)
                detail = await fetch_flipkart_detail(result)
                if detail:
                    detail["exam_name"] = exam_name
                    detail["marketplace"] = "Flipkart"
                    detail["scraped_at"] = datetime.now().isoformat()
                    products.append(detail)
                    
                    if (i + 1) % 5 == 0:
                        await log_manager.broadcast(
                            "Flipkart",
                            f"Scraped {i + 1}/{min(len(search_results), max_results)} Flipkart products...",
                            "info"
                        )
            except Exception as e:
                await log_manager.broadcast(
                    "Flipkart",
                    f"Error on product {i + 1}: {str(e)[:60]}",
                    "warning"
                )
        
        await log_manager.broadcast(
            "Flipkart",
            f"Completed Flipkart scrape: {len(products)} products for '{exam_name}'.",
            "success"
        )
        
    except Exception as e:
        await log_manager.broadcast(
            "Flipkart",
            f"Flipkart scrape failed: {str(e)[:80]}. Using mock data.",
            "warning"
        )
        products = generate_mock_flipkart_data(exam_name)
    
    if not products:
        await log_manager.broadcast(
            "Flipkart",
            "No products scraped. Loading mock data for development.",
            "info"
        )
        products = generate_mock_flipkart_data(exam_name)
    
    return products


async def search_flipkart(query: str, max_results: int = 20) -> list[dict]:
    """Search Flipkart and extract book listings."""
    results = []
    
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for page in range(1, min(SCRAPING_MAX_PAGES + 1, 4)):
            try:
                url = "https://www.flipkart.com/search"
                params = {
                    "q": query,
                    "otracker": "search",
                    "as-type": "HISTORY",
                    "page": str(page),
                }
                
                resp = await client.get(url, params=params, headers=HEADERS)
                
                if resp.status_code != 200:
                    await log_manager.broadcast(
                        "Flipkart",
                        f"Search page {page}: HTTP {resp.status_code}",
                        "warning"
                    )
                    continue
                
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Flipkart uses various class structures; try multiple selectors
                items = soup.select('[data-id]') or soup.select('._1AtVbE') or soup.select('._13oc-S')
                
                for item in items:
                    try:
                        result = parse_flipkart_result(item)
                        if result and result.get("title"):
                            results.append(result)
                    except Exception:
                        pass
                
                if len(results) >= max_results:
                    break
                
                await asyncio.sleep(SCRAPING_DELAY)
                
            except Exception as e:
                await log_manager.broadcast(
                    "Flipkart",
                    f"Search page {page} failed: {str(e)[:60]}",
                    "warning"
                )
    
    return results[:max_results]


def parse_flipkart_result(item) -> dict | None:
    """Parse a Flipkart search result card."""
    result = {}
    
    # Title - Flipkart uses various class names
    title_el = (
        item.select_one('a[class*="title"]') or 
        item.select_one('.IRpwTa') or 
        item.select_one('._4rR01T') or
        item.select_one('a[title]')
    )
    if title_el:
        result["title"] = title_el.get_text(strip=True) or title_el.get("title", "")
    
    if not result.get("title"):
        return None
    
    # Product URL
    link = item.select_one('a[href*="/p/"]') or item.select_one('a[class*="title"]')
    if link and link.get("href"):
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.flipkart.com" + href
        result["product_url"] = href.split("?")[0]
    
    # Price
    price_el = item.select_one('._30jeq3') or item.select_one('[class*="price"]')
    if price_el:
        price_text = price_el.get_text(strip=True).replace("₹", "").replace(",", "")
        try:
            result["price"] = float(price_text)
        except ValueError:
            pass
    
    # MRP
    mrp_el = item.select_one('._3I9_wc') or item.select_one('[class*="strike"]')
    if mrp_el:
        mrp_text = mrp_el.get_text(strip=True).replace("₹", "").replace(",", "")
        try:
            result["mrp"] = float(mrp_text)
        except ValueError:
            pass
    
    # Rating
    rating_el = item.select_one('._3LWZlK') or item.select_one('[class*="rating"]')
    if rating_el:
        try:
            result["rating"] = float(rating_el.get_text(strip=True))
        except ValueError:
            pass
    
    # Review count
    review_el = item.select_one('span._2_R_DZ span') or item.select_one('[class*="review"]')
    if review_el:
        review_text = review_el.get_text(strip=True)
        match = re.search(r'([\d,]+)\s*(?:Rating|Review)', review_text, re.I)
        if match:
            try:
                result["review_count"] = int(match.group(1).replace(",", ""))
            except ValueError:
                pass
    
    return result


async def fetch_flipkart_detail(search_result: dict) -> dict | None:
    """Fetch additional details from Flipkart product page."""
    url = search_result.get("product_url")
    if not url:
        return search_result
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            
            if resp.status_code != 200:
                return search_result
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Try to extract publisher, author, pages from spec table
            spec_rows = soup.select('tr._1s_Smc') or soup.select('._14cfVK tr')
            for row in spec_rows:
                cols = row.select("td")
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True).lower()
                    val = cols[1].get_text(strip=True)
                    
                    if "publisher" in key:
                        search_result["publisher"] = val
                    elif "author" in key:
                        search_result["author"] = val
                    elif "page" in key:
                        try:
                            search_result["pages"] = int(re.search(r'\d+', val).group())
                        except (AttributeError, ValueError):
                            pass
                    elif "language" in key:
                        search_result["language"] = val
            
            # Description
            desc_el = soup.select_one('._1mXcCf') or soup.select_one('[class*="description"]')
            if desc_el:
                search_result["description"] = desc_el.get_text(strip=True)[:500]
    
    except Exception:
        pass
    
    return search_result


def generate_mock_flipkart_data(exam_name: str) -> list[dict]:
    """Generate realistic mock Flipkart data for development/demo."""
    publishers = [
        ("Arihant Publications", "Arihant Experts"),
        ("Kiran Prakashan", "Think Tank of Kiran"),
        ("Disha Publications", "Disha Experts"),
        ("McGraw Hill Education", "TMH Experts"),
        ("Lucent Publications", "Lucent Team"),
        ("Upkar Publications", "Dr. Lal & Singh"),
        ("S.Chand Publishing", "R.S. Aggarwal"),
        ("GK Publications", "GK Team"),
        ("Testbook", "Testbook Team"),
        ("Oswaal Books", "Oswaal Editorial Board"),
    ]
    
    book_types = [
        ("Complete Guide", "Mixed", 1100),
        ("Previous Year Solved Papers", "PYQ", 750),
        ("Practice Papers", "PYQ", 550),
        ("Master Guide", "Theory", 950),
        ("Chapterwise Solutions", "PYQ", 680),
        ("Objective Questions Bank", "PYQ", 600),
        ("General Knowledge", "Subject Wise", 400),
        ("English & Hindi Medium", "Mixed", 850),
        ("SmartBook", "Smart", 720),
        ("Quick Revision", "Theory", 350),
        ("Topic-wise Practice", "PYQ", 500),
        ("Comprehensive Study Material", "Theory", 1200),
        ("Current Affairs Yearly", "Subject Wise", 450),
        ("Reasoning & Aptitude", "Subject Wise", 700),
        ("All Subjects Combined", "Mixed", 900),
    ]
    
    import random
    random.seed((hash(exam_name) + 7) % 2**32)
    
    short_name = exam_name.split()[0] + " " + (exam_name.split()[1] if len(exam_name.split()) > 1 else "")
    
    products = []
    for i, (book_type, fmt, base_pages) in enumerate(book_types):
        pub, author = publishers[i % len(publishers)]
        base_price = random.randint(230, 600)
        mrp = base_price + random.randint(80, 250)
        rating = round(random.uniform(3.3, 4.7), 1)
        reviews = random.randint(100, 15000)
        
        products.append({
            "title": f"{short_name} {book_type} {datetime.now().year} | {pub}",
            "author": author,
            "publisher": pub,
            "price": float(base_price),
            "mrp": float(mrp),
            "rating": rating,
            "review_count": reviews,
            "book_format": fmt,
            "language": random.choice(["English", "English", "Hindi", "English/Hindi"]),
            "pages": base_pages + random.randint(-30, 80),
            "marketplace": "Flipkart",
            "product_url": f"https://www.flipkart.com/search?q={short_name.replace(' ', '+')}+{book_type.replace(' ', '+')}",
            "description": f"Comprehensive {book_type.lower()} for {exam_name}. Updated for latest exam pattern with solved examples and practice sets.",
            "exam_name": exam_name,
            "scraped_at": datetime.now().isoformat(),
        })
    
    return products
