/**
 * Product Launch Dashboard — Frontend Application Logic
 * Handles API calls, WebSocket activity log, section navigation, and data rendering.
 */

const API = '';
let currentExam = null;
let ws = null;

// ── Initialization ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadExamList();
    loadUpcomingExams();
    connectWebSocket();
});

// ── Exam List ───────────────────────────────────────────────────────────────
async function loadExamList() {
    try {
        const res = await fetch(`${API}/api/exams/list`);
        const exams = await res.json();
        const select = document.getElementById('examSelect');
        exams.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('Failed to load exam list:', err);
    }
}

function onExamSelected() {
    const select = document.getElementById('examSelect');
    if (select.value) {
        currentExam = select.value;
        document.getElementById('examManualInput').value = '';
        loadExamData(currentExam);
    }
}

function onManualExamEnter() {
    const input = document.getElementById('examManualInput');
    if (input.value.trim()) {
        currentExam = input.value.trim();
        document.getElementById('examSelect').value = '';
        loadExamData(currentExam);
    }
}

// ── Section Navigation ──────────────────────────────────────────────────────
function showSection(section) {
    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.section === section) item.classList.add('active');
    });

    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');

    // Show selected section
    const el = document.getElementById(`section-${section}`);
    if (el) el.style.display = 'block';

    // If exam-specific section but no exam selected
    if (['overview', 'competitors', 'reviews', 'features', 'gaps'].includes(section) && !currentExam) {
        document.getElementById('section-no-exam').style.display = 'block';
        if (el) el.style.display = 'none';
    }
}

// ── Load Exam Data ──────────────────────────────────────────────────────────
async function loadExamData(examName) {
    document.getElementById('overviewTitle').textContent = `📊 ${examName} — Overview`;

    // Show exam-specific sections
    showSection('overview');
    document.getElementById('section-overview').style.display = 'block';
    document.getElementById('section-no-exam').style.display = 'none';

    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/overview`);
        if (res.ok) {
            const data = await res.json();
            updateKPIs(data);
            await loadCompetitorTable(examName);
        } else {
            // No data yet — show empty KPIs
            updateKPIs({
                total_products: 0, avg_price: null, avg_rating: null,
                bestseller_count: 0, amazon_count: 0, flipkart_count: 0, total_reviews: 0
            });
        }
    } catch (err) {
        console.error('Failed to load exam data:', err);
    }
}

function updateKPIs(data) {
    document.getElementById('kpiTotalBooks').textContent = data.total_products || '0';
    document.getElementById('kpiAvgPrice').textContent = data.avg_price ? `₹${data.avg_price}` : '—';
    document.getElementById('kpiAvgRating').textContent = data.avg_rating ? `${data.avg_rating} ★` : '—';
    document.getElementById('kpiBestsellers').textContent = data.bestseller_count || '0';
    document.getElementById('kpiAmazon').textContent = data.amazon_count || '0';
    document.getElementById('kpiFlipkart').textContent = data.flipkart_count || '0';
    document.getElementById('kpiReviews').textContent = data.total_reviews ? data.total_reviews.toLocaleString() : '0';
}

// ── Competitor Table ────────────────────────────────────────────────────────
async function loadCompetitorTable(examName) {
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/products`);
        if (!res.ok) return;
        const products = await res.json();
        renderCompetitorTable(products);
    } catch (err) {
        console.error('Failed to load products:', err);
    }
}

function renderCompetitorTable(products) {
    const tbody = document.getElementById('competitorTableBody');
    if (!products || products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:32px; color:#9096A6;">No competitor data yet. Click "Scrape Data" to start.</td></tr>';
        return;
    }

    tbody.innerHTML = products.map(p => `
        <tr>
            <td style="max-width:280px;">
                <div style="font-weight:600; line-height:1.3;">${truncate(p.title, 80)}</div>
                ${p.product_url ? `<a href="${p.product_url}" target="_blank" style="font-size:11px;">View →</a>` : ''}
            </td>
            <td>${p.author || '—'}</td>
            <td>${p.publisher || '—'}</td>
            <td>
                <span class="badge-marketplace ${p.marketplace === 'Amazon' ? 'badge-amazon' : 'badge-flipkart'}">
                    ${p.marketplace}
                </span>
            </td>
            <td>${p.price ? `₹${p.price}` : '—'}</td>
            <td>
                ${p.rating ? `<span class="stars">${'★'.repeat(Math.round(p.rating))}${'☆'.repeat(5 - Math.round(p.rating))}</span> ${p.rating}` : '—'}
            </td>
            <td>${p.review_count ? p.review_count.toLocaleString() : '—'}</td>
            <td>${p.book_format || '—'}</td>
            <td>${p.best_seller_rank || '—'}</td>
        </tr>
    `).join('');
}

