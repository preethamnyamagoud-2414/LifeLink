/**
 * LifeLink - Donor Search Engine
 * Geolocation distance sorting, biological compatibility matching, 
 * filter controls, loading animations, robust error handling, and privacy-protected contact.
 */
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const form = $('donorSearchForm');
    if (!form) return;

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
    const submitBtn = $('searchSubmitBtn');

    let coords = null;
    let me = null;
    let isSearching = false;

    // Pre-fill from URL parameters (e.g. from home page quick search or request tracker)
    const params = new URLSearchParams(location.search);
    const bgParam = params.get('blood_group');
    if (bgParam) {
        try {
            const radio = form.querySelector(`input[name="blood_group"][value="${CSS.escape(bgParam.toUpperCase())}"]`);
            if (radio) radio.checked = true;
        } catch (e) {
            // Fallback for older browsers without CSS.escape
            const radios = form.querySelectorAll('input[name="blood_group"]');
            radios.forEach(r => { if (r.value.toUpperCase() === bgParam.toUpperCase()) r.checked = true; });
        }
    }
    const locParam = params.get('location') || params.get('city');
    if (locParam && textLoc) {
        textLoc.value = locParam;
    }

    function setBanner(kind, html, showBtn, btnLabel) {
        if (!banner || !bannerText) return;
        banner.classList.remove('is-error', 'is-ok');
        if (kind) banner.classList.add(kind);
        bannerText.innerHTML = html;
        if (locBtn) {
            locBtn.style.display = showBtn ? '' : 'none';
            if (btnLabel) locBtn.innerHTML = btnLabel;
        }
        if (window.LL && typeof LL.icons === 'function') LL.icons();
    }

    async function requestLocation() {
        if (locBtn) locBtn.disabled = true;
        let perm = 'prompt';
        if (window.LL && typeof LL.locationPermission === 'function') {
            try { perm = await LL.locationPermission(); } catch (e) {}
        }
        
        setBanner('', perm === 'granted'
            ? 'Detecting your coordinates (browser permission already authorized)...'
            : 'Waiting for location authorization — click <strong>Allow</strong> in your browser prompt...', true);

        try {
            if (window.LL && typeof LL.getLocation === 'function') {
                coords = await LL.getLocation();
            } else if (navigator.geolocation) {
                coords = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(
                        pos => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: Math.round(pos.coords.accuracy) }),
                        err => reject(new Error(err.message || 'Location access denied')),
                        { timeout: 10000, enableHighAccuracy: true }
                    );
                });
            } else {
                throw new Error('Geolocation is not supported by your browser.');
            }

            setBanner('is-ok', `<strong>Location active</strong> (accuracy ±${coords.accuracy} m). Donors are ordered by biological compatibility and distance.`, true, '<i data-lucide="refresh-cw"></i> Refresh GPS');
            if (radius) radius.disabled = false;
        } catch (e) {
            coords = null;
            setBanner('is-error', `<strong>GPS location optional.</strong> ${window.LL && LL.esc ? LL.esc(e.message) : e.message}. You can search by entering a city or district below.`, true, '<i data-lucide="crosshair"></i> Retry GPS');
        } finally {
            if (locBtn) locBtn.disabled = false;
        }
        search(false);
    }

    async function search(scroll) {
        if (isSearching) return;
        isSearching = true;

        const origBtnHtml = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="pulse-dot"></span> <span>Searching...</span>';
        }

        if (loading) loading.classList.add('active');
        if (results) results.style.display = 'none';
        if (empty) empty.style.display = 'none';

        try {
            const fd = new FormData(form);
            const q = new URLSearchParams();
            q.set('blood_group', fd.get('blood_group') || 'ALL');
            q.set('available_only', fd.get('available_only') ? '1' : '0');
            q.set('compatible', fd.get('compatible') ? '1' : '0');
            q.set('format', 'json');

            if (coords) {
                q.set('lat', coords.lat);
                q.set('lng', coords.lng);
                if (radius && radius.value) q.set('radius_km', radius.value);
            }
            if (textLoc && textLoc.value.trim()) {
                q.set('location', textLoc.value.trim());
            }

            let data = null;
            if (window.LL && typeof LL.api === 'function') {
                data = await LL.api('/api/donors/search?' + q.toString());
            } else {
                const resp = await fetch('/api/donors/search?' + q.toString(), {
                    headers: { 'Accept': 'application/json' }
                });
                data = await resp.json();
            }

            render(data);
            if (scroll && results && data && data.donors && data.donors.length) {
                results.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } catch (e) {
            console.error('Donor search failed:', e);
            if (countText) countText.textContent = 'Search failed';
            if (empty) {
                empty.style.display = 'block';
                const emptyTitle = empty.querySelector('.empty-search-title');
                const emptyDesc = empty.querySelector('.empty-search-desc');
                if (emptyTitle) emptyTitle.textContent = 'Unable to Load Donors';
                if (emptyDesc) emptyDesc.textContent = e.message || 'Please check your connection or database server and try again.';
            }
            if (window.LL && typeof LL.toast === 'function') {
                LL.toast(e.message || 'Error communicating with search registry.', 'error');
            } else if (window.showLifeLinkToast) {
                window.showLifeLinkToast(e.message || 'Error communicating with search registry.', 'error');
            }
        } finally {
            isSearching = false;
            if (loading) loading.classList.remove('active');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = origBtnHtml || '<i data-lucide="search"></i> <span>Search Donors</span>';
            }
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    }

    function render(data) {
        const donors = (data && data.donors) ? data.donors : [];
        const count = donors.length;

        if (countText) {
            countText.textContent = `${count} Verified ${count === 1 ? 'Donor' : 'Donors'} Found`;
        }

        const locText = textLoc ? textLoc.value.trim() : '';
        if (nearBadge) {
            if (coords && radius) {
                nearBadge.style.display = '';
                nearBadge.textContent = radius.value === '0' ? 'Near you, any distance' : `Within ${radius.value} km of you`;
            } else if (locText) {
                nearBadge.style.display = '';
                nearBadge.textContent = `In: ${locText}`;
            } else {
                nearBadge.style.display = 'none';
            }
        }

        if (!donors.length) {
            if (results) results.style.display = 'none';
            if (empty) {
                empty.style.display = 'block';
                const emptyTitle = empty.querySelector('.empty-search-title');
                const emptyDesc = empty.querySelector('.empty-search-desc');
                if (emptyTitle) emptyTitle.textContent = 'No Matching Donors Found in this Area';
                if (emptyDesc) {
                    emptyDesc.textContent = locText
                        ? `We could not find active donors matching your current filter criteria in "${locText}".`
                        : 'We could not find active donors matching your current filter criteria.';
                }
            }
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
            return;
        }

        if (empty) empty.style.display = 'none';
        if (results) {
            results.style.display = 'grid';
            results.innerHTML = donors.map(card).join('');
        }
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    function card(d) {
        const isAvail = (d.is_available === true || d.is_available === 1 || d.is_available === '1');
        const status = isAvail
            ? '<span class="badge badge-success"><span class="pulse-dot"></span> Available Now</span>'
            : '<span class="badge badge-neutral"><i data-lucide="moon"></i> Resting Cooldown</span>';

        let dist = '';
        if (d.distance_km != null) {
            dist = `<span class="ll-distance"><i data-lucide="navigation"></i> ${window.LL && LL.fmtKm ? LL.fmtKm(d.distance_km) : d.distance_km + ' km'} away</span>`;
        } else {
            dist = '<span class="ll-muted">Distance calculated upon GPS share</span>';
        }

        const cityDistrict = [d.city, d.district, d.state].filter(Boolean).join(', ') || 'Regional Registry';
        const donations = d.donations_count != null ? d.donations_count : (d.total_donations || 0);
        const matchText = d.exact_match ? 'Exact Blood Group Match' : 'Compatible Biological Donor';
        const contactPref = (d.contact_preference || 'both').toLowerCase();
        let prefLabel = 'Phone & Email';
        if (contactPref === 'phone') prefLabel = 'Phone Preferred';
        else if (contactPref === 'email') prefLabel = 'Email Preferred';

        const rawName = d.display_name || 'Verified Donor';
        const name = window.LL && LL.esc ? LL.esc(rawName) : rawName;
        const initials = window.LL && LL.initials ? LL.esc(LL.initials(rawName)) : rawName.slice(0, 2).toUpperCase();
        const bg = window.LL && LL.esc ? LL.esc(d.blood_group || 'O+') : (d.blood_group || 'O+');

        return `
        <div class="card card-hover">
            <div class="card-body">
                <div class="donor-card-header">
                    <div class="donor-identity-box">
                        <div class="donor-avatar-circle">${initials}</div>
                        <div class="donor-meta-info">
                            <h3>${name} <i data-lucide="shield-check" style="width: 16px; height: 16px; color: var(--color-success-dark);" title="Verified Donor"></i></h3>
                            <div class="donor-location-tag">
                                <i data-lucide="map-pin" style="width: 14px; height: 14px;"></i>
                                <span>${window.LL && LL.esc ? LL.esc(cityDistrict) : cityDistrict}</span>
                            </div>
                        </div>
                    </div>
                    <div class="blood-symbol-pill" style="width: 48px; height: 48px; font-size: 1.25rem; margin-bottom: 0;">${bg}</div>
                </div>
                <div class="donor-info-list">
                    <div class="donor-info-row"><span class="donor-info-label">Availability:</span> ${status}</div>
                    <div class="donor-info-row"><span class="donor-info-label">Donation Track:</span> <span class="donor-info-val">${donations} Transfusions Facilitated</span></div>
                    <div class="donor-info-row"><span class="donor-info-label">Match Tier:</span> <span class="donor-info-val">${matchText}</span></div>
                    <div class="donor-info-row"><span class="donor-info-label">Contact Route:</span>
                        <span style="font-size: 0.8125rem; color: var(--color-text-muted); display: inline-flex; align-items: center; gap: 4px;">
                            <i data-lucide="lock" style="width: 12px; height: 12px;"></i> ${prefLabel}
                        </span>
                    </div>
                </div>
                <button class="btn btn-primary btn-block btn-sm" type="button" data-contact="${d.user_id}" data-name="${name}" data-bg="${bg}">
                    <i data-lucide="send"></i> Request Emergency Contact
                </button>
            </div>
        </div>`;
    }

    // Attach search form listeners
    form.addEventListener('submit', e => {
        e.preventDefault();
        search(true);
    });

    form.querySelectorAll('.blood-pill-option input, input[type="checkbox"]').forEach(el => {
        el.addEventListener('change', () => search(false));
    });

    if (radius) {
        radius.addEventListener('change', () => search(false));
    }
    if (locBtn) {
        locBtn.addEventListener('click', requestLocation);
    }

    // Contact modal handling
    const modal = $('contactModalOverlay');
    const closeContactModal = () => {
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    if (results) {
        results.addEventListener('click', e => {
            const b = e.target.closest('[data-contact]');
            if (!b || !modal) return;
            if ($('modalDonorDisplayName')) $('modalDonorDisplayName').textContent = b.dataset.name;
            if ($('modalDonorBloodGroup')) $('modalDonorBloodGroup').textContent = b.dataset.bg;
            if ($('modalTargetDonorId')) $('modalTargetDonorId').value = b.dataset.contact;
            if (me && me.user) {
                if ($('modalReqName') && !$('modalReqName').value) $('modalReqName').value = me.user.full_name || '';
                if ($('modalReqPhone') && !$('modalReqPhone').value) $('modalReqPhone').value = me.user.phone || '';
            }
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
            setTimeout(() => { if ($('modalReqName')) $('modalReqName').focus(); }, 60);
        });
    }

    window.openContactModal = function (id, name, bgv) {
        if (!modal) return;
        if ($('modalDonorDisplayName')) $('modalDonorDisplayName').textContent = name;
        if ($('modalDonorBloodGroup')) $('modalDonorBloodGroup').textContent = bgv;
        if ($('modalTargetDonorId')) $('modalTargetDonorId').value = id;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
    };

    const closeBtn = $('contactModalClose');
    const cancelBtn = $('contactModalCancel');
    if (closeBtn) closeBtn.addEventListener('click', closeContactModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeContactModal);
    if (modal) {
        modal.addEventListener('click', e => { if (e.target === modal) closeContactModal(); });
    }

    const contactForm = $('secureContactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', async e => {
            e.preventDefault();
            const btn = contactForm.querySelector('button[type="submit"]');
            if (btn) btn.disabled = true;

            const payload = {
                donor_user_id: Number($('modalTargetDonorId')?.value),
                requester_name: ($('modalReqName')?.value || '').trim(),
                requester_phone: ($('modalReqPhone')?.value || '').trim(),
                case_notes: ($('modalReqNotes')?.value || '').trim()
            };

            const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';

            try {
                let resData;
                if (window.LL && typeof LL.api === 'function') {
                    resData = await LL.api('/api/donors/contact-request', { body: payload });
                } else {
                    const resp = await fetch('/api/donors/contact-request', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify(payload)
                    });
                    resData = await resp.json();
                }

                closeContactModal();
                if ($('modalReqNotes')) $('modalReqNotes').value = '';
                if (window.LL && typeof LL.toast === 'function') {
                    LL.toast(resData.message || 'Contact request sent to donor.');
                } else if (window.showLifeLinkToast) {
                    window.showLifeLinkToast(resData.message || 'Contact request sent to donor.', 'success');
                } else {
                    alert(resData.message || 'Contact request sent to donor.');
                }
            } catch (err) {
                if (window.LL && typeof LL.toast === 'function') {
                    LL.toast(err.message || 'Failed to dispatch contact request.', 'error');
                } else if (window.showLifeLinkToast) {
                    window.showLifeLinkToast(err.message || 'Failed to dispatch contact request.', 'error');
                } else {
                    alert(err.message || 'Failed to dispatch contact request.');
                }
            } finally {
                if (btn) btn.disabled = false;
            }
        });
    }

    // Initialize public navigation session if available
    if (window.LL && typeof LL.initPublicNav === 'function') {
        LL.initPublicNav().then(d => { me = d; }).catch(() => {});
    }

    if (radius) {
        radius.disabled = true;
    }

    // Only auto-request location if the browser permission has already been granted
    if (window.LL && typeof LL.locationPermission === 'function') {
        LL.locationPermission().then(state => {
            if (state === 'granted') {
                requestLocation();
            } else {
                setBanner('', 'Enable location access to discover active donors closest to you, with exact distance calculation.', true, '<i data-lucide="crosshair"></i> Use My Current Location');
            }
        }).catch(() => {});
    }

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
});
