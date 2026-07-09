/* =========================================================================
   script.js — Smart Warehouse Storage Allocation System
   Handles: dark mode toggle, mobile sidebar, loading overlay,
   and a reusable client-side sort/search/paginate helper for tables.
   ========================================================================= */

/* ---------------------------------------------------------------------
   Dark mode
   --------------------------------------------------------------------- */
(function initDarkMode() {
    const root = document.documentElement;
    const stored = localStorage.getItem('warehouse-theme');
    if (stored) {
        root.setAttribute('data-bs-theme', stored);
    }

    document.addEventListener('DOMContentLoaded', function () {
        const toggleBtn = document.getElementById('darkModeToggle');
        updateToggleLabel();

        if (toggleBtn) {
            toggleBtn.addEventListener('click', function () {
                const current = root.getAttribute('data-bs-theme') || 'light';
                const next = current === 'dark' ? 'light' : 'dark';
                root.setAttribute('data-bs-theme', next);
                localStorage.setItem('warehouse-theme', next);
                updateToggleLabel();
            });
        }

        function updateToggleLabel() {
            if (!toggleBtn) return;
            const current = root.getAttribute('data-bs-theme') || 'light';
            const icon = toggleBtn.querySelector('i');
            const label = toggleBtn.querySelector('span');
            if (current === 'dark') {
                icon.className = 'bi bi-sun';
                label.textContent = 'Light Mode';
            } else {
                icon.className = 'bi bi-moon-stars';
                label.textContent = 'Dark Mode';
            }
        }
    });
})();

/* ---------------------------------------------------------------------
   Mobile sidebar toggle
   --------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
        document.addEventListener('click', function (e) {
            if (sidebar.classList.contains('open') &&
                !sidebar.contains(e.target) &&
                e.target !== toggle && !toggle.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    }

    // Auto-dismiss flash alerts after a few seconds
    document.querySelectorAll('.alert').forEach(function (alertEl) {
        setTimeout(() => {
            const alert = bootstrap.Alert.getOrCreateInstance(alertEl);
            if (alert) alert.close();
        }, 6000);
    });
});

/* ---------------------------------------------------------------------
   Loading overlay
   --------------------------------------------------------------------- */
function showLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('d-none');
}
function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.add('d-none');
}

// Show overlay automatically on any allocation form submit
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('#allocateForm').forEach(function (form) {
        form.addEventListener('submit', showLoadingOverlay);
    });
});

/* ---------------------------------------------------------------------
   Reusable table: client-side sort + search + pagination
   --------------------------------------------------------------------- */
function initSortableSearchableTable(tableId, searchInputId, paginationId, pageSize) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const tbody = table.querySelector('tbody');
    let allRows = Array.from(tbody.querySelectorAll('tr'));
    let filteredRows = allRows;
    let currentPage = 1;
    const rowsPerPage = pageSize || 10;

    const searchInput = searchInputId ? document.getElementById(searchInputId) : null;
    const paginationEl = paginationId ? document.getElementById(paginationId) : null;

    function render() {
        // Filter
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        filteredRows = allRows.filter(row => !query || row.textContent.toLowerCase().includes(query));

        // Paginate
        const totalPages = Math.max(1, Math.ceil(filteredRows.length / rowsPerPage));
        if (currentPage > totalPages) currentPage = totalPages;
        const start = (currentPage - 1) * rowsPerPage;
        const pageRows = filteredRows.slice(start, start + rowsPerPage);

        // Detach all, then re-append visible page rows in order
        allRows.forEach(r => r.remove());
        pageRows.forEach(r => tbody.appendChild(r));

        if (filteredRows.length === 0) {
            const emptyRow = document.createElement('tr');
            const colCount = table.querySelectorAll('thead th').length || 1;
            emptyRow.innerHTML = `<td colspan="${colCount}" class="text-center text-secondary py-3">No matching records found.</td>`;
            tbody.appendChild(emptyRow);
        }

        // Build pagination controls
        if (paginationEl) {
            paginationEl.innerHTML = '';
            if (totalPages > 1) {
                for (let p = 1; p <= totalPages; p++) {
                    const li = document.createElement('li');
                    li.className = 'page-item' + (p === currentPage ? ' active' : '');
                    li.innerHTML = `<a class="page-link" href="#">${p}</a>`;
                    li.addEventListener('click', function (e) {
                        e.preventDefault();
                        currentPage = p;
                        render();
                    });
                    paginationEl.appendChild(li);
                }
            }
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', function () {
            currentPage = 1;
            render();
        });
    }

    // Sorting
    table.querySelectorAll('thead th[data-sort]').forEach((th, index) => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', function () {
            const type = th.getAttribute('data-sort');
            const asc = th.getAttribute('data-asc') !== 'true';
            table.querySelectorAll('thead th').forEach(h => h.removeAttribute('data-asc'));
            th.setAttribute('data-asc', asc);

            // Remove any previous sort indicator
            table.querySelectorAll('thead th i.sort-indicator').forEach(i => i.remove());
            const indicator = document.createElement('i');
            indicator.className = 'bi sort-indicator ' + (asc ? 'bi-caret-up-fill' : 'bi-caret-down-fill');
            indicator.style.marginLeft = '6px';
            indicator.style.fontSize = '0.7rem';
            th.appendChild(indicator);

            allRows.sort((a, b) => {
                const cellA = a.children[index].textContent.trim();
                const cellB = b.children[index].textContent.trim();
                let cmp;
                if (type === 'number') {
                    cmp = (parseFloat(cellA) || 0) - (parseFloat(cellB) || 0);
                } else {
                    cmp = cellA.localeCompare(cellB);
                }
                return asc ? cmp : -cmp;
            });
            currentPage = 1;
            render();
        });
    });

    render();
}
