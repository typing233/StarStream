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
    const streamUrl = `/api/stream/file/${item.id}?token=${token}`;

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
                <button id="volume-btn" class="btn btn-sm btn-outline">🔊</button>
                <input type="range" id="volume-slider" min="0" max="1" step="0.05" value="1" style="width:60px">
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
                <div class="player-options" id="player-options">
                    <div>
                        <label style="font-size:0.8rem;color:var(--text-secondary)">画质</label>
                        <select id="resolution-select">
                            <option value="original" selected>原始画质</option>
                            <option value="1080p">1080p</option>
                            <option value="720p">720p</option>
                            <option value="480p">480p</option>
                            <option value="360p">360p</option>
                        </select>
                    </div>
                    <div id="audio-track-wrapper" class="hidden">
                        <label style="font-size:0.8rem;color:var(--text-secondary)">音轨</label>
                        <select id="audio-track-select"></select>
                    </div>
                    <div id="subtitle-wrapper" class="hidden">
                        <label style="font-size:0.8rem;color:var(--text-secondary)">字幕</label>
                        <select id="subtitle-select"></select>
                    </div>
                </div>
                <div id="track-status" style="margin-top:0.5rem;font-size:0.8rem;color:var(--success)" class="hidden"></div>
            </div>
        </div>
    `;

    const video = document.getElementById('video-el');
    const playBtn = document.getElementById('play-btn');
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const timeDisplay = document.getElementById('time-display');
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const volumeSlider = document.getElementById('volume-slider');
    const resolutionSelect = document.getElementById('resolution-select');

    let currentResolution = 'original';
    let currentAudioTrack = 0;

    video.src = streamUrl;

    function reloadWithSettings() {
        const wasPlaying = !video.paused;
        const currentTime = video.currentTime;

        if (currentResolution === 'original') {
            video.src = `/api/stream/file/${item.id}?token=${token}`;
        } else {
            video.src = `/api/stream/transcode/${item.id}?resolution=${currentResolution}&audio_track=${currentAudioTrack}&token=${token}`;
        }

        video.addEventListener('loadedmetadata', function onMeta() {
            video.removeEventListener('loadedmetadata', onMeta);
            if (currentResolution === 'original') {
                video.currentTime = currentTime;
            }
            if (wasPlaying) video.play().catch(() => {});
        });
        video.load();
    }

    playBtn.addEventListener('click', () => {
        if (video.paused) { video.play(); playBtn.textContent = '⏸'; }
        else { video.pause(); playBtn.textContent = '▶'; }
    });

    video.addEventListener('play', () => playBtn.textContent = '⏸');
    video.addEventListener('pause', () => playBtn.textContent = '▶');

    video.addEventListener('timeupdate', () => {
        if (video.duration && isFinite(video.duration)) {
            const pct = (video.currentTime / video.duration) * 100;
            progressFill.style.width = pct + '%';
            timeDisplay.textContent = `${formatDuration(video.currentTime)} / ${formatDuration(video.duration)}`;
        }
    });

    progressBar.addEventListener('click', (e) => {
        if (video.duration && isFinite(video.duration)) {
            const rect = progressBar.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            video.currentTime = pct * video.duration;
        }
    });

    volumeSlider.addEventListener('input', () => {
        video.volume = parseFloat(volumeSlider.value);
    });

    fullscreenBtn.addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.querySelector('.video-wrapper').requestFullscreen();
    });

    resolutionSelect.addEventListener('change', () => {
        currentResolution = resolutionSelect.value;
        showTrackStatus(`切换画质: ${currentResolution === 'original' ? '原始' : currentResolution}`);
        reloadWithSettings();
    });

    loadTracksForVideo(item.id, token, (audioIdx) => {
        currentAudioTrack = audioIdx;
        if (currentResolution !== 'original') {
            showTrackStatus(`切换音轨: Track ${audioIdx + 1}`);
            reloadWithSettings();
        } else {
            showTrackStatus('音轨切换需要选择非原始画质（转码模式下生效）');
        }
    });
}

function showTrackStatus(msg) {
    const el = document.getElementById('track-status');
    if (el) {
        el.textContent = msg;
        el.classList.remove('hidden');
        setTimeout(() => el.classList.add('hidden'), 3000);
    }
}

async function loadTracksForVideo(mediaId, token, onAudioChange) {
    try {
        const res = await fetch(`/api/stream/tracks/${mediaId}?token=${token}`);
        if (!res.ok) return;
        const tracks = await res.json();

        if (tracks.audio_tracks && tracks.audio_tracks.length > 0) {
            const wrapper = document.getElementById('audio-track-wrapper');
            const select = document.getElementById('audio-track-select');
            wrapper.classList.remove('hidden');
            select.innerHTML = tracks.audio_tracks.map((t, i) =>
                `<option value="${i}">${t.title} [${t.language}] (${t.codec}, ${t.channels}ch)</option>`
            ).join('');

            select.addEventListener('change', () => {
                onAudioChange(parseInt(select.value));
            });
        }

        if (tracks.subtitle_tracks && tracks.subtitle_tracks.length > 0) {
            const wrapper = document.getElementById('subtitle-wrapper');
            const select = document.getElementById('subtitle-select');
            wrapper.classList.remove('hidden');
            select.innerHTML = `<option value="">关闭字幕</option>` +
                tracks.subtitle_tracks.map(t =>
                    `<option value="${t.index}">${t.title} [${t.language}] (${t.codec})</option>`
                ).join('');

            select.addEventListener('change', () => {
                const video = document.getElementById('video-el');
                // Remove all existing text tracks
                while (video.querySelector('track')) {
                    video.querySelector('track').remove();
                }
                // Clear existing textTracks display
                for (let i = 0; i < video.textTracks.length; i++) {
                    video.textTracks[i].mode = 'disabled';
                }

                if (select.value) {
                    const trackEl = document.createElement('track');
                    trackEl.kind = 'subtitles';
                    trackEl.label = select.options[select.selectedIndex].text;
                    trackEl.srclang = 'und';
                    trackEl.src = `/api/stream/subtitle/${mediaId}/${select.value}?token=${token}`;
                    trackEl.default = true;
                    video.appendChild(trackEl);

                    // Force the new track to show
                    setTimeout(() => {
                        if (video.textTracks.length > 0) {
                            video.textTracks[video.textTracks.length - 1].mode = 'showing';
                        }
                    }, 100);

                    showTrackStatus(`字幕已开启: ${select.options[select.selectedIndex].text}`);
                } else {
                    showTrackStatus('字幕已关闭');
                }
            });
        }
    } catch (e) {
        console.error('Failed to load tracks:', e);
    }
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
                    ${item.metadata_json?.artist && item.metadata_json.artist !== 'unknown' ? item.metadata_json.artist : ''}
                    ${item.metadata_json?.album && item.metadata_json.album !== 'unknown' ? ' · ' + item.metadata_json.album : ''}
                    ${item.year ? ' · ' + item.year : ''}
                </p>
                <audio id="audio-el" preload="metadata" src="/api/stream/file/${item.id}?token=${token}"></audio>
                <div class="player-controls" style="margin-top:1.5rem;max-width:500px;margin-left:auto;margin-right:auto">
                    <button id="play-btn" class="btn btn-sm">▶</button>
                    <div class="progress-bar" id="progress-bar">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                    <span class="time-display" id="time-display">0:00 / 0:00</span>
                    <input type="range" id="volume-slider" min="0" max="1" step="0.05" value="1" style="width:60px">
                </div>
            </div>
        </div>
    `;

    const audio = document.getElementById('audio-el');
    const playBtn = document.getElementById('play-btn');
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const timeDisplay = document.getElementById('time-display');
    const volumeSlider = document.getElementById('volume-slider');

    playBtn.addEventListener('click', () => {
        if (audio.paused) { audio.play(); playBtn.textContent = '⏸'; }
        else { audio.pause(); playBtn.textContent = '▶'; }
    });

    audio.addEventListener('play', () => playBtn.textContent = '⏸');
    audio.addEventListener('pause', () => playBtn.textContent = '▶');

    audio.addEventListener('timeupdate', () => {
        if (audio.duration && isFinite(audio.duration)) {
            progressFill.style.width = (audio.currentTime / audio.duration) * 100 + '%';
            timeDisplay.textContent = `${formatDuration(audio.currentTime)} / ${formatDuration(audio.duration)}`;
        }
    });

    progressBar.addEventListener('click', (e) => {
        if (audio.duration && isFinite(audio.duration)) {
            const rect = progressBar.getBoundingClientRect();
            audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
        }
    });

    volumeSlider.addEventListener('input', () => {
        audio.volume = parseFloat(volumeSlider.value);
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
    const format = (item.metadata_json?.format || '').toLowerCase();
    const fileUrl = `/api/stream/file/${item.id}?token=${token}`;

    let viewerContent = '';

    if (format === 'pdf') {
        // Use browser's native PDF viewer via object/embed with fallback
        viewerContent = `
            <div class="ebook-viewer" id="pdf-viewer-container">
                <object data="${fileUrl}" type="application/pdf" width="100%" style="height:80vh;border-radius:var(--radius)">
                    <embed src="${fileUrl}" type="application/pdf" width="100%" style="height:80vh">
                        <p style="padding:2rem;text-align:center">
                            浏览器不支持内嵌PDF预览。
                            <a href="${fileUrl}" class="btn" style="margin-top:1rem" target="_blank">在新标签打开PDF</a>
                        </p>
                    </embed>
                </object>
            </div>
        `;
    } else if (format === 'epub') {
        viewerContent = `
            <div class="ebook-viewer" id="epub-viewer">
                <div style="padding:2rem;text-align:center">
                    <div class="loading"><div class="spinner"></div></div>
                    <p style="margin-top:1rem">正在加载EPUB...</p>
                </div>
            </div>
        `;
    } else {
        viewerContent = `
            <div class="ebook-viewer">
                <div style="padding:2rem;text-align:center">
                    <p style="font-size:1.1rem;margin-bottom:1rem">${format.toUpperCase()} 格式电子书</p>
                    <p style="color:var(--text-secondary)">此格式暂不支持在线预览，请下载后使用专用阅读器打开</p>
                    <a href="${fileUrl}" class="btn" style="margin-top:1.5rem" download>下载文件 (${formatFileSize(item.file_size)})</a>
                </div>
            </div>
        `;
    }

    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
                ${format === 'pdf' ? `<a href="${fileUrl}" target="_blank" class="btn btn-outline btn-sm" style="margin-left:0.5rem">在新标签打开</a>` : ''}
            </div>
            <div class="player-info" style="margin-bottom:1rem">
                <h2>${escapeHtml(item.title)}</h2>
                <p style="color:var(--text-secondary)">
                    ${item.year ? item.year + ' · ' : ''}${format.toUpperCase()} · ${formatFileSize(item.file_size)}
                    ${item.metadata_json?.pages && item.metadata_json.pages !== 'unknown' ? ' · ' + item.metadata_json.pages + ' 页' : ''}
                </p>
            </div>
            ${viewerContent}
        </div>
    `;

    if (format === 'epub') {
        loadEpub(fileUrl);
    }
}

async function loadEpub(fileUrl) {
    const viewer = document.getElementById('epub-viewer');
    try {
        const res = await fetch(fileUrl);
        if (!res.ok) throw new Error('fetch failed');

        viewer.innerHTML = `
            <div style="padding:2rem;text-align:center">
                <p style="margin-bottom:1rem">EPUB 文件已加载</p>
                <p style="color:var(--text-secondary);margin-bottom:1.5rem">由于浏览器限制，EPUB需使用专用阅读器。</p>
                <a href="${fileUrl}" class="btn" download>下载 EPUB</a>
                <a href="${fileUrl}" class="btn btn-outline" style="margin-left:0.5rem" target="_blank">尝试打开</a>
            </div>
        `;
    } catch (e) {
        viewer.innerHTML = `<p class="error-msg" style="padding:2rem">加载失败</p>`;
    }
}

function formatDuration(seconds) {
    if (!seconds || !isFinite(seconds)) return '0:00';
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
