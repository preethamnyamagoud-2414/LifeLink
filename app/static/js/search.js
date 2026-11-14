/**
 * LifeLink - Donor search: geolocation, distance sorting, compatibility filtering, privacy-safe contact.
 */
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const form = $('donorSearchForm');
    const loading = $('searchLoadingState');
    const results = $('donorResultsContainer');
    const empty = $('searchEmptyState');
    const countText = $('resultsCountText');
    const nearBadge = $('resultsNearBadge');
    const banner = $('locationBanner');
    const bannerText = $('locationBannerText');
    const locBtn = $('useLocationBtn');
    const radius = $('radiusSelect');
    const textLoc = $('searchLocationInput');

    let coords = null;
    let me = null;

    // Pre-fill from URL (e.g. home page quick lookup or "Find more O- donors")
    const params = new URLSearchParams(location.search);
    const bg = params.get('blood_group');
    if (bg) {
        const radio = form.querySelector(`input[name="blood_group"][value="${CSS.escape(bg)}"]`);
        if (radio) radio.checked = true;
    }
    if (params.get('location')) textLoc.value = params.get('location');

    function setBanner(kind, html, showBtn, btnLabel) {
        banner.classList.remove('is-error', 'is-ok');
        if (kind) banner.classList.add(kind);
        bannerText.innerHTML = html;
        locBtn.style.display = showBtn ? '' : 'none';
        if (btnLabel) locBtn.innerHTML = btnLabel;
        LL.icons();
    }

    async function requestLocation() {
        locBtn.disabled = true;
        const perm = await LL.locationPermission();
        setBanner('', perm === 'granted'
            ? 'Getting your location (location is already allowed for this site, so the browser will not ask again)...'
            : 'Waiting for location permission - click <strong>Allow</strong> in the prompt near the address bar...', true);
        try {
            coords = await LL.getLocation();
            setBanner('is-ok', `<strong>Using your current location</strong> (accurate to about ${coords.accuracy} m; location access is allowed for this site). Donors are sorted by distance.`, true, '<i data-lucide="refresh-cw"></i> Refresh location');
            radius.disabled = false;
        } catch (e) {
            coords = null;
            setBanner('is-error', `<strong>Location needed for nearby donors.</strong> ${LL.esc(e.message)} You can still search by typing a city.`, true, '<i data-lucide="crosshair"></i> Try again');
        } finally {
            locBtn.disabled = false;
        }
        search(false);
    }

    function search(scroll) {
        const fd = new FormData(form);
        const q = new URLSearchParams();
        q.set('blood_group', fd.get('blood_group') || 'ALL');
        q.set('available_only', fd.get('available_only') ? '1' : '0');
        q.set('compatible', fd.get('compatible') ? '1' : '0');
        if (coords) {
            q.set('lat', coords.lat);
            q.set('lng', coords.lng);
            q.set('radius_km', radius.value);
        } else if (textLoc.value.trim()) {
            q.set('location', textLoc.value.trim());
        }

        loading && loading.classList.add('active');
        results.style.display = 'none';
        empty.style.display = 'none';

        LL.api('/api/donors/search?' + q.toString())
            .then(data => {
                render(data);
                if (scroll) results.scrollIntoView({ behavior: 'smooth', block: 'start' });
            })
            .catch(e => {
                countText.textContent = 'Search failed';
                LL.toast(e.message, 'error');
            })
            .finally(() => loading && loading.classList.remove('active'));
    }

    function render(data) {
        const donors = data.donors || [];
        countText.textContent = `${donors.length} ${donors.length === 1 ? 'donor' : 'donors'} found`;
        if (coords) {
            nearBadge.style.display = '';
            nearBadge.textContent = radius.value === '0' ? 'Near you, any distance' : `Within ${radius.value} km of you`;
        } else if (textLoc.value.trim()) {
            nearBadge.style.display = '';
            nearBadge.textContent = `In: ${textLoc.value.trim()}`;
        } else {
            nearBadge.style.display = 'none';
        }

        if (!donors.length) {
            empty.style.display = 'block';
            LL.icons();
            return;
        }
        results.style.display = 'grid';
        results.innerHTML = donors.map(card).join('');
        LL.icons();
    }

    function card(d) {
        const status = d.is_available
            ? '<span class="badge badge-success"><span class="pulse-dot"></span> Available now</span>'
            : '<span class="badge badge-neutral"><i data-lucide="moon"></i> Alerts paused</span>';
        const dist = d.distance_km != null
            ? `<span class="ll-distance"><i data-lucide="navigation"></i> ${LL.fmtKm(d.distance_km)} away</span>`
            : '<span class="ll-muted">Distance unknown (location off)</span>';
        return `
        <div class="card card-hover">
            <div class="card-body">
                <div class="donor-card-header">
                    <div class="donor-identity-box">
                        <div class="donor-avatar-circle">${LL.esc(LL.initials(d.display_name))}</div>
                        <div class="donor-meta-info">
                            <h3>${LL.esc(d.display_name)} <i data-lucide="shield-check" style="width: 16px; height: 16px; color: var(--color-success-dark);" title="Passed health screening"></i></h3>
                            <div class="donor-location-tag"><i data-lucide="map-pin" style="width: 14px; height: 14px;"></i>
                                <span>${LL.esc([d.district, d.city].filter(Boolean).join(', ') || 'Location shared')}</span></div>
                        </div>
                    </div>
                    <div class="blood-symbol-pill" style="width: 48px; height: 48px; font-size: 1.25rem; margin-bottom: 0;">${LL.esc(d.blood_group)}</div>
                </div>
                <div class="donor-info-list">
                    <div class="donor-info-row"><span class="donor-info-label">Distance:</span> ${dist}</div>
                    <div class="donor-info-row"><span class="donor-info-label">Status:</span> ${status}</div>
                    <div class="donor-info-row"><span class="donor-info-label">Match:</span>
                        <span class="donor-info-val">${d.exact_match ? 'Exact blood group' : 'Compatible donor'}</span></div>
                    <div class="donor-info-row"><span class="donor-info-label">Donations:</span> <span class="donor-info-val">${d.donations_count} recorded</span></div>
                </div>
                <button class="btn btn-primary btn-block btn-sm" type="button" data-contact="${d.user_id}" data-name="${LL.esc(d.display_name)}" data-bg="${LL.esc(d.blood_group)}">
                    <i data-lucide="send"></i> Request Emergency Contact
                </button>
            </div>
        </div>`;
    }

    // ---------- events ----------
    form.addEventListener('submit', e => { e.preventDefault(); search(true); });
    form.querySelectorAll('.blood-pill-option input, input[type="checkbox"]').forEach(el => el.addEventListener('change', () => search(false)));
    radius.addEventListener('change', () => search(false));
    locBtn.addEventListener('click', requestLocation);
    const resetBtn = $('resetFiltersBtn');
    if (resetBtn) resetBtn.addEventListener('click', () => {
        form.querySelector('input[name="blood_group"][value="ALL"]').checked = true;
        form.querySelector('input[name="available_only"]').checked = false;
        form.querySelector('input[name="compatible"]').checked = true;
        radius.value = '0';
        textLoc.value = '';
        search(true);
    });

    // ---------- contact modal ----------
    const modal = $('contactModalOverlay');
    const close = () => { modal.classList.remove('active'); document.body.style.overflow = ''; };
    results.addEventListener('click', e => {
        const b = e.target.closest('[data-contact]');
        if (!b) return;
        $('modalDonorDisplayName').textContent = b.dataset.name;
        $('modalDonorBloodGroup').textContent = b.dataset.bg;
        $('modalTargetDonorId').value = b.dataset.contact;
        if (me) {
            if (!$('modalReqName').value) $('modalReqName').value = me.user.full_name;
            if (!$('modalReqPhone').value) $('modalReqPhone').value = me.user.phone || '';
        }
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        LL.icons();
        setTimeout(() => $('modalReqName').focus(), 50);
    });
    window.openContactModal = function (id, name, bgv) { // kept for compatibility
        $('modalDonorDisplayName').textContent = name;
        $('modalDonorBloodGroup').textContent = bgv;
        $('modalTargetDonorId').value = id;
        modal.classList.add('active');
    };
    $('contactModalClose').addEventListener('click', close);
    $('contactModalCancel').addEventListener('click', close);
    modal.addEventListener('click', e => { if (e.target === modal) close(); });

    $('secureContactForm').addEventListener('submit', async e => {
        e.preventDefault();
        const btn = e.target.querySelector('button[type="submit"]');
        btn.disabled = true;
        try {
            const d = await LL.api('/api/donors/contact-request', {
                body: {
                    donor_user_id: Number($('modalTargetDonorId').value),
                    requester_name: $('modalReqName').value.trim(),
                    requester_phone: $('modalReqPhone').value.trim(),
                    case_notes: $('modalReqNotes').value.trim()
                }
            });
            close();
            $('modalReqNotes').value = '';
            LL.toast(d.message);
        } catch (err) {
            LL.toast(err.message, 'error');
        } finally {
            btn.disabled = false;
        }
    });

    // ---------- start ----------
    LL.initPublicNav().then(d => { me = d; }).catch(() => {});
    radius.disabled = true;
    LL.locationPermission().then(state => {
        if (state === 'granted' || state === 'prompt') {
            requestLocation();
        } else {
            setBanner('is-error', '<strong>Location access is blocked for this site.</strong> Click the location icon in the address bar and choose "Allow" to see nearby donors with distance. Showing all donors for now.', true, '<i data-lucide="crosshair"></i> Try again');
            search(false);
        }
    });
});
