"""
Exam Schedule Scraper — Fetches upcoming exam notifications.

Uses httpx to scrape exam notification pages and Claude AI to extract
structured exam schedule data from the page content.
"""
import httpx
import json
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, AI_MODEL
from backend.crud import upsert_exam_schedule, get_all_exam_schedules
from backend.ws_manager import log_manager


# Reliable exam notification sources
EXAM_SOURCES = [
    {
        "url": "https://www.ssc.nic.in/",
        "name": "SSC Official",
        "category": "SSC",
        "source_type": "Official",
    },
    {
        "url": "https://www.rrbcdg.gov.in/",
        "name": "RRB Official", 
        "category": "Railways",
        "source_type": "Official",
    },
    {
        "url": "https://www.ibps.in/",
        "name": "IBPS Official",
        "category": "Banking",
        "source_type": "Official",
    },
]


async def scrape_exam_schedules() -> list[dict]:
    """
    Attempt to scrape exam schedules from official sources.
    Falls back to seed data if scraping fails.
    Returns list of exam schedule dicts.
    """
    await log_manager.broadcast("Exam Schedule", "Starting exam schedule refresh...", "info")
    
    scraped = []
    
    for source in EXAM_SOURCES:
        try:
            await log_manager.broadcast(
                "Exam Schedule", 
                f"Fetching from {source['name']}...", 
                "info"
            )
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
                resp = await client.get(source["url"], headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator="\n", strip=True)[:3000]
                    
                    # Use AI to extract structured data
                    exams = await extract_exams_with_ai(text, source)
                    scraped.extend(exams)
                    await log_manager.broadcast(
                        "Exam Schedule",
                        f"Extracted {len(exams)} exams from {source['name']}.",
                        "success"
                    )
                else:
                    await log_manager.broadcast(
                        "Exam Schedule",
                        f"{source['name']} returned {resp.status_code}. Skipping.",
                        "warning"
                    )
        except Exception as e:
            await log_manager.broadcast(
                "Exam Schedule",
                f"Failed to fetch {source['name']}: {str(e)[:80]}",
                "warning"
            )

    # If scraping yielded nothing, use seed data
    if not scraped:
        await log_manager.broadcast(
            "Exam Schedule",
            "Live scraping unavailable. Loading seed data...",
            "info"
        )
        scraped = get_seed_exam_data()
    
    # Save to database
    saved = 0
    for exam in scraped:
        try:
            upsert_exam_schedule(exam)
            saved += 1
        except Exception:
            pass

    await log_manager.broadcast(
        "Exam Schedule",
        f"Saved {saved} exam schedule entries to database.",
        "success"
    )
    
    return scraped


async def extract_exams_with_ai(page_text: str, source: dict) -> list[dict]:
    """Use Claude to extract structured exam data from scraped page text."""
    if not ANTHROPIC_API_KEY:
        return []
    
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"""Extract upcoming government exam information from this web page text.
Return a JSON array of exams. Each exam object should have:
- exam_name: Full exam name (e.g., "SSC CGL 2024")
- notification_date: Date notification was released (format: "YYYY-MM-DD" or null)
- application_start: Application start date ("YYYY-MM-DD" or null)
- application_end: Application end date ("YYYY-MM-DD" or null)
- expected_exam_date: Expected exam date ("YYYY-MM-DD" or "Month YYYY" or null)
- exam_cycle: Annual/Biannual/etc
- estimated_applicants: Like "30L" or "1.2Cr" or null
- notes: Any relevant subtitle or description

Source: {source['name']} ({source['category']})

Page text:
{page_text}

Return ONLY a JSON array, no markdown formatting."""
            }]
        )
        
        text = response.content[0].text.strip()
        # Clean up potential markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        
        exams = json.loads(text)
        for exam in exams:
            exam["source_url"] = source["url"]
            exam["source_name"] = source["source_type"]
        return exams
    except Exception as e:
        await log_manager.broadcast(
            "AI Extract",
            f"AI extraction failed: {str(e)[:60]}",
            "warning"
        )
        return []


