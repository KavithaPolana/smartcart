/**
 * SmartCart - Universal Responsive Mobile Navigation Controller
 * Handles 3-lines hamburger toggles and mobile drawer menus for:
 * 1. Public / Auth pages (#public-menu-toggle, #public-mobile-drawer)
 * 2. Customer portal pages (#mobile-menu-btn / #smart-menu-toggle, #mobile-drawer / #smart-mobile-drawer)
 * 3. Admin portal pages (#admin-menu-toggle, #admin-mobile-drawer)
 */

(function () {
    function initNavbar() {
        // 1. Setup Public Navigation Drawer Toggle
        setupMenuToggle('public-menu-toggle', 'public-mobile-drawer');

        // 2. Setup Customer Portal Navigation Drawer Toggle
        setupMenuToggle('mobile-menu-btn', 'mobile-drawer');
        setupMenuToggle('smart-menu-toggle', 'smart-mobile-drawer');

        // 3. Setup Admin Portal Navigation Drawer Toggle
        setupMenuToggle('admin-menu-toggle', 'admin-mobile-drawer');

        // 4. Setup any fallback generic toggles
        const genericToggles = document.querySelectorAll('[data-drawer-target]');
        genericToggles.forEach(function (btn) {
            const targetId = btn.getAttribute('data-drawer-target');
            if (targetId) {
                setupMenuToggle(btn, targetId);
            }
        });
    }

    function setupMenuToggle(btnOrId, drawerOrId) {
        let toggleBtn = typeof btnOrId === 'string'
            ? (document.getElementById(btnOrId) || document.querySelector('.' + btnOrId))
            : btnOrId;

        let drawer = typeof drawerOrId === 'string'
            ? (document.getElementById(drawerOrId) || document.querySelector('.' + drawerOrId))
            : drawerOrId;

        if (!toggleBtn || !drawer) return;

        // Prevent duplicate event listeners
        if (toggleBtn.dataset.navbarBound === 'true') return;
        toggleBtn.dataset.navbarBound = 'true';

        function updateIcon(isOpen) {
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
        }

        function closeDrawer() {
            if (drawer.classList.contains('open')) {
                drawer.classList.remove('open');
                toggleBtn.setAttribute('aria-expanded', 'false');
                updateIcon(false);
            }
        }

        function openDrawer() {
            drawer.classList.add('open');
            toggleBtn.setAttribute('aria-expanded', 'true');
            updateIcon(true);
        }

        toggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const isOpen = drawer.classList.toggle('open');
            toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            updateIcon(isOpen);
        });

        // Close on escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeDrawer();
            }
        });

        // Close drawer when clicking outside
        document.addEventListener('click', function (e) {
            if (drawer.classList.contains('open')) {
                if (!drawer.contains(e.target) && !toggleBtn.contains(e.target)) {
                    closeDrawer();
                }
            }
        });

        // Close drawer when clicking on any link inside the drawer
        const drawerLinks = drawer.querySelectorAll('a');
        drawerLinks.forEach(function (link) {
            link.addEventListener('click', function () {
                closeDrawer();
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavbar);
    } else {
        initNavbar();
    }
})();
