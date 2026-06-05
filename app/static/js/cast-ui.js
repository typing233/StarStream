import { api, getToken } from './app.js';
import { showToast } from './toast.js';

let castModal = null;

export function showCastModal(mediaId) {
    if (castModal) castModal.remove();

    castModal = document.createElement('div');
    castModal.className = 'modal-overlay';
    castModal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>投屏到设备</h3>
                <button class="modal-close btn btn-sm btn-outline">&times;</button>
            </div>
            <div class="modal-body">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>
    `;
    document.body.appendChild(castModal);

    castModal.querySelector('.modal-close').addEventListener('click', closeCastModal);
    castModal.addEventListener('click', (e) => {
        if (e.target === castModal) closeCastModal();
    });

    loadDevices(mediaId);
}

function closeCastModal() {
    if (castModal) {
        castModal.remove();
        castModal = null;
    }
}

async function loadDevices(mediaId) {
    const body = castModal.querySelector('.modal-body');
    try {
        const res = await api('/api/v1/cast/devices');
        const data = await res.json();
        const devices = data.devices || [];

        if (devices.length === 0) {
            body.innerHTML = `
                <div class="empty-state" style="padding:1rem">
                    <p>未发现可用设备</p>
                    <p style="font-size:0.8rem;color:var(--text-secondary);margin-top:0.5rem">
                        请确保设备与服务器在同一局域网内
                    </p>
                </div>
            `;
            return;
        }

        body.innerHTML = `
            <div class="device-list">
                ${devices.map(d => `
                    <div class="device-item" data-id="${d.id}">
                        <span class="device-icon">${d.type === 'chromecast' ? '📺' : '🔊'}</span>
                        <div class="device-info">
                            <span class="device-name">${escapeHtml(d.name)}</span>
                            <span class="device-type">${d.type === 'chromecast' ? 'Chromecast' : 'DLNA'}</span>
                        </div>
                        <button class="btn btn-sm cast-to-btn">投屏</button>
                    </div>
                `).join('')}
            </div>
        `;

        body.querySelectorAll('.cast-to-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const item = e.target.closest('.device-item');
                const deviceId = item.dataset.id;
                btn.disabled = true;
                btn.textContent = '连接中...';
                try {
                    const castRes = await api('/api/v1/cast/play', {
                        method: 'POST',
                        body: JSON.stringify({ device_id: deviceId, media_id: mediaId }),
                    });
                    if (castRes.ok) {
                        showToast('投屏成功', 'success');
                        closeCastModal();
                    } else {
                        const err = await castRes.json();
                        showToast(err.detail || '投屏失败', 'error');
                        btn.disabled = false;
                        btn.textContent = '投屏';
                    }
                } catch (e) {
                    showToast('投屏失败', 'error');
                    btn.disabled = false;
                    btn.textContent = '投屏';
                }
            });
        });
    } catch (e) {
        body.innerHTML = '<p class="error-msg">设备发现失败</p>';
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
