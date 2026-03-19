/**
 * Book Launch Intelligence Dashboard — app.js
 * 3-tab layout: Competitor Analysis | Raw Reviews | Sentiment & Gaps
 */

const API = '';
let currentExam = null;
let currentProducts = [];
let ws = null;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadExamList();
    loadUpcomingExams();
    connectWebSocket();
});

// ── Exam Dropdown ─────────────────────────────────────────────────────────────
async function loadExamList() {
    try {
        const res = await fetch(`${API}/api/exams/list`);
        const exams = await res.json();
        const select = document.getElementById('examSelect');
        let hasSSC = false;
        exams.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
            if (name === 'SSC CGL') hasSSC = true;
        });
        
        // Default selection: SSC CGL
        if (hasSSC) {
            select.value = 'SSC CGL';
            onExamSelected();
        }
    } catch (err) { console.error('loadExamList:', err); }
}

function onExamSelected() {
    const val = document.getElementById('examSelect').value;
    if (val) {
        currentExam = val;
        loadExamData(currentExam);
    }
}

// ── Scrape ────────────────────────────────────────────────────────────────────
async function scrapeExam() {
    if (!currentExam) { addLogEntry('warning', 'Select an exam first.'); return; }
    const count = document.getElementById('productCount').value || 20;
    const btn = document.getElementById('scrapeBtn');
    if (btn) { btn.innerHTML = '⏳ Scraping...'; btn.disabled = true; }
    addLogEntry('info', `Starting scrape for "${currentExam}" — ${count} books + inline reviews...`);
    try {
        const res = await fetch(
            `${API}/api/exams/${encodeURIComponent(currentExam)}/scrape?max_results=${count}`,
            { method: 'POST' }
        );
        if (res.ok) {
            const data = await res.json();
            addLogEntry('success', `Done: ${data.total_saved} products, ${data.reviews_count || 0} reviews in ${data.duration_seconds}s.`);
            await loadExamData(currentExam);
        } else {
            addLogEntry('error', 'Scrape failed. Check logs.');
        }
    } catch (err) { addLogEntry('error', `Scrape error: ${err.message}`); }
    if (btn) { btn.innerHTML = '⚡ Scrape Data'; btn.disabled = false; }
}

// ── Sentiment Check ───────────────────────────────────────────────────────────
async function runSentimentCheck() {
    if (!currentExam) { addLogEntry('warning', 'Select an exam first.'); return; }
    const count = document.getElementById('productCount').value || 20;
    const btn = document.getElementById('sentimentBtn');
    if (btn) { btn.innerHTML = '⏳ Analyzing...'; btn.disabled = true; }
    addLogEntry('info', `Running Claude AI sentiment analysis for "${currentExam}"...`);
    switchTab('sentiment');
    try {
        const res = await fetch(
            `${API}/api/exams/${encodeURIComponent(currentExam)}/sentiment-check?num_products=${count}`,
            { method: 'POST' }
        );
        if (res.ok) {
            const data = await res.json();
            renderSentimentResults(data);
            addLogEntry('success', 'Sentiment analysis complete!');
        } else {
            const err = await res.json().catch(() => ({}));
            addLogEntry('error', `Sentiment failed: ${err.detail || 'Check API key and reviews.'}`);
        }
    } catch (err) { addLogEntry('error', `Sentiment error: ${err.message}`); }
    if (btn) { btn.innerHTML = '🧠 Sentiment Check'; btn.disabled = false; }
}

// ── Tab Switching ─────────────────────────────────────────────────────────────
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    const tabEl = document.querySelector(`.tab[data-tab="${tabName}"]`);
    if (tabEl) tabEl.classList.add('active');
    document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
    const panel = document.getElementById(`panel-${tabName}`);
    if (panel) panel.style.display = 'block';
}

