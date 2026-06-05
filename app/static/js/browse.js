import { api, navigate } from './app.js';
import { showToast } from './toast.js';

let currentFilter = null;
let currentSearch = '';
let currentSort = 'title';
let currentOrder = 'asc';
let currentPage = 1;
let totalPages = 0;

export async function renderBrowse(container) {
    container.innerHTML = `
        <div class="breadcrumb">首页 / 媒体库</div>
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
        <div class="search-sort-bar">
            <div class="search-bar">
                <input type="text" id="search-input" placeholder="搜索媒体..." value="${escapeHtml(currentSearch)}">
                <button class="btn" id="search-btn">搜索</button>
            </div>
            <div class="sort-controls">
                <select id="sort-select">
                    <option value="title" ${currentSort === 'title' ? 'selected' : ''}>按名称</option>
                    <option value="created_at" ${currentSort === 'created_at' ? 'selected' : ''}>按添加时间</option>
                    <option value="file_size" ${currentSort === 'file_size' ? 'selected' : ''}>按大小</option>
                    <option value="year" ${currentSort === 'year' ? 'selected' : ''}>按年份</option>
                </select>
                <button class="btn btn-sm btn-outline" id="order-btn">${currentOrder === 'asc' ? '↑' : '↓'}</button>
            </div>
        </div>
        <div id="media-grid" class="media-grid">
            <div class="loading"><div class="spinner"></div></div>
        </div>
        <div id="pagination" class="pagination hidden"></div>
    `;

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.type || null;
            currentPage = 1;
            loadMedia();
        });
    });

    document.getElementById('search-btn').addEventListener('click', () => {
        currentSearch = document.getElementById('search-input').value.trim();
        currentPage = 1;
        loadMedia();
    });

    document.getElementById('search-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            currentSearch = e.target.value.trim();
            currentPage = 1;
            loadMedia();
        }
    });

    document.getElementById('sort-select').addEventListener('change', (e) => {
        currentSort = e.target.value;
        currentPage = 1;
        loadMedia();
    });

    document.getElementById('order-btn').addEventListener('click', () => {
        currentOrder = currentOrder === 'asc' ? 'desc' : 'asc';
        document.getElementById('order-btn').textContent = currentOrder === 'asc' ? '↑' : '↓';
        currentPage = 1;
        loadMedia();
    });

    loadStats();
    loadMedia();
}

async function loadStats() {
    try {
        const res = await api('/api/v1/media/stats');
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
    params.set('sort_by', currentSort);
    params.set('sort_order', currentOrder);
    params.set('page', currentPage);
    params.set('per_page', '60');

    try {
        const res = await api(`/api/v1/media?${params}`);
        const data = await res.json();
        const items = data.items || [];
        totalPages = data.total_pages || 0;

        if (items.length === 0) {
            gridEl.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">🎬</div><p>没有找到媒体文件<br>请先在"目录管理"中添加媒体目录</p></div>`;
            updatePagination();
            return;
        }

        gridEl.innerHTML = items.map(item => `
            <div class="media-card" onclick="window.location.hash='#/play/${item.id}'">
                <div class="media-card-cover">
                    ${item.cover_path
                        ? `<img src="/api/v1/stream/thumbnail/${item.cover_path}" alt="" loading="lazy">`
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

        updatePagination();
    } catch (e) {
        gridEl.innerHTML = '<p class="error-msg">加载失败</p>';
    }
}

function updatePagination() {
    const paginationEl = document.getElementById('pagination');
    if (totalPages <= 1) {
        paginationEl.classList.add('hidden');
        return;
    }
    paginationEl.classList.remove('hidden');
    paginationEl.innerHTML = `
        <button class="btn btn-sm btn-outline" ${currentPage <= 1 ? 'disabled' : ''} id="prev-page">上一页</button>
        <span class="page-info">第 ${currentPage} / ${totalPages} 页</span>
        <button class="btn btn-sm btn-outline" ${currentPage >= totalPages ? 'disabled' : ''} id="next-page">下一页</button>
    `;
    document.getElementById('prev-page')?.addEventListener('click', () => {
        if (currentPage > 1) { currentPage--; loadMedia(); }
    });
    document.getElementById('next-page')?.addEventListener('click', () => {
        if (currentPage < totalPages) { currentPage++; loadMedia(); }
    });
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
