const Cast = {
    devices: [],
    activeDevice: null,
    pollInterval: null,

    async discoverDevices() {
        try {
            const data = await App.api("/api/cast/devices");
            this.devices = data.devices || [];
            return this.devices;
        } catch (e) {
            this.devices = [];
            return [];
        }
    },

    renderCastButton(container, mediaId) {
        const btn = document.createElement("button");
        btn.className = "btn btn-sm cast-btn";
        btn.textContent = "Cast";
        btn.onclick = async () => {
            const devices = await this.discoverDevices();
            if (devices.length === 0) {
                App.toast("No cast devices found", "info");
                return;
            }
            this.showDevicePicker(devices, mediaId);
        };
        container.appendChild(btn);
    },

    showDevicePicker(devices, mediaId) {
        const existing = document.querySelector(".cast-picker-overlay");
        if (existing) existing.remove();

        const overlay = document.createElement("div");
        overlay.className = "modal-overlay cast-picker-overlay";
        overlay.innerHTML = `
            <div class="modal">
                <h3>Cast to Device</h3>
                <div class="device-list">
                    ${devices.map(d => `
                        <div class="device-item" onclick="Cast.castTo('${d.id}', ${mediaId})">
                            <span class="device-icon">${d.type === "chromecast" ? "&#128250;" : "&#128225;"}</span>
                            <span class="device-name">${d.name}</span>
                            <span class="device-type">${d.type}</span>
                        </div>
                    `).join("")}
                </div>
                <button class="btn btn-sm" onclick="this.closest('.cast-picker-overlay').remove()" style="margin-top:12px">Cancel</button>
            </div>
        `;
        document.body.appendChild(overlay);
    },

    async castTo(deviceId, mediaId) {
        const overlay = document.querySelector(".cast-picker-overlay");
        if (overlay) overlay.remove();
        try {
            await App.api("/api/cast/play", {
                method: "POST",
                body: JSON.stringify({ device_id: deviceId, media_id: mediaId }),
            });
            this.activeDevice = deviceId;
            App.toast("Casting started", "success");
            this.showCastBar();
        } catch (err) {
            App.toast(err.message, "error");
        }
    },

    showCastBar() {
        let bar = document.getElementById("cast-bar");
        if (!bar) {
            bar = document.createElement("div");
            bar.id = "cast-bar";
            bar.className = "cast-bar";
            document.body.appendChild(bar);
        }
        bar.innerHTML = `
            <span>Casting...</span>
            <button class="btn btn-sm" onclick="Cast.pauseCast()">Pause</button>
            <button class="btn btn-sm btn-danger" onclick="Cast.stopCast()">Stop</button>
        `;
    },

    async pauseCast() {
        if (!this.activeDevice) return;
        try {
            await App.api(`/api/cast/pause?device_id=${this.activeDevice}`, { method: "POST" });
        } catch (e) {}
    },

    async stopCast() {
        if (!this.activeDevice) return;
        try {
            await App.api(`/api/cast/stop?device_id=${this.activeDevice}`, { method: "POST" });
        } catch (e) {}
        this.activeDevice = null;
        const bar = document.getElementById("cast-bar");
        if (bar) bar.remove();
    },
};
