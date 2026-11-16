/**
 * LifeLink shared client helpers: API calls, session, formatting, modals, geolocation.
 * Load after main.js on every page.
 */
(function () {
    'use strict';

    const COMPAT = {
        'O-': ['O-'],
        'O+': ['O-', 'O+'],
        'A-': ['O-', 'A-'],
        'A+': ['O-', 'O+', 'A-', 'A+'],
        'B-': ['O-', 'B-'],
        'B+': ['O-', 'O+', 'B-', 'B+'],
        'AB-': ['O-', 'A-', 'B-', 'AB-'],
        'AB+': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
    };

    async function api(path, opts = {}) {
        const o = {
            method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'),
            headers: { 'Accept': 'application/json', ...(opts.headers || {}) },
            credentials: 'same-origin'
        };

        const csrfMeta = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        const csrfInput = document.querySelector('input[name="csrf_token"]')?.value;
        const csrfToken = csrfMeta || csrfInput || '';
        if (csrfToken && !o.headers['X-CSRFToken']) {
            o.headers['X-CSRFToken'] = csrfToken;
        }

        if (opts.body !== undefined) {
            o.headers['Content-Type'] = 'application/json';
            let bodyObj = opts.body;
            if (typeof bodyObj === 'object' && bodyObj !== null && !Array.isArray(bodyObj)) {
                if (csrfToken && !bodyObj.csrf_token) {
                    bodyObj = { ...bodyObj, csrf_token: csrfToken };
                }
            }
            o.body = JSON.stringify(bodyObj);
        }
        let res;
        try {
            res = await fetch(path, o);
        } catch (e) {
            const err = new Error('Cannot reach the LifeLink server. Make sure the server is reachable.');
            err.status = 0;
            throw err;
        }
        let data = {};
        try { data = await res.json(); } catch (e) { /* non-JSON */ }
        if (!res.ok || data.success === false) {
            const err = new Error(data.message || `Request failed (${res.status})`);
            err.status = res.status;
            err.data = data;
            throw err;
        }
        return data;
    }

    function storeUser(user) {
        try {
            if (user) {
                localStorage.setItem('lifelink_active_user', JSON.stringify(user));
                sessionStorage.setItem('lifelink_user', JSON.stringify(user));
            }
        } catch (e) { /* storage unavailable */ }
    }
    function clearUser() {
        try {
            localStorage.removeItem('lifelink_active_user');
            sessionStorage.removeItem('lifelink_user');
            localStorage.removeItem('lifelink_registered_users');
        } catch (e) { /* ignore */ }
    }
    function cachedUser() {
        try { return JSON.parse(sessionStorage.getItem('lifelink_user') || localStorage.getItem('lifelink_active_user') || 'null'); }
        catch (e) { return null; }
    }

    /** Returns {user, donor, unread_notifications, dashboard} or null when signed out. */
    async function me() {
        try {
            const d = await api('/api/auth/me');
            storeUser(d.user);
            return d;
        } catch (e) {
            if (e.status === 401) { clearUser(); return null; }
            throw e;
        }
    }

    /** Redirects to sign-in when not signed in. Never resolves in that case. */
    async function requireAuth() {
        let d = null;
        try { d = await me(); } catch (e) { toast(e.message, 'error'); }
        if (!d) {
            const next = encodeURIComponent(location.pathname + location.search + location.hash);
            location.replace('/auth/login?auth=required&next=' + next);
            return new Promise(() => {});
        }
        return d;
    }

    function logout() {
        clearUser();
        api('/api/auth/logout', { method: 'POST' }).catch(() => {}).finally(() => location.replace('/auth/login'));
    }

    function dashboardFor(user) {
        if (!user) return '/auth/login';
        if (user.role === 'admin') return '/admin/dashboard';
        if (user.role === 'donor') return '/donor/dashboard';
        return '/patient/dashboard';
    }

    // ---------- formatting ----------
    function esc(v) {
        if (v === null || v === undefined) return '';
        return String(v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }
    function initials(name) {
        return (name || '?').trim().split(/\s+/).map(p => p[0]).join('').substring(0, 2).toUpperCase();
    }
    function reqCode(id) { return 'REQ-' + String(id).padStart(4, '0'); }
    function parseDate(s) {
        if (!s) return null;
        const d = new Date(String(s).replace(' ', 'T'));
        return isNaN(d) ? null : d;
    }
    function fmtDate(s) {
        const d = parseDate(s);
        if (!d) return s || '';
        return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
    }
    function fmtDateTime(s) {
        const d = parseDate(s);
        if (!d) return s || '';
        return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
    function timeAgo(s) {
        const d = parseDate(s);
        if (!d) return '';
        const sec = Math.round((Date.now() - d.getTime()) / 1000);
        if (sec < 60) return 'just now';
        const min = Math.round(sec / 60);
        if (min < 60) return `${min} min ago`;
        const hr = Math.round(min / 60);
        if (hr < 24) return `${hr} h ago`;
        const day = Math.round(hr / 24);
        if (day < 30) return `${day} d ago`;
        return fmtDate(s);
    }
    function fmtKm(km) {
        if (km === null || km === undefined) return '';
        return km < 1 ? `${Math.round(km * 1000)} m` : `${Number(km).toFixed(1)} km`;
    }
    function urgencyBadge(u) {
        const cls = u === 'CRITICAL' ? 'badge-critical' : (u === 'URGENT' ? 'badge-urgent' : 'badge-neutral');
        const pulse = u === 'CRITICAL' ? '<span class="pulse-dot"></span> ' : '';
        return `<span class="badge ${cls}">${pulse}${esc(u)}</span>`;
    }
    function statusBadge(s) {
        if (s === 'ACTIVE') return '<span class="badge badge-success"><span class="pulse-dot"></span> Active</span>';
        if (s === 'FULFILLED') return '<span class="badge badge-standard"><i data-lucide="check-circle-2"></i> Fulfilled</span>';
        if (s === 'CANCELLED') return '<span class="badge badge-neutral"><i data-lucide="x-circle"></i> Cancelled</span>';
        return `<span class="badge badge-neutral">${esc(s)}</span>`;
    }
    function responseBadge(s) {
        if (s === 'OFFERED') return '<span class="badge badge-success"><span class="pulse-dot"></span> Volunteered</span>';
        if (s === 'DONATED') return '<span class="badge badge-standard"><i data-lucide="heart"></i> Donated</span>';
        if (s === 'WITHDRAWN') return '<span class="badge badge-neutral">Withdrawn</span>';
        return `<span class="badge badge-neutral">${esc(s)}</span>`;
    }
    function eligibilityBadge(el) {
        if (!el) return '';
        if (el.status === 'ELIGIBLE') return '<span class="badge badge-success"><i data-lucide="check"></i> Eligible to donate</span>';
        if (el.status === 'PERMANENT_DEFERRAL') return '<span class="badge badge-critical"><i data-lucide="ban"></i> Not eligible</span>';
        return `<span class="badge badge-urgent"><i data-lucide="clock"></i> Not eligible ${el.eligible_from ? 'until ' + esc(fmtDate(el.eligible_from)) : 'right now'}</span>`;
    }
    function icons() { if (window.lucide) window.lucide.createIcons(); }

    function toast(message, type) {
        if (window.showLifeLinkToast) window.showLifeLinkToast(esc(message), type);
        else alert(message);
    }

    // ---------- modal ----------
    let activeModal = null;
    function closeModal() {
        if (!activeModal) return;
        activeModal.remove();
        activeModal = null;
        document.body.style.overflow = '';
    }
    /**
     * openModal({title, body (html), actions: [{label, cls, onClick(modalEl) -> (false to keep open), id}], wide})
     */
    function openModal(opts) {
        closeModal();
        const ov = document.createElement('div');
        ov.className = 'll-modal-overlay';
        ov.innerHTML = `
            <div class="ll-modal ${opts.wide ? 'll-modal-wide' : ''}" role="dialog" aria-modal="true" aria-label="${esc(opts.title)}">
                <div class="ll-modal-header">
                    <h3>${esc(opts.title)}</h3>
                    <button type="button" class="ll-modal-close" aria-label="Close"><i data-lucide="x"></i></button>
                </div>
                <div class="ll-modal-body">${opts.body || ''}</div>
                <div class="ll-modal-error alert alert-danger" style="display:none;"></div>
                <div class="ll-modal-footer"></div>
            </div>`;
        const footer = ov.querySelector('.ll-modal-footer');
        (opts.actions || [{ label: 'Close', cls: 'btn-outline' }]).forEach(a => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'btn ' + (a.cls || 'btn-primary');
            b.innerHTML = a.label;
            b.addEventListener('click', async () => {
                if (!a.onClick) { closeModal(); return; }
                const errBox = ov.querySelector('.ll-modal-error');
                errBox.style.display = 'none';
                const orig = b.innerHTML;
                b.disabled = true;
                b.innerHTML = 'Please wait...';
                try {
                    const keep = await a.onClick(ov);
                    if (keep !== false) closeModal();
                } catch (e) {
                    errBox.textContent = e.message || String(e);
                    errBox.style.display = 'block';
                } finally {
                    b.disabled = false;
                    b.innerHTML = orig;
                    icons();
                }
            });
            footer.appendChild(b);
        });
        ov.querySelector('.ll-modal-close').addEventListener('click', closeModal);
        ov.addEventListener('click', e => { if (e.target === ov) closeModal(); });
        document.body.appendChild(ov);
        document.body.style.overflow = 'hidden';
        activeModal = ov;
        icons();
        const first = ov.querySelector('input, select, textarea');
        if (first) setTimeout(() => first.focus(), 50);
        if (opts.onOpen) opts.onOpen(ov);
        return ov;
    }
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

    function confirmAction(title, message, confirmLabel, onConfirm, danger) {
        return openModal({
            title,
            body: `<p style="font-size:0.9rem;color:var(--color-text-muted);margin:0;">${message}</p>`,
            actions: [
                { label: 'Go back', cls: 'btn-outline' },
                { label: confirmLabel, cls: danger ? 'btn-emergency' : 'btn-primary', onClick: onConfirm }
            ]
        });
    }

    // ---------- geolocation ----------
    function getLocation() {
        return new Promise((resolve, reject) => {
            if (!('geolocation' in navigator)) {
                reject(new Error('This browser does not support location access.'));
                return;
            }
            if (!window.isSecureContext) {
                reject(new Error('Location only works when the site is opened from http://localhost (start run.bat).'));
                return;
            }
            navigator.geolocation.getCurrentPosition(
                pos => resolve({ lat: +pos.coords.latitude.toFixed(6), lng: +pos.coords.longitude.toFixed(6), accuracy: Math.round(pos.coords.accuracy) }),
                err => {
                    let msg = 'Could not get your location.';
                    if (err.code === 1) msg = 'Location permission was denied. Click the location icon in the address bar, choose "Allow", then try again.';
                    else if (err.code === 2) msg = 'Your location is unavailable. Check that Windows location services are turned on.';
                    else if (err.code === 3) msg = 'Getting your location timed out. Please try again.';
                    reject(new Error(msg));
                },
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
            );
        });
    }
    async function locationPermission() {
        try {
            if (navigator.permissions) {
                const p = await navigator.permissions.query({ name: 'geolocation' });
                return p.state; // granted | prompt | denied
            }
        } catch (e) { /* ignore */ }
        return 'prompt';
    }

    // ---------- public navbar (sign-in state) ----------
    async function initPublicNav() {
        const navAuth = document.getElementById('navAuthActions');
        const drawerActions = document.getElementById('mobileDrawerActions');
        if (!navAuth && !drawerActions) return null;
        let d = null;
        try { d = await me(); } catch (e) { return null; }
        if (!d) return null;
        const user = d.user;
        const dash = dashboardFor(user);
        const first = esc((user.full_name || 'Member').split(' ')[0]);
        document.querySelectorAll('[data-nav-dashboard]').forEach(el => {
            el.style.display = '';
            const a = el.tagName === 'A' ? el : el.querySelector('a');
            if (a) a.href = dash;
        });
        if (navAuth) {
            navAuth.innerHTML = `
                <a href="/emergency-request" class="btn btn-emergency btn-sm"><i data-lucide="alert-circle"></i> <span>Emergency Request</span></a>
                <a href="${dash}" class="btn btn-outline btn-sm"><i data-lucide="layout-dashboard"></i> <span>${first}</span></a>
                <button type="button" class="btn btn-outline btn-sm" data-logout style="border-color: rgba(220,38,38,0.3); color: var(--color-critical);"><i data-lucide="log-out"></i> <span>Sign Out</span></button>`;
        }
        if (drawerActions) {
            drawerActions.innerHTML = `
                <a href="/emergency-request" class="btn btn-emergency btn-block"><i data-lucide="alert-circle"></i> Emergency Request</a>
                <a href="${dash}" class="btn btn-outline btn-block"><i data-lucide="user"></i> My Dashboard (${first})</a>
                <button type="button" class="btn btn-outline btn-block" data-logout style="border-color: rgba(220,38,38,0.4); color: var(--color-critical);"><i data-lucide="log-out"></i> Sign Out</button>`;
        }
        icons();
        return d;
    }

    // Any element with data-logout signs the user out
    document.addEventListener('click', e => {
        const el = e.target.closest('[data-logout]');
        if (el) { e.preventDefault(); logout(); return; }
        // Close the mobile dashboard drawer after choosing a link
        const link = e.target.closest('.dashboard-sidebar.active a');
        if (link) {
            document.querySelector('.dashboard-sidebar').classList.remove('active');
            const ov = document.getElementById('dashboardNavOverlay');
            if (ov) ov.classList.remove('active');
            document.body.style.overflow = '';
        }
    });

    window.LL = {
        COMPAT, api, me, requireAuth, logout, dashboardFor, storeUser, clearUser, cachedUser,
        esc, initials, reqCode, fmtDate, fmtDateTime, timeAgo, fmtKm,
        urgencyBadge, statusBadge, responseBadge, eligibilityBadge, icons, toast,
        openModal, closeModal, confirmAction, getLocation, locationPermission, initPublicNav
    };
    // Backwards compatibility with existing inline handlers
    window.logoutLifeLinkPreview = logout;
})();