// ── Load Exam Data ────────────────────────────────────────────────────────────
async function loadExamData(examName) {
    document.getElementById('analysisTabs').style.display = 'block';
    const noState = document.getElementById('noExamState');
    if (noState) noState.style.display = 'none';
    const sentBtn = document.getElementById('sentimentBtn');
    if (sentBtn) sentBtn.style.display = 'inline-flex';
    switchTab('competitor');
    addLogEntry('info', `Loading data for "${examName}"...`);

    try {
        // Load products (all, no limit)
        const prodRes = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/products`);
        if (prodRes.ok) {
            currentProducts = await prodRes.json();
            renderCompetitorAnalysis(currentProducts, examName);
            addLogEntry('success', `${currentProducts.length} products loaded.`);
        } else {
            currentProducts = [];
            resetCompetitorKPIs();
            addLogEntry('warning', `No data yet for "${examName}". Click ⚡ Scrape Data.`);
        }

        // Load KPI overview
        const ovRes = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/overview`);
        if (ovRes.ok) {
            const ov = await ovRes.json();
            updateTAM(ov);
        }

        // Load reviews
        await loadReviews(examName);

    } catch (err) {
        addLogEntry('error', `Failed to load: ${err.message}`);
    }
}

// ── Competitor Analysis Rendering ─────────────────────────────────────────────

function renderCompetitorAnalysis(products, examName) {
    if (!products || !products.length) {
        resetCompetitorKPIs();
        document.getElementById('masterTableBody').innerHTML =
            '<tr><td colspan="14" class="empty-state" style="padding:40px;">No data yet. Click ⚡ Scrape Data.</td></tr>';
        return;
    }

    const count = document.getElementById('productCount')?.value || 20;

    // ── KPI: Total, Rating, Price, Gap, BSR ──────────────────────────────────
    const total = products.length;
    document.getElementById('kpiTotal').textContent = total;

    const ratedProducts = products.filter(p => p.rating && p.rating > 0);
    const avgRating = ratedProducts.length
        ? (ratedProducts.reduce((s, p) => s + p.rating, 0) / ratedProducts.length).toFixed(1)
        : null;
    document.getElementById('kpiRating').innerHTML = avgRating
        ? `${avgRating}<span class="kpi-unit"> / 5</span>`
        : '—';
    document.getElementById('kpiRatingDesc').textContent =
        `${ratedProducts.length} rated of ${total} books.`;

    const priced = products.filter(p => p.price && p.price > 0);
    const avgPrice = priced.length
        ? Math.round(priced.reduce((s, p) => s + p.price, 0) / priced.length)
        : null;
    document.getElementById('kpiAvgPrice').textContent = avgPrice ? `₹${avgPrice}` : '—';

    // Best seller = highest rated + most reviewed — check its price vs avg
    const sortedByRating = [...products].filter(p => p.price > 0).sort(
        (a, b) => ((b.rating || 0) - (a.rating || 0)) || ((b.review_count || 0) - (a.review_count || 0))
    );
    if (sortedByRating.length && avgPrice) {
        const best = sortedByRating[0];
        const gap = Math.round(best.price - avgPrice);
        const sign = gap > 0 ? '+' : '';
        const color = gap < 0 ? 'var(--green)' : (gap > 0 ? 'var(--red)' : 'var(--text-main)');
        document.getElementById('kpiPriceGap').innerHTML =
            `<span style="color:${color};">${sign}₹${Math.abs(gap)}</span>`;
    } else {
        document.getElementById('kpiPriceGap').textContent = '—';
    }

    // Best BSR rank
    const withBSR = products
        .filter(p => p.best_seller_rank && /^\d+$/.test(String(p.best_seller_rank).trim()))
        .sort((a, b) => parseInt(a.best_seller_rank) - parseInt(b.best_seller_rank));
    if (withBSR.length) {
        const top = withBSR[0];
        document.getElementById('kpiTopBSR').innerHTML =
            `${top.amazon_rank || ('#' + top.best_seller_rank)}`;
    } else {
        document.getElementById('kpiTopBSR').textContent = '—';
    }

    // ── Charts ────────────────────────────────────────────────────────────────
    renderRatingsChart(products, count);
    renderFormatChart(products);
    renderLanguageChart(products);

    // ── Update chart subtitle ─────────────────────────────────────────────────
    const sub = document.getElementById('ratingChartSubtitle');
    if (sub) sub.textContent = `Top ${total} books`;

    // ── Master Table ──────────────────────────────────────────────────────────
    renderMasterTable(products, avgPrice);
}

