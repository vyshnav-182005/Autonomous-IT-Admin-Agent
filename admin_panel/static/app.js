/**
 * OpsPilot AI — Admin Panel JavaScript
 * Handles confirmation dialogs, search filtering, and UI interactions
 */

document.addEventListener('DOMContentLoaded', () => {
    initConfirmDialogs();
    initFlashAutoClose();
    initLoadingIndicator();
});


/**
 * Confirmation dialogs for destructive actions.
 * Buttons with `data-confirm` attribute will show a modal before submitting.
 */
function initConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const message = button.getAttribute('data-confirm');
            const form = button.closest('form');

            showConfirmModal(message, () => {
                // Show loading, then submit
                showLoading();
                form.submit();
            });
        });
    });
}


/**
 * Show a custom confirmation modal.
 */
function showConfirmModal(message, onConfirm) {
    // Remove existing modal if any
    const existing = document.querySelector('.modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.setAttribute('data-testid', 'confirm-modal');

    overlay.innerHTML = `
        <div class="modal-box">
            <div class="modal-title">⚠️ Confirm Action</div>
            <div class="modal-text">${message}</div>
            <div class="modal-actions">
                <button class="btn btn-ghost" data-testid="modal-cancel-btn" id="modal-cancel">Cancel</button>
                <button class="btn btn-danger" data-testid="modal-confirm-btn" id="modal-confirm">Confirm</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    // Event listeners
    document.getElementById('modal-cancel').addEventListener('click', () => {
        overlay.remove();
    });

    document.getElementById('modal-confirm').addEventListener('click', () => {
        overlay.remove();
        onConfirm();
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });

    // Close on Escape
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}


/**
 * Auto-close flash messages after 6 seconds.
 */
function initFlashAutoClose() {
    const flash = document.getElementById('flash-msg');
    if (flash) {
        setTimeout(() => {
            flash.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            setTimeout(() => flash.remove(), 400);
        }, 6000);
    }
}


/**
 * Show a loading spinner overlay.
 */
function showLoading() {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = '<div class="spinner"></div>';
    document.body.appendChild(overlay);

    // Auto-remove after 5 seconds (fallback)
    setTimeout(() => overlay.remove(), 5000);
}


/**
 * Simulate a brief loading delay for form submissions.
 */
function initLoadingIndicator() {
    // Show loading on non-confirmed form submissions
    document.querySelectorAll('form:not(:has([data-confirm]))').forEach(form => {
        form.addEventListener('submit', () => {
            showLoading();
        });
    });
}
