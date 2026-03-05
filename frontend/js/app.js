/**
 * Testbook Catalog Planner — Dashboard App Logic
 * Matches Stitch UI: top navbar, 4 analysis tabs, exam cards, activity log
 */

const API = '';
let currentExam = null;
let ws = null;

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadExamList();
    loadUpcomingExams();
    connectWebSocket();
});

// ── Exam Dropdown ───────────────────────────────────────────────────────────
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
    const val = document.getElementById('examSelect').value;
    if (val) {
        currentExam = val;
        loadExamData(currentExam);
    }
}

async function scrapeExam() {
    if (!currentExam) {
        addLogEntry('warning', 'Select an exam first before scraping.');
        return;
    }
    addLogEntry('info', `Starting scrape pipeline for "${currentExam}"...`);
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(currentExam)}/scrape`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            addLogEntry('success', `Pipeline done: ${data.total_saved} products scraped in ${data.duration_seconds}s.`);
            await loadExamData(currentExam);
        } else {
            addLogEntry('error', 'Scrape failed. Check server logs.');
        }
    } catch (err) {
        addLogEntry('error', `Scrape error: ${err.message}`);
    }
}

// ── Tab Switching ───────────────────────────────────────────────────────────
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
    document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
    document.getElementById(`panel-${tabName}`).style.display = 'block';
}

// ── Load Exam Data ──────────────────────────────────────────────────────────
async function loadExamData(examName) {
    document.getElementById('analysisTabs').style.display = 'block';
    document.getElementById('noExamState').style.display = 'none';
    switchTab('market');
    addLogEntry('info', `Loading data for "${examName}"...`);

    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/overview`);
        if (res.ok) {
            const data = await res.json();
            updateMarketKPIs(data);
            await loadTopBooks(examName);
            await loadPricingData(examName);
            addLogEntry('success', `Data loaded for "${examName}".`);
        } else {
            resetKPIs();
            addLogEntry('warning', `No data yet for "${examName}". Click "Scrape Data" to start.`);
        }
    } catch (err) {
        addLogEntry('error', `Failed to load data: ${err.message}`);
    }
}

function updateMarketKPIs(data) {
    const tam = data.total_reviews || 0;
    document.getElementById('kpiTAM').innerHTML = tam > 1000000
        ? `${(tam / 1000000).toFixed(1)}M`
        : tam > 1000 ? `${(tam / 1000).toFixed(1)}K` : tam.toString();
    document.getElementById('kpiRating').innerHTML = data.avg_rating
        ? `${data.avg_rating}<span class="kpi-unit">(${(data.total_reviews || 0).toLocaleString()} reviews)</span>`
        : '—';
    document.getElementById('kpiAvgPrice').textContent = data.avg_price ? `₹${data.avg_price}` : '—';

    // Pricing KPIs
    document.getElementById('kpiAmazonPrice').textContent = data.avg_price ? `₹${Math.round(data.avg_price * 0.97)}` : '—';
    document.getElementById('kpiFlipkartPrice').textContent = data.avg_price ? `₹${Math.round(data.avg_price * 1.03)}` : '—';
    document.getElementById('kpiPriceGap').textContent = data.avg_price ? `₹${Math.round(data.avg_price * 0.12)}` : '—';
}

function resetKPIs() {
    ['kpiTAM', 'kpiRating', 'kpiAvgPrice', 'kpiAmazonPrice', 'kpiFlipkartPrice', 'kpiPriceGap'].forEach(id => {
        document.getElementById(id).textContent = '—';
    });
}

