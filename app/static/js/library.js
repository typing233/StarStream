const Library = {
    async render() {
        const app = document.getElementById("app");
        app.innerHTML = `
            <div class="section-header">
                <h2>Media Libraries</h2>
                <button class="btn" onclick="Library.showAddModal()">Add Library</button>
            </div>
            <div class="library-list" id="library-list">Loading...</div>
        `;
        await this.load();
    },

    async load() {
        try {
            const libs = await App.api("/api/libraries");
            const list = document.getElementById("library-list");
            if (libs.length === 0) {
                list.innerHTML = `<p style="color:var(--text-secondary)">No libraries yet. Add a directory to get started.</p>`;
                return;
            }
            list.innerHTML = libs.map(lib => `
                <div class="library-card" onclick="location.hash='#/browse/${lib.id}'">
                    <div class="info">
                        <h3>${lib.name}</h3>
                        <p>${lib.path} &middot; ${lib.media_count} items</p>
                    </div>
                    <div class="actions">
                        <button class="btn btn-sm" onclick="event.stopPropagation();Library.rescan(${lib.id})">Rescan</button>
                        <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();Library.remove(${lib.id})">Delete</button>
                    </div>
                </div>
            `).join("");
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    showAddModal() {
        const overlay = document.createElement("div");
        overlay.className = "modal-overlay";
        overlay.innerHTML = `
            <div class="modal">
                <h3>Add Library</h3>
                <form id="add-lib-form">
                    <div class="form-group">
                        <label>Name</label>
                        <input type="text" id="lib-name" required placeholder="My Movies">
                    </div>
                    <div class="form-group">
                        <label>Directory Path</label>
                        <input type="text" id="lib-path" required placeholder="/path/to/media">
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end">
                        <button type="button" class="btn btn-sm" style="background:var(--bg-tertiary)" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                        <button type="submit" class="btn btn-sm">Add</button>
                    </div>
                </form>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
        document.getElementById("add-lib-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("lib-name").value;
            const path = document.getElementById("lib-path").value;
            try {
                await App.api("/api/libraries", {
                    method: "POST",
                    body: JSON.stringify({ name, path }),
                });
                overlay.remove();
                App.toast("Library added, scanning...", "success");
                await this.load();
            } catch (err) {
                App.toast(err.message, "error");
            }
        });
    },

    async rescan(id) {
        try {
            await App.api(`/api/libraries/${id}/scan`, { method: "POST" });
            App.toast("Rescan started", "success");
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    async remove(id) {
        if (!confirm("Delete this library and all its media records?")) return;
        try {
            await App.api(`/api/libraries/${id}`, { method: "DELETE" });
            App.toast("Library deleted", "success");
            await this.load();
        } catch (err) {
            App.toast(err.message, "error");
        }
    },
};
