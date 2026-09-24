/**
 * SmartCart - Universal Responsive Mobile Navigation Controller
 * Handles 3-lines hamburger toggles and mobile drawer menus for:
 * 1. Public / Auth pages (#public-menu-toggle, #public-mobile-drawer)
 * 2. Customer portal pages (#mobile-menu-btn / #smart-menu-toggle, #mobile-drawer / #smart-mobile-drawer)
 * 3. Admin portal pages (#admin-menu-toggle, #admin-mobile-drawer)
 */

window.toggleSmartDrawer = function (btnOrId, drawerOrId) {
    var toggleBtn = typeof btnOrId === 'string'
        ? (document.getElementById(btnOrId) || document.querySelector('.' + btnOrId))
        : btnOrId;

    var drawer = typeof drawerOrId === 'string'
        ? (document.getElementById(drawerOrId) || document.querySelector('.' + drawerOrId))
        : drawerOrId;

    if (!toggleBtn || !drawer) return;

    var isOpen = drawer.classList.toggle('open');
    toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');

    // Update icon if present
    var icon = toggleBtn.querySelector('i');
    if (icon) {
        if (isOpen) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-xmark');
        } else {
            icon.classList.remove('fa-xmark');
            icon.classList.add('fa-bars');
        }
    }

    if (isOpen) {
        drawer.style.display = 'flex';
    } else {
        drawer.style.display = 'none';
    }
};

(function () {
    var lastToggleTimestamp = 0;

    function initNavbar() {
        setupMenuToggle('public-menu-toggle', 'public-mobile-drawer');
        setupMenuToggle('mobile-menu-btn', 'mobile-drawer');
        setupMenuToggle('smart-menu-toggle', 'smart-mobile-drawer');
        setupMenuToggle('admin-menu-toggle', 'admin-mobile-drawer');

        // Setup any generic toggles with data attributes
        var genericToggles = document.querySelectorAll('[data-drawer-target]');
        genericToggles.forEach(function (btn) {
            var targetId = btn.getAttribute('data-drawer-target');
            if (targetId) {
                setupMenuToggle(btn, targetId);
            }
        });
    }

    function setupMenuToggle(btnOrId, drawerOrId) {
        var toggleBtn = typeof btnOrId === 'string'
            ? (document.getElementById(btnOrId) || document.querySelector('.' + btnOrId))
            : btnOrId;

        var drawer = typeof drawerOrId === 'string'
            ? (document.getElementById(drawerOrId) || document.querySelector('.' + drawerOrId))
            : drawerOrId;

        if (!toggleBtn || !drawer) return;

        if (toggleBtn.dataset.navbarBound === 'true') return;
        toggleBtn.dataset.navbarBound = 'true';

        function updateIcon(isOpen) {
            var icon = toggleBtn.querySelector('i');
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
            if (drawer.classList.contains('open') || drawer.style.display === 'flex') {
                drawer.classList.remove('open');
                drawer.style.display = 'none';
                toggleBtn.setAttribute('aria-expanded', 'false');
                updateIcon(false);
            }
        }

        function toggleDrawer(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            lastToggleTimestamp = Date.now();
            var isOpen = drawer.classList.toggle('open');
            if (isOpen) {
                drawer.style.display = 'flex';
            } else {
                drawer.style.display = 'none';
            }
            toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            updateIcon(isOpen);
        }

        toggleBtn.addEventListener('click', toggleDrawer);

        // Close on escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeDrawer();
            }
        });

        // Close drawer when clicking outside (debounced to avoid immediate close on mobile touch)
        document.addEventListener('click', function (e) {
            if (Date.now() - lastToggleTimestamp < 350) {
                return;
            }
            if (drawer.classList.contains('open') || drawer.style.display === 'flex') {
                if (!drawer.contains(e.target) && !toggleBtn.contains(e.target)) {
                    closeDrawer();
                }
            }
        });

        // Close drawer when clicking on any link inside the drawer
        var drawerLinks = drawer.querySelectorAll('a');
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
