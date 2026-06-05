import { api } from './app.js';
import { showToast } from './toast.js';

let currentTab = 'users';

export async function renderAdmin(container) {
    container.innerHTML = `
        <div class="page-header">
            <h2>系统管理</h2>
        </div>
        <div class="admin-tabs">
            <button class="tab-btn active" data-tab="users">用户管理</button>
            <button class="tab-btn" data-tab="plugins">插件</button>
            <button class="tab-btn" data-tab="system">系统信息</button>
            <button class="tab-btn" data-tab="logs">活动日志</button>
        </div>
        <div id="admin-content" class="admin-content"></div>
    `;

    container.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.dataset.tab;
            loadTab();
        });
    });

    loadTab();
}

function loadTab() {
    switch (currentTab) {
        case 'users': loadUsersTab(); break;
        case 'plugins': loadPluginsTab(); break;
        case 'system': loadSystemTab(); break;
        case 'logs': loadLogsTab(); break;
    }
}

async function loadUsersTab() {
    const content = document.getElementById('admin-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const res = await api('/api/v1/admin/users');
        const users = await res.json();

        content.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>用户名</th>
                        <th>角色</th>
                        <th>创建时间</th>
                        <th>媒体库数</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    ${users.map(u => `
                        <tr>
                            <td>${u.id}</td>
                            <td>${escapeHtml(u.username)}</td>
                            <td><span class="role-badge role-${u.role}">${u.role}</span></td>
                            <td>${u.created_at ? new Date(u.created_at).toLocaleDateString('zh-CN') : '-'}</td>
                            <td>${u.library_count}</td>
                            <td class="actions-cell">
                                ${u.role === 'user'
                                    ? `<button class="btn btn-sm" onclick="window._adminAction('promote', ${u.id})">升级管理员</button>`
                                    : `<button class="btn btn-sm btn-outline" onclick="window._adminAction('demote', ${u.id})">降为用户</button>`
                                }
                                <button class="btn btn-sm btn-danger" onclick="window._adminAction('delete', ${u.id})">删除</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (e) {
        content.innerHTML = '<p class="error-msg">加载用户列表失败</p>';
    }
}

window._adminAction = async function(action, userId) {
    if (action === 'delete' && !confirm('确定要删除此用户吗？其所有媒体库也将被删除。')) return;

    try {
        let res;
        if (action === 'promote') {
            res = await api(`/api/v1/admin/users/${userId}/role`, {
                method: 'PUT', body: JSON.stringify({ role: 'admin' })
            });
        } else if (action === 'demote') {
            res = await api(`/api/v1/admin/users/${userId}/role`, {
                method: 'PUT', body: JSON.stringify({ role: 'user' })
            });
        } else if (action === 'delete') {
            res = await api(`/api/v1/admin/users/${userId}`, { method: 'DELETE' });
        }

        if (res.ok) {
            showToast('操作成功', 'success');
            loadUsersTab();
        } else {
            const err = await res.json();
            showToast(err.detail || '操作失败', 'error');
        }
    } catch (e) {
        showToast('操作失败', 'error');
    }
};

async function loadPluginsTab() {
    const content = document.getElementById('admin-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const res = await api('/api/v1/admin/plugins');
        const plugins = await res.json();

        if (plugins.length === 0) {
            content.innerHTML = `
                <div class="empty-state" style="padding:2rem">
                    <p>暂无已安装插件</p>
                    <p style="font-size:0.85rem;color:var(--text-secondary);margin-top:0.5rem">
                        将插件目录放入 plugins/ 文件夹即可
                    </p>
                </div>
            `;
            return;
        }

        content.innerHTML = `
            <div class="plugin-list">
                ${plugins.map(p => `
                    <div class="plugin-item">
                        <div class="plugin-info">
                            <h4>${escapeHtml(p.name)} <span class="plugin-version">v${p.version}</span></h4>
                            <p>${escapeHtml(p.description)}</p>
                            ${p.error ? `<p class="error-msg" style="font-size:0.8rem">${escapeHtml(p.error)}</p>` : ''}
                        </div>
                        <div class="plugin-actions">
                            <label class="toggle-switch">
                                <input type="checkbox" ${p.enabled ? 'checked' : ''}
                                    onchange="window._togglePlugin('${escapeHtml(p.name)}', this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        content.innerHTML = '<p class="error-msg">加载插件列表失败</p>';
    }
}

window._togglePlugin = async function(name, enabled) {
    try {
        const action = enabled ? 'enable' : 'disable';
        const res = await api(`/api/v1/admin/plugins/${name}/${action}`, { method: 'POST' });
        if (res.ok) {
            showToast(`插件 ${name} 已${enabled ? '启用' : '禁用'}`, 'success');
        } else {
            showToast('操作失败', 'error');
            loadPluginsTab();
        }
    } catch (e) {
        showToast('操作失败', 'error');
        loadPluginsTab();
    }
};

async function loadSystemTab() {
    const content = document.getElementById('admin-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const res = await api('/api/v1/admin/stats');
        const stats = await res.json();

        content.innerHTML = `
            <div class="system-info">
                <div class="info-grid">
                    <div class="info-card">
                        <div class="info-value">${stats.total_users}</div>
                        <div class="info-label">注册用户</div>
                    </div>
                    <div class="info-card">
                        <div class="info-value">${stats.total_libraries}</div>
                        <div class="info-label">媒体库</div>
                    </div>
                    <div class="info-card">
                        <div class="info-value">${stats.total_media}</div>
                        <div class="info-label">媒体文件</div>
                    </div>
                    <div class="info-card">
                        <div class="info-value">${formatSize(stats.total_storage_bytes)}</div>
                        <div class="info-label">存储用量</div>
                    </div>
                </div>
                <h4 style="margin-top:1.5rem;margin-bottom:0.75rem">类型分布</h4>
                <div class="info-grid">
                    ${Object.entries(stats.media_by_type || {}).map(([type, count]) => `
                        <div class="info-card">
                            <div class="info-value">${count}</div>
                            <div class="info-label">${getTypeLabel(type)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } catch (e) {
        content.innerHTML = '<p class="error-msg">加载系统信息失败</p>';
    }
}

async function loadLogsTab() {
    const content = document.getElementById('admin-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const res = await api('/api/v1/admin/activity?per_page=50');
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            content.innerHTML = '<div class="empty-state" style="padding:2rem"><p>暂无活动记录</p></div>';
            return;
        }

        content.innerHTML = `
            <table class="admin-table">
                <thead>
                    <tr>
                        <th>时间</th>
                        <th>用户</th>
                        <th>操作</th>
                        <th>详情</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.items.map(log => `
                        <tr>
                            <td>${log.created_at ? new Date(log.created_at).toLocaleString('zh-CN') : '-'}</td>
                            <td>${escapeHtml(log.username || '-')}</td>
                            <td><span class="action-badge">${escapeHtml(log.action)}</span></td>
                            <td class="details-cell">${log.details_json ? escapeHtml(JSON.stringify(log.details_json).slice(0, 80)) : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${data.total_pages > 1 ? `<p style="margin-top:1rem;color:var(--text-secondary);font-size:0.85rem">显示最近 ${data.items.length} 条 / 共 ${data.total} 条</p>` : ''}
        `;
    } catch (e) {
        content.innerHTML = '<p class="error-msg">加载日志失败</p>';
    }
}

function getTypeLabel(type) {
    const labels = { video: '视频', audio: '音乐', image: '图片', ebook: '电子书' };
    return labels[type] || type;
}

function formatSize(bytes) {
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(1) + ' GB';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
