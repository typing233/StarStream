import { api } from './app.js';

export async function renderLibrary(container) {
    container.innerHTML = `
        <div class="page-header">
            <h2>目录管理</h2>
        </div>
        <div class="add-library-form">
            <h3 style="margin-bottom:1rem">添加媒体目录</h3>
            <div class="form-row">
                <div class="form-group">
                    <label>目录名称</label>
                    <input type="text" id="lib-name" placeholder="例如：电影">
                </div>
                <div class="form-group">
                    <label>目录路径</label>
                    <input type="text" id="lib-path" placeholder="例如：/home/user/movies">
                </div>
                <button id="add-lib-btn" class="btn" style="margin-bottom:0">添加</button>
            </div>
            <div id="lib-error" class="error-msg hidden"></div>
        </div>
        <div id="library-list" class="library-list">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    `;

    document.getElementById('add-lib-btn').addEventListener('click', addLibrary);
    loadLibraries();
}

async function loadLibraries() {
    const listEl = document.getElementById('library-list');
    try {
        const res = await api('/api/libraries');
        const libraries = await res.json();
        if (libraries.length === 0) {
            listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">📁</div><p>还没有添加媒体目录</p></div>`;
            return;
        }
        listEl.innerHTML = libraries.map(lib => `
            <div class="library-item">
                <div class="library-item-info">
                    <h3>${escapeHtml(lib.name)}</h3>
                    <p>${escapeHtml(lib.path)} ${lib.last_scanned ? '· 上次扫描: ' + new Date(lib.last_scanned).toLocaleString() : '· 扫描中...'}</p>
                </div>
                <div class="library-item-actions">
                    <button class="btn btn-sm btn-outline" onclick="window._rescanLib(${lib.id})">重新扫描</button>
                    <button class="btn btn-sm btn-danger" onclick="window._deleteLib(${lib.id})">删除</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        listEl.innerHTML = '<p class="error-msg">加载失败</p>';
    }
}

async function addLibrary() {
    const name = document.getElementById('lib-name').value.trim();
    const path = document.getElementById('lib-path').value.trim();
    const errorEl = document.getElementById('lib-error');

    if (!name || !path) {
        errorEl.textContent = '请填写名称和路径';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const res = await api('/api/libraries', {
            method: 'POST',
            body: JSON.stringify({ name, path }),
        });
        if (!res.ok) {
            const data = await res.json();
            errorEl.textContent = data.detail || '添加失败';
            errorEl.classList.remove('hidden');
            return;
        }
        errorEl.classList.add('hidden');
        document.getElementById('lib-name').value = '';
        document.getElementById('lib-path').value = '';
        loadLibraries();
    } catch (e) {
        errorEl.textContent = '网络错误';
        errorEl.classList.remove('hidden');
    }
}

window._rescanLib = async function(id) {
    await api(`/api/libraries/${id}/scan`, { method: 'POST' });
    loadLibraries();
};

window._deleteLib = async function(id) {
    if (!confirm('确定删除此目录？所有相关媒体记录将被清除。')) return;
    await api(`/api/libraries/${id}`, { method: 'DELETE' });
    loadLibraries();
};

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
