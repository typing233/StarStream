import { api, setAuth, navigate } from './app.js';

export function renderAuth(container) {
    container.innerHTML = `
        <div class="auth-container">
            <div class="auth-box">
                <h1>StarStream</h1>
                <p>个人媒体流服务</p>
                <div class="form-group">
                    <label>用户名</label>
                    <input type="text" id="auth-username" placeholder="输入用户名">
                </div>
                <div class="form-group">
                    <label>密码</label>
                    <input type="password" id="auth-password" placeholder="输入密码">
                </div>
                <div id="auth-error" class="error-msg hidden"></div>
                <div class="auth-actions">
                    <button id="login-btn" class="btn">登录</button>
                    <button id="register-btn" class="btn btn-outline">注册</button>
                </div>
            </div>
        </div>
    `;

    const usernameInput = document.getElementById('auth-username');
    const passwordInput = document.getElementById('auth-password');
    const errorEl = document.getElementById('auth-error');

    async function doAuth(endpoint) {
        const username = usernameInput.value.trim();
        const password = passwordInput.value;
        if (!username || !password) {
            showError('请输入用户名和密码');
            return;
        }
        try {
            const res = await fetch(`/api/auth/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            const data = await res.json();
            if (!res.ok) {
                showError(data.detail || '操作失败');
                return;
            }
            setAuth(data.token, data.username);
            navigate('browse');
        } catch (e) {
            showError('网络错误');
        }
    }

    function showError(msg) {
        errorEl.textContent = msg;
        errorEl.classList.remove('hidden');
    }

    document.getElementById('login-btn').addEventListener('click', () => doAuth('login'));
    document.getElementById('register-btn').addEventListener('click', () => doAuth('register'));
    passwordInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doAuth('login');
    });
}
