"""Pydantic models for API request/response validation."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Exam Models ──────────────────────────────────────────────────────────────
class ExamBase(BaseModel):
    name: str

class ExamOut(ExamBase):
    id: int
    created_at: Optional[str] = None
    last_scraped: Optional[str] = None


# ── Exam Schedule Models ─────────────────────────────────────────────────────
class ExamScheduleBase(BaseModel):
    exam_name: str
    notification_date: Optional[str] = None
    application_start: Optional[str] = None
    application_end: Optional[str] = None
    expected_exam_date: Optional[str] = None
    exam_cycle: Optional[str] = None
    estimated_applicants: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    notes: Optional[str] = None

class ExamScheduleOut(ExamScheduleBase):
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── Product Models ───────────────────────────────────────────────────────────
class ProductBase(BaseModel):
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    marketplace: str
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    discount: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    best_seller_rank: Optional[str] = None
    book_format: Optional[str] = None
    pages: Optional[int] = None
    language: Optional[str] = None
    isbn: Optional[str] = None
    description: Optional[str] = None
    is_bestseller: int = 0

class ProductOut(ProductBase):
    id: int
    exam_id: int
    scraped_at: Optional[str] = None


# ── Review Models ────────────────────────────────────────────────────────────
class ReviewBase(BaseModel):
    reviewer_name: Optional[str] = None
    rating: Optional[float] = None
    title: Optional[str] = None
    content: Optional[str] = None
    review_date: Optional[str] = None
    verified_purchase: int = 0
    helpful_count: int = 0
    marketplace: Optional[str] = None

class ReviewOut(ReviewBase):
    id: int
    product_id: int
    scraped_at: Optional[str] = None


# ── AI Analysis Models ───────────────────────────────────────────────────────
class AIAnalysisOut(BaseModel):
    id: int
    product_id: int
    sentiment_data: Optional[str] = None
    feature_data: Optional[str] = None
    analyzed_at: Optional[str] = None


# ── Market Gaps Models ───────────────────────────────────────────────────────
class MarketGapOut(BaseModel):
    id: int
    exam_id: int
    gap_data: Optional[str] = None
    recommendations: Optional[str] = None
    analyzed_at: Optional[str] = None


# ── API Response Models ──────────────────────────────────────────────────────
class StatusResponse(BaseModel):
    status: str
    message: str

class ExamOverview(BaseModel):
    exam: ExamOut
    total_products: int
    avg_price: Optional[float] = None
    avg_rating: Optional[float] = None
    bestseller_count: int = 0
    amazon_count: int = 0
    flipkart_count: int = 0
    total_reviews: int = 0


# ── Pipeline Models ──────────────────────────────────────────────────────────
class PipelineRequest(BaseModel):
    exam_name: str
    scrape_amazon: bool = True
    scrape_flipkart: bool = True
    run_ai_analysis: bool = True

class LogEntry(BaseModel):
    timestamp: str
    step: str
    message: str
    level: str = "info"  # info, success, warning, error
