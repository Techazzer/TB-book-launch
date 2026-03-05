# DECISIONS.md — Architecture Decision Records

## ADR-001: FastAPI + Static Frontend
**Date**: 2026-03-05
**Decision**: Use FastAPI for backend API, serve Stitch-generated static HTML/CSS/JS frontend
**Rationale**: FastAPI is fast, async-capable, auto-generates OpenAPI docs. Stitch exports clean HTML/CSS that can be served as static files.

## ADR-002: SQLite for Storage
**Date**: 2026-03-05
**Decision**: Use SQLite with WAL mode for all data storage
**Rationale**: Local-first deployment, no external DB dependency, sufficient for single-team use. Upgradeable to PostgreSQL later.

## ADR-003: Section-Level Refresh & Export
**Date**: 2026-03-05
**Decision**: Each dashboard section gets its own refresh button and CSV export button
**Rationale**: Prevents full-page refreshes, allows granular control, exports are section-specific and immediately usable.

## ADR-004: WebSocket Activity Log
**Date**: 2026-03-05
**Decision**: Use WebSocket for real-time activity log updates
**Rationale**: HTTP polling would miss rapid updates. WebSocket provides true real-time streaming of pipeline progress.
