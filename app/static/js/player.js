import { api, getToken } from './app.js';

export async function renderPlayer(container, mediaId) {
    if (!mediaId) {
        container.innerHTML = '<p>无效的媒体ID</p>';
        return;
    }

    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const res = await api(`/api/media/${mediaId}`);
        if (!res.ok) {
            container.innerHTML = '<p class="error-msg">媒体不存在</p>';
            return;
        }
        const item = await res.json();

        switch (item.media_type) {
            case 'video':
                renderVideoPlayer(container, item);
                break;
            case 'audio':
                renderAudioPlayer(container, item);
                break;
            case 'image':
                renderImageViewer(container, item);
                break;
            case 'ebook':
                renderEbookViewer(container, item);
                break;
            default:
                container.innerHTML = '<p>不支持的媒体类型</p>';
        }
    } catch (e) {
        container.innerHTML = '<p class="error-msg">加载失败</p>';
    }
}

function renderVideoPlayer(container, item) {
    const token = getToken();
    const streamUrl = `/api/stream/file/${item.id}`;

    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
            </div>
            <div class="video-wrapper">
                <video id="video-el" preload="metadata"></video>
            </div>
            <div class="player-controls">
                <button id="play-btn" class="btn btn-sm">▶</button>
                <div class="progress-bar" id="progress-bar">
                    <div class="progress-fill" id="progress-fill"></div>
                </div>
                <span class="time-display" id="time-display">0:00 / 0:00</span>
                <button id="fullscreen-btn" class="btn btn-sm btn-outline">⛶</button>
            </div>
            <div class="player-info">
                <h2>${escapeHtml(item.title)}</h2>
                <p style="color:var(--text-secondary);margin-top:0.3rem">
                    ${item.year ? item.year + ' · ' : ''}
                    ${item.duration ? formatDuration(item.duration) : ''}
                    ${item.metadata_json?.resolution ? ' · ' + item.metadata_json.resolution : ''}
                    ${item.metadata_json?.codec ? ' · ' + item.metadata_json.codec : ''}
                </p>
                <div class="player-options">
                    <div>
                        <label style="font-size:0.8rem;color:var(--text-secondary)">画质</label>
                        <select id="resolution-select">
                            <option value="original">原始</option>
                            <option value="1080p">1080p</option>
                            <option value="720p">720p</option>
                            <option value="480p">480p</option>
                            <option value="360p">360p</option>
                        </select>
                    </div>
                    <div id="audio-track-container" class="hidden">
                        <label style="font-size:0.8rem;color:var(--text-secondary)">音轨</label>
                        <select id="audio-track-select"></select>
                    </div>
                    <div id="subtitle-container" class="hidden">
                        <label style="font-size:0.8rem;color:var(--text-secondary)">字幕</label>
                        <select id="subtitle-select"></select>
                    </div>
                </div>
            </div>
        </div>
    `;

    const video = document.getElementById('video-el');
    const playBtn = document.getElementById('play-btn');
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const timeDisplay = document.getElementById('time-display');
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const resolutionSelect = document.getElementById('resolution-select');

    function loadSource(resolution, audioTrack = 0) {
        const currentTime = video.currentTime;
        if (resolution === 'original') {
            video.src = streamUrl + `?token=${token}`;
        } else {
            video.src = `/api/stream/transcode/${item.id}?resolution=${resolution}&audio_track=${audioTrack}&token=${token}`;
        }
        video.currentTime = currentTime;
        video.play().catch(() => {});
    }

    // Use fetch with auth header workaround: set src with token param
    // We need a custom approach since video element can't send auth headers
    video.src = streamUrl + `?token=${token}`;

    playBtn.addEventListener('click', () => {
        if (video.paused) { video.play(); playBtn.textContent = '⏸'; }
        else { video.pause(); playBtn.textContent = '▶'; }
    });

    video.addEventListener('play', () => playBtn.textContent = '⏸');
    video.addEventListener('pause', () => playBtn.textContent = '▶');

    video.addEventListener('timeupdate', () => {
        if (video.duration) {
            const pct = (video.currentTime / video.duration) * 100;
            progressFill.style.width = pct + '%';
            timeDisplay.textContent = `${formatDuration(video.currentTime)} / ${formatDuration(video.duration)}`;
        }
    });

    progressBar.addEventListener('click', (e) => {
        const rect = progressBar.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        video.currentTime = pct * video.duration;
    });

    fullscreenBtn.addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.querySelector('.video-wrapper').requestFullscreen();
    });

    resolutionSelect.addEventListener('change', () => {
        const audioSelect = document.getElementById('audio-track-select');
        const audioTrack = audioSelect ? parseInt(audioSelect.value) || 0 : 0;
        loadSource(resolutionSelect.value, audioTrack);
    });

    loadTracks(item.id);
}

async function loadTracks(mediaId) {
    try {
        const token = getToken();
        const res = await fetch(`/api/stream/tracks/${mediaId}?token=${token}`);
        const tracks = await res.json();

        if (tracks.audio_tracks && tracks.audio_tracks.length > 1) {
            const container = document.getElementById('audio-track-container');
            const select = document.getElementById('audio-track-select');
            container.classList.remove('hidden');
            select.innerHTML = tracks.audio_tracks.map((t, i) =>
                `<option value="${i}">${t.title} (${t.language})</option>`
            ).join('');

            select.addEventListener('change', () => {
                const resSelect = document.getElementById('resolution-select');
                const video = document.getElementById('video-el');
                if (resSelect.value !== 'original') {
                    const currentTime = video.currentTime;
                    video.src = `/api/stream/transcode/${mediaId}?resolution=${resSelect.value}&audio_track=${select.value}&token=${getToken()}`;
                    video.currentTime = currentTime;
                    video.play().catch(() => {});
                }
            });
        }

        if (tracks.subtitle_tracks && tracks.subtitle_tracks.length > 0) {
            const container = document.getElementById('subtitle-container');
            const select = document.getElementById('subtitle-select');
            container.classList.remove('hidden');
            select.innerHTML = `<option value="">关闭</option>` +
                tracks.subtitle_tracks.map(t =>
                    `<option value="${t.index}">${t.title} (${t.language})</option>`
                ).join('');

            select.addEventListener('change', () => {
                const video = document.getElementById('video-el');
                // Remove existing tracks
                video.querySelectorAll('track').forEach(t => t.remove());
                if (select.value) {
                    const track = document.createElement('track');
                    track.kind = 'subtitles';
                    track.src = `/api/stream/subtitle/${mediaId}/${select.value}?token=${getToken()}`;
                    track.default = true;
                    video.appendChild(track);
                    video.textTracks[0].mode = 'showing';
                }
            });
        }
    } catch (e) {}
}

function renderAudioPlayer(container, item) {
    const token = getToken();
    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
            </div>
            <div class="audio-player">
                <div class="audio-cover">
                    ${item.cover_path
                        ? `<img src="/api/stream/thumbnail/${item.cover_path}" alt="">`
                        : `<span style="font-size:5rem">🎵</span>`
                    }
                </div>
                <h2>${escapeHtml(item.title)}</h2>
                <p style="color:var(--text-secondary);margin:0.5rem 0">
                    ${item.metadata_json?.artist ? item.metadata_json.artist + ' · ' : ''}
                    ${item.metadata_json?.album || ''}
                    ${item.year ? ' · ' + item.year : ''}
                </p>
                <audio id="audio-el" preload="metadata" src="/api/stream/file/${item.id}?token=${token}"></audio>
                <div class="player-controls" style="margin-top:1.5rem;max-width:500px;margin-left:auto;margin-right:auto">
                    <button id="play-btn" class="btn btn-sm">▶</button>
                    <div class="progress-bar" id="progress-bar">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                    <span class="time-display" id="time-display">0:00 / 0:00</span>
                </div>
            </div>
        </div>
    `;

    const audio = document.getElementById('audio-el');
    const playBtn = document.getElementById('play-btn');
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const timeDisplay = document.getElementById('time-display');

    playBtn.addEventListener('click', () => {
        if (audio.paused) { audio.play(); playBtn.textContent = '⏸'; }
        else { audio.pause(); playBtn.textContent = '▶'; }
    });

    audio.addEventListener('timeupdate', () => {
        if (audio.duration) {
            progressFill.style.width = (audio.currentTime / audio.duration) * 100 + '%';
            timeDisplay.textContent = `${formatDuration(audio.currentTime)} / ${formatDuration(audio.duration)}`;
        }
    });

    progressBar.addEventListener('click', (e) => {
        const rect = progressBar.getBoundingClientRect();
        audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
    });
}

