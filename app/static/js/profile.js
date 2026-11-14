/**
 * LifeLink profile card: shows saved details, with an "Edit profile" mode.
 * LLProfile.mount(container, { getMe: () => meData, onSaved: async () => {}, onEditHealth: fn|null })
 */
(function () {
    'use strict';

    function row(label, value) {
        return `<div class="ll-profile-row"><span>${label}</span><strong>${value || '<span class="ll-muted">Not set</span>'}</strong></div>`;
    }

    function mount(container, opts) {
        function view() {
            const { user, donor } = opts.getMe();
            const e = LL.esc;
            container.innerHTML = `
                <div class="ll-profile-grid">
                    ${row('Full name', e(user.full_name))}
                    ${row('Email (used to sign in)', e(user.email))}
                    ${row('Mobile number', e(user.phone))}
                    ${row('City / town', e((donor && donor.city) || user.city))}
                    ${row('Area / district', e((donor && donor.district) || user.district))}
                    ${donor ? row('Blood group', e(donor.blood_group)) : ''}
                    ${donor ? row('Weight', donor.weight_kg ? e(donor.weight_kg) + ' kg' : '') : ''}
                    ${donor ? row('Date of birth', e(LL.fmtDate(donor.dob))) : ''}
                </div>
                <div class="ll-profile-actions">
                    ${donor && opts.onEditHealth ? '<button type="button" class="btn btn-outline btn-sm" data-profile-health><i data-lucide="stethoscope"></i> Edit donor &amp; health details</button>' : ''}
                    <button type="button" class="btn btn-primary btn-sm" data-profile-edit><i data-lucide="pencil"></i> Edit profile</button>
                </div>`;
            container.querySelector('[data-profile-edit]').addEventListener('click', edit);
            const h = container.querySelector('[data-profile-health]');
            if (h) h.addEventListener('click', opts.onEditHealth);
            LL.icons();
        }

        function edit() {
            const { user, donor } = opts.getMe();
            const e = LL.esc;
            container.innerHTML = `
                <form class="ll-profile-form" novalidate>
                    <div class="ll-form-grid">
                        <div class="form-group"><label class="form-label" for="pfName">Full name <span class="required-mark">*</span></label>
                            <input type="text" id="pfName" class="form-control" value="${e(user.full_name)}" required></div>
                        <div class="form-group"><label class="form-label" for="pfEmail">Email</label>
                            <input type="email" id="pfEmail" class="form-control" value="${e(user.email)}" disabled>
                            <span class="form-hint">Email is your sign-in ID and cannot be changed.</span></div>
                        <div class="form-group"><label class="form-label" for="pfPhone">Mobile number <span class="required-mark">*</span></label>
                            <input type="tel" id="pfPhone" class="form-control" value="${e(user.phone)}" required></div>
                        <div class="form-group"><label class="form-label" for="pfCity">City / town</label>
                            <input type="text" id="pfCity" class="form-control" value="${e((donor && donor.city) || user.city)}"></div>
                        <div class="form-group"><label class="form-label" for="pfDistrict">Area / district</label>
                            <input type="text" id="pfDistrict" class="form-control" value="${e((donor && donor.district) || user.district)}"></div>
                    </div>
                    <div class="ll-profile-actions">
                        <button type="button" class="btn btn-outline btn-sm" data-profile-cancel>Cancel</button>
                        <button type="submit" class="btn btn-primary btn-sm"><i data-lucide="save"></i> Save changes</button>
                    </div>
                </form>`;
            const form = container.querySelector('form');
            container.querySelector('[data-profile-cancel]').addEventListener('click', view);
            form.addEventListener('submit', async ev => {
                ev.preventDefault();
                const btn = form.querySelector('button[type="submit"]');
                const v = id => form.querySelector('#' + id).value.trim();
                if (!v('pfName') || !v('pfPhone')) { LL.toast('Name and mobile number are required.', 'error'); return; }
                btn.disabled = true;
                try {
                    const d = await LL.api('/api/profile', { body: { full_name: v('pfName'), phone: v('pfPhone'), city: v('pfCity'), district: v('pfDistrict') } });
                    LL.toast(d.message);
                    await opts.onSaved();
                    view();
                } catch (err) {
                    LL.toast(err.message, 'error');
                    btn.disabled = false;
                }
            });
            LL.icons();
            form.querySelector('#pfName').focus();
        }

        view();
        return { refresh: view, edit };
    }

    window.LLProfile = { mount };
})();
