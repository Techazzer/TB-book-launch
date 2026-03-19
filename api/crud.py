"""CRUD operations for the database supporting both SQLite and PostgreSQL."""
import json
from typing import Optional
from database import get_connection, get_cursor, PLACEHOLDER, get_last_row_id

# ── Helper ───────────────────────────────────────────────────────────────────
def row_to_dict(row):
    """Normalize row to dict for both SQLite.Row and Postgres RealDictRow."""
    if row is None: return None
    return dict(row)

# ── Exams ────────────────────────────────────────────────────────────────────
def upsert_exam(name: str) -> int:
    conn = get_connection()
    cur = get_cursor(conn)
    # INSERT OR IGNORE is SQLite; Postgres uses ON CONFLICT DO NOTHING
    query = f"INSERT INTO exams (name) VALUES ({PLACEHOLDER}) ON CONFLICT (name) DO NOTHING"
    cur.execute(query, (name,))
    
    query = f"SELECT id FROM exams WHERE name = {PLACEHOLDER}"
    cur.execute(query, (name,))
    row = cur.fetchone()
    conn.close()
    return row["id"]

def get_exam_by_name(name: str) -> Optional[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"SELECT * FROM exams WHERE name = {PLACEHOLDER}"
    cur.execute(query, (name,))
    row = cur.fetchone()
    conn.close()
    return row_to_dict(row)

def get_all_exams() -> list[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute("SELECT * FROM exams ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def update_exam_scraped(exam_id: int):
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"UPDATE exams SET last_scraped = CURRENT_TIMESTAMP WHERE id = {PLACEHOLDER}"
    cur.execute(query, (exam_id,))
    conn.commit()
    conn.close()

# ── Exam Schedule ────────────────────────────────────────────────────────────
def upsert_exam_schedule(data: dict) -> int:
    conn = get_connection()
    cur = get_cursor(conn)
    
    # Postgres/SQLite compatible upsert
    query = f"""
        INSERT INTO exam_schedule 
            (exam_name, conducting_body, notification_date, application_start, 
             application_end, expected_exam_date, vacancy_posts, exam_cycle, 
             estimated_applicants, source_url, source_name, 
             official_notification_link, last_update_date, notes)
        VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, 
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, 
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        ON CONFLICT(exam_name) DO UPDATE SET
            conducting_body = EXCLUDED.conducting_body,
            notification_date = EXCLUDED.notification_date,
            application_start = EXCLUDED.application_start,
            application_end = EXCLUDED.application_end,
            expected_exam_date = EXCLUDED.expected_exam_date,
            vacancy_posts = EXCLUDED.vacancy_posts,
            exam_cycle = EXCLUDED.exam_cycle,
            estimated_applicants = EXCLUDED.estimated_applicants,
            source_url = EXCLUDED.source_url,
            source_name = EXCLUDED.source_name,
            official_notification_link = EXCLUDED.official_notification_link,
            last_update_date = EXCLUDED.last_update_date,
            notes = EXCLUDED.notes,
            updated_at = CURRENT_TIMESTAMP
    """
    
    params = (
        data.get("exam_name"), data.get("conducting_body"), data.get("notification_date"),
        data.get("application_start"), data.get("application_end"), data.get("expected_exam_date"),
        data.get("vacancy_posts"), data.get("exam_cycle"), data.get("estimated_applicants"),
        data.get("source_url"), data.get("source_name"), data.get("official_notification_link"),
        data.get("last_update_date"), data.get("notes")
    )
    
    # For Postgres, we can append RETURNING id to get the row id immediately
    # But for compatibility, we just run the query then fetch what we inserted
    # (Especially since ON CONFLICT doesn't always return id)
    
    cur.execute(query, params)
    conn.commit()
    
    cur.execute(f"SELECT id FROM exam_schedule WHERE exam_name = {PLACEHOLDER}", (data.get("exam_name"),))
    last_id = cur.fetchone()["id"]
    conn.close()
    return last_id

def get_upcoming_exams(limit: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    # date('now') is SQLite. In Postgres, it's CURRENT_DATE.
    from database import DATABASE_URL
    date_now = "CURRENT_DATE" if DATABASE_URL else "date('now')"
    
    query = f"""
        SELECT * FROM exam_schedule 
        WHERE expected_exam_date IS NOT NULL 
        AND expected_exam_date >= {date_now}
        ORDER BY expected_exam_date ASC
    """
    if limit:
        query += f" LIMIT {PLACEHOLDER}"
        cur.execute(query, (limit,))
    else:
        cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_all_exam_schedules() -> list[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute("SELECT * FROM exam_schedule ORDER BY expected_exam_date ASC")
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

# ── Products ─────────────────────────────────────────────────────────────────
def upsert_product(data: dict) -> int:
    exam_name = data.get("exam_name", "")
    if not exam_name: raise ValueError("exam_name is required in product data")
    exam_id = upsert_exam(exam_name)
    return insert_product(exam_id, data)

def insert_product(exam_id: int, data: dict) -> int:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"""
        INSERT INTO products 
            (exam_id, title, author, publisher, marketplace, product_url, 
             image_url, price, mrp, discount, rating, review_count, 
             best_seller_rank, book_format, pages, language, isbn, 
             asin, amazon_rank, description, is_bestseller)
        VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, 
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, 
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, 
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
    """
    # SQLite uses cur.lastrowid; Postgres we append RETURNING id
    from database import DATABASE_URL
    if DATABASE_URL: query += " RETURNING id"
    
    params = (
        exam_id, data.get("title", ""), data.get("author"), data.get("publisher"), data.get("marketplace", ""),
        data.get("product_url"), data.get("image_url"), data.get("price"), data.get("mrp"), data.get("discount"),
        data.get("rating"), data.get("review_count", 0), data.get("best_seller_rank"), data.get("book_format"),
        data.get("pages"), data.get("language"), data.get("isbn"), data.get("asin"), data.get("amazon_rank"),
        data.get("description"), data.get("is_bestseller", 0)
    )
    
    cur.execute(query, params)
    last_id = get_last_row_id(cur)
    conn.commit()
    conn.close()
    return last_id

def get_products_by_exam(exam_name_or_id) -> list[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    if isinstance(exam_name_or_id, str):
        query = f"""SELECT p.* FROM products p 
                   JOIN exams e ON p.exam_id = e.id 
                   WHERE e.name = {PLACEHOLDER}
                   ORDER BY p.rating DESC, p.review_count DESC"""
        cur.execute(query, (exam_name_or_id,))
    else:
        query = f"SELECT * FROM products WHERE exam_id = {PLACEHOLDER} ORDER BY rating DESC, review_count DESC"
        cur.execute(query, (exam_name_or_id,))
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_product_by_id(product_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"SELECT * FROM products WHERE id = {PLACEHOLDER}"
    cur.execute(query, (product_id,))
    row = cur.fetchone()
    conn.close()
    return row_to_dict(row)

def delete_products_by_exam(exam_id: int):
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"DELETE FROM products WHERE exam_id = {PLACEHOLDER}"
    cur.execute(query, (exam_id,))
    conn.commit()
    conn.close()

# ── Reviews ──────────────────────────────────────────────────────────────────
def insert_review(product_id: int, data: dict) -> int:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"""INSERT INTO reviews 
            (product_id, reviewer_name, rating, title, content, 
             review_date, verified_purchase, helpful_count, marketplace)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, 
                    {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})"""
    
    from database import DATABASE_URL
    if DATABASE_URL: query += " RETURNING id"
    
    params = (
        product_id, data.get("reviewer_name"), data.get("rating"), data.get("title"), data.get("content"),
        data.get("review_date"), data.get("verified_purchase", 0), data.get("helpful_count", 0),
        data.get("marketplace")
    )
    cur.execute(query, params)
    last_id = get_last_row_id(cur)
    conn.commit()
    conn.close()
    return last_id

def get_reviews_by_product(product_id: int) -> list[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"SELECT * FROM reviews WHERE product_id = {PLACEHOLDER} ORDER BY review_date DESC"
    cur.execute(query, (product_id,))
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_all_reviews_by_exam(exam_name: str) -> list[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"""SELECT r.*, p.title as product_title, p.asin, p.product_url, p.author
               FROM reviews r
               JOIN products p ON r.product_id = p.id
               JOIN exams e ON p.exam_id = e.id
               WHERE e.name = {PLACEHOLDER}
               ORDER BY r.review_date DESC"""
    cur.execute(query, (exam_name,))
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def delete_reviews_by_product(product_id: int):
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"DELETE FROM reviews WHERE product_id = {PLACEHOLDER}"
    cur.execute(query, (product_id,))
    conn.commit()
    conn.close()

# ── AI Analysis ───────────────────────────────────────────────────────────────
def save_ai_analysis(product_id: int, sentiment_data: dict, feature_data: dict):
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"""INSERT INTO ai_analysis (product_id, sentiment_data, feature_data)
               VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
               ON CONFLICT (product_id) DO UPDATE SET
               sentiment_data = EXCLUDED.sentiment_data,
               feature_data = EXCLUDED.feature_data,
               analyzed_at = CURRENT_TIMESTAMP"""
    cur.execute(query, (product_id, json.dumps(sentiment_data), json.dumps(feature_data)))
    conn.commit()
    conn.close()

def get_ai_analysis(product_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"SELECT * FROM ai_analysis WHERE product_id = {PLACEHOLDER}"
    cur.execute(query, (product_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        d = row_to_dict(row)
        d['sentiment_data'] = json.loads(d['sentiment_data'])
        d['feature_data'] = json.loads(d['feature_data'])
        return d
    return None

def save_market_gaps(exam_id: int, gap_data: dict, recommendations: dict):
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"""INSERT INTO market_gaps (exam_id, gap_data, recommendations)
               VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
               ON CONFLICT (exam_id) DO UPDATE SET
               gap_data = EXCLUDED.gap_data,
               recommendations = EXCLUDED.recommendations,
               analyzed_at = CURRENT_TIMESTAMP"""
    cur.execute(query, (exam_id, json.dumps(gap_data), json.dumps(recommendations)))
    conn.commit()
    conn.close()

def get_market_gaps(exam_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = get_cursor(conn)
    query = f"SELECT * FROM market_gaps WHERE exam_id = {PLACEHOLDER} ORDER BY analyzed_at DESC LIMIT 1"
    cur.execute(query, (exam_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        d = row_to_dict(row)
        d['gap_data'] = json.loads(d['gap_data'])
        d['recommendations'] = json.loads(d['recommendations'])
        return d
    return None
