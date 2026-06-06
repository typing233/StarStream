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
                <div class="tab-bar" style="display:flex;gap:0;margin-bottom:16px;border-bottom:1px solid var(--border)">
                    <button class="tab-btn active" data-tab="upload" style="flex:1;padding:8px;background:none;border:none;color:var(--text-primary);cursor:pointer;border-bottom:2px solid var(--accent)">Upload Files</button>
                    <button class="tab-btn" data-tab="path" style="flex:1;padding:8px;background:none;border:none;color:var(--text-secondary);cursor:pointer;border-bottom:2px solid transparent">Server Path</button>
                </div>
                <div id="tab-upload">
                    <form id="upload-lib-form">
                        <div class="form-group">
                            <label>Library Name</label>
                            <input type="text" id="upload-lib-name" required placeholder="My Movies">
                        </div>
                        <div class="form-group">
                            <label>Select Files or Folder</label>
                            <input type="file" id="upload-files" multiple webkitdirectory style="display:none">
                            <input type="file" id="upload-files-flat" multiple style="display:none">
                            <div style="display:flex;gap:8px">
                                <button type="button" class="btn btn-sm" onclick="document.getElementById('upload-files').click()">Choose Folder</button>
                                <button type="button" class="btn btn-sm" style="background:var(--bg-tertiary)" onclick="document.getElementById('upload-files-flat').click()">Choose Files</button>
                            </div>
                            <div id="upload-file-info" style="margin-top:8px;color:var(--text-secondary);font-size:0.8rem"></div>
                        </div>
                        <div id="upload-progress" style="display:none;margin-bottom:12px">
                            <div style="background:var(--bg-tertiary);border-radius:4px;overflow:hidden;height:6px">
                                <div id="upload-bar" style="height:100%;background:var(--accent);width:0%;transition:width 0.3s"></div>
                            </div>
                            <div id="upload-status" style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px"></div>
                        </div>
                        <div style="display:flex;gap:8px;justify-content:flex-end">
                            <button type="button" class="btn btn-sm" style="background:var(--bg-tertiary)" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                            <button type="submit" class="btn btn-sm" id="upload-submit-btn">Upload & Scan</button>
                        </div>
                    </form>
                </div>
                <div id="tab-path" style="display:none">
                    <form id="add-lib-form">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" id="lib-name" required placeholder="My Movies">
                        </div>
                        <div class="form-group">
                            <label>Server Directory Path</label>
                            <input type="text" id="lib-path" required placeholder="/path/to/media">
                        </div>
                        <div style="display:flex;gap:8px;justify-content:flex-end">
                            <button type="button" class="btn btn-sm" style="background:var(--bg-tertiary)" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                            <button type="submit" class="btn btn-sm">Add</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });

        // Tab switching
        overlay.querySelectorAll(".tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                overlay.querySelectorAll(".tab-btn").forEach(b => {
                    b.classList.remove("active");
                    b.style.color = "var(--text-secondary)";
                    b.style.borderBottomColor = "transparent";
                });
                btn.classList.add("active");
                btn.style.color = "var(--text-primary)";
                btn.style.borderBottomColor = "var(--accent)";
                document.getElementById("tab-upload").style.display = btn.dataset.tab === "upload" ? "" : "none";
                document.getElementById("tab-path").style.display = btn.dataset.tab === "path" ? "" : "none";
            });
        });

        // File selection display
        let selectedFiles = [];
        const fileInfo = document.getElementById("upload-file-info");

        document.getElementById("upload-files").addEventListener("change", (e) => {
            selectedFiles = Array.from(e.target.files);
            fileInfo.textContent = `${selectedFiles.length} file(s) selected from folder`;
        });
        document.getElementById("upload-files-flat").addEventListener("change", (e) => {
            selectedFiles = Array.from(e.target.files);
            fileInfo.textContent = `${selectedFiles.length} file(s) selected`;
        });

        // Upload form
        document.getElementById("upload-lib-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            if (selectedFiles.length === 0) {
                App.toast("Please select files first", "error");
                return;
            }
            const name = document.getElementById("upload-lib-name").value;
            const submitBtn = document.getElementById("upload-submit-btn");
            const progress = document.getElementById("upload-progress");
            const bar = document.getElementById("upload-bar");
            const status = document.getElementById("upload-status");

            submitBtn.disabled = true;
            submitBtn.textContent = "Uploading...";
            progress.style.display = "";

            const formData = new FormData();
            formData.append("name", name);
            for (const file of selectedFiles) {
                const path = file.webkitRelativePath || file.name;
                formData.append("files", file, path);
            }

            try {
                const xhr = new XMLHttpRequest();
                xhr.open("POST", "/api/libraries/upload");
                xhr.setRequestHeader("Authorization", `Bearer ${App.token}`);

                xhr.upload.addEventListener("progress", (ev) => {
                    if (ev.lengthComputable) {
                        const pct = Math.round((ev.loaded / ev.total) * 100);
                        bar.style.width = pct + "%";
                        status.textContent = `${pct}% — ${(ev.loaded / 1024 / 1024).toFixed(1)} MB / ${(ev.total / 1024 / 1024).toFixed(1)} MB`;
                    }
                });

                xhr.onload = async () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        overlay.remove();
                        App.toast("Library uploaded, scanning...", "success");
                        await this.load();
                    } else {
                        const err = JSON.parse(xhr.responseText);
                        App.toast(err.detail || "Upload failed", "error");
                        submitBtn.disabled = false;
                        submitBtn.textContent = "Upload & Scan";
                    }
                };
                xhr.onerror = () => {
                    App.toast("Upload failed", "error");
                    submitBtn.disabled = false;
                    submitBtn.textContent = "Upload & Scan";
                };
                xhr.send(formData);
            } catch (err) {
                App.toast(err.message, "error");
                submitBtn.disabled = false;
                submitBtn.textContent = "Upload & Scan";
            }
        });

        // Server path form
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
