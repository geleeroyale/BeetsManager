document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Check beets configuration on page load
    checkBeetsConfig();

    // Initialize navigation event listeners
    setupNavigation();
    
    // Check if we need to show the connection status in the header
    checkConnectionStatus();
});

function setupNavigation() {
    // Get all nav links
    const navLinks = document.querySelectorAll('.nav-link');
    
    // Add click event to each nav link
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Remove active class from all links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
        });
    });
}

function checkBeetsConfig() {
    // Get configuration information from the page
    const configStatus = document.getElementById('config-status');
    if (!configStatus) return;

    const statusData = JSON.parse(configStatus.dataset.status || '{}');
    
    // Update UI based on configuration status
    updateConfigUI(statusData);
}

function updateConfigUI(status) {
    const configAlert = document.getElementById('config-alert');
    const configDetails = document.getElementById('config-details');
    
    if (!status.beets_installed) {
        configAlert.classList.remove('d-none', 'alert-success');
        configAlert.classList.add('alert-danger');
        configAlert.textContent = 'Beets is not installed or not in PATH. Please install beets first.';
        return;
    }
    
    if (!status.config_exists || !status.db_exists) {
        configAlert.classList.remove('d-none', 'alert-success');
        configAlert.classList.add('alert-warning');
        configAlert.textContent = 'Beets is installed but not fully configured. Please check the configuration.';
    } else {
        configAlert.classList.remove('d-none', 'alert-danger', 'alert-warning');
        configAlert.classList.add('alert-success');
        configAlert.textContent = 'Beets is installed and configured correctly.';
    }
    
    // Show configuration details
    let detailsHTML = '<ul class="list-group mt-3">';
    detailsHTML += `<li class="list-group-item ${status.beets_installed ? 'list-group-item-success' : 'list-group-item-danger'}">
                        <i class="fas fa-${status.beets_installed ? 'check' : 'times'}"></i> 
                        Beets Installation: ${status.beets_installed ? 'Installed' : 'Not Installed'}
                    </li>`;
    detailsHTML += `<li class="list-group-item ${status.config_exists ? 'list-group-item-success' : 'list-group-item-warning'}">
                        <i class="fas fa-${status.config_exists ? 'check' : 'exclamation'}"></i> 
                        Configuration File: ${status.config_exists ? 'Found' : 'Not Found'} 
                        <span class="text-muted">(${status.config_path})</span>
                    </li>`;
    detailsHTML += `<li class="list-group-item ${status.db_exists ? 'list-group-item-success' : 'list-group-item-warning'}">
                        <i class="fas fa-${status.db_exists ? 'check' : 'exclamation'}"></i> 
                        Database File: ${status.db_exists ? 'Found' : 'Not Found'} 
                        <span class="text-muted">(${status.db_path})</span>
                    </li>`;
    detailsHTML += '</ul>';
    
    configDetails.innerHTML = detailsHTML;
}

function showError(message) {
    const errorToast = new bootstrap.Toast(document.getElementById('errorToast'));
    document.getElementById('errorToastBody').textContent = message;
    errorToast.show();
}

function showSuccess(message) {
    const successToast = new bootstrap.Toast(document.getElementById('successToast'));
    document.getElementById('successToastBody').textContent = message;
    successToast.show();
}

// Helper function to format time in seconds to MM:SS
function formatTime(seconds) {
    if (!seconds) return '0:00';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

// Helper function to create loading spinner
function createLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.className = 'spinner-border spinner-border-sm text-light';
    spinner.setAttribute('role', 'status');
    
    const span = document.createElement('span');
    span.className = 'visually-hidden';
    span.textContent = 'Loading...';
    
    spinner.appendChild(span);
    return spinner;
}

// Helper function to enable/disable buttons with loading state
function setButtonLoading(button, isLoading) {
    if (isLoading) {
        const originalText = button.textContent;
        button.setAttribute('data-original-text', originalText);
        button.disabled = true;
        button.innerHTML = '';
        
        const spinner = createLoadingSpinner();
        button.appendChild(spinner);
        
        const textSpan = document.createElement('span');
        textSpan.textContent = ' Loading...';
        button.appendChild(textSpan);
    } else {
        const originalText = button.getAttribute('data-original-text');
        button.textContent = originalText;
        button.disabled = false;
    }
}

// Check connection status and update navigation
function checkConnectionStatus() {
    // Add a connection indicator to the navbar if it doesn't exist
    const navbar = document.querySelector('.navbar-nav');
    if (navbar) {
        // Check if connection indicator already exists
        let connectionIndicator = document.getElementById('connection-indicator');
        if (!connectionIndicator) {
            // Create a new indicator
            connectionIndicator = document.createElement('li');
            connectionIndicator.className = 'nav-item ms-3';
            connectionIndicator.id = 'connection-indicator';
            
            // Create the indicator content
            connectionIndicator.innerHTML = `
                <span class="badge bg-secondary d-flex align-items-center">
                    <i class="fas fa-spinner fa-spin me-1"></i>
                    <span>Checking...</span>
                </span>
            `;
            
            navbar.appendChild(connectionIndicator);
        }
        
        // Fetch the connection mode
        fetch('/api/connection/mode')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch connection mode');
                }
                return response.json();
            })
            .then(data => {
                // Update the indicator based on mode
                if (data.mode === 'local') {
                    connectionIndicator.innerHTML = `
                        <a href="/config" class="badge bg-success d-flex align-items-center text-decoration-none">
                            <i class="fas fa-laptop me-1"></i>
                            <span>Local</span>
                        </a>
                    `;
                } else {
                    const host = data.remote_config?.host || 'Remote';
                    connectionIndicator.innerHTML = `
                        <a href="/config" class="badge bg-primary d-flex align-items-center text-decoration-none">
                            <i class="fas fa-server me-1"></i>
                            <span>${host}</span>
                        </a>
                    `;
                }
            })
            .catch(error => {
                console.error('Error checking connection status:', error);
                connectionIndicator.innerHTML = `
                    <a href="/config" class="badge bg-danger d-flex align-items-center text-decoration-none">
                        <i class="fas fa-exclamation-triangle me-1"></i>
                        <span>Error</span>
                    </a>
                `;
            });
    }
}
