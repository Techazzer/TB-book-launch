"""SQLite database initialization and schema."""
import sqlite3
from pathlib import Path
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")  # Wait up to 5 seconds for locks
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        -- Exams master table
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scraped TIMESTAMP
        );

        -- Exam schedule / upcoming exams
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        -- Products scraped from marketplaces
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
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
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );

        -- Reviews scraped from marketplaces
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            reviewer_name TEXT,
            rating REAL,
            title TEXT,
            content TEXT,
            review_date TEXT,
            verified_purchase INTEGER DEFAULT 0,
            helpful_count INTEGER DEFAULT 0,
            marketplace TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        -- AI analysis results per product
        CREATE TABLE IF NOT EXISTS ai_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER UNIQUE NOT NULL,
            sentiment_data TEXT,
            feature_data TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        -- Market gap insights per exam
        CREATE TABLE IF NOT EXISTS market_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            gap_data TEXT,
            recommendations TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_products_exam ON products(exam_id);
        CREATE INDEX IF NOT EXISTS idx_products_marketplace ON products(marketplace);
        CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
        CREATE INDEX IF NOT EXISTS idx_schedule_date ON exam_schedule(expected_exam_date);
        CREATE INDEX IF NOT EXISTS idx_schedule_name ON exam_schedule(exam_name);
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