function renderRatingsChart(products, count) {
    const total = products.length || 1;
    const r = { p45: 0, p40: 0, below: 0, unrated: 0 };
    products.forEach(p => {
        if (!p.rating || p.rating === 0) r.unrated++;
        else if (p.rating >= 4.5) r.p45++;
        else if (p.rating >= 4.0) r.p40++;
        else r.below++;
    });
    const pct = v => Math.round(v / total * 100);
    setStat('pct45plus', pct(r.p45) + '%', 'bar45plus', pct(r.p45));
    setStat('pct4to45',  pct(r.p40) + '%', 'bar4to45',  pct(r.p40));
    setStat('pctBelow4', pct(r.below) + '%','barBelow4', pct(r.below));
    setStat('pctUnrated',pct(r.unrated) + '%','barUnrated',pct(r.unrated));
}

function renderFormatChart(products) {
    const fmts = { PYQ: 0, Theory: 0, Mixed: 0 };
    products.forEach(p => { fmts[classifyFormat(p.book_format || p.title)]++; });
    const total = products.length || 1;
    setStat('pctPYQ',    Math.round(fmts.PYQ    / total * 100) + '%', 'barPYQ',    Math.round(fmts.PYQ    / total * 100));
    setStat('pctTheory', Math.round(fmts.Theory / total * 100) + '%', 'barTheory', Math.round(fmts.Theory / total * 100));
    setStat('pctMixed',  Math.round(fmts.Mixed  / total * 100) + '%', 'barMixed',  Math.round(fmts.Mixed  / total * 100));
}

function renderLanguageChart(products) {
    const langs = {};
    products.forEach(p => {
        const l = (p.language || '').trim();
        if (!l) return;
        // Normalize
        const key = l.split(/[,/]/)[0].trim() || 'Unknown';
        langs[key] = (langs[key] || 0) + 1;
    });
    const total = products.length || 1;
    const sorted = Object.entries(langs).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const container = document.getElementById('languageChart');
    if (!sorted.length) {
        container.innerHTML = '<p style="color:var(--text-light);font-size:12px;text-align:center;margin-top:20px;">No language data yet.</p>';
        return;
    }
    container.innerHTML = sorted.map(([lang, cnt]) => {
        const pct = Math.round(cnt / total * 100);
        return `
          <div>
            <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
              <span style="font-weight:500;">${lang}</span>
              <span style="color:var(--text-light);">${cnt} books (${pct}%)</span>
            </div>
            <div style="background:var(--border-light);border-radius:4px;height:6px;overflow:hidden;">
              <div style="background:var(--blue);height:100%;width:${pct}%;border-radius:4px;transition:width .5s;"></div>
            </div>
          </div>`;
    }).join('');
}

function setStat(textId, text, barId, pct) {
    const el = document.getElementById(textId);
    const bar = document.getElementById(barId);
    if (el) el.textContent = text;
    if (bar) bar.style.height = Math.max(pct * 1.2, 4) + 'px';
}

