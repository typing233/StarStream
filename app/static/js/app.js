import { renderAuth } from './auth.js';
import { renderLibrary } from './library.js';
import { renderBrowse } from './browse.js';
import { renderPlayer } from './player.js';
import { renderAdmin } from './admin.js';

const state = {
    token: localStorage.getItem('starstream_token'),
    username: localStorage.getItem('starstream_username'),
    role: localStorage.getItem('starstream_role'),
};

export function getToken() { return state.token; }
export function getUsername() { return state.username; }
export function getRole() { return state.role; }

export function setAuth(token, username, role) {
    state.token = token;
    state.username = username;
    state.role = role;
    localStorage.setItem('starstream_token', token);
    localStorage.setItem('starstream_username', username);
    localStorage.setItem('starstream_role', role);
}

export function logout() {
    state.token = null;
    state.username = null;
    state.role = null;
    localStorage.removeItem('starstream_token');
    localStorage.removeItem('starstream_username');
    localStorage.removeItem('starstream_role');
    navigate('login');
}

export async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }
    const res = await fetch(path, { ...options, headers });
    if (res.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    return res;
}

export function navigate(page, params = {}) {
    const hash = params.id ? `#/${page}/${params.id}` : `#/${page}`;
    window.location.hash = hash;
}

function router() {
    const hash = window.location.hash || '#/browse';
    const parts = hash.slice(2).split('/');
    const page = parts[0] || 'browse';
    const id = parts[1] || null;

    const navbar = document.getElementById('navbar');
    const content = document.getElementById('content');

    if (!state.token && page !== 'login') {
        navbar.classList.add('hidden');
        renderAuth(content);
        return;
    }

    if (state.token) {
        navbar.classList.remove('hidden');
        document.getElementById('username-display').textContent = state.username;

        const adminLink = document.getElementById('admin-link');
        if (state.role === 'admin') {
            adminLink.classList.remove('hidden');
        } else {
            adminLink.classList.add('hidden');
        }

        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.page === page);
        });
    }

    switch (page) {
        case 'login':
            navbar.classList.add('hidden');
            renderAuth(content);
            break;
        case 'browse':
            renderBrowse(content);
            break;
        case 'libraries':
            renderLibrary(content);
            break;
        case 'play':
            renderPlayer(content, id);
            break;
        case 'admin':
            if (state.role === 'admin') {
                renderAdmin(content);
            } else {
                renderBrowse(content);
            }
            break;
        default:
            renderBrowse(content);
    }
}

document.getElementById('logout-btn').addEventListener('click', logout);
window.addEventListener('hashchange', router);
router();
