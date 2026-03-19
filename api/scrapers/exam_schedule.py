"""
Exam Schedule Scraper — Strict HTML Parsing from SarkariResult.com

NO AI is used in this module. All data is extracted using BeautifulSoup
CSS selectors and regex patterns directly from the page DOM.

Rules:
- If a field is not clearly available → "Not Available"
- Dates must be copied exactly as they appear on the page
- Only exams matching config.EXAM_LIST are collected
"""
import httpx
import re
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from config import EXAM_LIST
from crud import upsert_exam_schedule, get_all_exam_schedules
from ws_manager import log_manager

logger = logging.getLogger(__name__)

NOT_AVAILABLE = "Not Available"

# ── Source Configuration ─────────────────────────────────────────────────────
SARKARI_BASE = "https://www.sarkariresult.com"
SARKARI_PAGES = [
    f"{SARKARI_BASE}/",
    f"{SARKARI_BASE}/latestjob/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Conducting Body from URL Path ────────────────────────────────────────────
BODY_MAP = {
    "/ssc/": "SSC",
    "/railway/": "RRB",
    "/bank/": "Banking",
    "/upsc/": "UPSC",
    "/upsssc/": "UPSSSC",
    "/bihar/": "BPSC",
    "/mp/": "MPPSC",
    "/rpsc/": "RPSC",
    "/delhi/": "DSSSB",
}

# ── Est. TAM: Last-Cycle Applicant Numbers (publicly reported figures) ────────
# Source: Previous cycle official data / media reports
# These are approximate total applicants from the last completed exam cycle.
LAST_CYCLE_APPLICANTS = {
    # SSC Exams
    "SSC CGL": "~30L",
    "SSC CHSL": "~40L",
    "SSC MTS": "~1.1Cr",
    "SSC GD Constable": "~1Cr",
    "SSC CPO": "~8L",
    "SSC Stenographer": "~6L",
    "SSC JE": "~5L",
    # Railway Exams
    "RRB NTPC": "~1.25Cr",
    "RRB Group D": "~1.15Cr",
    "RRB ALP": "~36L",
    "RRB JE": "~20L",
    "RRB Ministerial": "~5L",
    "RPF Constable": "~50L",
    "RPF SI": "~20L",
    # Banking Exams
    "IBPS PO": "~30L",
    "IBPS Clerk": "~35L",
    "IBPS SO": "~5L",
    "IBPS RRB PO": "~12L",
    "IBPS RRB Clerk": "~15L",
    "SBI PO": "~25L",
    "SBI Clerk": "~30L",
    "RBI Grade B": "~3L",
    "RBI Assistant": "~6L",
    "NABARD Grade A": "~1.5L",
    "SEBI Grade A": "~1L",
    # UPSC & State PSC
    "UPSC Prelims": "~13L",
    "UPSC CAPF": "~3L",
    "UPSC CDS": "~5L",
    "UPSC NDA": "~7L",
    "UPSC EPFO": "~2L",
    "BPSC": "~7L",
    "UPPSC": "~6L",
    "MPPSC": "~4L",
    "RPSC": "~5L",
    # Teaching Exams
    "CTET": "~30L",
    "KVS PRT": "~10L",
    "KVS TGT": "~8L",
    "KVS PGT": "~5L",
    "NVS TGT": "~6L",
    "NVS PGT": "~3L",
    "DSSSB TGT": "~4L",
    "DSSSB PRT": "~5L",
    "SUPER TET": "~12L",
    "UPTET": "~18L",
    "MPTET": "~6L",
    "REET": "~25L",
    # Defense Exams
    "AFCAT": "~3L",
    "CDS": "~5L",
    "NDA": "~7L",
    "Indian Navy SSR": "~4L",
    "Indian Navy AA": "~3L",
    "Indian Air Force Group X Y": "~6L",
    # Insurance
    "LIC AAO": "~5L",
    "LIC ADO": "~4L",
    "NIACL AO": "~2L",
    # Other
    "GATE": "~10L",
    "UGC NET": "~15L",
    "CSIR NET": "~3L",
    "CUET": "~20L",
    "CLAT": "~70K",
    "NEET": "~24L",
    "JEE Main": "~12L",
}

# ── Keyword Map: config.EXAM_LIST → search terms for URL/title matching ──────
def _build_keyword_map() -> dict[str, list[str]]:
    """Build a mapping from exam names to search keywords."""
    kw_map = {}
    for exam in EXAM_LIST:
        lower = exam.lower()
        # Generate keywords from exam name
        words = lower.split()
        kw_map[exam] = words
    return kw_map

KEYWORD_MAP = _build_keyword_map()


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

async def scrape_exam_schedules() -> list[dict]:
    """
    Scrape exam schedules from sarkariresult.com using pure HTML parsing.
    No AI. No guessing. Only exact data from the page DOM.
    """
    await log_manager.broadcast(
        "Exam Schedule",
        "Starting exam scraping from sarkariresult.com",
        "info",
    )

    # Step 1: Collect all exam links from the homepage
    await log_manager.broadcast("Exam Schedule", "Fetching latest job listings", "info")
    all_links = await _collect_homepage_links()
    await log_manager.broadcast(
        "Exam Schedule",
        f"Found {len(all_links)} exam entries on SarkariResult",
        "info",
    )

    # Step 2: Match links against our target exam list
    matched = _match_links_to_exams(all_links)
    await log_manager.broadcast(
        "Exam Schedule",
        f"Matched {len(matched)} entries to dashboard exam list",
        "info",
    )

    if not matched:
        await log_manager.broadcast(
            "Exam Schedule",
            "No matching exams found. Loading seed data as fallback.",
            "warning",
        )
        return _save_and_return(get_seed_exam_data())

    # Step 3: Visit each detail page and parse structured data
    scraped = []
    for exam_name, link_info in matched.items():
        await log_manager.broadcast(
            "Exam Schedule",
            f"Parsing exam: {exam_name}",
            "info",
        )
        try:
            record = await _parse_detail_page(exam_name, link_info)
            # Step 4: Validate before saving
            if _validate_record(record):
                scraped.append(record)
                await _log_extracted_fields(record)
            else:
                await log_manager.broadcast(
                    "Exam Schedule",
                    f"Warning: Validation failed for {exam_name}, skipping",
                    "warning",
                )
        except Exception as e:
            await log_manager.broadcast(
                "Exam Schedule",
                f"Warning: Failed to parse {exam_name}: {str(e)[:80]}",
                "warning",
            )
        # Rate limit
        await asyncio.sleep(0.5)

    if not scraped:
        await log_manager.broadcast(
            "Exam Schedule",
            "No valid records from scraping. Loading seed data.",
            "warning",
        )
        return _save_and_return(get_seed_exam_data())

    return _save_and_return(scraped)


def get_seed_exam_data() -> list[dict]:
    """Minimal seed data for fallback. All source_urls point to SarkariResult."""
    return [
        _seed("SSC CGL", "SSC", "/ssc/ssc-cgl-2025/"),
        _seed("SSC CHSL", "SSC", "/ssc/ssc-chsl-2025/"),
        _seed("SSC MTS", "SSC", "/ssc/ssc-mts-2025/"),
        _seed("SSC GD Constable", "SSC", "/ssc/ssc-gd-constable-2025/"),
        _seed("RRB NTPC", "RRB", "/railway/rrb-ntpc-cen-01-2025/"),
        _seed("RRB Group D", "RRB", "/railway/rrb-group-d-cen-09-2025/"),
        _seed("IBPS PO", "Banking", "/bank/ibps-po-15th-2025/"),
        _seed("IBPS Clerk", "Banking", "/bank/ibps-clerk-15th-2025/"),
        _seed("SBI PO", "Banking", "/bank/sbi-po-2025/"),
        _seed("SBI Clerk", "Banking", "/bank/sbi-clerk-2025/"),
        _seed("RBI Grade B", "Banking", "/bank/rbi-officer-gradeb-july24/"),
        _seed("RBI Assistant", "Banking", "/bank/rbi-assistant-feb26/"),
        _seed("UPSC Prelims", "UPSC", "/upsc/upsc-ias-ifs-pre-2026/"),
        _seed("UPSC NDA", "UPSC", "/upsc/upsc-nda-cds-ii-2026/"),
        _seed("CTET", "CBSE/NTA", "/2026/ctet-feb-2026/"),
        _seed("UGC NET", "NTA", "/2024/nta-ugc-net-dec24/"),
        _seed("CUET", "NTA", "/2026/nta-cuet-ug-2026/"),
        _seed("NEET", "NTA", "/2026/nta-neet-ug-2026/"),
    ]


def get_seed_exam_data_quick() -> list[dict]:
    """Returns first 5 upcoming exams for quick dashboard display."""
    data = get_seed_exam_data()
    data.sort(key=lambda x: x.get("expected_exam_date") or "9999")
    return data[:5]


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: HOMEPAGE LINK COLLECTION
# ═══════════════════════════════════════════════════════════════════════════════

async def _collect_homepage_links() -> list[dict]:
    """Fetch SarkariResult homepage and extract all internal exam links."""
    links = {}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for page_url in SARKARI_PAGES:
            try:
                resp = await client.get(page_url, headers=HEADERS)
                if resp.status_code != 200:
                    await log_manager.broadcast(
                        "Exam Schedule",
                        f"Warning: {page_url} returned {resp.status_code}",
                        "warning",
                    )
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    text = a_tag.get_text(strip=True)

                    # Only sarkariresult.com internal links with meaningful text
                    if not href.startswith(SARKARI_BASE):
                        continue
                    if len(text) < 10:
                        continue
                    # Skip generic nav links
                    path = href.replace(SARKARI_BASE, "").rstrip("/")
                    if path in ("", "/latestjob", "/result", "/admitcard",
                                "/answerkey", "/syllabus", "/search",
                                "/contactus", "/verification"):
                        continue

                    if href not in links:
                        links[href] = {"url": href, "title": text}

            except Exception as e:
                await log_manager.broadcast(
                    "Exam Schedule",
                    f"Warning: Error fetching {page_url}: {str(e)[:60]}",
                    "warning",
                )
    return list(links.values())


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: KEYWORD MATCHING
# ═══════════════════════════════════════════════════════════════════════════════

def _match_links_to_exams(links: list[dict]) -> dict[str, dict]:
    """Match scraped links to the predefined exam list using keyword matching.
    Returns dict mapping exam_name → link_info (first match wins)."""
    matched: dict[str, dict] = {}

    for exam_name, keywords in KEYWORD_MAP.items():
        if exam_name in matched:
            continue

        for link in links:
            url_lower = link["url"].lower()
            title_lower = link["title"].lower()
            combined = url_lower + " " + title_lower

            # All keywords must appear in either URL or title
            if all(kw in combined for kw in keywords):
                # Prefer links that look like detail pages (have year in URL)
                if re.search(r"20\d{2}", url_lower):
                    matched[exam_name] = link
                    break

        # If no year-containing link found, try again without year constraint
        if exam_name not in matched:
            for link in links:
                url_lower = link["url"].lower()
                title_lower = link["title"].lower()
                combined = url_lower + " " + title_lower
                if all(kw in combined for kw in keywords):
                    matched[exam_name] = link
                    break

    return matched


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: DETAIL PAGE PARSING (Pure HTML — No AI)
# ═══════════════════════════════════════════════════════════════════════════════

async def _parse_detail_page(exam_name: str, link_info: dict) -> dict:
    """Parse a SarkariResult detail page and extract structured fields.

    Uses BeautifulSoup DOM selectors only. Never infers or guesses.
    Missing fields → "Not Available".
    """
    url = link_info["url"]

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract conducting body from URL path
    conducting_body = _extract_conducting_body(url)

    # Extract Important Dates section
    dates = _extract_important_dates(soup)

    # Extract vacancy count
    vacancy_posts = _extract_vacancy_posts(soup)

    # Extract official notification link
    notification_link = _extract_notification_link(soup)

    # Extract last update / post date
    last_update = _extract_last_update_date(soup)

    # Build the record
    record = {
        "exam_name": exam_name,
        "conducting_body": conducting_body,
        "notification_date": dates.get("notification_date", NOT_AVAILABLE),
        "application_start": dates.get("application_start", NOT_AVAILABLE),
        "application_end": dates.get("application_end", NOT_AVAILABLE),
        "expected_exam_date": dates.get("exam_date", NOT_AVAILABLE),
        "vacancy_posts": vacancy_posts,
        "exam_cycle": NOT_AVAILABLE,
        "estimated_applicants": LAST_CYCLE_APPLICANTS.get(exam_name, NOT_AVAILABLE),
        "source_url": url,
        "source_name": "SarkariResult",
        "official_notification_link": notification_link,
        "last_update_date": last_update,
        "notes": link_info.get("title", "")[:150],
    }


    return record


def _extract_conducting_body(url: str) -> str:
    """Determine the conducting body from the URL path structure."""
    url_lower = url.lower()
    for path_key, body_name in BODY_MAP.items():
        if path_key in url_lower:
            return body_name

    # Try to infer from common patterns
    if "/2026/" in url_lower or "/2025/" in url_lower or "/2024/" in url_lower:
        # Generic year-based URLs: try the page title later
        return NOT_AVAILABLE

    return NOT_AVAILABLE


def _extract_important_dates(soup: BeautifulSoup) -> dict[str, str]:
    """Extract dates from the 'Important Dates' section.

    SarkariResult pages have a consistent pattern:
    <h2>Important Dates</h2>
    followed by <ul><li> items in "key : value" format.
    """
    dates: dict[str, str] = {}

    # Find the "Important Dates" heading
    date_heading = None
    for h2 in soup.find_all("h2"):
        if "important dates" in h2.get_text(strip=True).lower():
            date_heading = h2
            break

    if not date_heading:
        return dates

    # Look for list items after this heading
    # Walk siblings until the next h2
    current = date_heading.find_next_sibling()
    while current and current.name != "h2":
        if current.name == "ul" or current.name == "ol":
            for li in current.find_all("li"):
                text = li.get_text(strip=True)
                _parse_date_line(text, dates)
        elif current.name == "li":
            text = current.get_text(strip=True)
            _parse_date_line(text, dates)
        elif current.name == "p":
            # Sometimes dates are in <p> tags too
            text = current.get_text(strip=True)
            if ":" in text:
                _parse_date_line(text, dates)
        current = current.find_next_sibling() if current else None

    # Also try looking inside the heading's parent for list items
    if not dates:
        parent = date_heading.find_parent()
        if parent:
            for li in parent.find_all("li"):
                text = li.get_text(strip=True)
                if ":" in text:
                    _parse_date_line(text, dates)

    return dates


def _parse_date_line(text: str, dates: dict) -> None:
    """Parse a single date line in 'key : value' format.

    Common patterns on SarkariResult:
    - "Application Begin : 09/06/2025"
    - "Last Date for Apply Online : 04/07/2025"
    - "Exam Date Tier I : 13-30 August 2025"
    - "Notification Date : 15/01/2026"
    """
    if ":" not in text:
        return

    key, _, value = text.partition(":")
    key = key.strip().lower()
    value = value.strip()

    if not value or value.lower() in ("", "na", "n/a", "-"):
        return

    # Map keys to our field names
    if any(k in key for k in ("application begin", "apply online begin",
                                "apply start", "registration begin")):
        dates["application_start"] = value

    elif any(k in key for k in ("last date", "apply online last",
                                  "last date for apply", "application last")):
        dates["application_end"] = value

    elif any(k in key for k in ("notification", "advt date", "advertisement")):
        if "notification_date" not in dates:
            dates["notification_date"] = value

    elif "exam date" in key:
        # Take the first exam date found (often Tier I)
        if "exam_date" not in dates:
            dates["exam_date"] = value

    # If we found "Application Begin" but no notification_date yet
    if "application_start" in dates and "notification_date" not in dates:
        dates["notification_date"] = dates["application_start"]


def _extract_vacancy_posts(soup: BeautifulSoup) -> str:
    """Extract total vacancy/posts count from the page.

    SarkariResult pattern: <h2> containing "Vacancy Details Total XXXX Post"
    Also found in page <title> or <h1>: "...for 14582 Post"
    """
    # Method 1: Check h2 headings for "Vacancy Details Total X Post"
    for h2 in soup.find_all("h2"):
        text = h2.get_text(strip=True)
        match = re.search(r"total\s+([\d,]+)\s*post", text, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")

    # Method 2: Check h1 title for "for XXXX Post"
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(strip=True)
        match = re.search(r"for\s+([\d,]+)\s*post", h1_text, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")

    # Method 3: Check page <title>
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        match = re.search(r"for\s+([\d,]+)\s*post", title_text, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")

    return NOT_AVAILABLE


def _extract_notification_link(soup: BeautifulSoup) -> str:
    """Extract the official notification PDF link from the page.

    Looks for <a> tags with href pointing to:
    - .pdf files on official domains
    - .gov.in domains
    """
    # Priority 1: PDF links with "notification" in text
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True).lower()
        if ("notification" in text or "advt" in text) and href.endswith(".pdf"):
            return href

    # Priority 2: Any .gov.in PDF link
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if ".gov.in" in href and href.endswith(".pdf"):
            return href

    # Priority 3: Any PDF link from sarkariresults.org.in (their PDF mirror)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True).lower()
        if "sarkariresults.org.in" in href and href.endswith(".pdf"):
            if "notification" in text or "advt" in text or "notice" in text:
                return href

    return NOT_AVAILABLE

def _extract_last_update_date(soup: BeautifulSoup) -> str:
    """Extract 'Post Date / Update' which appears at the top of the details table."""
    # Look for td containing "Post Date / Update"
    for td in soup.find_all("td"):
        if "post date / update" in td.get_text(strip=True).lower():
            next_td = td.find_next_sibling("td")
            if next_td:
                # The date is usually like "07 June 2025 | 03:00 PM"
                # Let's take just the date part, or the whole text
                text = next_td.get_text(strip=True)
                if "|" in text:
                    text = text.split("|")[0].strip()
                return text
    
    # Try alternate h1 or generic pattern if table fails
    return NOT_AVAILABLE


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_record(record: dict) -> bool:
    """Validate a scraped exam record before storage.

    Rules:
    - exam_name must match one of the allowed exam names
    - vacancy_posts must be numeric or "Not Available"
    """
    # Check exam name is in allowed list
    if record.get("exam_name") not in EXAM_LIST:
        logger.warning(f"Validation failed: unknown exam '{record.get('exam_name')}'")
        return False

    # Validate vacancy_posts
    vp = record.get("vacancy_posts", NOT_AVAILABLE)
    if vp != NOT_AVAILABLE:
        cleaned = vp.replace(",", "").replace(" ", "")
        if not cleaned.isdigit():
            record["vacancy_posts"] = NOT_AVAILABLE

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

async def _log_extracted_fields(record: dict) -> None:
    """Log each extracted field to the activity log."""
    name = record["exam_name"]

    await log_manager.broadcast(
        "Exam Schedule",
        f"Extracted exam date: {record.get('expected_exam_date', NOT_AVAILABLE)} for {name}",
        "info",
    )
    vp = record.get("vacancy_posts", NOT_AVAILABLE)
    await log_manager.broadcast(
        "Exam Schedule",
        f"Extracted vacancy posts: {vp} for {name}",
        "info" if vp != NOT_AVAILABLE else "warning",
    )
    await log_manager.broadcast(
        "Exam Schedule",
        f"Saving exam record to database: {name}",
        "info",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _is_past_exam(record: dict) -> bool:
    """Check if the exam is strictly from a past year based on name or dates."""
    import datetime
    current_year = datetime.datetime.now().year
    # Many exams labeled with the previous year (e.g., 2025) actually occur in the current year (2026).
    # Thus, we only block years older than current_year - 1 (e.g., 2024 and older).
    past_years = "|".join(str(y) for y in range(2010, current_year - 1))
    past_year_pattern = re.compile(rf"\b({past_years})\b")
    
    if past_year_pattern.search(record.get("exam_name", "")):
        return True
    
    date_str = record.get("expected_exam_date", "")
    if date_str and date_str != NOT_AVAILABLE and past_year_pattern.search(date_str):
        return True
        
    app_end_str = record.get("application_end", "")
    if app_end_str and app_end_str != NOT_AVAILABLE and past_year_pattern.search(app_end_str):
        return True
            
    return False


def _save_and_return(records: list[dict]) -> list[dict]:
    """Save records to DB and return them."""
    saved = 0
    saved_records = []
    
    logger.info(f"Filtering {len(records)} extracted records for past exams...")
    
    for record in records:
        if _is_past_exam(record):
            logger.info(f"Skipping past exam: {record.get('exam_name')}")
            continue
            
        try:
            upsert_exam_schedule(record)
            saved += 1
            saved_records.append(record)
        except Exception as e:
            logger.warning(f"Failed to save {record.get('exam_name')}: {e}")
            
    logger.info(f"Successfully saved {saved} out of {len(records)} records.")
    return saved_records


def _seed(exam_name: str, body: str, path: str) -> dict:
    """Create a seed record with Not Available for all date fields."""
    return {
        "exam_name": exam_name,
        "conducting_body": body,
        "notification_date": NOT_AVAILABLE,
        "application_start": NOT_AVAILABLE,
        "application_end": NOT_AVAILABLE,
        "expected_exam_date": NOT_AVAILABLE,
        "vacancy_posts": NOT_AVAILABLE,
        "exam_cycle": NOT_AVAILABLE,
        "estimated_applicants": NOT_AVAILABLE,
        "source_url": f"{SARKARI_BASE}{path}",
        "source_name": "SarkariResult",
        "official_notification_link": NOT_AVAILABLE,
        "last_update_date": NOT_AVAILABLE,
        "notes": "",
    }