function renderMasterTable(products, avgPrice) {
    const tbody = document.getElementById('masterTableBody');
    tbody.innerHTML = products.map((p, i) => {
        // Rating — only show stars if rating > 0
        let ratingHtml = '—';
        if (p.rating && p.rating > 0) {
            const stars = '★'.repeat(Math.round(p.rating)) + '☆'.repeat(5 - Math.round(p.rating));
            ratingHtml = `<span style="color:#f59e0b;font-size:11px;">${stars}</span> <b>${p.rating}</b>`;
        }

        // BSR — prefer amazon_rank, fallback to best_seller_rank
        let bsr = '—';
        if (p.amazon_rank) {
            bsr = `<span style="font-size:11px;">${truncate(p.amazon_rank, 35)}</span>`;
        } else if (p.best_seller_rank) {
            bsr = `#${p.best_seller_rank}`;
        }

        // Price gap from avg
        let gapHtml = '—';
        if (p.price && avgPrice) {
            const diff = Math.round(p.price - avgPrice);
            const sign = diff > 0 ? '+' : '';
            const color = diff < 0 ? 'var(--green)' : (diff > 0 ? 'var(--red)' : 'var(--text-main)');
            gapHtml = `<span style="color:${color};font-weight:600;">${sign}₹${Math.abs(diff)}</span>`;
        }

        // Discount %
        let discHtml = '—';
        if (p.mrp && p.price && p.mrp > p.price) {
            const disc = Math.round((p.mrp - p.price) / p.mrp * 100);
            discHtml = `<span style="color:var(--green);font-weight:600;">${disc}% off</span>`;
        }

        const link = p.asin
            ? `https://www.amazon.in/dp/${p.asin}`
            : (p.product_url || null);

        return `
        <tr>
            <td style="color:var(--text-light);font-size:11px;">${i + 1}</td>
            <td style="max-width:220px;">
                <div style="font-weight:600;font-size:12px;line-height:1.4;">${truncate(p.title, 65)}</div>
                ${p.publisher ? `<div style="font-size:10px;color:var(--text-light);">${p.publisher}</div>` : ''}
            </td>
            <td style="font-size:12px;">${p.author || '—'}</td>
            <td style="font-size:12px;">${p.publisher || '—'}</td>
            <td>${getFormatBadge(p.book_format)}</td>
            <td style="font-size:12px;">${p.pages || '—'}</td>
            <td style="font-size:12px;">${(p.language || '').trim() || '—'}</td>
            <td style="font-size:12px;">${p.price ? `<b>₹${p.price}</b>` : '—'}</td>
            <td style="font-size:11px;color:var(--text-light);text-decoration:line-through;">${p.mrp ? `₹${p.mrp}` : '—'}</td>
            <td>${discHtml}</td>
            <td>${ratingHtml}${p.review_count ? `<div style="font-size:10px;color:var(--text-light);">(${formatCount(p.review_count)})</div>` : ''}</td>
            <td style="font-size:12px;">${p.review_count ? formatCount(p.review_count) : '—'}</td>
            <td style="font-size:11px;max-width:180px;">${bsr}</td>
            <td>${link ? `<a href="${link}" target="_blank" style="font-size:11px;color:var(--blue);">View →</a>` : '—'}</td>
        </tr>`;
    }).join('');
}

function updateTAM(ov) {
    const raw = ov?.estimated_applicants || ov?.exam?.estimated_applicants || '';
    const clean = raw ? raw.replace(/^[\-~\s]+/, '').trim() : '';
    document.getElementById('kpiTAM').innerHTML = clean || '—';
}

function resetCompetitorKPIs() {
    ['kpiTotal','kpiRating','kpiAvgPrice','kpiPriceGap','kpiTAM','kpiTopBSR'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
    });
    document.getElementById('masterTableBody').innerHTML =
        '<tr><td colspan="14" class="empty-state" style="padding:40px;">Select an exam and click ⚡ Scrape Data.</td></tr>';
}