// ── Upcoming Exams ──────────────────────────────────────────────────────────
async function loadUpcomingExams() {
    try {
        const res = await fetch(`${API}/api/schedule/upcoming?limit=5`);
        const exams = await res.json();
        renderUpcomingExams(exams);
    } catch (err) {
        renderUpcomingExamsEmpty();
    }
}

function renderUpcomingExams(exams) {
    const grid = document.getElementById('upcomingExamsGrid');
    if (!exams || exams.length === 0) {
        renderUpcomingExamsEmpty();
        return;
    }
    grid.innerHTML = exams.map(e => `
        <div class="exam-card" onclick="selectExamFromCard('${e.exam_name}')">
            <div class="exam-card-name">${e.exam_name}</div>
            <div class="exam-card-date">📅 ${e.expected_exam_date || 'Date TBD'}</div>
            <div class="exam-card-meta">${e.exam_cycle || ''} ${e.estimated_applicants ? `• ~${e.estimated_applicants} applicants` : ''}</div>
            <div class="exam-card-badge">
                ${getDaysUntilBadge(e.expected_exam_date)}
            </div>
        </div>
    `).join('');
}

function renderUpcomingExamsEmpty() {
    const grid = document.getElementById('upcomingExamsGrid');
    grid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-tertiary);">
            <div style="font-size: 32px; margin-bottom: 12px; opacity: 0.5;">📅</div>
            <h3 style="font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px;">No Upcoming Exams Yet</h3>
            <p style="font-size: 12px;">Exam schedule data will appear here once populated.</p>
        </div>
    `;
}

function selectExamFromCard(examName) {
    currentExam = examName;
    document.getElementById('examSelect').value = examName;
    document.getElementById('examManualInput').value = '';
    loadExamData(examName);
}

function getDaysUntilBadge(dateStr) {
    if (!dateStr) return '<span class="badge badge-info">Date TBD</span>';
    const days = Math.ceil((new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24));
    if (days < 0) return '<span class="badge badge-error">Passed</span>';
    if (days <= 30) return `<span class="badge badge-error">${days} days</span>`;
    if (days <= 90) return `<span class="badge badge-warning">${days} days</span>`;
    return `<span class="badge badge-success">${days} days</span>`;
}

// ── Section Refresh ─────────────────────────────────────────────────────────
async function refreshSection(section) {
    addLogEntry('info', 'Refresh', `Refreshing ${section} data...`);

    switch (section) {
        case 'upcoming':
            await loadUpcomingExams();
            addLogEntry('success', 'Refresh', 'Upcoming exams refreshed.');
            break;
        case 'scrape':
            if (!currentExam) {
                addLogEntry('warning', 'Scrape', 'No exam selected. Choose an exam first.');
                return;
            }
            await triggerScrape(currentExam);
            break;
        case 'competitors':
            if (currentExam) await loadCompetitorTable(currentExam);
            addLogEntry('success', 'Refresh', 'Competitor data refreshed.');
            break;
        case 'reviews':
            if (currentExam) await loadReviewData(currentExam);
            addLogEntry('success', 'Refresh', 'Review data refreshed.');
            break;
        case 'features':
            if (currentExam) await loadFeatureData(currentExam);
            addLogEntry('success', 'Refresh', 'Feature data refreshed.');
            break;
        case 'gaps':
            if (currentExam) await loadGapData(currentExam);
            addLogEntry('success', 'Refresh', 'Gap analysis refreshed.');
            break;
    }
}

// ── Scrape Trigger ──────────────────────────────────────────────────────────
async function triggerScrape(examName) {
    const btn = document.getElementById('scrapeBtn');
    btn.classList.add('btn-loading');
    btn.textContent = '⏳ Scraping...';

    addLogEntry('info', 'Pipeline', `Starting scrape for "${examName}"...`);

    try {
        const res = await fetch(`${API}/api/pipeline/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ exam_name: examName }),
        });
        const data = await res.json();
        if (res.ok) {
            addLogEntry('success', 'Pipeline', `Scrape completed for "${examName}".`);
            await loadExamData(examName);
        } else {
            addLogEntry('error', 'Pipeline', data.detail || 'Scrape failed.');
        }
    } catch (err) {
        addLogEntry('error', 'Pipeline', `Network error: ${err.message}`);
    } finally {
        btn.classList.remove('btn-loading');
        btn.textContent = '🔄 Scrape Data';
    }
}

