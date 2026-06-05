import { api, getToken } from './app.js';
import { showToast } from './toast.js';
import { showCastModal } from './cast-ui.js';

let playStartTime = 0;
let currentMediaId = null;

export async function renderPlayer(container, mediaId) {
    if (!mediaId) {
        container.innerHTML = '<p>无效的媒体ID</p>';
        return;
    }

    currentMediaId = parseInt(mediaId);
    playStartTime = Date.now();
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const res = await api(`/api/v1/media/${mediaId}`);
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

function reportPlayActivity(mediaId, durationWatched, completed = false) {
    try {
        api('/api/v1/activity/play', {
            method: 'POST',
            body: JSON.stringify({
                media_id: mediaId,
                duration_watched: Math.round(durationWatched),
                completed,
            }),
        });
    } catch (e) {}
}

function renderVideoPlayer(container, item) {
    const token = getToken();
    const streamUrl = `/api/v1/stream/file/${item.id}?token=${token}`;

    const srcRes = item.metadata_json?.resolution || '';
    let autoResolution = '720p';
    if (srcRes) {
        const height = parseInt(srcRes.split('x')[1]) || 0;
        if (height <= 480) autoResolution = '480p';
        else if (height <= 720) autoResolution = '720p';
        else autoResolution = '1080p';
    }

    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
                <button class="btn btn-sm btn-outline" id="cast-btn" style="margin-left:0.5rem">📺 投屏</button>
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
            <div class="keyboard-hints">
                <span>空格:播放/暂停</span> <span>←→:快进退5s</span> <span>↑↓:音量</span> <span>F:全屏</span> <span>M:静音</span>
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
    let totalDuration = item.duration || 0;
    let transcodeStartTime = 0;

    video.src = streamUrl;

    document.getElementById('cast-btn').addEventListener('click', () => showCastModal(item.id));

    function buildTranscodeUrl(seekTime) {
        const res = currentResolution === 'original' ? autoResolution : currentResolution;
        let url = `/api/v1/stream/transcode/${item.id}?resolution=${res}&audio_track=${currentAudioTrack}&token=${token}`;
        if (seekTime > 0) url += `&start_time=${seekTime.toFixed(2)}`;
        return url;
    }

    function switchToTranscode(seekTime) {
        transcodeStartTime = seekTime;
        video.src = buildTranscodeUrl(seekTime);
        video.load();
        video.play().catch(() => {});
        if (currentResolution === 'original') {
            currentResolution = autoResolution;
            resolutionSelect.value = autoResolution;
        }
    }

    function reloadWithSettings() {
        const seekTime = getEffectiveTime();
        if (currentResolution === 'original' && currentAudioTrack === 0) {
            transcodeStartTime = 0;
            video.src = streamUrl;
            video.load();
            video.addEventListener('loadedmetadata', function onMeta() {
                video.removeEventListener('loadedmetadata', onMeta);
                video.currentTime = seekTime;
                video.play().catch(() => {});
            });
        } else {
            switchToTranscode(seekTime);
        }
    }

    function getEffectiveTime() {
        if (transcodeStartTime > 0) {
            return transcodeStartTime + (video.currentTime || 0);
        }
        return video.currentTime || 0;
    }

    playBtn.addEventListener('click', () => {
        if (video.paused) { video.play(); playBtn.textContent = '⏸'; }
        else { video.pause(); playBtn.textContent = '▶'; }
    });

    video.addEventListener('play', () => playBtn.textContent = '⏸');
    video.addEventListener('pause', () => playBtn.textContent = '▶');

    video.addEventListener('loadedmetadata', () => {
        if (currentResolution === 'original' && video.duration && isFinite(video.duration)) {
            totalDuration = video.duration;
        }
    });

    video.addEventListener('timeupdate', () => {
        const effectiveTime = getEffectiveTime();
        const dur = totalDuration || item.duration || 0;
        if (dur > 0) {
            const pct = (effectiveTime / dur) * 100;
            progressFill.style.width = Math.min(pct, 100) + '%';
            timeDisplay.textContent = `${formatDuration(effectiveTime)} / ${formatDuration(dur)}`;
        }
    });

    video.addEventListener('ended', () => {
        reportPlayActivity(item.id, getEffectiveTime(), true);
    });

    progressBar.addEventListener('click', (e) => {
        const dur = totalDuration || item.duration || 0;
        if (dur <= 0) return;
        const rect = progressBar.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        const seekTime = pct * dur;

        if (currentResolution === 'original' && currentAudioTrack === 0) {
            video.currentTime = seekTime;
        } else {
            switchToTranscode(seekTime);
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

    // Keyboard shortcuts
    function handleKeyboard(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        switch (e.key) {
            case ' ':
                e.preventDefault();
                if (video.paused) video.play(); else video.pause();
                break;
            case 'ArrowLeft':
                e.preventDefault();
                if (currentResolution === 'original' && currentAudioTrack === 0) {
                    video.currentTime = Math.max(0, video.currentTime - 5);
                }
                break;
            case 'ArrowRight':
                e.preventDefault();
                if (currentResolution === 'original' && currentAudioTrack === 0) {
                    video.currentTime = Math.min(video.duration || 0, video.currentTime + 5);
                }
                break;
            case 'ArrowUp':
                e.preventDefault();
                video.volume = Math.min(1, video.volume + 0.1);
                volumeSlider.value = video.volume;
                break;
            case 'ArrowDown':
                e.preventDefault();
                video.volume = Math.max(0, video.volume - 0.1);
                volumeSlider.value = video.volume;
                break;
            case 'f': case 'F':
                if (document.fullscreenElement) document.exitFullscreen();
                else document.querySelector('.video-wrapper')?.requestFullscreen();
                break;
            case 'm': case 'M':
                video.muted = !video.muted;
                break;
        }
    }
    document.addEventListener('keydown', handleKeyboard);

    // Clean up on page change
    const cleanup = () => {
        document.removeEventListener('keydown', handleKeyboard);
        window.removeEventListener('hashchange', cleanup);
        const watched = getEffectiveTime();
        if (watched > 5) reportPlayActivity(item.id, watched, false);
    };
    window.addEventListener('hashchange', cleanup);

    loadTracksForVideo(item.id, token, (audioIdx) => {
        currentAudioTrack = audioIdx;
        showTrackStatus(`正在切换到音轨 ${audioIdx + 1}...`);
        const seekTime = getEffectiveTime();
        switchToTranscode(seekTime);
        showTrackStatus(`已切换音轨 ${audioIdx + 1}`);
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
        const res = await fetch(`/api/v1/stream/tracks/${mediaId}?token=${token}`);
        if (!res.ok) return;
        const tracks = await res.json();

        if (tracks.audio_tracks && tracks.audio_tracks.length > 0) {
            const wrapper = document.getElementById('audio-track-wrapper');
            const select = document.getElementById('audio-track-select');
            wrapper.classList.remove('hidden');
            select.innerHTML = tracks.audio_tracks.map((t, i) =>
                `<option value="${i}">${t.title} [${t.language}] (${t.codec}, ${t.channels}ch)</option>`
            ).join('');
            select.addEventListener('change', () => onAudioChange(parseInt(select.value)));
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
                while (video.querySelector('track')) video.querySelector('track').remove();
                for (let i = 0; i < video.textTracks.length; i++) video.textTracks[i].mode = 'disabled';

                if (select.value) {
                    const trackEl = document.createElement('track');
                    trackEl.kind = 'subtitles';
                    trackEl.label = select.options[select.selectedIndex].text;
                    trackEl.srclang = 'und';
                    trackEl.src = `/api/v1/stream/subtitle/${mediaId}/${select.value}?token=${token}`;
                    trackEl.default = true;
                    video.appendChild(trackEl);
                    setTimeout(() => {
                        if (video.textTracks.length > 0) video.textTracks[video.textTracks.length - 1].mode = 'showing';
                    }, 100);
                    showTrackStatus(`字幕已开启: ${select.options[select.selectedIndex].text}`);
                } else {
                    showTrackStatus('字幕已关闭');
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
                <button class="btn btn-sm btn-outline" id="cast-btn" style="margin-left:0.5rem">📺 投屏</button>
            </div>
            <div class="audio-player">
                <div class="audio-cover">
                    ${item.cover_path
                        ? `<img src="/api/v1/stream/thumbnail/${item.cover_path}" alt="">`
                        : `<span style="font-size:5rem">🎵</span>`
                    }
                </div>
                <h2>${escapeHtml(item.title)}</h2>
                <p style="color:var(--text-secondary);margin:0.5rem 0">
                    ${item.metadata_json?.artist && item.metadata_json.artist !== 'unknown' ? item.metadata_json.artist : ''}
                    ${item.metadata_json?.album && item.metadata_json.album !== 'unknown' ? ' · ' + item.metadata_json.album : ''}
                    ${item.year ? ' · ' + item.year : ''}
                </p>
                <audio id="audio-el" preload="metadata" src="/api/v1/stream/file/${item.id}?token=${token}"></audio>
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

    document.getElementById('cast-btn').addEventListener('click', () => showCastModal(item.id));

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

    audio.addEventListener('ended', () => {
        reportPlayActivity(item.id, audio.duration || 0, true);
    });

    progressBar.addEventListener('click', (e) => {
        if (audio.duration && isFinite(audio.duration)) {
            const rect = progressBar.getBoundingClientRect();
            audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
        }
    });

    volumeSlider.addEventListener('input', () => { audio.volume = parseFloat(volumeSlider.value); });

    // Keyboard
    function handleKeyboard(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        switch (e.key) {
            case ' ':
                e.preventDefault();
                if (audio.paused) audio.play(); else audio.pause();
                break;
            case 'ArrowLeft': e.preventDefault(); audio.currentTime = Math.max(0, audio.currentTime - 5); break;
            case 'ArrowRight': e.preventDefault(); audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 5); break;
            case 'ArrowUp': e.preventDefault(); audio.volume = Math.min(1, audio.volume + 0.1); volumeSlider.value = audio.volume; break;
            case 'ArrowDown': e.preventDefault(); audio.volume = Math.max(0, audio.volume - 0.1); volumeSlider.value = audio.volume; break;
            case 'm': case 'M': audio.muted = !audio.muted; break;
        }
    }
    document.addEventListener('keydown', handleKeyboard);
    const cleanup = () => {
        document.removeEventListener('keydown', handleKeyboard);
        window.removeEventListener('hashchange', cleanup);
        if (audio.currentTime > 5) reportPlayActivity(item.id, audio.currentTime, false);
    };
    window.addEventListener('hashchange', cleanup);
}

function renderImageViewer(container, item) {
    const token = getToken();
    container.innerHTML = `
        <div class="player-container">
            <div class="player-back">
                <a href="#/browse" class="btn btn-outline btn-sm">&larr; 返回</a>
            </div>
            <div class="image-viewer">
                <img src="/api/v1/stream/file/${item.id}?token=${token}" alt="${escapeHtml(item.title)}">
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
    const fileUrl = `/api/v1/stream/file/${item.id}?token=${token}`;

    let viewerContent = '';
    if (format === 'pdf') {
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
                    <p style="margin-bottom:1rem">EPUB 文件</p>
                    <p style="color:var(--text-secondary);margin-bottom:1.5rem">由于浏览器限制，EPUB需使用专用阅读器。</p>
                    <a href="${fileUrl}" class="btn" download>下载 EPUB</a>
                </div>
            </div>
        `;
    } else {
        viewerContent = `
            <div class="ebook-viewer">
                <div style="padding:2rem;text-align:center">
                    <p style="font-size:1.1rem;margin-bottom:1rem">${format.toUpperCase()} 格式电子书</p>
                    <p style="color:var(--text-secondary)">此格式暂不支持在线预览</p>
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