// ── Sentiment Tab Rendering ───────────────────────────────────────────────────
function renderSentimentResults(data) {
    const emptyEl = document.getElementById('sentimentEmpty');
    const resultsEl = document.getElementById('sentimentResults');
    if (emptyEl) emptyEl.style.display = 'none';
    if (resultsEl) resultsEl.style.display = 'block';

    // Header
    const headerEl = document.getElementById('sentimentHeader');
    if (headerEl) {
        headerEl.textContent = `💬 Sentiment & Gap Analysis of ${data.books_with_reviews || data.num_products || ''} Books`;
    }

    // KPI cards
    const s = data.summary || {};
    document.getElementById('sentPositive').textContent = (s.positive_pct ?? '—') + (s.positive_pct != null ? '%' : '');
    document.getElementById('sentNeutral').textContent  = (s.neutral_pct  ?? '—') + (s.neutral_pct  != null ? '%' : '');
    document.getElementById('sentNegative').textContent = (s.negative_pct ?? '—') + (s.negative_pct != null ? '%' : '');

    const pBar = document.getElementById('sentPositiveBar');
    const nBar = document.getElementById('sentNeutralBar');
    const xBar = document.getElementById('sentNegativeBar');
    if (pBar) pBar.style.width = (s.positive_pct || 0) + '%';
    if (nBar) nBar.style.width = (s.neutral_pct  || 0) + '%';
    if (xBar) xBar.style.width = (s.negative_pct || 0) + '%';

    // Praises
    const praisesList = document.getElementById('praisesList');
    if (praisesList && data.top_praises) {
        praisesList.innerHTML = data.top_praises.map(p =>
            `<li style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:13px;">
                <span style="color:var(--green);margin-right:6px;">✓</span>
                <strong>${p.point}</strong>
                ${p.frequency ? `<span style="float:right;font-size:10px;color:var(--text-light);">${p.frequency}</span>` : ''}
                ${p.books?.length ? `<div style="font-size:11px;color:var(--text-light);margin-top:2px;">${p.books.join(', ')}</div>` : ''}
            </li>`
        ).join('');
    }

    // Complaints
    const complaintsList = document.getElementById('complaintsList');
    if (complaintsList && data.top_complaints) {
        complaintsList.innerHTML = data.top_complaints.map(c =>
            `<li style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:13px;">
                <span style="color:var(--red);margin-right:6px;">⚠</span>
                <strong>${c.point}</strong>
                ${c.frequency ? `<span style="float:right;font-size:10px;color:var(--text-light);">${c.frequency}</span>` : ''}
                ${c.books?.length ? `<div style="font-size:11px;color:var(--text-light);margin-top:2px;">${c.books.join(', ')}</div>` : ''}
            </li>`
        ).join('');
    }

    // Gaps
    const gapsList = document.getElementById('gapsList');
    if (gapsList && data.market_gaps) {
        gapsList.innerHTML = data.market_gaps.map(g =>
            `<li style="padding:10px 0;border-bottom:1px solid var(--border-light);">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <strong style="font-size:13px;">${g.gap}</strong>
                    <span class="cat-badge ${g.priority === 'High' ? 'cat-ssc' : (g.priority === 'Medium' ? 'cat-banking' : 'cat-other')}" style="font-size:10px;">${g.priority || ''}</span>
                </div>
                <p style="margin:0;font-size:12px;color:var(--text-mid);">${g.opportunity || ''}</p>
            </li>`
        ).join('');
    }

    // Positioning
    const posText = document.getElementById('positioningText');
    if (posText) posText.textContent = data.positioning_recommendation || '';
}

// ── Utility: Format + classify ─────────────────────────────────────────────────
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
    return '<span class="fmt-badge fmt-mixed">Mixed</span>';
}

function truncate(str, n) {
    if (!str) return '';
    return str.length > n ? str.slice(0, n) + '…' : str;
}

function formatCount(n) {
    if (!n) return '0';
    if (n >= 100000) return (n / 100000).toFixed(1) + 'L';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return n.toString();
}

// ── Raw Reviews ───────────────────────────────────────────────────────────────
async function loadReviews(examName) {
    try {
        const res = await fetch(`${API}/api/exams/${encodeURIComponent(examName)}/reviews`);
        if (!res.ok) { renderRawReviews([]); return; }
        renderRawReviews(await res.json());
    } catch { renderRawReviews([]); }
}

function renderRawReviews(reviews) {
    const tbody = document.getElementById('rawReviewsBody');
    if (!reviews || !reviews.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state" style="padding:40px;">No reviews yet. Run ⚡ Scrape Data — reviews are collected automatically.</td></tr>';
        return;
    }
    tbody.innerHTML = reviews.map(r => {
        const asin = r.asin;
        const link = asin ? `https://www.amazon.in/dp/${asin}` : (r.product_url || null);

        // Show raw float rating (e.g. 4.5) — not rounded whole number
        let ratingHtml = '—';
        if (r.rating && r.rating > 0) {
            const val = parseFloat(r.rating);
            const fullStars = Math.floor(val);
            const halfStar = (val - fullStars) >= 0.3 ? '½' : '';
            ratingHtml = `<span style="color:#f59e0b;">${'★'.repeat(fullStars)}${halfStar}</span> <b>${val}</b>`;
        }

        return `<tr>
            <td style="max-width:180px;font-size:12px;font-weight:600;">${truncate(r.product_title || '', 50)}</td>
            <td style="font-size:12px;">${r.author || '—'}</td>
            <td>${link ? `<a href="${link}" target="_blank" style="font-size:11px;color:var(--blue);">View →</a>` : '—'}</td>
            <td style="white-space:nowrap;">${ratingHtml}</td>
            <td style="max-width:340px;font-size:11px;color:var(--text-mid);">${truncate(r.content || '', 150)}</td>
            <td style="font-size:11px;white-space:nowrap;">${r.review_date || '—'}</td>
        </tr>`;
    }).join('');
}

