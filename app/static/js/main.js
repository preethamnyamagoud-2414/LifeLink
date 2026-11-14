/**
 * LifeLink — Modern Healthcare SaaS Frontend Interactivity
 * Accessible Mobile Navigation, Status Toggles, Lucide Init & Notifications
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // 2. Mobile Drawer Navigation Controller
    const menuToggle = document.getElementById('mobileMenuToggle');
    const drawerClose = document.getElementById('mobileDrawerClose');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const mobileOverlay = document.getElementById('mobileNavOverlay');

    function openMobileMenu() {
        if (!mobileDrawer || !mobileOverlay) return;
        mobileDrawer.classList.add('active');
        mobileOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'true');
    }

    function closeMobileMenu() {
        if (!mobileDrawer || !mobileOverlay) return;
        mobileDrawer.classList.remove('active');
        mobileOverlay.classList.remove('active');
        document.body.style.overflow = '';
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
    }

    if (menuToggle) {
        menuToggle.addEventListener('click', openMobileMenu);
    }
    if (drawerClose) {
        drawerClose.addEventListener('click', closeMobileMenu);
    }
    if (mobileOverlay) {
        mobileOverlay.addEventListener('click', closeMobileMenu);
    }

    // Close on Escape key press
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileDrawer && mobileDrawer.classList.contains('active')) {
            closeMobileMenu();
        }
    });

    // 2b. Dashboard Mobile Sidebar Controller
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const dashboardSidebar = document.querySelector('.dashboard-sidebar');
    let dashOverlay = document.getElementById('dashboardNavOverlay');

    if (sidebarToggleBtn && dashboardSidebar) {
        if (!dashOverlay) {
            dashOverlay = document.createElement('div');
            dashOverlay.id = 'dashboardNavOverlay';
            dashOverlay.className = 'mobile-nav-overlay';
            document.body.appendChild(dashOverlay);
        }

        function openSidebar() {
            dashboardSidebar.classList.add('active');
            dashOverlay.classList.add('active');
            document.body.style.overflow = 'hidden';
            sidebarToggleBtn.setAttribute('aria-expanded', 'true');
        }

        function closeSidebar() {
            dashboardSidebar.classList.remove('active');
            dashOverlay.classList.remove('active');
            document.body.style.overflow = '';
            sidebarToggleBtn.setAttribute('aria-expanded', 'false');
        }

        sidebarToggleBtn.addEventListener('click', openSidebar);
        dashOverlay.addEventListener('click', closeSidebar);

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && dashboardSidebar.classList.contains('active')) {
                closeSidebar();
            }
        });
    }

    // 3. Interactive Donor Availability Switch (AJAX + UI Feedback)
    const availabilityCheckbox = document.getElementById('donorAvailabilityToggle');
    const availabilityStatusPill = document.getElementById('donorAvailabilityStatusPill');

    if (availabilityCheckbox && availabilityStatusPill) {
        availabilityCheckbox.addEventListener('change', (e) => {
            const isAvailable = e.target.checked;
            if (isAvailable) {
                availabilityStatusPill.className = 'badge badge-success';
                availabilityStatusPill.innerHTML = '<span class="pulse-dot"></span> Available to Donate (Active)';
            } else {
                availabilityStatusPill.className = 'badge badge-neutral';
                availabilityStatusPill.innerHTML = '<i data-lucide="moon"></i> Resting / Paused';
                if (window.lucide) window.lucide.createIcons();
            }

            // Sync with backend API if available
            const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
            fetch('/donor/availability', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ is_available: isAvailable, csrf_token: csrfToken })
            })
                .then(res => res.json())
                .then(data => {
                    showToast(data.message || (isAvailable ? 'Status: AVAILABLE for urgent calls' : 'Status: Alerts paused'));
                })
                .catch(() => {
                    showToast(isAvailable ? 'Status: AVAILABLE for urgent transfusion calls (Local Mode)' : 'Status: Donor alerts paused (Local Mode)');
                });
        });
    }

    // 4. Lightweight UI Toast Notification System
    function showToast(message, type = 'info') {
        let toastContainer = document.getElementById('lifelinkToastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'lifelinkToastContainer';
            toastContainer.style.position = 'fixed';
            toastContainer.style.bottom = '24px';
            toastContainer.style.right = '24px';
            toastContainer.style.zIndex = '9999';
            toastContainer.style.display = 'flex';
            toastContainer.style.flexDirection = 'column';
            toastContainer.style.gap = '10px';
            toastContainer.style.maxWidth = '380px';
            toastContainer.style.pointerEvents = 'none';
            document.body.appendChild(toastContainer);

            // Responsive positioning for small devices
            if (window.innerWidth <= 480) {
                toastContainer.style.left = '16px';
                toastContainer.style.right = '16px';
                toastContainer.style.bottom = '16px';
                toastContainer.style.maxWidth = 'none';
            }
        }

        const toast = document.createElement('div');
        toast.style.background = 'rgba(23, 43, 77, 0.96)';
        toast.style.backdropFilter = 'blur(8px)';
        toast.style.webkitBackdropFilter = 'blur(8px)';
        toast.style.color = '#FFFFFF';
        toast.style.padding = '12px 18px';
        toast.style.borderRadius = '10px';
        toast.style.fontSize = '0.875rem';
        toast.style.fontWeight = '500';
        toast.style.boxShadow = '0 10px 25px -5px rgba(15, 23, 42, 0.35), 0 4px 6px -2px rgba(0,0,0,0.1)';
        toast.style.border = '1px solid rgba(255, 255, 255, 0.12)';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.gap = '10px';
        toast.style.transition = 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)';
        toast.style.transform = 'translateY(16px) scale(0.96)';
        toast.style.opacity = '0';
        toast.style.pointerEvents = 'auto';

        const dotColor = type === 'error' ? '#EF4444' : '#10B981';
        toast.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background-color: ${dotColor}; flex-shrink: 0; display: inline-block;"></span> <span style="line-height: 1.4;">${message}</span>`;

        toastContainer.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.transform = 'translateY(0) scale(1)';
            toast.style.opacity = '1';
        });

        // Dismiss after 4s
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(12px) scale(0.96)';
            setTimeout(() => toast.remove(), 250);
        }, 4000);
    }

    // Export showToast globally
    window.showLifeLinkToast = showToast;
});

/**
 * Universal Show/Hide Password Toggle
 * Toggles between password and text input types and flips Lucide icon
 */
window.togglePasswordVisibility = function(inputId, toggleBtn) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const isPassword = input.getAttribute('type') === 'password';
    input.setAttribute('type', isPassword ? 'text' : 'password');

    const icon = toggleBtn.querySelector('i');
    if (icon) {
        icon.setAttribute('data-lucide', isPassword ? 'eye-off' : 'eye');
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }
};
