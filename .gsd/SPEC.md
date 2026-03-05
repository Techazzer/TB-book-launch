# SPEC.md — Product Launch Dashboard

> **Status**: `FINALIZED`

## Vision
An internal market intelligence dashboard for Testbook's exam book publishing team that replaces manual research with a structured, data-driven workflow. The system scrapes Amazon India and Flipkart, analyzes competitor books via AI, tracks upcoming exam schedules, and presents actionable insights — enabling the team to make informed decisions about which exam preparation books to launch or update.

## Goals
1. **Automate marketplace research** — Scrape Amazon & Flipkart for competitor books, pricing, ratings, and reviews per exam
2. **Upcoming exam intelligence** — Surface exams coming in the next 6 months with tentative dates, notifications, and application windows
3. **AI-powered analysis** — Sentiment analysis on reviews, feature gap detection, competitor spec comparison (PYQ/theory/mixed)
4. **Launch decision support** — Recommend ideal book specifications, pricing strategy, and launch timing based on exam cycles
5. **Exportable insights** — Section-level CSV downloads for every dashboard section

## Non-Goals (Out of Scope)
- User authentication / login system (internal-only tool)
- Cloud deployment (local-first, deploy later)
- Real-time sales tracking or inventory management
- Integration with Testbook's internal publishing pipeline
- Mobile app version

## Users
Internal Testbook publishing team members (product managers, editors, market researchers). Same access level for everyone, no roles.

## Constraints
- **Technical**: SQLite for storage, Python/FastAPI backend, Stitch-designed UI (HTML/CSS/JS frontend)
- **Data sources**: Amazon India + Flipkart web scraping (subject to anti-bot measures)
- **AI**: Claude API for sentiment analysis and feature extraction
- **Legal**: Web scraping subject to marketplace ToS — use responsible rate limiting
- **Timeline**: MVP first, iterate

## Success Criteria
- [ ] User can select an exam and see full competitive landscape within minutes
- [ ] Upcoming exams section shows next 6 months of exam dates
- [ ] Book analysis shows competitor pricing, ratings, reviews across Amazon & Flipkart
- [ ] AI sentiment analysis identifies review complaints and feature gaps
- [ ] Live activity log shows real-time scraping/analysis progress
- [ ] Every section has working CSV export
- [ ] Every section has independent refresh capability
- [ ] Dashboard is clean, light-themed, simple to understand

## Key Data Points Per Exam
| Category | Data Points |
|----------|------------|
| **Exam Info** | Exam name, notification dates, application dates, expected exam date, exam cycle, estimated applicants (TAM) |
| **Competitor Books** | Title, author, publisher, marketplace presence (Amazon/Flipkart/other), format (PYQ/theory/mixed) |
| **Pricing** | Amazon price, Flipkart price, category average price, best-seller vs average price delta |
| **Ratings** | Amazon rating + review count, Flipkart rating + review count |
| **AI Analysis** | Review sentiment (positive/negative/neutral), common complaints, feature gaps, recommended book specs |
| **Launch Decision** | Ideal format, pricing recommendation, optimal timing based on exam timeline |
