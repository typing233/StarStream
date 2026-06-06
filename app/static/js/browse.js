const Browse = {
    async render() {
        const app = document.getElementById("app");
        app.innerHTML = `
            <div class="section-header">
                <h2>Browse</h2>
            </div>
            <div id="browse-content">Loading...</div>
        `;
        try {
            const libs = await App.api("/api/libraries");
            const content = document.getElementById("browse-content");
            if (libs.length === 0) {
                content.innerHTML = `<p style="color:var(--text-secondary)">No libraries. <a href="#/libraries">Add one</a> to get started.</p>`;
                return;
            }
            if (libs.length === 1) {
                location.hash = `#/browse/${libs[0].id}`;
                return;
            }
            content.innerHTML = `
                <div class="library-list">
                    ${libs.map(lib => `
                        <div class="library-card" onclick="location.hash='#/browse/${lib.id}'">
                            <div class="info">
                                <h3>${lib.name}</h3>
                                <p>${lib.media_count} items</p>
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    async renderLibrary(libId) {
        const app = document.getElementById("app");
        app.innerHTML = `
            <button class="back-btn" onclick="location.hash='#/browse'">&larr; Back</button>
            <div class="filter-bar" id="filter-bar">
                <button class="filter-btn active" data-type="">All</button>
                <button class="filter-btn" data-type="video">Video</button>
                <button class="filter-btn" data-type="audio">Music</button>
                <button class="filter-btn" data-type="image">Images</button>
                <button class="filter-btn" data-type="ebook">Ebooks</button>
            </div>
            <div class="media-grid" id="media-grid">Loading...</div>
        `;

        document.querySelectorAll(".filter-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.loadMedia(libId, btn.dataset.type);
            });
        });

        await this.loadMedia(libId, "");
    },

    async loadMedia(libId, type) {
        const grid = document.getElementById("media-grid");
        try {
            const url = `/api/libraries/${libId}/media` + (type ? `?media_type=${type}` : "");
            const items = await App.api(url);
            if (items.length === 0) {
                grid.innerHTML = `<p style="color:var(--text-secondary)">No media found. Try rescanning the library.</p>`;
                return;
            }
            grid.innerHTML = items.map(item => `
                <div class="media-card" onclick="location.hash='#/play/${item.id}'">
                    <div class="cover">
                        ${item.cover_path
                            ? `<img src="/api/stream/${item.id}/cover" alt="${item.title}" loading="lazy">`
                            : `<span class="placeholder">${this.typeIcon(item.media_type)}</span>`
                        }
                    </div>
                    <div class="meta">
                        <div class="title" title="${item.title}">${item.title}</div>
                        <div class="sub">${item.year || ""} ${item.media_type} ${item.artist ? "· " + item.artist : ""}</div>
                    </div>
                </div>
            `).join("");
        } catch (err) {
            grid.innerHTML = "";
            App.toast(err.message, "error");
        }
    },

    typeIcon(type) {
        const icons = { video: "🎬", audio: "🎵", image: "🖼", ebook: "📖" };
        return icons[type] || "📁";
    },
};
