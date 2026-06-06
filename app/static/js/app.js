const App = {
    token: localStorage.getItem("token"),
    userRole: localStorage.getItem("userRole"),
    currentView: null,

    init() {
        window.addEventListener("hashchange", () => this.route());
        document.querySelector(".nav-brand").addEventListener("click", () => {
            location.hash = "#/browse";
        });
        this.route();
        if (this.token) this.fetchUserInfo();
    },

    async fetchUserInfo() {
        try {
            const user = await this.api("/api/auth/me");
            this.userRole = user.role;
            localStorage.setItem("userRole", user.role);
            this.updateNav();
        } catch (e) {}
    },

    route() {
        const hash = location.hash || "#/";
        if (!this.token && !hash.startsWith("#/auth")) {
            location.hash = "#/auth";
            return;
        }
        this.updateNav();

        if (hash.startsWith("#/auth")) Auth.render();
        else if (hash.startsWith("#/admin")) Admin.render();
        else if (hash.startsWith("#/stats")) Stats.render();
        else if (hash.startsWith("#/libraries")) Library.render();
        else if (hash.startsWith("#/browse/")) Browse.renderLibrary(hash.split("/")[2]);
        else if (hash.startsWith("#/browse")) Browse.render();
        else if (hash.startsWith("#/play/")) Player.render(hash.split("/")[2]);
        else { location.hash = "#/browse"; }
    },

    updateNav() {
        const nav = document.getElementById("nav-links");
        const searchArea = document.getElementById("nav-search");
        if (!this.token) {
            nav.innerHTML = "";
            searchArea.innerHTML = "";
            return;
        }
        let links = `
            <a href="#/browse">Browse</a>
            <a href="#/libraries">Libraries</a>
            <a href="#/stats">Stats</a>
        `;
        if (this.userRole === "admin") {
            links += `<a href="#/admin">Admin</a>`;
        }
        links += `<button onclick="App.logout()">Logout</button>`;
        nav.innerHTML = links;
        Search.renderSearchBar();
    },

    login(token) {
        this.token = token;
        localStorage.setItem("token", token);
        this.fetchUserInfo();
        location.hash = "#/browse";
    },

    logout() {
        this.token = null;
        this.userRole = null;
        localStorage.removeItem("token");
        localStorage.removeItem("userRole");
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
