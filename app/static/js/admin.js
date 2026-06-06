const Admin = {
    async render() {
        if (App.userRole !== "admin") {
            App.toast("Admin access required", "error");
            location.hash = "#/browse";
            return;
        }
        const app = document.getElementById("app");
        app.innerHTML = `
            <div class="section-header"><h2>Admin Panel</h2></div>
            <div class="admin-tabs">
                <button class="tab-btn active" data-tab="users">Users</button>
                <button class="tab-btn" data-tab="libraries">Libraries</button>
                <button class="tab-btn" data-tab="system">System</button>
                <button class="tab-btn" data-tab="plugins">Plugins</button>
                <button class="tab-btn" data-tab="logs">Logs</button>
            </div>
            <div id="admin-content">Loading...</div>
        `;
        document.querySelectorAll(".tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.loadTab(btn.dataset.tab);
            });
        });
        await this.loadTab("users");
    },

    async loadTab(tab) {
        const content = document.getElementById("admin-content");
        try {
            if (tab === "users") await this.renderUsers(content);
            else if (tab === "libraries") await this.renderLibraries(content);
            else if (tab === "system") await this.renderSystem(content);
            else if (tab === "plugins") await this.renderPlugins(content);
            else if (tab === "logs") await this.renderLogs(content);
        } catch (err) {
            content.innerHTML = `<p class="error-text">${err.message}</p>`;
        }
    },

    async renderUsers(el) {
        const users = await App.api("/api/admin/users");
        el.innerHTML = `
            <table class="admin-table">
                <thead><tr><th>ID</th><th>Username</th><th>Role</th><th>Libraries</th><th>Actions</th></tr></thead>
                <tbody>
                    ${users.map(u => `
                        <tr>
                            <td>${u.id}</td>
                            <td>${u.username}</td>
                            <td><span class="role-badge ${u.role}">${u.role}</span></td>
                            <td>${u.library_count}</td>
                            <td>
                                <button class="btn btn-sm" onclick="Admin.toggleRole(${u.id}, '${u.role}')">${u.role === "admin" ? "Demote" : "Promote"}</button>
                                <button class="btn btn-sm btn-danger" onclick="Admin.deleteUser(${u.id})">Delete</button>
                            </td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    },

    async renderLibraries(el) {
        const libs = await App.api("/api/admin/libraries");
        el.innerHTML = `
            <table class="admin-table">
                <thead><tr><th>ID</th><th>Name</th><th>Owner</th><th>Items</th><th>Watch</th><th>Actions</th></tr></thead>
                <tbody>
                    ${libs.map(lib => `
                        <tr>
                            <td>${lib.id}</td>
                            <td>${lib.name}</td>
                            <td>${lib.owner}</td>
                            <td>${lib.media_count}</td>
                            <td>${lib.watch_enabled ? "Active" : "Off"}</td>
                            <td><button class="btn btn-sm btn-danger" onclick="Admin.deleteLibrary(${lib.id})">Delete</button></td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    },

    async renderSystem(el) {
        const info = await App.api("/api/admin/system");
        el.innerHTML = `
            <div class="stats-grid">
                <div class="stats-card"><div class="stats-value">${info.total_users}</div><div class="stats-label">Users</div></div>
                <div class="stats-card"><div class="stats-value">${info.total_libraries}</div><div class="stats-label">Libraries</div></div>
                <div class="stats-card"><div class="stats-value">${info.total_media}</div><div class="stats-label">Media Items</div></div>
                <div class="stats-card"><div class="stats-value">${info.db_size_mb} MB</div><div class="stats-label">Database</div></div>
                <div class="stats-card"><div class="stats-value">${info.data_dir_size_mb} MB</div><div class="stats-label">Data Dir</div></div>
            </div>
        `;
    },

    async renderPlugins(el) {
        const plugins = await App.api("/api/plugins");
        if (plugins.length === 0) {
            el.innerHTML = `<p style="color:var(--text-secondary)">No plugins discovered.</p>`;
            return;
        }
        el.innerHTML = `
            <table class="admin-table">
                <thead><tr><th>Name</th><th>Version</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                    ${plugins.map(p => `
                        <tr>
                            <td>${p.name}</td>
                            <td>${p.version}</td>
                            <td><span class="role-badge ${p.enabled ? "admin" : ""}">${p.enabled ? "Enabled" : "Disabled"}</span></td>
                            <td>
                                <button class="btn btn-sm" onclick="Admin.togglePlugin('${p.name}', ${p.enabled})">${p.enabled ? "Disable" : "Enable"}</button>
                            </td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    },

    async renderLogs(el) {
        const data = await App.api("/api/admin/logs?per_page=30");
        el.innerHTML = `
            <table class="admin-table admin-table-compact">
                <thead><tr><th>Time</th><th>User</th><th>Method</th><th>Path</th><th>Status</th><th>IP</th></tr></thead>
                <tbody>
                    ${data.items.map(log => `
                        <tr>
                            <td>${log.timestamp ? new Date(log.timestamp).toLocaleString() : ""}</td>
                            <td>${log.user_id || "-"}</td>
                            <td>${log.method}</td>
                            <td class="path-cell" title="${log.path}">${log.path}</td>
                            <td><span class="status-code status-${Math.floor(log.status_code/100)}xx">${log.status_code}</span></td>
                            <td>${log.ip_address || "-"}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    },

    async toggleRole(userId, currentRole) {
        const newRole = currentRole === "admin" ? "user" : "admin";
        try {
            await App.api(`/api/admin/users/${userId}/role`, {
                method: "PUT",
                body: JSON.stringify({ role: newRole }),
            });
            App.toast(`Role updated to ${newRole}`, "success");
            this.loadTab("users");
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    async deleteUser(userId) {
        if (!confirm("Delete this user and all their data?")) return;
        try {
            await App.api(`/api/admin/users/${userId}`, { method: "DELETE" });
            App.toast("User deleted", "success");
            this.loadTab("users");
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    async deleteLibrary(libId) {
        if (!confirm("Delete this library?")) return;
        try {
            await App.api(`/api/admin/libraries/${libId}`, { method: "DELETE" });
            App.toast("Library deleted", "success");
            this.loadTab("libraries");
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    async togglePlugin(name, enabled) {
        const action = enabled ? "disable" : "enable";
        try {
            await App.api(`/api/plugins/${name}/${action}`, { method: "POST" });
            App.toast(`Plugin ${action}d`, "success");
            this.loadTab("plugins");
        } catch (err) {
            App.toast(err.message, "error");
        }
    },
};