function downloadReviewsCSV() {
    if (!currentExam) { addLogEntry('warning', 'Select an exam first.'); return; }
    window.location.href = `${API}/api/exams/${encodeURIComponent(currentExam)}/reviews/csv`;
}

// ── Section Refresh ───────────────────────────────────────────────────────────
async function refreshSection(section) {
    addLogEntry('info', `Refreshing ${section}...`);
    if (!currentExam) { addLogEntry('warning', 'No exam selected.'); return; }
    switch (section) {
        case 'competitor': renderCompetitorAnalysis(currentProducts); break;
        case 'reviews':    await loadReviews(currentExam); break;
        case 'upcoming':
            try {
                await fetch(`${API}/api/schedule/refresh`, { method: 'POST' });
                await loadUpcomingExams();
            } catch {}
            break;
        default: await loadExamData(currentExam);
    }
    addLogEntry('success', `${section} refreshed.`);
}

// ── CSV Downloads ─────────────────────────────────────────────────────────────
function downloadCSV(section) {
    if (!currentExam) { addLogEntry('warning', 'Select an exam first.'); return; }
    const enc = encodeURIComponent(currentExam);
    let url = '';
    switch (section) {
        case 'schedule': url = `${API}/api/schedule/csv`; break;
        case 'products': url = `${API}/api/exams/${enc}/products/csv`; break;
        case 'reviews':  url = `${API}/api/exams/${enc}/reviews/csv`; break;
        case 'sentiment': url = `${API}/api/exams/${enc}/analysis/csv`; break;
        default: addLogEntry('info', `CSV for "${section}" not yet available.`); return;
    }
    addLogEntry('info', `Downloading ${section} CSV...`);
    window.location.href = url;
}

// ── Upcoming Exams ────────────────────────────────────────────────────────────
async function loadUpcomingExams() {
    try {
        const res = await fetch(`${API}/api/schedule/all`);
        const allExams = await res.json();
        const today = new Date(); today.setHours(0, 0, 0, 0);
        let valid = allExams.map(e => ({ ...e, _date: parseExamDate(e.expected_exam_date, e.exam_name) }))
            .filter(e => e._date === null || e._date >= today)
            .sort((a, b) => a._date - b._date)  // Ascending: soonest first
            .slice(0, 6);
        renderUpcomingCards(valid);
    } catch { renderUpcomingEmpty(); }
}