function renderImageViewer(container, item) {
    const token = getToken();
    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
            </div>
            <div class="image-viewer">
                <img src="/api/stream/file/${item.id}?token=${token}" alt="${escapeHtml(item.title)}">
            </div>
            <div class="player-info">
                <h2>${escapeHtml(item.title)}</h2>
                <p style="color:var(--text-secondary);margin-top:0.3rem">
                    ${item.metadata_json?.resolution || ''} · ${formatFileSize(item.file_size)}
                </p>
            </div>
        </div>
    `;
}

function renderEbookViewer(container, item) {
    const token = getToken();
    const ext = item.file_path?.split('.').pop()?.toLowerCase();

    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
            </div>
            <div class="player-info" style="margin-bottom:1rem">
                <h2>${escapeHtml(item.title)}</h2>
                <p style="color:var(--text-secondary)">
                    ${item.year ? item.year + ' · ' : ''}${ext?.toUpperCase()} · ${formatFileSize(item.file_size)}
                </p>
            </div>
            <div class="ebook-viewer">
                ${ext === 'pdf'
                    ? `<iframe src="/api/stream/file/${item.id}?token=${token}#toolbar=1"></iframe>`
                    : `<div style="padding:2rem;text-align:center">
                        <p>此格式需要下载阅读</p>
                        <a href="/api/stream/file/${item.id}?token=${token}" class="btn" style="margin-top:1rem" download>下载文件</a>
                      </div>`
                }
            </div>
        </div>
    `;
}

function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    return `${m}:${String(s).padStart(2,'0')}`;
}

function formatFileSize(bytes) {
    if (!bytes) return '';
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
