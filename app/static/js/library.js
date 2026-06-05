import { api } from './app.js';

export async function renderLibrary(container) {
    container.innerHTML = `
        <div class="page-header">
            <h2>目录管理</h2>
        </div>
        <div class="add-library-form">
            <h3 style="margin-bottom:1rem">添加媒体目录</h3>
            <div class="form-group">
                <label>目录名称</label>
                <input type="text" id="lib-name" placeholder="例如：电影、音乐">
            </div>
            <div class="form-group">
                <label>选择目录 <span id="selected-path-display" style="color:var(--accent)"></span></label>
                <div class="dir-browser" id="dir-browser">
                    <div class="dir-browser-header">
                        <button id="dir-up-btn" class="btn btn-sm btn-outline">&uarr; 上级</button>
                        <span id="dir-current-path" class="dir-path-text"></span>
                    </div>
                    <div id="dir-list" class="dir-list"></div>
                </div>
            </div>
            <input type="hidden" id="lib-path" value="">
            <div style="display:flex;gap:0.5rem;margin-top:1rem">
                <button id="select-dir-btn" class="btn" disabled>选择当前目录</button>
                <button id="add-lib-btn" class="btn" disabled style="opacity:0.5">添加并扫描</button>
            </div>
            <div id="lib-error" class="error-msg hidden"></div>
        </div>
        <div id="library-list" class="library-list">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    `;

    document.getElementById('dir-up-btn').addEventListener('click', goUp);
    document.getElementById('select-dir-btn').addEventListener('click', selectCurrentDir);
    document.getElementById('add-lib-btn').addEventListener('click', addLibrary);

    browseTo('');
    loadLibraries();
}

let currentBrowsePath = '';

async function browseTo(path) {
    const listEl = document.getElementById('dir-list');
    listEl.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const params = path ? `?path=${encodeURIComponent(path)}` : '';
        const res = await api(`/api/v1/libraries/browse${params}`);
        const data = await res.json();
        if (!res.ok) {
            listEl.innerHTML = `<p class="error-msg">${data.detail || '无法访问'}</p>`;
            return;
        }

        currentBrowsePath = data.current;
        document.getElementById('dir-current-path').textContent = data.current;
        document.getElementById('select-dir-btn').disabled = false;

        if (data.directories.length === 0) {
            listEl.innerHTML = '<p style="padding:0.5rem;color:var(--text-secondary)">此目录下没有子目录</p>';
        } else {
            listEl.innerHTML = data.directories.map(d => `
                <div class="dir-item" data-path="${escapeAttr(d.path)}">
                    <span class="dir-icon">📁</span>
                    <span class="dir-name">${escapeHtml(d.name)}</span>
                </div>
            `).join('');

            listEl.querySelectorAll('.dir-item').forEach(item => {
                item.addEventListener('click', () => browseTo(item.dataset.path));
            });
        }
    } catch (e) {
        listEl.innerHTML = '<p class="error-msg">加载目录失败</p>';
    }
}

function goUp() {
    const parts = currentBrowsePath.split('/');
    if (parts.length > 1) {
        const parent = parts.slice(0, -1).join('/') || '/';
        browseTo(parent);
    }
}

function selectCurrentDir() {
    document.getElementById('lib-path').value = currentBrowsePath;
    document.getElementById('selected-path-display').textContent = `已选择: ${currentBrowsePath}`;
    const addBtn = document.getElementById('add-lib-btn');
    addBtn.disabled = false;
    addBtn.style.opacity = '1';
}

async function addLibrary() {
    const name = document.getElementById('lib-name').value.trim();
    const path = document.getElementById('lib-path').value;
    const errorEl = document.getElementById('lib-error');

    if (!path) {
        errorEl.textContent = '请先选择一个目录';
        errorEl.classList.remove('hidden');
        return;
    }
    if (!name) {
        const parts = path.split('/');
        document.getElementById('lib-name').value = parts[parts.length - 1] || 'Media';
    }

    const finalName = document.getElementById('lib-name').value.trim() || 'Media';

    try {
        const res = await api('/api/v1/libraries', {
            method: 'POST',
            body: JSON.stringify({ name: finalName, path }),
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
        document.getElementById('selected-path-display').textContent = '';
        const addBtn = document.getElementById('add-lib-btn');
        addBtn.disabled = true;
        addBtn.style.opacity = '0.5';
        loadLibraries();
    } catch (e) {
        errorEl.textContent = '网络错误';
        errorEl.classList.remove('hidden');
    }
}

async function loadLibraries() {
    const listEl = document.getElementById('library-list');
    try {
        const res = await api('/api/v1/libraries');
        const libraries = await res.json();
        if (libraries.length === 0) {
            listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">📁</div><p>还没有添加媒体目录<br>请在上方浏览并选择一个目录</p></div>`;
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

window._rescanLib = async function(id) {
    await api(`/api/v1/libraries/${id}/scan`, { method: 'POST' });
    loadLibraries();
};

window._deleteLib = async function(id) {
    if (!confirm('确定删除此目录？所有相关媒体记录将被清除。')) return;
    await api(`/api/v1/libraries/${id}`, { method: 'DELETE' });
    loadLibraries();
};

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}
