const Player = {
    hls: null,
    _currentMediaId: null,
    _playedSeconds: 0,
    _lastTimeUpdate: 0,
    _reported: false,
    _mediaElement: null,

    _cleanup() {
        if (this._mediaElement && this._currentMediaId && !this._reported) {
            this._reportFinal();
        }
        this.destroyHls();
        window.removeEventListener("beforeunload", this._onBeforeUnload);
        this._mediaElement = null;
        this._playedSeconds = 0;
        this._lastReportedSeconds = 0;
        this._lastTimeUpdate = 0;
        this._reported = false;
    },

    _onBeforeUnload: null,

    _setupTracking(mediaElement, mediaId) {
        this._mediaElement = mediaElement;
        this._currentMediaId = mediaId;
        this._playedSeconds = 0;
        this._lastReportedSeconds = 0;
        this._lastTimeUpdate = 0;
        this._reported = false;

        mediaElement.addEventListener("timeupdate", () => {
            const now = mediaElement.currentTime;
            if (this._lastTimeUpdate > 0 && now > this._lastTimeUpdate) {
                const delta = now - this._lastTimeUpdate;
                if (delta < 2) this._playedSeconds += delta;
            }
            this._lastTimeUpdate = now;
        });

        mediaElement.addEventListener("pause", () => {
            this._reportDelta(false);
        });

        mediaElement.addEventListener("ended", () => {
            this._reportDelta(true);
            this._reported = true;
        });

        this._onBeforeUnload = () => { this._reportFinal(); };
        window.addEventListener("beforeunload", this._onBeforeUnload);
    },

    _reportDelta(completed) {
        const delta = Math.round(this._playedSeconds - this._lastReportedSeconds);
        if (delta < 1) return;
        this._lastReportedSeconds = this._playedSeconds;
        const mediaId = this._currentMediaId;
        App.api("/api/stats/play", {
            method: "POST",
            body: JSON.stringify({ media_id: parseInt(mediaId), duration_watched: delta, completed }),
        }).catch(() => {});
    },

    _reportFinal() {
        if (this._reported) return;
        this._reported = true;
        const delta = Math.round(this._playedSeconds - this._lastReportedSeconds);
        if (delta < 1) return;
        this._lastReportedSeconds = this._playedSeconds;
        const mediaId = this._currentMediaId;
        const completed = this._mediaElement && this._mediaElement.ended;
        const body = JSON.stringify({ media_id: parseInt(mediaId), duration_watched: delta, completed: !!completed });
        try {
            fetch(App.url("/api/stats/play"), {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${App.token}` },
                body: body,
                keepalive: true,
            });
        } catch (e) {}
    },

    async render(mediaId) {
        this._cleanup();
        this._currentMediaId = mediaId;
        const app = document.getElementById("app");
        app.innerHTML = `<button class="back-btn" onclick="Player._cleanup();history.back()">&larr; Back</button><div class="player-container" id="player-container">Loading...</div>`;

        try {
            const info = await App.api(`/api/stream/${mediaId}/info`);
            const container = document.getElementById("player-container");

            if (info.media_type === "video") this.renderVideo(container, mediaId, info);
            else if (info.media_type === "audio") this.renderAudio(container, mediaId, info);
            else if (info.media_type === "image") this.renderImage(container, mediaId, info);
            else if (info.media_type === "ebook") this.renderEbook(container, mediaId, info);
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    renderVideo(container, mediaId, info) {
        const token = App.token;
        container.innerHTML = `
            <video id="video-player" controls preload="metadata"></video>
            <div class="player-info">
                <h2>${info.title}</h2>
                <div class="details">
                    ${info.year ? info.year + " · " : ""}${info.width}x${info.height} · ${info.codec || ""}
                    ${info.duration ? " · " + this.formatDuration(info.duration) : ""}
                </div>
                <div class="player-controls" id="player-controls"></div>
            </div>
        `;

        const video = document.getElementById("video-player");
        this._setupTracking(video, mediaId);
        const controls = document.getElementById("player-controls");

        let controlsHtml = "";

        if (info.audio_tracks.length > 1) {
            controlsHtml += `<select id="audio-select" title="Audio Track">
                ${info.audio_tracks.map((t, i) => `<option value="${i}">${t.language} ${t.title || ""} (${t.codec})</option>`).join("")}
            </select>`;
        }

        if (info.subtitle_tracks.length > 0) {
            controlsHtml += `<select id="sub-select" title="Subtitles">
                <option value="-1">Off</option>
                ${info.subtitle_tracks.map((t, i) => `<option value="${i}">${t.language} ${t.title || ""}</option>`).join("")}
            </select>`;
        }

        controlsHtml += `<select id="quality-select" title="Quality">
            <option value="original">Original (Direct)</option>
            <option value="1080p">1080p</option>
            <option value="720p">720p</option>
            <option value="480p">480p</option>
            <option value="360p">360p</option>
        </select>`;

        controls.innerHTML = controlsHtml;
        Cast.renderCastButton(controls, mediaId);

        this.playDirect(video, mediaId, token);

        const qualitySelect = document.getElementById("quality-select");
        const audioSelect = document.getElementById("audio-select");
        const subSelect = document.getElementById("sub-select");

        const switchStream = () => {
            const quality = qualitySelect.value;
            const audioTrack = audioSelect ? parseInt(audioSelect.value) : 0;
            const currentTime = video.currentTime;

            if (quality === "original" && (!audioSelect || audioTrack === 0)) {
                this.destroyHls();
                this.playDirect(video, mediaId, token);
                video.currentTime = currentTime;
            } else {
                this.playHls(video, mediaId, quality, audioTrack, token);
                video.addEventListener("loadedmetadata", () => { video.currentTime = currentTime; }, { once: true });
            }
        };

        qualitySelect.addEventListener("change", switchStream);
        if (audioSelect) audioSelect.addEventListener("change", switchStream);

        if (subSelect) {
            subSelect.addEventListener("change", () => {
                const idx = parseInt(subSelect.value);
                const existingTracks = video.querySelectorAll("track");
                existingTracks.forEach(t => t.remove());
                for (let t of video.textTracks) { t.mode = "hidden"; }

                if (idx >= 0) {
                    const track = document.createElement("track");
                    track.kind = "subtitles";
                    track.src = App.url(`/api/transcode/${mediaId}/subtitle/${idx}?token=${token}`);
                    track.default = true;
                    video.appendChild(track);
                    setTimeout(() => { if (video.textTracks[0]) video.textTracks[0].mode = "showing"; }, 500);
                }
            });
        }
    },

    playDirect(video, mediaId, token) {
        this.destroyHls();
        video.src = App.url(`/api/stream/${mediaId}?token=${token}`);
        video.load();
    },

    playHls(video, mediaId, quality, audioTrack, token) {
        this.destroyHls();
        const src = App.url(`/api/transcode/${mediaId}/hls/master.m3u8?resolution=${quality}&audio_track=${audioTrack}&token=${token}`);

        if (Hls && Hls.isSupported()) {
            this.hls = new Hls({
                xhrSetup: (xhr) => {
                    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
                },
            });
            this.hls.loadSource(src);
            this.hls.attachMedia(video);
            this.hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
        } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
            video.src = src;
            video.play();
        } else {
            App.toast("HLS not supported in this browser", "error");
        }
    },

    destroyHls() {
        if (this.hls) {
            this.hls.destroy();
            this.hls = null;
        }
    },

    renderAudio(container, mediaId, info) {
        const token = App.token;
        container.innerHTML = `
            <div style="text-align:center;padding:40px 0">
                <img src="${App.url("/api/stream/" + mediaId + "/cover")}?token=${token}" alt="cover"
                     style="width:250px;height:250px;object-fit:cover;border-radius:var(--radius);background:var(--bg-tertiary)"
                     onerror="this.style.display='none'">
            </div>
            <audio id="audio-player" controls preload="metadata" style="width:100%">
                <source src="${App.url("/api/stream/" + mediaId)}?token=${token}">
            </audio>
            <div class="player-info">
                <h2>${info.title}</h2>
                <div class="details">
                    ${info.artist ? info.artist + " · " : ""}${info.album || ""}
                    ${info.duration ? " · " + this.formatDuration(info.duration) : ""}
                </div>
                <div class="player-controls" id="player-controls"></div>
            </div>
        `;
        const audio = document.getElementById("audio-player");
        this._setupTracking(audio, mediaId);
        const controls = document.getElementById("player-controls");
        Cast.renderCastButton(controls, mediaId);
    },

    renderImage(container, mediaId, info) {
        container.innerHTML = `
            <div class="image-viewer">
                <img src="${App.url("/api/stream/" + mediaId)}?token=${App.token}" alt="${info.title}">
            </div>
            <div class="player-info">
                <h2>${info.title}</h2>
                <div class="details">${info.width}x${info.height}</div>
            </div>
        `;
    },

    renderEbook(container, mediaId, info) {
        const streamUrl = App.url(`/api/stream/${mediaId}?token=${App.token}`);
        const ext = (info.file_ext || "").toLowerCase();

        container.innerHTML = `
            <div class="player-info"><h2>${info.title}</h2></div>
            <div class="ebook-viewer" id="ebook-area" style="width:100%;height:70vh"></div>
            <div class="ebook-nav">
                <button class="btn btn-sm" id="ebook-prev">&larr; Previous</button>
                <button class="btn btn-sm" id="ebook-next">Next &rarr;</button>
            </div>
        `;

        if (ext === ".pdf" && window.pdfjsLib) {
            this.renderPdf(streamUrl);
        } else if (typeof ePub !== "undefined" && ext === ".epub") {
            this.renderEpub(streamUrl);
        } else if (window.pdfjsLib) {
            this.renderPdf(streamUrl);
        } else {
            document.getElementById("ebook-area").innerHTML = `<p style="padding:20px;color:var(--text-secondary)">
                <a href="${streamUrl}" download class="btn">Download File</a></p>`;
        }
    },

    renderEpub(url) {
        const book = ePub(url);
        const rendition = book.renderTo("ebook-area", { width: "100%", height: "100%" });
        rendition.display();
        document.getElementById("ebook-prev").addEventListener("click", () => rendition.prev());
        document.getElementById("ebook-next").addEventListener("click", () => rendition.next());
    },

    renderPdf(url) {
        const area = document.getElementById("ebook-area");
        area.innerHTML = "";
        let currentPage = 1;
        let pdfDoc = null;

        const canvas = document.createElement("canvas");
        canvas.style.width = "100%";
        area.appendChild(canvas);

        pdfjsLib.getDocument(url).promise.then(pdf => {
            pdfDoc = pdf;
            renderPage(currentPage);
        });

        function renderPage(num) {
            pdfDoc.getPage(num).then(page => {
                const viewport = page.getViewport({ scale: 1.5 });
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                page.render({ canvasContext: canvas.getContext("2d"), viewport });
            });
        }

        document.getElementById("ebook-prev").addEventListener("click", () => {
            if (currentPage > 1) { currentPage--; renderPage(currentPage); }
        });
        document.getElementById("ebook-next").addEventListener("click", () => {
            if (pdfDoc && currentPage < pdfDoc.numPages) { currentPage++; renderPage(currentPage); }
        });
    },

    formatDuration(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
        return `${m}:${String(s).padStart(2, "0")}`;
    },
};
