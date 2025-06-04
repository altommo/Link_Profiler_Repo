// Configuration - determine API base URL dynamically
const API_BASE = window.location.protocol === 'file:' 
    ? 'https://api.yspanel.com' 
    : (window.location.origin.includes('monitor.yspanel.com') 
        ? 'https://api.yspanel.com' 
        : window.location.origin);

let authToken = localStorage.getItem('authToken');
let refreshInterval;
let currentUsername = '';

// DOMContentLoaded: Check for token and show appropriate screen
document.addEventListener('DOMContentLoaded', function() {
    if (authToken) {
        verifyToken();
    } else {
        document.getElementById('loginContainer').style.display = 'flex';
    }

    // Add event listeners for sidebar navigation
    document.querySelectorAll('.sidebar .nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const sectionId = this.dataset.section;
            showSection(sectionId);
        });
    });
});

// Login form submission
document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    await login();
});

async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const loginAlert = document.getElementById('loginAlert');

    try {
        const response = await fetch(`${API_BASE}/auth/token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
        });

        const data = await response.json();

        if (response.ok) {
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            
            // Verify the user is admin and get username
            const userResponse = await callAuthenticatedAPI('/users/me');
            
            if (userResponse && userResponse.is_admin) {
                currentUsername = userResponse.username;
                document.getElementById('loggedInUsername').textContent = currentUsername;
                showDashboard();
            } else {
                showError('Access denied. Admin privileges required.');
                logout(); // Clear token if not admin
            }
        } else {
            showError(data.detail || 'Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        showError('Connection error. Please try again.');
    }
}

async function verifyToken() {
    try {
        const userData = await callAuthenticatedAPI('/users/me');

        if (userData && userData.is_admin) {
            currentUsername = userData.username;
            document.getElementById('loggedInUsername').textContent = currentUsername;
            showDashboard();
        } else {
            logout();
        }
    } catch (error) {
        logout();
    }
}

function showDashboard() {
    document.getElementById('loginContainer').style.display = 'none';
    document.getElementById('dashboardContainer').style.display = 'flex'; // Use flex for layout
    startDataRefresh();
    showSection('dashboard'); // Show default section
}

function showError(message) {
    const loginAlert = document.getElementById('loginAlert');
    loginAlert.textContent = message;
    loginAlert.classList.remove('d-none');
    setTimeout(() => {
        loginAlert.classList.add('d-none');
    }, 5000);
}

function logout() {
    localStorage.removeItem('authToken');
    authToken = null;
    currentUsername = '';
    document.getElementById('loginContainer').style.display = 'flex';
    document.getElementById('dashboardContainer').style.display = 'none';
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}

async function callAuthenticatedAPI(endpoint, method = 'GET', data = null) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
    };
    const options = { method, headers };
    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        if (response.status === 401 || response.status === 403) {
            logout(); // Token expired or unauthorized
            return null;
        }
        if (!response.ok) {
            const errorData = await response.json();
            console.error(`API call failed for ${endpoint}:`, response.status, errorData);
            // Optionally show a dashboard-wide error alert
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error(`Error during API call to ${endpoint}:`, error);
        // Optionally show a dashboard-wide error alert
        return null;
    }
}

async function loadStats() {
    try {
        const stats = await callAuthenticatedAPI('/api/dashboard/stats'); // New endpoint
        if (!stats) return;

        // Update metrics
        document.getElementById('pendingJobs').textContent = stats.queue_metrics?.pending_jobs || 0;
        document.getElementById('activeSatellites').textContent = stats.queue_metrics?.active_crawlers || 0;
        document.getElementById('successRate').textContent = (stats.performance_stats?.success_rate || 0).toFixed(1) + '%';
        document.getElementById('totalProfiles').textContent = stats.data_summaries?.total_link_profiles || 0;

        // Update system status
        const isHealthy = stats.api_health?.status === 'healthy' && 
                          stats.redis?.status === 'connected' && 
                          stats.database?.status === 'connected';
        const statusElement = document.getElementById('systemStatus');
        const badgeClass = isHealthy ? 'status-healthy' : 'status-unhealthy';
        const icon = isHealthy ? 'fa-check-circle' : 'fa-exclamation-triangle';
        const text = isHealthy ? 'All Systems Operational' : 'System Issues Detected';
        
        statusElement.innerHTML = `
            <span class="status-badge ${badgeClass}">
                <i class="fas ${icon} me-1"></i>${text}
            </span>
            <small class="text-muted ms-3">Last updated: ${new Date().toLocaleTimeString()}</small>
        `;

        // Update system resources
        if (stats.system) {
            updateProgressBar('cpuProgress', 'cpuText', stats.system.cpu_percent, '%');
            updateProgressBar('memoryProgress', 'memoryText', stats.system.memory?.percent, '%');
            updateProgressBar('diskProgress', 'diskText', stats.system.disk?.percent, '%');
        }

        // Update satellites
        updateSatellites(stats.queue_metrics?.satellites || []);

    } catch (error) {
        console.error('Error loading stats:', error);
        // If error is due to authentication, logout is handled by callAuthenticatedAPI
    }
}

function updateProgressBar(progressId, textId, value, suffix = '') {
    const progressBar = document.getElementById(progressId);
    const textElement = document.getElementById(textId);
    
    if (value !== undefined && value !== null) {
        progressBar.style.width = value + '%';
        progressBar.className = 'progress-bar ' + getProgressBarClass(value);
        textElement.textContent = value.toFixed(1) + suffix;
    }
}

function getProgressBarClass(value) {
    if (value < 50) return 'bg-success';
    if (value < 80) return 'bg-warning';
    return 'bg-danger';
}

function updateSatellites(satellites) {
    const container = document.getElementById('satelliteStatus');
    
    if (satellites.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">No active crawlers</div>';
        return;
    }

    const satelliteHTML = satellites.map(satellite => {
        const statusClass = `satellite-status-indicator satellite-status-${satellite.status || 'unknown'}`;
        return `
            <div class="d-flex justify-content-between align-items-center mb-2 p-2 rounded" style="background: #f8f9fa;">
                <div>
                    <strong>${satellite.crawler_id || 'Unknown'}</strong>
                    <small class="text-muted d-block">${satellite.region || 'Unknown region'}</small>
                </div>
                <div class="text-end">
                    <span class="${statusClass}"></span>${(satellite.status || 'Unknown').toUpperCase()}
                    <small class="text-muted d-block">Jobs: ${satellite.jobs_processed || 0}</small>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = satelliteHTML;
}

function startDataRefresh() {
    loadStats(); // Load immediately
    if (refreshInterval) {
        clearInterval(refreshInterval); // Clear any existing interval
    }
    refreshInterval = setInterval(loadStats, 10000); // Refresh every 10 seconds
}

function showSection(sectionId) {
    // Hide all content sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.style.display = 'none';
    });

    // Show the requested section
    const activeSection = document.getElementById(sectionId);
    if (activeSection) {
        activeSection.style.display = 'block';
    }

    // Update active class in sidebar
    document.querySelectorAll('.sidebar .nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`.sidebar .nav-link[data-section="${sectionId}"]`).classList.add('active');
}
