// Autumn Theme Toggle & Persistence
(function() {
    function getServerTheme() {
        return document.documentElement.getAttribute('data-server-theme') || '';
    }

    function getStoredTheme() {
        return localStorage.getItem('prioritysuite-theme');
    }

    function setStoredTheme(theme) {
        localStorage.setItem('prioritysuite-theme', theme);
    }

    function getPreferredTheme() {
        // If a server theme is specified (e.g. user selected in profile settings),
        // give precedence to server theme unless the user used the client toggle in this session
        const server = getServerTheme();
        const stored = getStoredTheme();
        if (stored && stored !== 'auto') {
            return stored;
        }
        if (server && server !== 'auto') {
            return server;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function updateButtonUI(effectiveTheme) {
        const icon = document.getElementById('theme-toggle-icon');
        const text = document.getElementById('theme-toggle-text');
        if (icon) {
            icon.textContent = effectiveTheme === 'dark' ? '🌙' : '🍂';
        }
        if (text) {
            text.textContent = effectiveTheme === 'dark' ? 'Dark (Autumn)' : 'Light (Parchment)';
        }
    }

    function applyTheme(theme) {
        const effectiveTheme = (theme === 'auto' || !theme)
            ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : theme;
        document.documentElement.setAttribute('data-bs-theme', effectiveTheme);
        updateButtonUI(effectiveTheme);
    }

    // Apply attribute immediately to prevent FOUC
    applyTheme(getPreferredTheme());

    // Update button text and icon as soon as DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            updateButtonUI(document.documentElement.getAttribute('data-bs-theme'));
        });
    } else {
        updateButtonUI(document.documentElement.getAttribute('data-bs-theme'));
    }

    window.toggleTheme = function() {
        const current = document.documentElement.getAttribute('data-bs-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        setStoredTheme(next);
        applyTheme(next);
    };

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (!getStoredTheme() || getStoredTheme() === 'auto') {
            applyTheme('auto');
        }
    });
})();