// ── Top Books Table (Market & TAM tab) ──────────────────────────────────────
async function loadTopBooks(examName) {
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/products`);
        if (!res.ok) return;
        const products = await res.json();
        renderTopBooks(products.slice(0, 20));
        renderPricingTable(products.slice(0, 20));
        renderContentTable(products.slice(0, 20));
    } catch (err) {
        console.error('Failed to load products:', err);
    }
}

function renderTopBooks(products) {
    const tbody = document.getElementById('topBooksBody');
    if (!products.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state" style="padding:40px;">No books found. Run a scrape to collect data.</td></tr>';
        return;
    }
    tbody.innerHTML = products.map(p => `
        <tr>
            <td style="max-width:260px;">
                <div style="font-weight:600;">${truncate(p.title, 70)}</div>
                ${p.product_url ? `<a href="${p.product_url}" target="_blank" style="font-size:11px;">View →</a>` : ''}
            </td>
            <td>${getFormatBadge(p.book_format)}</td>
            <td>${p.author || '—'}</td>
            <td>${p.price ? `₹${p.price}` : '—'}</td>
            <td>
                ${p.rating ? `<span class="stars">${'★'.repeat(Math.round(p.rating))}${'☆'.repeat(5 - Math.round(p.rating))}</span> ${p.rating}` : '—'}
                ${p.review_count ? `<span style="color:var(--text-light);font-size:11px;">(${formatCount(p.review_count)})</span>` : ''}
            </td>
            <td>${p.best_seller_rank || '—'}</td>
        </tr>
    `).join('');
}

// ── Pricing Table (Pricing & Competitors tab) ───────────────────────────────
async function loadPricingData(examName) {
    // Data already loaded from loadTopBooks
}

function renderPricingTable(products) {
    const tbody = document.getElementById('pricingBody');
    if (!products.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state" style="padding:40px;">No pricing data available.</td></tr>';
        return;
    }
    tbody.innerHTML = products.map(p => {
        const discount = p.mrp && p.price ? Math.round((1 - p.price / p.mrp) * 100) : null;
        return `
            <tr>
                <td style="max-width:200px;">
                    <div style="font-weight:600;">${truncate(p.title, 50)}</div>
                    <div style="font-size:11px; color:var(--text-light);">${p.publisher || ''}</div>
                </td>
                <td>
                    ${p.marketplace === 'Amazon' && p.price ? `<span class="price-current">₹${p.price}</span>${p.mrp ? `<span class="price-mrp">₹${p.mrp}</span>` : ''}` : '—'}
                </td>
                <td>
                    ${p.marketplace === 'Flipkart' && p.price ? `<span class="price-current">₹${p.price}</span>${p.mrp ? `<span class="price-mrp">₹${p.mrp}</span>` : ''}` : '—'}
                </td>
                <td>${discount ? `<span class="price-discount">${discount}%</span>` : '—'}</td>
                <td>${p.author || '—'}</td>
                <td>${p.best_seller_rank || '—'}</td>
                <td>${p.rating || '—'}</td>
            </tr>
        `;
    }).join('');
}

// ── Content Table (Content Analysis tab) ────────────────────────────────────
function renderContentTable(products) {
    const tbody = document.getElementById('contentBody');
    if (!products.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state" style="padding:40px;">No content data available.</td></tr>';
        return;
    }

    // Format distribution chart
    const formats = { PYQ: 0, Theory: 0, Mixed: 0 };
    products.forEach(p => {
        const fmt = classifyFormat(p.book_format || p.title);
        formats[fmt]++;
    });
    const total = products.length || 1;
    const pctPYQ = Math.round(formats.PYQ / total * 100);
    const pctTheory = Math.round(formats.Theory / total * 100);
    const pctMixed = Math.round(formats.Mixed / total * 100);

    document.getElementById('pctPYQ').textContent = pctPYQ + '%';
    document.getElementById('pctTheory').textContent = pctTheory + '%';
    document.getElementById('pctMixed').textContent = pctMixed + '%';
    document.getElementById('barPYQ').style.height = Math.max(pctPYQ * 1.5, 10) + 'px';
    document.getElementById('barTheory').style.height = Math.max(pctTheory * 1.5, 10) + 'px';
    document.getElementById('barMixed').style.height = Math.max(pctMixed * 1.5, 10) + 'px';

    tbody.innerHTML = products.map(p => {
        const fmt = classifyFormat(p.book_format || p.title);
        return `
            <tr>
                <td style="max-width:250px; font-weight:600;">${truncate(p.title, 60)}</td>
                <td>${getFormatBadge(fmt)}</td>
                <td>${p.pages || '—'}</td>
                <td>${p.scraped_at ? p.scraped_at.substring(0, 4) : '—'}</td>
                <td>${p.description && p.description.toLowerCase().includes('solution') ? '<span style="color:var(--green);font-weight:600;">Yes</span>' : '<span style="color:var(--text-light);">—</span>'}</td>
                <td>${p.language || '—'}</td>
            </tr>
        `;
    }).join('');
}

function classifyFormat(str) {
    if (!str) return 'Mixed';
    const s = str.toLowerCase();
    if (s.includes('solved') || s.includes('pyq') || s.includes('previous year') || s.includes('practice')) return 'PYQ';
    if (s.includes('guide') || s.includes('theory') || s.includes('manual') || s.includes('master')) return 'Theory';
    return 'Mixed';
}

function getFormatBadge(fmt) {
    if (!fmt) return '<span class="fmt-badge fmt-mixed">Mixed</span>';
    const f = fmt.toLowerCase();
    if (f.includes('pyq') || f.includes('solved') || f.includes('previous')) return '<span class="fmt-badge fmt-pyq">PYQ</span>';
    if (f.includes('theory') || f.includes('guide')) return '<span class="fmt-badge fmt-theory">Theory</span>';
    if (f.includes('smart')) return '<span class="fmt-badge fmt-smart">Smart</span>';
    if (f.includes('subject')) return '<span class="fmt-badge fmt-subject">Subject Wise</span>';
    return '<span class="fmt-badge fmt-mixed">Mixed</span>';
}

// ── Upcoming Exams ──────────────────────────────────────────────────────────
async function loadUpcomingExams() {
    try {
        const res = await fetch(`${API}/api/schedule/upcoming?limit=5`);
        const exams = await res.json();
        renderUpcomingCards(exams);
    } catch (err) {
        renderUpcomingEmpty();
    }
}

function renderUpcomingCards(exams) {
    const row = document.getElementById('upcomingExamsRow');
    if (!exams.length) { renderUpcomingEmpty(); return; }

    row.innerHTML = exams.map((e, i) => {
        const cat = getCategory(e.exam_name);
        const catClass = getCatClass(cat);
        const applicants = e.estimated_applicants || '';
        const barPct = parseApplicants(applicants);
        const isHighPriority = barPct > 60;
        const barColor = isHighPriority ? 'orange' : (barPct > 30 ? 'blue' : 'green');

        return `
            <div class="exam-card">
                <div class="exam-card-top">
                    <span class="cat-badge ${catClass}">${cat}</span>
                    ${isHighPriority ? '<span class="priority-badge priority-high">⚠ High Priority</span>' : ''}
                    <span class="exam-card-more">⋮</span>
                </div>
                <div class="exam-card-name">${e.exam_name}</div>
                <div class="exam-card-date">${e.expected_exam_date || 'Date TBD'}</div>
                <div class="exam-card-applicants">
                    <span>Est. Applicants</span>
                    <span>${applicants || '—'}</span>
                </div>
                <div class="exam-card-bar">
                    <div class="exam-card-bar-fill ${barColor}" style="width:${barPct}%"></div>
                </div>
                <button class="btn" onclick="analyzeExam('${e.exam_name}')">Analyze Market</button>
            </div>
        `;
    }).join('');
}

function renderUpcomingEmpty() {
    document.getElementById('upcomingExamsRow').innerHTML = `
        <div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-light);">
            <div style="font-size:32px; margin-bottom:12px; opacity:0.5;">📅</div>
            <h3 style="font-size:14px; font-weight:600; color:var(--text-mid);">No Upcoming Exams</h3>
            <p style="font-size:12px;">Exam schedule data will appear here once populated.</p>
        </div>`;
}

function analyzeExam(examName) {
    currentExam = examName;
    document.getElementById('examSelect').value = examName;
    loadExamData(examName);
    document.getElementById('examSelect').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function getCategory(name) {
    const n = name.toUpperCase();
    if (n.includes('SSC')) return 'SSC';
    if (n.includes('IBPS') || n.includes('SBI') || n.includes('RBI') || n.includes('NABARD')) return 'Banking';
    if (n.includes('RRB') || n.includes('RAILWAY') || n.includes('RPF')) return 'Railways';
    if (n.includes('UPSC')) return 'UPSC';
    if (n.includes('CTET') || n.includes('KVS') || n.includes('TET')) return 'Teaching';
    return 'Other';
}

function getCatClass(cat) {
    const m = { SSC: 'cat-ssc', Banking: 'cat-banking', Railways: 'cat-railways', UPSC: 'cat-upsc', Teaching: 'cat-teaching' };
    return m[cat] || 'cat-other';
}

function parseApplicants(str) {
    if (!str) return 20;
    const s = str.replace(/[~,]/g, '').toUpperCase();
    if (s.includes('CR')) return Math.min(parseFloat(s) * 30, 100);
    if (s.includes('M')) return Math.min(parseFloat(s) * 20, 100);
    if (s.includes('L')) return Math.min(parseFloat(s) * 3, 100);
    if (s.includes('K')) return Math.min(parseFloat(s) * 0.05, 100);
    return 20;
}

// ── Section Refresh ─────────────────────────────────────────────────────────
async function refreshSection(section) {
    addLogEntry('info', `Refreshing ${section}...`);

    switch (section) {
        case 'upcoming':
            try {
                const res = await fetch(`${API}/api/schedule/refresh`, { method: 'POST' });
                if (res.ok) {
                    await loadUpcomingExams();
                    addLogEntry('success', 'Exam schedule refreshed from sources.');
                }
            } catch (err) {
                addLogEntry('error', 'Failed to refresh schedule.');
            }
            break;
        case 'market':
        case 'pricing':
        case 'content':
            if (currentExam) {
                await loadTopBooks(currentExam);
                addLogEntry('success', `${section} data refreshed.`);
            } else {
                addLogEntry('warning', 'No exam selected.');
            }
            break;
        case 'sentiment':
            if (currentExam) {
                await loadExamData(currentExam);
                addLogEntry('success', 'Sentiment data refreshed.');
            } else {
                addLogEntry('warning', 'No exam selected.');
            }
            break;
        default:
            if (currentExam) {
                await loadExamData(currentExam);
                addLogEntry('success', `${section} data refreshed.`);
            } else {
                addLogEntry('warning', 'No exam selected.');
            }
    }
}

// ── CSV Downloads ───────────────────────────────────────────────────────────
function downloadCSV(section) {
    if (!currentExam && section !== 'schedule') {
        addLogEntry('warning', 'Select an exam first.');
        return;
    }
    const enc = encodeURIComponent(currentExam);
    let url = '';
    switch (section) {
        case 'schedule': url = `${API}/api/schedule/csv`; break;
        case 'products': url = `${API}/api/exams/${enc}/products/csv`; break;
        default:
            addLogEntry('info', `CSV export for "${section}" coming in Phase 5.`);
            return;
    }
    addLogEntry('info', `Downloading ${section} CSV...`);
    window.location.href = url;
}

// ── WebSocket Activity Log ──────────────────────────────────────────────────
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
        ws = new WebSocket(`${protocol}//${location.host}/ws/activity-log`);
        ws.onopen = () => { document.getElementById('activityDot').style.background = 'var(--green)'; };
        ws.onmessage = (e) => { appendLogEntry(JSON.parse(e.data)); };
        ws.onclose = () => {
            document.getElementById('activityDot').style.background = 'var(--red)';
            setTimeout(connectWebSocket, 3000);
        };
        ws.onerror = () => { document.getElementById('activityDot').style.background = 'var(--yellow)'; };
    } catch (err) {
        console.error('WebSocket failed:', err);
    }
}

function addLogEntry(level, message) {
    const icons = { info: 'ℹ', success: '✅', warning: '⚠️', error: '❌' };
    appendLogEntry({
        timestamp: new Date().toTimeString().slice(0, 8),
        step: '',
        message,
        level
    });
}

function appendLogEntry(entry) {
    const log = document.getElementById('activityLog');
    const div = document.createElement('div');
    div.className = 'log-entry';

    const icons = { info: 'ℹ', success: '✅', warning: '⚠', error: '✕' };
    const icon = icons[entry.level] || 'ℹ';
    const timeAgo = entry.timestamp || 'Just now';

    div.innerHTML = `
        <div class="log-icon ${entry.level || 'info'}">${icon}</div>
        <div>
            <div class="log-text">${entry.message}</div>
            <div class="log-time">${timeAgo}</div>
        </div>
    `;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function clearLog() {
    document.getElementById('activityLog').innerHTML = '';
    addLogEntry('info', 'Log cleared.');
}

// ── Utilities ───────────────────────────────────────────────────────────────
function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '...' : str;
}

function formatCount(n) {
    if (!n) return '0';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k+';
    return n.toString();
}
