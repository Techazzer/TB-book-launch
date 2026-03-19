"""CRUD operations for the database."""
import sqlite3
import json
from typing import Optional
from backend.database import get_connection


# ── Exams ────────────────────────────────────────────────────────────────────
def upsert_exam(name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO exams (name) VALUES (?)", (name,))
    conn.commit()
    cur.execute("SELECT id FROM exams WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    return row["id"]


def get_exam_by_name(name: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM exams WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_exams() -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM exams ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_exam_scraped(exam_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE exams SET last_scraped = CURRENT_TIMESTAMP WHERE id = ?",
        (exam_id,),
    )
    conn.commit()
    conn.close()


# ── Exam Schedule ────────────────────────────────────────────────────────────
def upsert_exam_schedule(data: dict) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO exam_schedule
            (exam_name, conducting_body, notification_date, application_start,
             application_end, expected_exam_date, vacancy_posts, exam_cycle,
             estimated_applicants, source_url, source_name,
             official_notification_link, last_update_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(exam_name) DO UPDATE SET
             conducting_body = excluded.conducting_body,
             notification_date = excluded.notification_date,
             application_start = excluded.application_start,
             application_end = excluded.application_end,
             expected_exam_date = excluded.expected_exam_date,
             vacancy_posts = excluded.vacancy_posts,
             exam_cycle = excluded.exam_cycle,
             estimated_applicants = excluded.estimated_applicants,
             source_url = excluded.source_url,
             source_name = excluded.source_name,
             official_notification_link = excluded.official_notification_link,
             last_update_date = excluded.last_update_date,
             notes = excluded.notes,
             updated_at = CURRENT_TIMESTAMP""",
        (
            data.get("exam_name"),
            data.get("conducting_body"),
            data.get("notification_date"),
            data.get("application_start"),
            data.get("application_end"),
            data.get("expected_exam_date"),
            data.get("vacancy_posts"),
            data.get("exam_cycle"),
            data.get("estimated_applicants"),
            data.get("source_url"),
            data.get("source_name"),
            data.get("official_notification_link"),
            data.get("last_update_date"),
            data.get("notes"),
        ),
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def get_upcoming_exams(limit: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT * FROM exam_schedule
        WHERE expected_exam_date IS NOT NULL
        AND expected_exam_date >= date('now')
        ORDER BY expected_exam_date ASC
    """
    if limit:
        query += " LIMIT ?"
        cur.execute(query, (limit,))
    else:
        cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_exam_schedules() -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM exam_schedule ORDER BY expected_exam_date ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Products ─────────────────────────────────────────────────────────────────
def upsert_product(data: dict) -> int:
    """Convenience: insert a product by exam_name (auto-resolves exam_id)."""
    exam_name = data.get("exam_name", "")
    if not exam_name:
        raise ValueError("exam_name is required in product data")
    exam_id = upsert_exam(exam_name)
    return insert_product(exam_id, data)


def insert_product(exam_id: int, data: dict) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO products
            (exam_id, title, author, publisher, marketplace, product_url,
             image_url, price, mrp, discount, rating, review_count,
             best_seller_rank, book_format, pages, language, isbn,
             asin, amazon_rank, description, is_bestseller)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            exam_id,
            data.get("title", ""),
            data.get("author"),
            data.get("publisher"),
            data.get("marketplace", ""),
            data.get("product_url"),
            data.get("image_url"),
            data.get("price"),
            data.get("mrp"),
            data.get("discount"),
            data.get("rating"),
            data.get("review_count", 0),
            data.get("best_seller_rank"),
            data.get("book_format"),
            data.get("pages"),
            data.get("language"),
            data.get("isbn"),
            data.get("asin"),
            data.get("amazon_rank"),
            data.get("description"),
            data.get("is_bestseller", 0),
        ),
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def get_products_by_exam(exam_name_or_id) -> list[dict]:
    """Get products by exam name (str) or exam id (int)."""
    conn = get_connection()
    cur = conn.cursor()
    if isinstance(exam_name_or_id, str):
        cur.execute(
            """SELECT p.* FROM products p
               JOIN exams e ON p.exam_id = e.id
               WHERE e.name = ?
               ORDER BY p.rating DESC, p.review_count DESC""",
            (exam_name_or_id,),
        )
    else:
        cur.execute(
            "SELECT * FROM products WHERE exam_id = ? ORDER BY rating DESC, review_count DESC",
            (exam_name_or_id,),
        )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]



def get_product_by_id(product_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_products_by_exam(exam_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM products WHERE exam_id = ?", (exam_id,))
    conn.commit()
    conn.close()


# ── Reviews ──────────────────────────────────────────────────────────────────
def insert_review(product_id: int, data: dict) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO reviews
            (product_id, reviewer_name, rating, title, content,
             review_date, verified_purchase, helpful_count, marketplace)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            product_id,
            data.get("reviewer_name"),
            data.get("rating"),
            data.get("title"),
            data.get("content"),
            data.get("review_date"),
            data.get("verified_purchase", 0),
            data.get("helpful_count", 0),
            data.get("marketplace"),
        )
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def get_reviews_by_product(product_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM reviews WHERE product_id = ? ORDER BY review_date DESC",
        (product_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_reviews_by_product(product_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM reviews WHERE product_id = ?", (product_id,))
    conn.commit()
    conn.close()


# ── AI Analysis ──────────────────────────────────────────────────────────────
def upsert_analysis(product_id: int, sentiment_data: dict = None, feature_data: dict = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO ai_analysis (product_id, sentiment_data, feature_data)
           VALUES (?, ?, ?)
           ON CONFLICT(product_id) DO UPDATE SET
             sentiment_data = COALESCE(excluded.sentiment_data, ai_analysis.sentiment_data),
             feature_data = COALESCE(excluded.feature_data, ai_analysis.feature_data),
             analyzed_at = CURRENT_TIMESTAMP""",
        (
            product_id,
            json.dumps(sentiment_data) if sentiment_data else None,
            json.dumps(feature_data) if feature_data else None,
        ),
    )
    conn.commit()
    conn.close()


def get_analysis_by_product(product_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ai_analysis WHERE product_id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        result = dict(row)
        if result.get("sentiment_data"):
            try:
                result["sentiment_data"] = json.loads(result["sentiment_data"])
            except json.JSONDecodeError:
                result["sentiment_data"] = None
        if result.get("feature_data"):
            try:
                result["feature_data"] = json.loads(result["feature_data"])
            except json.JSONDecodeError:
                result["feature_data"] = None
        return result
    return None


def get_analyses_by_exam(exam_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT a.*, p.title, p.marketplace
           FROM ai_analysis a
           JOIN products p ON a.product_id = p.id
           WHERE p.exam_id = ?""",
        (exam_id,),
    )
    rows = cur.fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        if r.get("sentiment_data"):
            try:
                r["sentiment_data"] = json.loads(r["sentiment_data"])
            except json.JSONDecodeError:
                r["sentiment_data"] = None
        if r.get("feature_data"):
            try:
                r["feature_data"] = json.loads(r["feature_data"])
            except json.JSONDecodeError:
                r["feature_data"] = None
        results.append(r)
    return results


# ── Market Gaps ──────────────────────────────────────────────────────────────
def upsert_market_gaps(exam_id: int, gap_data: dict, recommendations: dict = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM market_gaps WHERE exam_id = ?", (exam_id,))
    cur.execute(
        """INSERT INTO market_gaps (exam_id, gap_data, recommendations)
           VALUES (?, ?, ?)""",
        (
            exam_id,
            json.dumps(gap_data) if gap_data else None,
            json.dumps(recommendations) if recommendations else None,
        ),
    )
    conn.commit()
    conn.close()


def get_market_gaps(exam_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM market_gaps WHERE exam_id = ? ORDER BY analyzed_at DESC LIMIT 1", (exam_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        result = dict(row)
        if result.get("gap_data"):
            try:
                result["gap_data"] = json.loads(result["gap_data"])
            except json.JSONDecodeError:
                result["gap_data"] = None
        if result.get("recommendations"):
            try:
                result["recommendations"] = json.loads(result["recommendations"])
            except json.JSONDecodeError:
                result["recommendations"] = None
        return result
    return None


# ── Stats ────────────────────────────────────────────────────────────────────
def get_exam_stats(exam_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT 
            COUNT(p.id) as total_products,
            AVG(p.price) as avg_price,
            AVG(p.rating) as avg_rating,
            SUM(CASE WHEN p.is_bestseller = 1 THEN 1 ELSE 0 END) as bestseller_count,
            SUM(CASE WHEN p.marketplace = 'Amazon' THEN 1 ELSE 0 END) as amazon_count,
            SUM(p.review_count) as total_reviews,
            MAX(s.estimated_applicants) as estimated_applicants
           FROM products p
           LEFT JOIN exams e ON p.exam_id = e.id
           LEFT JOIN exam_schedule s ON e.name = s.exam_name
           WHERE p.exam_id = ?""",
        (exam_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}