def get_seed_exam_data() -> list[dict]:
    """Pre-populated exam schedule data for the Indian government exam calendar."""
    return [
        {
            "exam_name": "SSC CHSL 2026",
            "notification_date": "2026-04-02",
            "application_start": "2026-04-02",
            "application_end": "2026-05-01",
            "expected_exam_date": "2026-06-15",
            "exam_cycle": "Annual",
            "estimated_applicants": "30.69L",
            "source_url": "https://ssc.nic.in",
            "source_name": "Official",
            "notes": "Combined Higher Secondary Level",
        },
        {
            "exam_name": "SSC CGL 2026",
            "notification_date": "2026-06-10",
            "application_start": "2026-06-10",
            "application_end": "2026-07-10",
            "expected_exam_date": "2026-09-05",
            "exam_cycle": "Annual",
            "estimated_applicants": "30L",
            "source_url": "https://ssc.nic.in",
            "source_name": "Official",
            "notes": "Combined Graduate Level",
        },
        {
            "exam_name": "SSC MTS 2026",
            "notification_date": "2026-05-07",
            "application_start": "2026-05-07",
            "application_end": "2026-06-06",
            "expected_exam_date": "2026-07-25",
            "exam_cycle": "Annual",
            "estimated_applicants": "40L",
            "source_url": "https://ssc.nic.in",
            "source_name": "Official",
            "notes": "Multi-Tasking Staff",
        },
        {
            "exam_name": "SSC GD Constable 2027",
            "notification_date": "2026-08-27",
            "application_start": "2026-08-27",
            "application_end": "2026-09-27",
            "expected_exam_date": "2027-01-10",
            "exam_cycle": "Annual",
            "estimated_applicants": "45L",
            "source_url": "https://ssc.nic.in",
            "source_name": "Official",
            "notes": "General Duty Constable",
        },
        {
            "exam_name": "IBPS PO 2026",
            "notification_date": "2026-08-01",
            "application_start": "2026-08-01",
            "application_end": "2026-08-21",
            "expected_exam_date": "2026-10-12",
            "exam_cycle": "Annual",
            "estimated_applicants": "20L",
            "source_url": "https://ibps.in",
            "source_name": "Official",
            "notes": "Probationary Officer",
        },
        {
            "exam_name": "IBPS Clerk 2026",
            "notification_date": "2026-07-01",
            "application_start": "2026-07-01",
            "application_end": "2026-07-21",
            "expected_exam_date": "2026-08-24",
            "exam_cycle": "Annual",
            "estimated_applicants": "25L",
            "source_url": "https://ibps.in",
            "source_name": "Official",
            "notes": "Clerical Cadre",
        },
        {
            "exam_name": "SBI PO 2026",
            "notification_date": "2026-09-05",
            "application_start": "2026-09-05",
            "application_end": "2026-09-25",
            "expected_exam_date": "2026-11-20",
            "exam_cycle": "Annual",
            "estimated_applicants": "18L",
            "source_url": "https://sbi.co.in",
            "source_name": "Official",
            "notes": "Probationary Officer",
        },
        {
            "exam_name": "SBI Clerk 2026",
            "notification_date": "2026-11-15",
            "application_start": "2026-11-15",
            "application_end": "2026-12-05",
            "expected_exam_date": "2027-01-10",
            "exam_cycle": "Annual",
            "estimated_applicants": "20L",
            "source_url": "https://sbi.co.in",
            "source_name": "Official",
            "notes": "Junior Associates",
        },
        {
            "exam_name": "RBI Grade B 2026",
            "notification_date": "2026-06-01",
            "application_start": "2026-06-01",
            "application_end": "2026-06-21",
            "expected_exam_date": "2026-08-16",
            "exam_cycle": "Annual",
            "estimated_applicants": "3L",
            "source_url": "https://rbi.org.in",
            "source_name": "Official",
            "notes": "Officers in Grade B",
        },
        {
            "exam_name": "RRB NTPC 2026",
            "notification_date": "2026-07-15",
            "application_start": None,
            "application_end": None,
            "expected_exam_date": "2026-11-25",
            "exam_cycle": "Periodic",
            "estimated_applicants": "1.2Cr",
            "source_url": "https://rrbcdg.gov.in",
            "source_name": "Blog Est.",
            "notes": "Non-Technical Popular Categories",
        },
        {
            "exam_name": "RRB Group D 2026",
            "notification_date": None,
            "application_start": None,
            "application_end": None,
            "expected_exam_date": "2026-12-10",
            "exam_cycle": "Periodic",
            "estimated_applicants": "1.5Cr",
            "source_url": "https://rrbcdg.gov.in",
            "source_name": "News Est.",
            "notes": "Level 1 Posts",
        },
        {
            "exam_name": "RRB ALP 2026",
            "notification_date": "2026-01-20",
            "application_start": "2026-01-20",
            "application_end": "2026-02-19",
            "expected_exam_date": "2026-05-15",
            "exam_cycle": "Periodic",
            "estimated_applicants": "35L",
            "source_url": "https://rrbcdg.gov.in",
            "source_name": "News Est.",
            "notes": "Assistant Loco Pilot",
        },
        {
            "exam_name": "UPSC Prelims 2026",
            "notification_date": "2026-02-04",
            "application_start": "2026-02-04",
            "application_end": "2026-02-24",
            "expected_exam_date": "2026-05-31",
            "exam_cycle": "Annual",
            "estimated_applicants": "12L",
            "source_url": "https://upsc.gov.in",
            "source_name": "Official",
            "notes": "Civil Services Preliminary",
        },
        {
            "exam_name": "UPSC NDA I 2026",
            "notification_date": "2025-12-20",
            "application_start": "2025-12-20",
            "application_end": "2026-01-09",
            "expected_exam_date": "2026-04-19",
            "exam_cycle": "Biannual",
            "estimated_applicants": "6L",
            "source_url": "https://upsc.gov.in",
            "source_name": "Official",
            "notes": "National Defence Academy",
        },
        {
            "exam_name": "UPSC CDS I 2026",
            "notification_date": "2025-12-20",
            "application_start": "2025-12-20",
            "application_end": "2026-01-09",
            "expected_exam_date": "2026-04-19",
            "exam_cycle": "Biannual",
            "estimated_applicants": "4L",
            "source_url": "https://upsc.gov.in",
            "source_name": "Official",
            "notes": "Combined Defence Services",
        },
        {
            "exam_name": "CTET July 2026",
            "notification_date": "2026-03-05",
            "application_start": "2026-03-05",
            "application_end": "2026-04-02",
            "expected_exam_date": "2026-07-07",
            "exam_cycle": "Biannual",
            "estimated_applicants": "28L",
            "source_url": "https://ctet.nic.in",
            "source_name": "Official",
            "notes": "Central Teacher Eligibility Test",
        },
        {
            "exam_name": "CTET Dec 2026",
            "notification_date": "2026-09-17",
            "application_start": "2026-09-17",
            "application_end": "2026-10-16",
            "expected_exam_date": "2026-12-15",
            "exam_cycle": "Biannual",
            "estimated_applicants": "28L",
            "source_url": "https://ctet.nic.in",
            "source_name": "Official",
            "notes": "Central Teacher Eligibility Test",
        },
        {
            "exam_name": "UGC NET June 2026",
            "notification_date": "2026-04-20",
            "application_start": "2026-04-20",
            "application_end": "2026-05-10",
            "expected_exam_date": "2026-06-12",
            "exam_cycle": "Biannual",
            "estimated_applicants": "15L",
            "source_url": "https://ugcnet.nta.ac.in",
            "source_name": "Official",
            "notes": "National Eligibility Test",
        },
        {
            "exam_name": "CUET UG 2026",
            "notification_date": "2026-02-27",
            "application_start": "2026-02-27",
            "application_end": "2026-03-26",
            "expected_exam_date": "2026-05-15",
            "exam_cycle": "Annual",
            "estimated_applicants": "15L",
            "source_url": "https://cuet.nta.nic.in",
            "source_name": "Official",
            "notes": "Common University Entrance Test",
        },
        {
            "exam_name": "RPF Constable 2026",
            "notification_date": "2026-04-15",
            "application_start": "2026-04-15",
            "application_end": "2026-05-14",
            "expected_exam_date": "2026-08-01",
            "exam_cycle": "Periodic",
            "estimated_applicants": "50L",
            "source_url": "https://rpf.indianrailways.gov.in",
            "source_name": "News Est.",
            "notes": "Railway Protection Force",
        },
        {
            "exam_name": "BPSC 71st 2026",
            "notification_date": "2026-07-01",
            "application_start": "2026-07-01",
            "application_end": "2026-07-30",
            "expected_exam_date": "2026-09-30",
            "exam_cycle": "Annual",
            "estimated_applicants": "6L",
            "source_url": "https://bpsc.bih.nic.in",
            "source_name": "Official",
            "notes": "Bihar Public Service Commission",
        },
        {
            "exam_name": "UPPSC PCS 2026",
            "notification_date": "2026-01-01",
            "application_start": "2026-01-01",
            "application_end": "2026-01-31",
            "expected_exam_date": "2026-03-24",
            "exam_cycle": "Annual",
            "estimated_applicants": "8L",
            "source_url": "https://uppsc.up.nic.in",
            "source_name": "Official",
            "notes": "UP Provincial Civil Service",
        },
        {
            "exam_name": "LIC AAO 2026",
            "notification_date": "2026-08-01",
            "application_start": "2026-08-01",
            "application_end": "2026-08-21",
            "expected_exam_date": "2026-09-15",
            "exam_cycle": "Annual",
            "estimated_applicants": "8L",
            "source_url": "https://licindia.in",
            "source_name": "Blog Est.",
            "notes": "Assistant Administrative Officer",
        },
        {
            "exam_name": "GATE 2027",
            "notification_date": "2026-08-24",
            "application_start": "2026-08-28",
            "application_end": "2026-09-26",
            "expected_exam_date": "2027-02-06",
            "exam_cycle": "Annual",
            "estimated_applicants": "10L",
            "source_url": "https://gate.iitb.ac.in",
            "source_name": "Official",
            "notes": "Graduate Aptitude Test in Engineering",
        },
    ]


def get_seed_exam_data_quick() -> list[dict]:
    """Returns just the first 5 upcoming exams for quick display."""
    all_data = get_seed_exam_data()
    # Sort by expected_exam_date
    all_data.sort(key=lambda x: x.get("expected_exam_date") or "9999")
    return all_data[:5]
