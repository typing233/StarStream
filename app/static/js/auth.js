const Auth = {
    render() {
        const app = document.getElementById("app");
        app.innerHTML = `
            <div class="auth-container">
                <h2 id="auth-title">Login</h2>
                <form id="auth-form">
                    <div class="form-group">
                        <label>Username</label>
                        <input type="text" id="auth-username" required minlength="3">
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="auth-password" required minlength="4">
                    </div>
                    <button type="submit" class="btn btn-block">Login</button>
                </form>
                <div class="toggle-link">
                    <span id="auth-toggle-text">Don't have an account? </span>
                    <a id="auth-toggle">Register</a>
                </div>
            </div>
        `;
        this.isLogin = true;
        document.getElementById("auth-toggle").addEventListener("click", () => this.toggle());
        document.getElementById("auth-form").addEventListener("submit", (e) => this.submit(e));
    },

    toggle() {
        this.isLogin = !this.isLogin;
        document.getElementById("auth-title").textContent = this.isLogin ? "Login" : "Register";
        document.querySelector("#auth-form .btn").textContent = this.isLogin ? "Login" : "Register";
        document.getElementById("auth-toggle").textContent = this.isLogin ? "Register" : "Login";
        document.getElementById("auth-toggle-text").textContent = this.isLogin
            ? "Don't have an account? "
            : "Already have an account? ";
    },

    async submit(e) {
        e.preventDefault();
        const username = document.getElementById("auth-username").value;
        const password = document.getElementById("auth-password").value;

        try {
            if (!this.isLogin) {
                await App.api("/api/auth/register", {
                    method: "POST",
                    body: JSON.stringify({ username, password }),
                });
                App.toast("Registered! Logging in...", "success");
            }
            const form = new URLSearchParams();
            form.append("username", username);
            form.append("password", password);
            const resp = await fetch("/api/auth/login", {
                method: "POST",
                body: form,
            });
            if (!resp.ok) throw new Error("Invalid credentials");
            const data = await resp.json();
            App.login(data.access_token);
        } catch (err) {
            App.toast(err.message, "error");
        }
    },
};
