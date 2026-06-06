const Browse = {
    currentSort: "title",
    currentOrder: "asc",
    currentPage: 1,
    perPage: 30,

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
        this.currentPage = 1;
        const app = document.getElementById("app");
        app.innerHTML = `
            <button class="back-btn" onclick="location.hash='#/browse'">&larr; Back</button>
            <div class="browse-toolbar">
                <div class="filter-bar" id="filter-bar">
                    <button class="filter-btn active" data-type="">All</button>
                    <button class="filter-btn" data-type="video">Video</button>
                    <button class="filter-btn" data-type="audio">Music</button>
                    <button class="filter-btn" data-type="image">Images</button>
                    <button class="filter-btn" data-type="ebook">Ebooks</button>
                </div>
                <div class="sort-bar">
                    <select id="sort-select">
                        <option value="title">Title</option>
                        <option value="year">Year</option>
                        <option value="created_at">Date Added</option>
                        <option value="duration">Duration</option>
                        <option value="file_size">Size</option>
                        <option value="play_count">Plays</option>
                    </select>
                    <button class="sort-order-btn" id="sort-order-btn" title="Toggle order">&#x2195;</button>
                </div>
            </div>
            <div class="media-grid" id="media-grid">Loading...</div>
            <div class="pagination" id="pagination"></div>
        `;

        document.querySelectorAll(".filter-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.currentPage = 1;
                this.loadMedia(libId, btn.dataset.type);
            });
        });

        document.getElementById("sort-select").addEventListener("change", (e) => {
            this.currentSort = e.target.value;
            this.currentPage = 1;
            this.loadMedia(libId, this.getActiveType());
        });

        document.getElementById("sort-order-btn").addEventListener("click", () => {
            this.currentOrder = this.currentOrder === "asc" ? "desc" : "asc";
            this.loadMedia(libId, this.getActiveType());
        });

        await this.loadMedia(libId, "");
    },

    getActiveType() {
        const active = document.querySelector(".filter-btn.active");
        return active ? active.dataset.type : "";
    },

    async loadMedia(libId, type) {
        const grid = document.getElementById("media-grid");
        try {
            let url = `/api/libraries/${libId}/media?page=${this.currentPage}&per_page=${this.perPage}&sort=${this.currentSort}&order=${this.currentOrder}`;
            if (type) url += `&media_type=${type}`;

            const data = await App.api(url);
            const items = data.items;

            if (items.length === 0) {
                grid.innerHTML = `<p style="color:var(--text-secondary)">No media found.</p>`;
                this.renderPagination(0, 0, libId, type);
                return;
            }

            grid.innerHTML = items.map(item => {
                const icon = this.typeIcon(item.media_type);
                return `
                <div class="media-card" onclick="location.hash='#/play/${item.id}'">
                    <div class="cover">
                        <img src="/api/stream/${item.id}/cover?token=${App.token}" alt="${item.title}" loading="lazy"
                             onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                        <span class="placeholder" style="display:none">${icon}</span>
                    </div>
                    <div class="meta">
                        <div class="title" title="${item.title}">${item.title}</div>
                        <div class="sub">${item.year || ""} ${item.media_type}${item.artist ? " · " + item.artist : ""}${item.play_count ? " · " + item.play_count + " plays" : ""}</div>
                    </div>
                </div>
            `;}).join("");

            this.renderPagination(data.total, data.pages, libId, type);
        } catch (err) {
            grid.innerHTML = "";
            App.toast(err.message, "error");
        }
    },

    renderPagination(total, pages, libId, type) {
        const el = document.getElementById("pagination");
        if (!el || pages <= 1) {
            if (el) el.innerHTML = "";
            return;
        }
        el.innerHTML = `
            <button class="btn btn-sm" ${this.currentPage <= 1 ? "disabled" : ""} onclick="Browse.goPage(${this.currentPage - 1}, '${libId}', '${type}')">Prev</button>
            <span class="page-info">Page ${this.currentPage} / ${pages} (${total} items)</span>
            <button class="btn btn-sm" ${this.currentPage >= pages ? "disabled" : ""} onclick="Browse.goPage(${this.currentPage + 1}, '${libId}', '${type}')">Next</button>
        `;
    },

    goPage(page, libId, type) {
        this.currentPage = page;
        this.loadMedia(libId, type);
    },

    typeIcon(type) {
        const icons = { video: "&#127916;", audio: "&#127925;", image: "&#128444;", ebook: "&#128214;" };
        return icons[type] || "&#128193;";
    },
};
