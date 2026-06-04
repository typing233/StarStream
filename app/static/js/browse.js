import { api, navigate } from './app.js';

let currentFilter = null;
let currentSearch = '';

export async function renderBrowse(container) {
    container.innerHTML = `
        <div class="page-header">
            <h2>媒体库</h2>
            <div class="filters">
                <button class="filter-btn active" data-type="">全部</button>
                <button class="filter-btn" data-type="video">视频</button>
                <button class="filter-btn" data-type="audio">音乐</button>
                <button class="filter-btn" data-type="image">图片</button>
                <button class="filter-btn" data-type="ebook">电子书</button>
            </div>
        </div>
        <div id="stats-area" class="stats-grid"></div>
        <div class="search-bar">
            <input type="text" id="search-input" placeholder="搜索媒体..." value="${escapeHtml(currentSearch)}">
            <button class="btn" id="search-btn">搜索</button>
        </div>
        <div id="media-grid" class="media-grid">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    `;

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.type || null;
            loadMedia();
        });
    });

    document.getElementById('search-btn').addEventListener('click', () => {
        currentSearch = document.getElementById('search-input').value.trim();
        loadMedia();
    });

    document.getElementById('search-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            currentSearch = e.target.value.trim();
            loadMedia();
        }
    });

    loadStats();
    loadMedia();
}

async function loadStats() {
    try {
        const res = await api('/api/media/stats');
        const stats = await res.json();
        document.getElementById('stats-area').innerHTML = `
            <div class="stat-card"><div class="stat-value">${stats.total}</div><div class="stat-label">总计</div></div>
            <div class="stat-card"><div class="stat-value">${stats.video}</div><div class="stat-label">视频</div></div>
            <div class="stat-card"><div class="stat-value">${stats.audio}</div><div class="stat-label">音乐</div></div>
            <div class="stat-card"><div class="stat-value">${stats.image}</div><div class="stat-label">图片</div></div>
            <div class="stat-card"><div class="stat-value">${stats.ebook}</div><div class="stat-label">电子书</div></div>
        `;
    } catch (e) {}
}

async function loadMedia() {
    const gridEl = document.getElementById('media-grid');
    gridEl.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    const params = new URLSearchParams();
    if (currentFilter) params.set('media_type', currentFilter);
    if (currentSearch) params.set('search', currentSearch);
    params.set('per_page', '100');

    try {
        const res = await api(`/api/media?${params}`);
        const items = await res.json();

        if (items.length === 0) {
            gridEl.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">🎬</div><p>没有找到媒体文件<br>请先在"目录管理"中添加媒体目录</p></div>`;
            return;
        }

        gridEl.innerHTML = items.map(item => `
            <div class="media-card" onclick="window.location.hash='#/play/${item.id}'">
                <div class="media-card-cover">
                    ${item.cover_path
                        ? `<img src="/api/stream/thumbnail/${item.cover_path}" alt="" loading="lazy">`
                        : `<span class="placeholder-icon">${getTypeIcon(item.media_type)}</span>`
                    }
                </div>
                <div class="media-card-info">
                    <div class="media-card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
                    <div class="media-card-meta">
                        <span class="media-type-badge badge-${item.media_type}">${getTypeLabel(item.media_type)}</span>
                        ${item.year ? ` · ${item.year}` : ''}
                        ${item.duration ? ` · ${formatDuration(item.duration)}` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        gridEl.innerHTML = '<p class="error-msg">加载失败</p>';
    }
}

function getTypeIcon(type) {
    switch (type) {
        case 'video': return '🎬';
        case 'audio': return '🎵';
        case 'image': return '🖼️';
        case 'ebook': return '📖';
        default: return '📁';
    }
}

function getTypeLabel(type) {
    switch (type) {
        case 'video': return '视频';
        case 'audio': return '音乐';
        case 'image': return '图片';
        case 'ebook': return '电子书';
        default: return type;
    }
}

function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    return `${m}:${String(s).padStart(2,'0')}`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
