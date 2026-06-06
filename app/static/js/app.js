const App = {
    token: localStorage.getItem("token"),
    currentView: null,

    init() {
        window.addEventListener("hashchange", () => this.route());
        document.querySelector(".nav-brand").addEventListener("click", () => {
            location.hash = "#/browse";
        });
        this.route();
    },

    route() {
        const hash = location.hash || "#/";
        if (!this.token && !hash.startsWith("#/auth")) {
            location.hash = "#/auth";
            return;
        }
        this.updateNav();

        if (hash.startsWith("#/auth")) Auth.render();
        else if (hash.startsWith("#/libraries")) Library.render();
        else if (hash.startsWith("#/browse/")) Browse.renderLibrary(hash.split("/")[2]);
        else if (hash.startsWith("#/browse")) Browse.render();
        else if (hash.startsWith("#/play/")) Player.render(hash.split("/")[2]);
        else { location.hash = "#/browse"; }
    },

    updateNav() {
        const nav = document.getElementById("nav-links");
        if (!this.token) {
            nav.innerHTML = "";
            return;
        }
        nav.innerHTML = `
            <a href="#/browse">Browse</a>
            <a href="#/libraries">Libraries</a>
            <button onclick="App.logout()">Logout</button>
        `;
    },

    login(token) {
        this.token = token;
        localStorage.setItem("token", token);
        location.hash = "#/browse";
        this.updateNav();
    },

    logout() {
        this.token = null;
        localStorage.removeItem("token");
        location.hash = "#/auth";
    },

    async api(path, options = {}) {
        const headers = options.headers || {};
        if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
        if (options.body && !(options.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }
        const resp = await fetch(path, { ...options, headers });
        if (resp.status === 401) {
            this.logout();
            throw new Error("Unauthorized");
        }
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: "Request failed" }));
            throw new Error(err.detail || "Error");
        }
        return resp.json();
    },

    toast(msg, type = "info") {
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    },
};

document.addEventListener("DOMContentLoaded", () => App.init());
