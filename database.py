"""Database initialization and schema supporting both SQLite (local) and PostgreSQL (Supabase)."""
import os
import sqlite3
from pathlib import Path
from config import DB_PATH, DATABASE_URL

# PostgreSQL adapter imports (conditional)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

# Global placeholder for raw SQL queries
PLACEHOLDER = "%s" if DATABASE_URL else "?"

def get_connection():
    """Returns a database connection."""
    if DATABASE_URL:
        if not psycopg2:
            raise ImportError("psycopg2-binary is required for PostgreSQL. Please run 'pip install psycopg2-binary'.")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    else:
        path = Path(DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

def get_cursor(conn):
    """Returns a cursor that returns results as dictionaries."""
    if DATABASE_URL:
        return conn.cursor(cursor_factory=RealDictCursor)
    else:
        return conn.cursor()

def get_last_row_id(cur, table_name=None):
    """
    Returns the ID of the last inserted row.
    SQLite uses cur.lastrowid.
    PostgreSQL usually needs 'RETURNING id' in the query, but we can also use cur.fetchone()
    if we included it, or use cur.lastrowid if the driver supports it (psycopg2 usually doesn't).
    """
    if not DATABASE_URL:
        return cur.lastrowid
    else:
        # Fallback for Postgres if we forgot RETURNING id
        try:
            row = cur.fetchone()
            if row and 'id' in row:
                return row['id']
            if row and isinstance(row, (list, tuple)):
                return row[0]
        except:
            pass
        return None

def init_db():
    """Initializes schema. Compatible with SQLite and PostgreSQL."""
    conn = get_connection()
    cur = get_cursor(conn)
    
    # We use Postgres-friendly SERIAL. database.py will convert to AUTOINCREMENT for SQLite.
    schema = """
        CREATE TABLE IF NOT EXISTS exams (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scraped TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exam_schedule (
            id SERIAL PRIMARY KEY,
            exam_name TEXT UNIQUE NOT NULL,
            conducting_body TEXT,
            notification_date TEXT,
            application_start TEXT,
            application_end TEXT,
            expected_exam_date TEXT,
            vacancy_posts TEXT,
            exam_cycle TEXT,
            estimated_applicants TEXT,
            source_url TEXT,
            source_name TEXT,
            official_notification_link TEXT,
            last_update_date TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            author TEXT,
            publisher TEXT,
            marketplace TEXT NOT NULL,
            product_url TEXT,
            image_url TEXT,
            price REAL,
            mrp REAL,
            discount TEXT,
            rating REAL,
            review_count INTEGER DEFAULT 0,
            best_seller_rank TEXT,
            book_format TEXT,
            pages INTEGER,
            language TEXT,
            isbn TEXT,
            asin TEXT,
            amazon_rank TEXT,
            description TEXT,
            is_bestseller INTEGER DEFAULT 0,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            reviewer_name TEXT,
            rating REAL,
            title TEXT,
            content TEXT,
            review_date TEXT,
            verified_purchase INTEGER DEFAULT 0,
            helpful_count INTEGER DEFAULT 0,
            marketplace TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    
    if not DATABASE_URL:
        schema = schema.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        schema = schema.replace("DOUBLE PRECISION", "REAL")

    try:
        if DATABASE_URL:
            # Postgres execute doesn't like multiple statements in one call sometimes
            # and Supabase often prefers manual schema run. This is for safety.
            for statement in schema.split(";"):
                if statement.strip():
                    cur.execute(statement)
        else:
            conn.executescript(schema)
        conn.commit()
    except Exception as e:
        print(f"init_db issue: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
