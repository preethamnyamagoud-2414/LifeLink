/**
 * LifeLink - Emergency request form (review modal + API submit) and track-page share button.
 */
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);

    // -------------------------------------------------------------------------
    // 1. Emergency request form
    // -------------------------------------------------------------------------
    const requestForm = $('emergencyRequestForm');
    const reviewBtn = $('btnReviewRequest');
    const confirmModal = $('confirmRequestModal');
    const btnFinalSubmit = $('btnFinalSubmitRequest');
    let hospitalLoc = null;

    if (requestForm) {
        // Pre-fill contact details from the account if authenticated
        if (window.LL && typeof LL.me === 'function') {
            LL.me().then(d => {
                if (!d || !d.user) return;
                if (typeof LL.initPublicNav === 'function') LL.initPublicNav();
                const u = d.user;
                if ($('reqContactName') && !$('reqContactName').value) $('reqContactName').value = u.full_name || '';
                if ($('reqContactPhone') && !$('reqContactPhone').value) $('reqContactPhone').value = u.phone || '';
                if ($('reqContactEmail') && !$('reqContactEmail').value) $('reqContactEmail').value = u.email || '';
                if ($('reqCity') && !$('reqCity').value && u.city) $('reqCity').value = u.city;
                const params = new URLSearchParams(location.search);
                if (params.get('blood_group') && $('reqBloodGroup')) $('reqBloodGroup').value = params.get('blood_group');
            }).catch(e => {
                console.warn('Optional prefill skipped:', e);
            });
        }
        const dateInput = $('reqDate');
        const today = new Date();
        const iso = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
        dateInput.min = iso;
        if (!dateInput.value) dateInput.value = iso;

        const locBtn = $('hospitalLocationBtn');
        if (locBtn) {
            locBtn.addEventListener('click', async () => {
                const box = $('hospitalLocationBox');
                const text = $('hospitalLocationText');
                if (hospitalLoc) {
                    // Second click removes the shared location
                    hospitalLoc = null;
                    box.classList.remove('is-set');
                    text.textContent = 'Location removed. Donors in the same city will be alerted.';
                    locBtn.innerHTML = '<i data-lucide="crosshair"></i> Use my current location';
                    LL.icons();
                    return;
                }
                locBtn.disabled = true;
                text.textContent = 'Waiting for location permission...';
                box.classList.remove('is-error', 'is-set');
                try {
                    hospitalLoc = await LL.getLocation();
                    box.classList.add('is-set');
                    text.textContent = `Location captured (about ${hospitalLoc.accuracy} m accuracy). Donors will see the distance to the hospital.`;
                    locBtn.innerHTML = '<i data-lucide="x"></i> Remove location';
                } catch (e) {
                    box.classList.add('is-error');
                    text.textContent = e.message + ' The request will still be sent; donors in the same city will be alerted.';
                } finally {
                    locBtn.disabled = false;
                    LL.icons();
                }
            });
        }
    }

    const urgencyRadios = document.querySelectorAll('.urgency-card-option input[type="radio"]');
    urgencyRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            urgencyRadios.forEach(r => { if (r.nextElementSibling) r.nextElementSibling.style.transform = ''; });
            if (radio.nextElementSibling) radio.nextElementSibling.style.transform = 'translateY(-2px)';
        });
    });

    function val(id) { return ($(id)?.value || '').trim(); }
    function setText(id, v) { const el = $(id); if (el) el.textContent = v; }
    const methodLabel = { whatsapp: 'WhatsApp message', email: 'Email', call_or_msg: 'Phone call or SMS', phone: 'Direct phone call' };

    function openConfirm() {
        confirmModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    function closeConfirm() {
        confirmModal.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (requestForm) {
        requestForm.addEventListener('submit', (e) => {
            // Direct enter or submit routes through review confirmation modal
            if (!confirmModal || !confirmModal.classList.contains('active')) {
                e.preventDefault();
                if (reviewBtn) reviewBtn.click();
            }
        });
    }

    if (reviewBtn && requestForm) {
        reviewBtn.addEventListener('click', () => {
            if (!requestForm.checkValidity()) { requestForm.reportValidity(); return; }
            const units = val('reqUnits') || '1';
            setText('confPatientName', val('reqPatientName'));
            setText('confContactPerson', `${val('reqContactName')} (${val('reqContactPhone')}${val('reqContactEmail') ? ' • ' + val('reqContactEmail') : ''})`);
            setText('confPreferredMethod', methodLabel[val('reqPreferredMethod')] || 'Direct phone call');
            setText('confBloodGroup', `${val('reqBloodGroup')} (${units} unit${Number(units) > 1 ? 's' : ''})`);
            setText('confUrgency', document.querySelector('input[name="urgency_level"]:checked')?.value || 'URGENT');
            setText('confHospital', [val('reqHospitalName'), val('reqArea'), val('reqCity')].filter(Boolean).join(', ') + (hospitalLoc ? ' (location shared)' : ''));
            setText('confDate', val('reqDate') || 'Today');
            openConfirm();
        });
    }
    ['btnCancelConfirmModal', 'btnCloseConfirmModal'].forEach(id => { if ($(id)) $(id).addEventListener('click', closeConfirm); });
    if (confirmModal) confirmModal.addEventListener('click', e => { if (e.target === confirmModal) closeConfirm(); });

    if (btnFinalSubmit && requestForm) {
        btnFinalSubmit.addEventListener('click', async () => {
            const payload = {
                urgency_level: document.querySelector('input[name="urgency_level"]:checked')?.value || 'URGENT',
                patient_name: val('reqPatientName'),
                blood_group: val('reqBloodGroup'),
                units_needed: Number(val('reqUnits')) || 1,
                required_date: val('reqDate'),
                preferred_contact_method: val('reqPreferredMethod'),
                contact_person: val('reqContactName'),
                contact_phone: val('reqContactPhone'),
                contact_email: val('reqContactEmail'),
                hospital_name: val('reqHospitalName'),
                city: val('reqCity'),
                hospital_area: val('reqArea'),
                hospital_address: val('reqHospitalAddress'),
                doctor_name: val('reqDoctorName'),
                state: val('reqState'),
                additional_notes: val('reqNotes')
            };
            if (hospitalLoc) { payload.lat = hospitalLoc.lat; payload.lng = hospitalLoc.lng; }

            const orig = btnFinalSubmit.innerHTML;
            btnFinalSubmit.disabled = true;
            btnFinalSubmit.innerHTML = '<span class="pulse-dot"></span> Broadcasting...';
            try {
                const d = await LL.api('/api/requests', { body: payload });
                closeConfirm();
                LL.toast(`${d.code} posted. ${d.alerted} nearby compatible donor${d.alerted === 1 ? '' : 's'} alerted.`);
                setTimeout(() => { location.href = d.redirect; }, 900);
            } catch (e) {
                closeConfirm();
                LL.toast(e.message, 'error');
                if (e.status === 401) {
                    setTimeout(() => {
                        location.href = '/auth/login?next=/emergency-request';
                    }, 1200);
                } else if (!e.status || e.status === 0 || e.status >= 500) {
                    // Fallback to standard form submit so user is never blocked
                    console.warn('AJAX broadcast failed, submitting form directly as fallback...', e);
                    requestForm.submit();
                }
            } finally {
                btnFinalSubmit.disabled = false;
                btnFinalSubmit.innerHTML = orig;
                LL.icons();
            }
        });
    }

    // -------------------------------------------------------------------------
    // 2. Track page: copy share link
    // -------------------------------------------------------------------------
    const btnCopyTrackLink = $('btnCopyTrackLink');
    if (btnCopyTrackLink) {
        btnCopyTrackLink.addEventListener('click', async () => {
            const url = location.href;
            let copied = false;
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(url);
                    copied = true;
                }
            } catch (e) { /* fallback below */ }

            if (!copied) {
                const ta = document.createElement('textarea');
                ta.value = url;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                try {
                    copied = document.execCommand('copy');
                } catch (err) { /* ignore */ }
                ta.remove();
            }
            const orig = btnCopyTrackLink.innerHTML;
            btnCopyTrackLink.innerHTML = '<i data-lucide="check"></i> Link copied';
            if (window.LL && LL.icons) LL.icons();
            if (window.LL && LL.toast) {
                LL.toast('Emergency request link copied to clipboard!');
            }
            setTimeout(() => { btnCopyTrackLink.innerHTML = orig; if (window.LL && LL.icons) LL.icons(); }, 2500);
        });
    }

    if (window.lucide) window.lucide.createIcons();
});