function parseExamDate(dateStr, examName) {
    if (!dateStr || dateStr === 'Not Available' || dateStr.toLowerCase().includes('soon')) return null;
    let norm = dateStr.trim();
    const currentYear = new Date().getFullYear();
    const yearM = norm.match(/\b(\d{4})\b/);
    if (yearM && parseInt(yearM[1]) < currentYear) return new Date(0);
    norm = norm.replace(/(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s+([a-zA-Z]+)/i, '$2 $3');
    const dmY = norm.match(/\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b/);
    if (dmY) norm = `${dmY[3]}-${dmY[2].padStart(2,'0')}-${dmY[1].padStart(2,'0')}`;
    const d = new Date(norm);
    return isNaN(d.getTime()) ? null : d;
}

async function refreshUpcomingExams() {
    const btn = document.getElementById('dashboardRefreshBtn');
    if (btn) { btn.innerHTML = '🔄 Scraping...'; btn.disabled = true; }
    try { await fetch(`${API}/api/schedule/refresh`, { method: 'POST' }); } catch {}
    if (btn) { btn.innerHTML = '🔄 Refresh'; btn.disabled = false; }
    await loadUpcomingExams();
}

function renderUpcomingCards(exams) {
    const row = document.getElementById('upcomingExamsRow');
    if (!exams.length) { renderUpcomingEmpty(); return; }
    row.innerHTML = exams.map(e => {
        const cat = getCategory(e.exam_name);
        const catClass = getCatClass(cat);
        const vacancy = e.vacancy_posts && e.vacancy_posts !== 'Not Available' ? e.vacancy_posts : null;
        const examDate = e.expected_exam_date && e.expected_exam_date !== 'Not Available' ? e.expected_exam_date : 'Not Available';
        const raw = e.estimated_applicants || '';
        const tam = raw ? raw.replace(/^[\-~\s]+/, '').trim() : '';
        return `<div class="exam-card">
            <div class="exam-card-top">
                <span class="cat-badge ${catClass}">${cat}</span>
                ${e.conducting_body ? `<span style="font-size:11px;color:var(--text-light);">${e.conducting_body}</span>` : ''}
                <span class="exam-card-more">⋮</span>
            </div>
            <div class="exam-card-name">${e.exam_name}</div>
            <div class="exam-card-date">${examDate}</div>
            <div class="exam-card-applicants">
                <span>Vacancy</span>
                <span>${vacancy || '<em style="color:var(--text-light)">Not Available</em>'}</span>
            </div>
            <div class="exam-card-applicants" style="margin-top:2px;">
                <span>Est. TAM</span>
                <span>${tam || '<em style="color:var(--text-light)">—</em>'}</span>
            </div>
            <div class="exam-card-bar">
                <div class="exam-card-bar-fill blue" style="width:${vacancy ? Math.min(parseInt(vacancy.replace(/,/g, ''))/500,100) : 0}%"></div>
            </div>
            ${e.source_url ? `<div style="font-size:11px;margin:6px 0;"><a href="${e.source_url}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none;">🔗 Verify on SarkariResult</a></div>` : ''}
            <div style="font-size:11px;color:var(--text-light);margin-bottom:12px;">Last Update: ${e.last_update_date && e.last_update_date !== 'Not Available' ? e.last_update_date : '—'}</div>
            <button class="btn" onclick="analyzeExam('${e.exam_name}')">Analyze Market</button>
        </div>`;
    }).join('');
}

function renderUpcomingEmpty() {
    document.getElementById('upcomingExamsRow').innerHTML =
        '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-light);"><div style="font-size:32px;margin-bottom:12px;">📅</div><h3 style="font-size:14px;">No Upcoming Exams</h3><p style="font-size:12px;">Exam schedule will appear here once populated.</p></div>';
}

function analyzeExam(examName) {
    const select = document.getElementById('examSelect');
    let best = '';
    for (let i = 0; i < select.options.length; i++) {
        const v = select.options[i].value;
        if (v && examName.includes(v) && v.length > best.length) best = v;
    }
    const final = best || examName;
    currentExam = final;
    select.value = final;
    loadExamData(final);
    select.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
    return { SSC:'cat-ssc', Banking:'cat-banking', Railways:'cat-railways', UPSC:'cat-upsc', Teaching:'cat-teaching' }[cat] || 'cat-other';
}

// ── WebSocket Log ─────────────────────────────────────────────────────────────
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
        ws = new WebSocket(`${protocol}//${location.host}/ws/activity-log`);
        ws.onopen = () => { document.getElementById('activityDot').style.background = 'var(--green)'; };
        ws.onclose = () => {
            document.getElementById('activityDot').style.background = 'var(--border-strong)';
            setTimeout(connectWebSocket, 3000);
        };
        ws.onerror = () => {};
        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                addLogEntry(msg.level || 'info', `[${msg.step || 'System'}] ${msg.message}`);
            } catch {}
        };
    } catch {}
}

function addLogEntry(type, message) {
    const log = document.getElementById('activityLog');
    if (!log) return;
    const icons = { info: 'ℹ', success: '✔', warning: '⚠', error: '✖' };
    const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <div class="log-icon ${type}">${icons[type] || 'ℹ'}</div>
        <div>
            <div class="log-text">${message}</div>
            <div class="log-time">${now}</div>
        </div>`;
    log.insertBefore(entry, log.firstChild);
    if (log.children.length > 80) log.removeChild(log.lastChild);
}

function clearLog() {
    const log = document.getElementById('activityLog');
    if (log) log.innerHTML = '';
}