// ── Review Intelligence ─────────────────────────────────────────────────────
async function loadReviewData(examName) {
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/analysis`);
        if (!res.ok) return;
        const analyses = await res.json();
        renderReviews(analyses);
    } catch (err) {
        console.error('Failed to load reviews:', err);
    }
}

function renderReviews(analyses) {
    const container = document.getElementById('reviewsContent');
    if (!analyses || analyses.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">💬</div><h3>No Review Analysis</h3><p>Scrape data and run AI analysis to see insights.</p></div>`;
        return;
    }

    container.innerHTML = analyses.map(a => {
        const s = a.sentiment_data || {};
        return `
            <div class="card" style="margin-bottom: 16px;">
                <div class="card-header">
                    <h3>${truncate(a.title || 'Unknown', 60)}</h3>
                    <span class="badge-marketplace ${a.marketplace === 'Amazon' ? 'badge-amazon' : 'badge-flipkart'}">${a.marketplace || ''}</span>
                </div>
                <div class="card-body">
                    <div class="kpi-grid" style="margin-bottom: 16px;">
                        <div class="kpi-card"><div class="kpi-label">Positive</div><div class="kpi-value success">${s.positive || 0}%</div></div>
                        <div class="kpi-card"><div class="kpi-label">Neutral</div><div class="kpi-value">${s.neutral || 0}%</div></div>
                        <div class="kpi-card"><div class="kpi-label">Negative</div><div class="kpi-value" style="color: var(--status-error);">${s.negative || 0}%</div></div>
                    </div>
                    ${s.strengths ? `<p style="font-size:12px; margin-bottom: 8px;"><strong>Strengths:</strong> ${Array.isArray(s.strengths) ? s.strengths.join(', ') : s.strengths}</p>` : ''}
                    ${s.weaknesses ? `<p style="font-size:12px; margin-bottom: 8px;"><strong>Weaknesses:</strong> ${Array.isArray(s.weaknesses) ? s.weaknesses.join(', ') : s.weaknesses}</p>` : ''}
                    ${s.top_complaints ? `<p style="font-size:12px;"><strong>Top Complaints:</strong> ${Array.isArray(s.top_complaints) ? s.top_complaints.join(', ') : s.top_complaints}</p>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// ── Feature Data ────────────────────────────────────────────────────────────
async function loadFeatureData(examName) {
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/analysis`);
        if (!res.ok) return;
        const analyses = await res.json();
        renderFeatures(analyses);
    } catch (err) {
        console.error('Failed to load features:', err);
    }
}

function renderFeatures(analyses) {
    const container = document.getElementById('featuresContent');
    const withFeatures = analyses.filter(a => a.feature_data);
    if (withFeatures.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🔍</div><h3>No Feature Data</h3><p>Run AI analysis to classify book types.</p></div>`;
        return;
    }

    container.innerHTML = `
        <div class="card">
            <div class="card-body no-padding">
                <div class="table-wrapper">
                    <table class="data-table">
                        <thead>
                            <tr><th>Book</th><th>Type</th><th>Format</th><th>Language</th><th>Tags</th></tr>
                        </thead>
                        <tbody>
                            ${withFeatures.map(a => {
                                const f = a.feature_data || {};
                                return `<tr>
                                    <td style="max-width:250px;"><strong>${truncate(a.title || '', 60)}</strong></td>
                                    <td>${f.book_type || '—'}</td>
                                    <td>${f.format || '—'}</td>
                                    <td>${f.language || '—'}</td>
                                    <td>${f.tags ? (Array.isArray(f.tags) ? f.tags.map(t => `<span class="badge badge-accent" style="margin:2px;">${t}</span>`).join('') : f.tags) : '—'}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

// ── Gap Analysis ────────────────────────────────────────────────────────────
async function loadGapData(examName) {
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/gaps`);
        if (!res.ok) return;
        const data = await res.json();
        renderGaps(data);
    } catch (err) {
        console.error('Failed to load gaps:', err);
    }
}

function renderGaps(data) {
    const container = document.getElementById('gapsContent');
    if (!data || (!data.gap_data && !data.recommendations)) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🎯</div><h3>No Gap Analysis</h3><p>Run full analysis to reveal market opportunities.</p></div>`;
        return;
    }

    const gaps = data.gap_data || {};
    const recs = data.recommendations || {};

    container.innerHTML = `
        <div class="card" style="margin-bottom: 16px;">
            <div class="card-header"><h3>Market Gaps</h3></div>
            <div class="card-body">
                ${gaps.gaps ? `<ul style="font-size:13px; line-height: 1.8;">${(Array.isArray(gaps.gaps) ? gaps.gaps : [gaps.gaps]).map(g => `<li>${typeof g === 'object' ? JSON.stringify(g) : g}</li>`).join('')}</ul>` : '<p style="color: var(--text-tertiary);">No gaps identified.</p>'}
            </div>
        </div>
        <div class="card">
            <div class="card-header"><h3>Recommendations</h3></div>
            <div class="card-body">
                ${recs.recommendations ? `<ul style="font-size:13px; line-height: 1.8;">${(Array.isArray(recs.recommendations) ? recs.recommendations : [recs.recommendations]).map(r => `<li>${typeof r === 'object' ? JSON.stringify(r) : r}</li>`).join('')}</ul>` : '<p style="color: var(--text-tertiary);">No recommendations yet.</p>'}
            </div>
        </div>
    `;
}

// ── CSV Downloads ───────────────────────────────────────────────────────────
function downloadCSV(section) {
    if (!currentExam && section !== 'schedule') {
        addLogEntry('warning', 'Export', 'No exam selected for CSV export.');
        return;
    }

    const examEncoded = encodeURIComponent(currentExam);
    let url = '';

    switch (section) {
        case 'schedule':
            url = `${API}/api/schedule/csv`;
            break;
        case 'products':
            url = `${API}/api/exams/${examEncoded}/products/csv`;
            break;
        default:
            addLogEntry('info', 'Export', `CSV export for "${section}" coming soon.`);
            return;
    }

    addLogEntry('info', 'Export', `Downloading ${section} CSV...`);
    window.location.href = url;
}

// ── WebSocket Activity Log ──────────────────────────────────────────────────
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/activity-log`;

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            document.getElementById('activityDot').style.background = 'var(--status-success)';
        };

        ws.onmessage = (event) => {
            const entry = JSON.parse(event.data);
            appendLogEntry(entry);
        };

        ws.onclose = () => {
            document.getElementById('activityDot').style.background = 'var(--status-error)';
            setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = () => {
            document.getElementById('activityDot').style.background = 'var(--status-warning)';
        };
    } catch (err) {
        console.error('WebSocket connection failed:', err);
    }
}

function addLogEntry(level, step, message) {
    const now = new Date();
    const timestamp = now.toTimeString().slice(0, 8);
    appendLogEntry({ timestamp, step, message, level });
}

function appendLogEntry(entry) {
    const log = document.getElementById('activityLog');
    const div = document.createElement('div');
    div.className = `log-entry level-${entry.level || 'info'}`;
    div.innerHTML = `
        <span class="log-time">${entry.timestamp}</span>
        <span class="log-message"><strong>[${entry.step}]</strong> ${entry.message}</span>
    `;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function clearLog() {
    const log = document.getElementById('activityLog');
    log.innerHTML = '';
    addLogEntry('info', 'System', 'Log cleared.');
}

// ── Utilities ───────────────────────────────────────────────────────────────
function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '...' : str;
}
