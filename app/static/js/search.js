const Search = {
    _timeout: null,

    renderSearchBar() {
        const container = document.getElementById("nav-search");
        if (!container || !App.token) return;
        container.innerHTML = `
            <div class="search-container">
                <input type="text" id="global-search" placeholder="Search media..." autocomplete="off">
                <div class="search-dropdown" id="search-dropdown"></div>
            </div>
        `;
        const input = document.getElementById("global-search");
        input.addEventListener("input", () => this.onInput(input.value));
        input.addEventListener("blur", () => setTimeout(() => this.hideDropdown(), 200));
        input.addEventListener("focus", () => { if (input.value.length >= 2) this.onInput(input.value); });
    },

    onInput(value) {
        clearTimeout(this._timeout);
        if (value.length < 2) {
            this.hideDropdown();
            return;
        }
        this._timeout = setTimeout(() => this.doSearch(value), 300);
    },

    async doSearch(query) {
        try {
            const data = await App.api(`/api/search?q=${encodeURIComponent(query)}&per_page=8`);
            this.showResults(data.items);
        } catch (e) {
            this.hideDropdown();
        }
    },

    showResults(items) {
        const dropdown = document.getElementById("search-dropdown");
        if (!dropdown) return;
        if (items.length === 0) {
            dropdown.innerHTML = `<div class="search-item no-results">No results</div>`;
            dropdown.classList.add("visible");
            return;
        }
        dropdown.innerHTML = items.map(item => `
            <div class="search-item" onclick="location.hash='#/play/${item.id}';Search.hideDropdown();">
                <span class="search-type">${item.media_type}</span>
                <span class="search-title">${item.title}</span>
                ${item.artist ? `<span class="search-artist">${item.artist}</span>` : ""}
            </div>
        `).join("");
        dropdown.classList.add("visible");
    },

    hideDropdown() {
        const dropdown = document.getElementById("search-dropdown");
        if (dropdown) dropdown.classList.remove("visible");
    },
};
