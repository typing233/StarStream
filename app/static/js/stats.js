const Stats = {
    async render() {
        const app = document.getElementById("app");
        app.innerHTML = `
            <div class="section-header"><h2>Statistics</h2></div>
            <div id="stats-content">Loading...</div>
        `;
        try {
            const summary = await App.api("/api/stats/summary");
            const popular = await App.api("/api/stats/popular");
            const history = await App.api("/api/stats/history?per_page=10");

            const content = document.getElementById("stats-content");
            content.innerHTML = `
                <div class="stats-grid">
                    <div class="stats-card"><div class="stats-value">${summary.total_plays}</div><div class="stats-label">Total Plays</div></div>
                    <div class="stats-card"><div class="stats-value">${summary.total_hours_watched}</div><div class="stats-label">Hours Watched</div></div>
                    <div class="stats-card"><div class="stats-value">${summary.unique_items_played}</div><div class="stats-label">Unique Items</div></div>
                    <div class="stats-card"><div class="stats-value">${summary.total_media_items}</div><div class="stats-label">Total Media</div></div>
                </div>

                <h3 style="margin-top:24px;">Most Played</h3>
                ${popular.length > 0 ? `
                <div class="popular-list">
                    ${popular.slice(0, 10).map((item, i) => `
                        <div class="popular-item">
                            <span class="popular-rank">#${i + 1}</span>
                            <span class="popular-title">${item.title}</span>
                            <span class="popular-type">${item.media_type}</span>
                            <div class="popular-bar-wrap">
                                <div class="popular-bar" style="width:${(item.play_count / (popular[0].play_count || 1)) * 100}%"></div>
                            </div>
                            <span class="popular-count">${item.play_count}</span>
                        </div>
                    `).join("")}
                </div>` : `<p style="color:var(--text-secondary)">No plays yet.</p>`}

                <h3 style="margin-top:24px;">Recent History</h3>
                ${history.items.length > 0 ? `
                <div class="history-list">
                    ${history.items.map(item => `
                        <div class="history-item" onclick="location.hash='#/play/${item.media_id}'">
                            <span class="history-title">${item.title}</span>
                            <span class="history-type">${item.media_type}</span>
                            <span class="history-time">${new Date(item.started_at).toLocaleDateString()}</span>
                        </div>
                    `).join("")}
                </div>` : `<p style="color:var(--text-secondary)">No history yet.</p>`}
            `;
        } catch (err) {
            document.getElementById("stats-content").innerHTML = `<p class="error-text">${err.message}</p>`;
        }
    },
};
