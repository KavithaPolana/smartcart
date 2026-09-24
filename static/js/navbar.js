/**
 * SmartCart - Universal Responsive Mobile Navigation Controller
 * Handles 3-lines hamburger toggles and mobile drawer menus for:
 * 1. Public / Auth pages (.public-navbar, .public-mobile-toggle, .public-mobile-drawer)
 * 2. Customer portal pages (.smart-navbar, .smart-main-navbar, .smart-mobile-toggle, .smart-mobile-drawer)
 * 3. Admin portal pages (.admin-header-bar, .admin-mobile-toggle, .admin-mobile-drawer)
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Setup Public Navigation Drawer Toggle
    setupMenuToggle('public-menu-toggle', 'public-mobile-drawer');

    // 2. Setup Customer Portal Navigation Drawer Toggle
    setupMenuToggle('mobile-menu-btn', 'mobile-drawer');
    setupMenuToggle('smart-menu-toggle', 'smart-mobile-drawer');

    // 3. Setup Admin Portal Navigation Drawer Toggle
    setupMenuToggle('admin-menu-toggle', 'admin-mobile-drawer');

    // Generic setup function
    function setupMenuToggle(btnId, drawerId) {
        const toggleBtn = document.getElementById(btnId) || document.querySelector(`.${btnId}`);
        const drawer = document.getElementById(drawerId) || document.querySelector(`.${drawerId}`);

        if (!toggleBtn || !drawer) return;

        toggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            const isOpen = drawer.classList.toggle('open');
            toggleBtn.setAttribute('aria-expanded', isOpen);

            const icon = toggleBtn.querySelector('i');
            if (icon) {
                if (isOpen) {
                    icon.classList.remove('fa-bars');
                    icon.classList.add('fa-xmark');
                } else {
                    icon.classList.remove('fa-xmark');
                    icon.classList.add('fa-bars');
                }
            }
        });

        // Close on escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && drawer.classList.contains('open')) {
                drawer.classList.remove('open');
                toggleBtn.setAttribute('aria-expanded', 'false');
                const icon = toggleBtn.querySelector('i');
                if (icon) {
                    icon.classList.remove('fa-xmark');
                    icon.classList.add('fa-bars');
                }
            }
        });

        // Close drawer when clicking outside
        document.addEventListener('click', function (e) {
            if (drawer.classList.contains('open') && !drawer.contains(e.target) && !toggleBtn.contains(e.target)) {
                drawer.classList.remove('open');
                toggleBtn.setAttribute('aria-expanded', 'false');
                const icon = toggleBtn.querySelector('i');
                if (icon) {
                    icon.classList.remove('fa-xmark');
                    icon.classList.add('fa-bars');
                }
            }
        });

        // Close drawer when clicking on any link inside the drawer
        const drawerLinks = drawer.querySelectorAll('a');
        drawerLinks.forEach(function (link) {
            link.addEventListener('click', function () {
                drawer.classList.remove('open');
                toggleBtn.setAttribute('aria-expanded', 'false');
                const icon = toggleBtn.querySelector('i');
                if (icon) {
                    icon.classList.remove('fa-xmark');
                    icon.classList.add('fa-bars');
                }
            });
        });
    }
});
