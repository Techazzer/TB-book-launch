# ROADMAP.md

> **Current Phase**: Phase 4 — Book Analysis & Competitor Intelligence
> **Milestone**: v1.0 — MVP Product Launch Dashboard

## Must-Haves (from SPEC)
- [ ] FastAPI backend with SQLite database
- [ ] Upcoming exams section (next 6 months, default 5, "Show All")
- [ ] Exam selector (dropdown + manual input)
- [ ] Amazon & Flipkart scraping pipeline
- [ ] Competitor book analysis (pricing, ratings, marketplace presence)
- [ ] AI sentiment analysis & feature gap detection
- [ ] Live activity log panel (right side)
- [ ] Section-level refresh buttons
- [ ] Section-level CSV export buttons
- [ ] Light theme, multi-page, simple UI (Stitch-designed)

## Phases

### Phase 1: Foundation & Backend
**Status**: ✅ Complete
**Objective**: Set up project structure, database schema, FastAPI backend, and basic Stitch-designed frontend shell
**Deliverables**:
- Project structure with FastAPI + static frontend
- SQLite database schema (exams, products, reviews, analysis, exam_schedule)
- API endpoints skeleton
- Stitch-designed page layouts (HTML/CSS) — landing page, main dashboard shell
- Basic exam selector component

### Phase 2: Upcoming Exams Module
**Status**: ✅ Complete
**Objective**: Build the upcoming exams intelligence section with exam schedule data
**Deliverables**:
- Exam schedule data model and API
- Web scraping for exam notifications from reliable sources
- "Upcoming Exams" top section (default 5, "Show All" with separate page)
- CSV export for upcoming exams
- Refresh button for exam schedule data

### Phase 3: Marketplace Scraping Engine
**Status**: ✅ Complete
**Objective**: Build robust Amazon & Flipkart scrapers with live activity logging
**Deliverables**:
- Amazon India scraper (search, product details, reviews)
- Flipkart scraper (search, product details, reviews)
- Scraping pipeline orchestrator with step-by-step logging
- Live activity log panel (right side, real-time WebSocket updates)
- Rate limiting, retry logic, error handling

### Phase 4: Book Analysis & Competitor Intelligence
**Status**: ⬜ Not Started
**Objective**: Build the core book analysis dashboard with competitor comparison
**Deliverables**:
- Competitor books table (title, author, publisher, format, marketplace presence)
- Pricing analysis (Amazon/Flipkart prices, category average, best-seller delta)
- Ratings & review counts (Amazon + Flipkart)
- Section refresh and CSV export buttons
- Competitor pricing comparison charts

### Phase 5: AI Analysis & Recommendations
**Status**: ⬜ Not Started
**Objective**: Integrate Claude AI for sentiment analysis, feature extraction, and launch recommendations
**Deliverables**:
- Review sentiment analysis (positive/negative/neutral distribution)
- Common complaints extraction from negative reviews
- Feature gap detection (what's missing in existing books)
- Book spec analysis (PYQ/theory/mixed classification)
- Launch timing recommendation based on exam cycle
- Ideal book specification suggestions

### Phase 6: Polish & Integration
**Status**: ⬜ Not Started
**Objective**: Final UI polish, end-to-end testing, performance optimization
**Deliverables**:
- All section-level refresh buttons working
- All section-level CSV exports verified
- Activity log fully integrated across all operations
- Error states and empty states designed
- Performance optimization (caching, lazy loading)
- End-to-end testing of full workflow
