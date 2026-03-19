"""Central configuration for the Product Launch Dashboard."""
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        pass

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_VERCEL = os.getenv("VERCEL", "") == "1"

# ── Paths ────────────────────────────────────────────────────────────────────
if not DATABASE_URL and not IS_VERCEL:
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "dashboard.db"))
else:
    # On Vercel or with Supabase, we don't need the local 'data' folder
    DB_PATH = "/tmp/dashboard.db" 

FRONTEND_DIR = BASE_DIR / "frontend"

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = "claude-3-5-sonnet-20241022"

# ── Scraping ─────────────────────────────────────────────────────────────────
MAX_PRODUCTS_PER_MARKETPLACE = int(os.getenv("MAX_PRODUCTS_PER_MARKETPLACE", "30"))
MAX_REVIEWS_PER_PRODUCT = int(os.getenv("MAX_REVIEWS_PER_PRODUCT", "100"))
SCRAPE_DELAY_MIN = float(os.getenv("SCRAPE_DELAY_MIN", "2"))
SCRAPE_DELAY_MAX = float(os.getenv("SCRAPE_DELAY_MAX", "5"))
SCRAPING_DELAY = float(os.getenv("SCRAPING_DELAY", "2"))  # seconds between requests
SCRAPING_MAX_PAGES = int(os.getenv("SCRAPING_MAX_PAGES", "3"))  # max search result pages

# ── Supported Exams ──────────────────────────────────────────────────────────
EXAM_LIST = [
    # SSC Exams
    "SSC CGL", "SSC CHSL", "SSC MTS", "SSC GD Constable",
    "SSC CPO", "SSC Stenographer", "SSC JE",
    # Railway Exams
    "RRB NTPC", "RRB Group D", "RRB ALP", "RRB JE",
    "RRB Ministerial", "RPF Constable", "RPF SI",
    # Banking Exams
    "IBPS PO", "IBPS Clerk", "IBPS SO", "IBPS RRB PO",
    "IBPS RRB Clerk", "SBI PO", "SBI Clerk", "RBI Grade B",
    "RBI Assistant", "NABARD Grade A", "SEBI Grade A",
    # UPSC & State PSC
    "UPSC Prelims", "UPSC CAPF", "UPSC CDS", "UPSC NDA",
    "UPSC EPFO", "BPSC", "UPPSC", "MPPSC", "RPSC",
    # Teaching Exams
    "CTET", "KVS PRT", "KVS TGT", "KVS PGT",
    "NVS TGT", "NVS PGT", "DSSSB TGT", "DSSSB PRT",
    "SUPER TET", "UPTET", "MPTET", "REET",
    # Defense Exams
    "AFCAT", "CDS", "NDA", "Indian Navy SSR",
    "Indian Navy AA", "Indian Air Force Group X Y",
    # Insurance
    "LIC AAO", "LIC ADO", "NIACL AO",
    # Other
    "GATE", "UGC NET", "CSIR NET",
    "CUET", "CLAT", "NEET", "JEE Main",
]

# ── Search Query Suffixes ────────────────────────────────────────────────────
SEARCH_SUFFIXES = [
    "book", "preparation book", "guide",
    "previous year papers", "practice set",
    "solved papers", "study material",
]
