/**
 * LifeLink donor profile + health screening form (used on Register and the Donor Dashboard).
 * LLDonorForm.render(container, existingDonor) / LLDonorForm.collect(container)
 */
(function () {
    'use strict';

    const QUESTIONS = [
        { key: 'unwell', text: 'In the last 7 days, have you had fever, cold, flu, or felt unwell?' },
        { key: 'antibiotics', text: 'Have you taken antibiotics in the last 7 days?' },
        { key: 'tattoo', text: 'Have you had a tattoo, body piercing or acupuncture in the last 12 months?' },
        { key: 'surgery', text: 'Have you had major surgery in the last 6 months?' },
        { key: 'malaria', text: 'Have you had malaria in the last 3 months?' },
        { key: 'pregnant', text: 'Are you pregnant, or have you given birth / been breastfeeding in the last 12 months?', femaleOnly: true },
        { key: 'blood_pressure', text: 'Do you have high or low blood pressure that is not under control?' },
        { key: 'infection', text: 'Have you ever tested positive for HIV, Hepatitis B, Hepatitis C or syphilis?' },
        { key: 'chronic', text: 'Do you have heart disease, cancer, kidney or liver disease, epilepsy, or a bleeding disorder?' },
        { key: 'insulin', text: 'Do you have diabetes that is treated with insulin?' }
    ];
    const GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];

    function esc(v) { return window.LL ? LL.esc(v) : String(v ?? ''); }
    function today() { return new Date().toISOString().slice(0, 10); }

    function render(container, d) {
        d = d || {};
        const answers = (d.screening && d.screening.answers) || {};
        const neverDonated = d.dob && !d.last_donation_date; // existing donor with no date
        const hasLoc = d.has_location && d.lat != null;

        container.innerHTML = `
            <div class="ll-form-grid">
                <div class="form-group">
                    <label class="form-label" for="dfBloodGroup">Blood group <span class="required-mark">*</span></label>
                    <select id="dfBloodGroup" class="form-select" required>
                        <option value="">Select...</option>
                        ${GROUPS.map(g => `<option value="${g}" ${d.blood_group === g ? 'selected' : ''}>${g}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfGender">Gender <span class="required-mark">*</span></label>
                    <select id="dfGender" class="form-select" required>
                        <option value="">Select...</option>
                        <option value="male" ${d.gender === 'male' ? 'selected' : ''}>Male</option>
                        <option value="female" ${d.gender === 'female' ? 'selected' : ''}>Female</option>
                        <option value="other" ${d.gender === 'other' ? 'selected' : ''}>Other / prefer not to say</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfDob">Date of birth <span class="required-mark">*</span></label>
                    <input type="date" id="dfDob" class="form-control" max="${today()}" value="${esc(d.dob || '')}" required>
                    <span class="form-hint">Donors must be 18 to 65 years old.</span>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfWeight">Body weight (kg) <span class="required-mark">*</span></label>
                    <input type="number" id="dfWeight" class="form-control" min="20" max="300" step="0.5" placeholder="e.g. 65" value="${esc(d.weight_kg ?? '')}" required>
                    <span class="form-hint">Minimum 45 kg.</span>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfHb">Hemoglobin (g/dL) <span class="ll-optional">optional</span></label>
                    <input type="number" id="dfHb" class="form-control" min="3" max="25" step="0.1" placeholder="e.g. 13.5" value="${esc(d.hemoglobin ?? '')}">
                    <span class="form-hint">If you know it. Minimum 12.5 g/dL.</span>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfLastDonation">Last blood donation</label>
                    <input type="date" id="dfLastDonation" class="form-control" max="${today()}" value="${esc(d.last_donation_date || '')}" ${neverDonated ? 'disabled' : ''}>
                    <label class="ll-inline-check"><input type="checkbox" id="dfNeverDonated" ${neverDonated ? 'checked' : ''}> I have never donated blood</label>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfCity">City / town <span class="required-mark">*</span></label>
                    <input type="text" id="dfCity" class="form-control" placeholder="e.g. Hyderabad" value="${esc(d.city || '')}" required>
                </div>
                <div class="form-group">
                    <label class="form-label" for="dfDistrict">Area / district</label>
                    <input type="text" id="dfDistrict" class="form-control" placeholder="e.g. Kukatpally" value="${esc(d.district || '')}">
                </div>
            </div>

            <div class="ll-location-box ${hasLoc ? 'is-set' : ''}" id="dfLocationBox" data-lat="${hasLoc ? d.lat : ''}" data-lng="${hasLoc ? d.lng : ''}">
                <div class="ll-location-icon"><i data-lucide="map-pin"></i></div>
                <div class="ll-location-text">
                    <strong>Your location <span class="required-mark">*</span></strong>
                    <span id="dfLocationStatus">${hasLoc ? 'Location saved. Patients nearby can see how far away you are (never your exact address).' : 'Needed so patients nearby can find you. Only the distance is shown to others, never your exact location.'}</span>
                </div>
                <button type="button" class="btn btn-outline btn-sm" id="dfLocationBtn"><i data-lucide="crosshair"></i> ${hasLoc ? 'Update location' : 'Share my location'}</button>
            </div>

            <div class="ll-screening">
                <h4><i data-lucide="stethoscope"></i> Health screening</h4>
                <p class="ll-screening-note">Answer honestly. This is a basic self-check to protect you and the patient. The blood bank will still do a full medical check before you donate.</p>
                ${QUESTIONS.map((q, i) => {
                    const v = answers[q.key];
                    return `
                    <div class="ll-question" data-key="${q.key}" ${q.femaleOnly ? 'data-female-only="1"' : ''}>
                        <span class="ll-question-text">${i + 1}. ${esc(q.text)}</span>
                        <div class="ll-yesno" role="radiogroup" aria-label="${esc(q.text)}">
                            <label><input type="radio" name="dfq_${q.key}" value="yes" ${v === true ? 'checked' : ''}><span>Yes</span></label>
                            <label><input type="radio" name="dfq_${q.key}" value="no" ${v === false ? 'checked' : ''}><span>No</span></label>
                        </div>
                    </div>`;
                }).join('')}
                <label class="ll-consent"><input type="checkbox" id="dfConsent"> I confirm my answers are true to the best of my knowledge.</label>
            </div>`;

        const gender = container.querySelector('#dfGender');
        const syncFemale = () => {
            container.querySelectorAll('[data-female-only]').forEach(el => {
                el.style.display = gender.value === 'female' ? '' : 'none';
            });
        };
        gender.addEventListener('change', syncFemale);
        syncFemale();

        const never = container.querySelector('#dfNeverDonated');
        const last = container.querySelector('#dfLastDonation');
        never.addEventListener('change', () => {
            last.disabled = never.checked;
            if (never.checked) last.value = '';
        });

        const box = container.querySelector('#dfLocationBox');
        const status = container.querySelector('#dfLocationStatus');
        const btn = container.querySelector('#dfLocationBtn');
        btn.addEventListener('click', () => captureLocation());
        // Ask straight away for new donors (the browser only shows its prompt the first time;
        // if permission was already allowed the location is filled in silently).
        if (!hasLoc) {
            LL.locationPermission().then(state => {
                if (state === 'denied') {
                    box.classList.add('is-error');
                    status.textContent = 'Location is blocked for this site. Click the lock/location icon left of the address bar, set Location to "Allow", then click "Share my location".';
                } else {
                    captureLocation();
                }
            });
        }
        async function captureLocation() {
            btn.disabled = true;
            const perm = await LL.locationPermission();
            status.textContent = perm === 'granted' ? 'Getting your location (already allowed for this site)...' : 'Waiting for location permission - click "Allow" in the browser prompt near the address bar...';
            box.classList.remove('is-error');
            try {
                const loc = await LL.getLocation();
                box.dataset.lat = loc.lat;
                box.dataset.lng = loc.lng;
                box.classList.add('is-set');
                status.textContent = `Location captured (accurate to about ${loc.accuracy} m). Only the distance is shown to others.`;
                btn.innerHTML = '<i data-lucide="crosshair"></i> Update location';
            } catch (e) {
                box.classList.add('is-error');
                status.textContent = e.message;
            } finally {
                btn.disabled = false;
                LL.icons();
            }
        }

        LL.icons();
    }

    function collect(container) {
        const val = id => (container.querySelector('#' + id)?.value || '').trim();
        const out = {
            blood_group: val('dfBloodGroup'),
            gender: val('dfGender'),
            dob: val('dfDob'),
            weight_kg: val('dfWeight') ? Number(val('dfWeight')) : null,
            hemoglobin: val('dfHb') ? Number(val('dfHb')) : null,
            last_donation_date: container.querySelector('#dfNeverDonated').checked ? '' : val('dfLastDonation'),
            city: val('dfCity'),
            district: val('dfDistrict'),
            answers: {},
            consent: container.querySelector('#dfConsent').checked
        };
        const box = container.querySelector('#dfLocationBox');
        if (box.dataset.lat) { out.lat = Number(box.dataset.lat); out.lng = Number(box.dataset.lng); }

        if (!out.blood_group) throw new Error('Please choose your blood group.');
        if (!out.gender) throw new Error('Please choose your gender.');
        if (!out.dob) throw new Error('Please enter your date of birth.');
        if (!out.weight_kg) throw new Error('Please enter your body weight.');
        if (!out.city) throw new Error('Please enter your city / town.');
        if (!container.querySelector('#dfNeverDonated').checked && !out.last_donation_date) {
            throw new Error('Enter your last donation date, or tick "I have never donated blood".');
        }
        if (out.lat === undefined) throw new Error('Please click "Share my location" and allow location access.');

        const missing = [];
        QUESTIONS.forEach((q, i) => {
            if (q.femaleOnly && out.gender !== 'female') { out.answers[q.key] = false; return; }
            const checked = container.querySelector(`input[name="dfq_${q.key}"]:checked`);
            if (!checked) missing.push(i + 1);
            else out.answers[q.key] = checked.value === 'yes';
        });
        if (missing.length) throw new Error(`Please answer health question${missing.length > 1 ? 's' : ''} ${missing.join(', ')}.`);
        if (!out.consent) throw new Error('Please confirm that your health answers are true.');
        return out;
    }

    /** Renders the server's eligibility verdict as HTML. */
    function eligibilityHtml(el) {
        if (!el) return '';
        if (el.eligible) {
            return `<div class="alert alert-success"><i data-lucide="check-circle-2"></i><div><strong>You are eligible to donate.</strong><div style="font-size:0.8125rem;margin-top:0.2rem;">Patients nearby can now find you in donor search.</div></div></div>`;
        }
        const perm = el.status === 'PERMANENT_DEFERRAL';
        const when = el.eligible_from ? `You can donate again from <strong>${LL.esc(LL.fmtDate(el.eligible_from))}</strong>.` : (perm ? 'For your safety and the patient\'s, you should not donate blood.' : 'Update your health screening when this no longer applies.');
        return `<div class="alert ${perm ? 'alert-danger' : 'alert-warning'}"><i data-lucide="${perm ? 'ban' : 'clock'}"></i><div>
            <strong>${perm ? 'You are not eligible to donate blood.' : 'You cannot donate right now.'}</strong>
            <ul class="ll-reasons">${el.reasons.map(r => `<li>${LL.esc(r.message)}${r.until ? ` <span class="ll-until">(until ${LL.esc(LL.fmtDate(r.until))})</span>` : ''}</li>`).join('')}</ul>
            <div style="font-size:0.8125rem;">${when} You are hidden from donor search until then.</div>
        </div></div>`;
    }

    window.LLDonorForm = { render, collect, eligibilityHtml, QUESTIONS };
})();
