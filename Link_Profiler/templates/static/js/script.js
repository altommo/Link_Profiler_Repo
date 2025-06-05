// Configuration - determine API base URL dynamically
const API_BASE = window.location.protocol === 'file:'
    ? 'https://api.yspanel.com'
    : (window.location.origin.includes('monitor.yspanel.com')
        ? 'https://api.yspanel.com'
        : window.location.origin);

let authToken = localStorage.getItem('authToken');
let refreshInterval;
let currentUsername = '';
let currentUserIsAdmin = false; // New variable to store admin status

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

    // Event listener for job status filter
    document.getElementById('jobStatusFilter').addEventListener('change', loadJobsTable);

    // Event listener for submit job form
    document.getElementById('submitJobForm').addEventListener('submit', submitJob);
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
            
            if (userResponse) {
                currentUsername = userResponse.username;
                currentUserIsAdmin = userResponse.is_admin; // Store admin status
                document.getElementById('loggedInUsername').textContent = currentUsername;
                showDashboard();
            } else {
                // If /users/me fails, it means token is invalid or user doesn't exist
                showError('Authentication failed. Please try again.');
                logout(); 
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

        if (userData) {
            currentUsername = userData.username;
            currentUserIsAdmin = userData.is_admin; // Store admin status
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

    // Hide Crawler Management for non-admin users
    const crawlerManagementLink = document.querySelector('.sidebar .nav-link[data-section="crawler-management"]');
    if (!currentUserIsAdmin) {
        crawlerManagementLink.style.display = 'none';
        // If current section is crawler-management, redirect to dashboard
        if (document.querySelector('.content-section:not([style*="display:none"])')?.id === 'crawler-management') {
            showSection('dashboard');
        }
    } else {
        crawlerManagementLink.style.display = 'block'; // Ensure it's visible for admins
    }

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
    currentUserIsAdmin = false; // Reset admin status on logout
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
            // If 401 (Unauthorized) or 403 (Forbidden), it means token is invalid/expired or user lacks permission
            logout(); 
            // Optionally show a specific message for 403 if needed, but logout is primary action
            if (response.status === 403) {
                alert("Access denied. You do not have permission to perform this action.");
            }
            return null;
        }
        if (!response.ok) {
            const errorData = await response.json();
            console.error(`API call failed for ${endpoint}:`, response.status, errorData);
            alert(`API Error (${response.status}): ${errorData.detail || response.statusText}`); // Show alert for other API errors
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error(`Error during API call to ${endpoint}:`, error);
        alert(`Connection error: ${error.message}`); // Show alert for network errors
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

        // Update satellites (for Dashboard Overview)
        // The detailed satellite table is now handled by loadSatellitesTable in Crawler Management
        // updateSatellites(stats.queue_metrics?.satellites || []);

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

// --- Crawler Management Tab Functions ---

async function loadJobsTable() {
    // Only load if user is admin
    if (!currentUserIsAdmin) {
        document.getElementById('all-jobs-table-body').innerHTML = '<tr><td colspan="9" class="text-center text-danger">Access Denied: Admin privileges required.</td></tr>';
        return;
    }

    const statusFilter = document.getElementById('jobStatusFilter').value;
    const tableBody = document.getElementById('all-jobs-table-body');
    tableBody.innerHTML = '<tr><td colspan="9" class="text-center"><i class="fas fa-spinner fa-spin me-2"></i>Loading jobs...</td></tr>';

    try {
        const jobs = await callAuthenticatedAPI(`/api/jobs/all?status_filter=${statusFilter}`);
        if (!jobs) {
            tableBody.innerHTML = '<tr><td colspan="9" class="text-center">Failed to load jobs.</td></tr>';
            return;
        }

        if (jobs.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="9" class="text-center">No jobs found.</td></tr>';
            return;
        }

        tableBody.innerHTML = ''; // Clear loading message
        jobs.forEach(job => {
            const row = tableBody.insertRow();
            const jobIdShort = job.id.substring(0, 8) + '...';
            const targetUrlShort = job.target_url.length > 40 ? job.target_url.substring(0, 37) + '...' : job.target_url;
            const createdDate = job.created_date ? new Date(job.created_date).toLocaleString() : 'N/A';
            const isDisabled = job.status === 'COMPLETED' || job.status === 'FAILED' || job.status === 'CANCELLED';

            row.innerHTML = `
                <td><a href="#" onclick="showJobDetails('${job.id}')">${jobIdShort}</a></td>
                <td>${targetUrlShort}</td>
                <td>${job.job_type}</td>
                <td class="job-status-${job.status.toUpperCase()}">${job.status}</td>
                <td>${job.progress_percentage !== undefined ? job.progress_percentage.toFixed(1) : 'N/A'}</td>
                <td>${job.urls_crawled || 0}</td>
                <td>${job.errors_count || 0}</td>
                <td>${createdDate}</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="cancelJob('${job.id}')" ${isDisabled ? 'disabled' : ''}>
                        <i class="fas fa-times"></i> Cancel
                    </button>
                </td>
            `;
        });
    } catch (error) {
        console.error('Error loading jobs:', error);
        tableBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">Error loading jobs. Please check console.</td></tr>';
    }
}

async function showJobDetails(jobId) {
    // Only allow if user is admin
    if (!currentUserIsAdmin) {
        alert("Access Denied: Admin privileges required to view job details.");
        return;
    }

    const jobDetailsModal = new bootstrap.Modal(document.getElementById('jobDetailsModal'));
    const modalBody = document.getElementById('jobDetailsModal').querySelector('.modal-body');
    modalBody.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin fa-2x"></i><p>Loading job details...</p></div>';

    try {
        const job = await callAuthenticatedAPI(`/api/jobs/${jobId}`);
        if (!job) {
            modalBody.innerHTML = '<div class="text-center text-danger">Failed to load job details.</div>';
            return;
        }

        document.getElementById('detail-job-id').textContent = job.id || 'N/A';
        document.getElementById('detail-target-url').textContent = job.target_url || 'N/A';
        document.getElementById('detail-job-type').textContent = job.job_type || 'N/A';
        document.getElementById('detail-status').className = `job-status-${(job.status || 'N/A').toUpperCase()}`;
        document.getElementById('detail-status').textContent = job.status || 'N/A';
        document.getElementById('detail-progress').textContent = job.progress_percentage !== undefined ? job.progress_percentage.toFixed(1) : 'N/A';
        document.getElementById('detail-urls-crawled').textContent = job.urls_crawled || 0;
        document.getElementById('detail-links-found').textContent = job.links_found || 0;
        document.getElementById('detail-errors-count').textContent = job.errors_count || 0;
        document.getElementById('detail-created-date').textContent = job.created_date ? new Date(job.created_date).toLocaleString() : 'N/A';
        document.getElementById('detail-started-date').textContent = job.started_date ? new Date(job.started_date).toLocaleString() : 'N/A';
        document.getElementById('detail-completed-date').textContent = job.completed_date ? new Date(job.completed_date).toLocaleString() : 'N/A';
        
        document.getElementById('detail-error-log').textContent = (job.error_log && job.error_log.length > 0) ? JSON.stringify(job.error_log, null, 2) : 'No errors.';
        document.getElementById('detail-results-summary').textContent = job.results ? JSON.stringify(job.results, null, 2) : 'No results.';

        jobDetailsModal.show();
    } catch (error) {
        console.error(`Error fetching job details for ${jobId}:`, error);
        modalBody.innerHTML = `<div class="text-center text-danger">Error loading job details: ${error.message}</div>`;
    }
}

async function cancelJob(jobId) {
    // Only allow if user is admin
    if (!currentUserIsAdmin) {
        alert("Access Denied: Admin privileges required to cancel jobs.");
        return;
    }

    if (confirm(`Are you sure you want to cancel job ${jobId}?`)) {
        try {
            const response = await callAuthenticatedAPI(`/api/jobs/${jobId}/cancel`, 'POST');
            if (response) {
                alert(`Job ${jobId} cancelled successfully.`);
                loadJobsTable(); // Refresh jobs table
            } else {
                alert(`Failed to cancel job ${jobId}.`);
            }
        } catch (error) {
            console.error(`Error cancelling job ${jobId}:`, error);
            alert(`Error cancelling job ${jobId}: ${error.message}`);
        }
    }
}

async function submitJob(event) {
    event.preventDefault();
    // Only allow if user is admin
    if (!currentUserIsAdmin) {
        alert("Access Denied: Admin privileges required to submit jobs.");
        return;
    }

    const form = event.target;
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';

    const targetUrl = document.getElementById('targetUrl').value;
    const initialSeedUrls = document.getElementById('initialSeedUrls').value.split(',').map(url => url.trim()).filter(url => url);
    const jobType = document.getElementById('jobType').value;
    const jobPriority = parseInt(document.getElementById('jobPriority').value);
    const scheduledAtInput = document.getElementById('scheduledAt').value;
    const cronSchedule = document.getElementById('cronSchedule').value.trim();
    const crawlConfigText = document.getElementById('crawlConfig').value;

    let config = {};
    if (crawlConfigText) {
        try {
            config = JSON.parse(crawlConfigText);
        } catch (e) {
            alert('Invalid JSON in Crawl Config. Please correct it.');
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Job';
            return;
        }
    }
    config.job_type = jobType; // Ensure job_type is always set in config

    const jobData = {
        target_url: targetUrl,
        initial_seed_urls: initialSeedUrls,
        config: config,
        priority: jobPriority,
        scheduled_at: scheduledAtInput ? new Date(scheduledAtInput).toISOString() : null,
        cron_schedule: cronSchedule || null
    };

    try {
        const response = await callAuthenticatedAPI('/api/queue/submit_crawl', 'POST', jobData);
        if (response && response.job_id) {
            alert(`Job submitted successfully! Job ID: ${response.job_id}`);
            form.reset(); // Clear form
            bootstrap.Modal.getInstance(document.getElementById('submitJobModal')).hide(); // Close modal
            loadJobsTable(); // Refresh jobs table
        } else {
            alert(`Failed to submit job: ${response?.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error submitting job:', error);
        alert(`Error submitting job: ${error.message}`);
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Job';
    }
}

async function loadSatellitesTable() {
    // Only load if user is admin
    if (!currentUserIsAdmin) {
        document.getElementById('satellites-table-body').innerHTML = '<tr><td colspan="10" class="text-center text-danger">Access Denied: Admin privileges required.</td></tr>';
        return;
    }

    const tableBody = document.getElementById('satellites-table-body');
    tableBody.innerHTML = '<tr><td colspan="10" class="text-center"><i class="fas fa-spinner fa-spin me-2"></i>Loading satellites...</td></tr>';

    try {
        const satellitesData = await callAuthenticatedAPI('/api/monitoring/satellites'); // Assuming this endpoint exists and is protected
        if (!satellitesData || !satellitesData.satellites) {
            tableBody.innerHTML = '<tr><td colspan="10" class="text-center">Failed to load satellites.</td></tr>';
            return;
        }

        const satellites = satellitesData.satellites;
        if (satellites.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="10" class="text-center">No active satellites.</td></tr>';
            return;
        }

        tableBody.innerHTML = ''; // Clear loading message
        satellites.forEach(sat => {
            const row = tableBody.insertRow();
            const statusClass = `satellite-status-indicator satellite-status-${sat.status || 'unknown'}`;
            const lastSeen = sat.last_seen ? new Date(sat.last_seen).toLocaleString() : 'N/A';
            const uptime = formatUptime(sat.uptime_seconds || 0);

            row.innerHTML = `
                <td>${sat.crawler_id || 'N/A'}</td>
                <td>${sat.region || 'N/A'}</td>
                <td><span class="${statusClass}"></span>${(sat.status || 'Unknown').toUpperCase()}</td>
                <td>${sat.code_version || 'N/A'}</td>
                <td>${sat.running_jobs || 0}</td>
                <td>${lastSeen}</td>
                <td>${uptime}</td>
                <td>${sat.cpu_usage !== undefined ? sat.cpu_usage.toFixed(1) : 'N/A'}</td>
                <td>${sat.memory_usage !== undefined ? sat.memory_usage.toFixed(1) : 'N/A'}</td>
                <td>
                    <button class="btn btn-sm btn-warning me-1" onclick="controlSingleSatellite('${sat.crawler_id}', 'PAUSE')"><i class="fas fa-pause"></i></button>
                    <button class="btn btn-sm btn-success me-1" onclick="controlSingleSatellite('${sat.crawler_id}', 'RESUME')"><i class="fas fa-play"></i></button>
                    <button class="btn btn-sm btn-danger" onclick="controlSingleSatellite('${sat.crawler_id}', 'SHUTDOWN')"><i class="fas fa-power-off"></i></button>
                </td>
            `;
        });
    } catch (error) {
        console.error('Error loading satellites:', error);
        tableBody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Error loading satellites. Please check console.</td></tr>';
    }
}

async function checkGlobalPauseStatus() {
    // Only check if user is admin
    if (!currentUserIsAdmin) {
        document.getElementById('global-pause-status').textContent = 'Access Denied';
        document.getElementById('global-pause-status').className = 'badge bg-danger';
        return;
    }

    const statusElement = document.getElementById('global-pause-status');
    try {
        const response = await callAuthenticatedAPI('/api/jobs/is_paused'); // Assuming this endpoint exists and is protected
        if (response && response.is_paused !== undefined) {
            if (response.is_paused) {
                statusElement.className = 'badge bg-warning';
                statusElement.textContent = 'Job Processing PAUSED';
            } else {
                statusElement.className = 'badge bg-success';
                statusElement.textContent = 'Job Processing ACTIVE';
            }
        } else {
            statusElement.className = 'badge bg-secondary';
            statusElement.textContent = 'Pause Status Unknown';
        }
    } catch (error) {
        console.error('Error checking global pause status:', error);
        statusElement.className = 'badge bg-danger';
        statusElement.textContent = 'Pause Status Error';
    }
}

async function controlAllSatellites(command) {
    // Only allow if user is admin
    if (!currentUserIsAdmin) {
        alert("Access Denied: Admin privileges required to control satellites.");
        return;
    }

    if (confirm(`Are you sure you want to ${command.toLowerCase()} ALL satellites?`)) {
        try {
            const response = await callAuthenticatedAPI(`/api/satellites/control/all/${command}`, 'POST');
            if (response && response.message) {
                alert(response.message);
                loadSatellitesTable(); // Refresh satellites table
                checkGlobalPauseStatus(); // Refresh pause status
            } else {
                alert(`Failed to send command to all satellites.`);
            }
        } catch (error) {
            console.error(`Error sending command to all satellites:`, error);
            alert(`Error sending command to all satellites: ${error.message}`);
        }
    }
}

async function controlSingleSatellite(crawlerId, command) {
    // Only allow if user is admin
    if (!currentUserIsAdmin) {
        alert("Access Denied: Admin privileges required to control satellites.");
        return;
    }

    if (confirm(`Are you sure you want to ${command.toLowerCase()} satellite ${crawlerId}?`)) {
        try {
            const response = await callAuthenticatedAPI(`/api/satellites/control/${crawlerId}/${command}`, 'POST');
            if (response && response.message) {
                alert(response.message);
                loadSatellitesTable(); // Refresh satellites table
            } else {
                alert(`Failed to send command to satellite ${crawlerId}.`);
            }
        } catch (error) {
            console.error(`Error sending command to satellite ${crawlerId}:`, error);
            alert(`Error sending command to satellite ${crawlerId}: ${error.message}`);
        }
    }
}

function formatUptime(seconds) {
    if (typeof seconds !== 'number' || isNaN(seconds)) return 'N/A';
    const days = Math.floor(seconds / (3600 * 24));
    seconds %= (3600 * 24);
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${days}d ${hours}h ${minutes}m ${secs}s`;
}

// --- General Dashboard Functions ---

function startDataRefresh() {
    loadStats(); // Load immediately for overview
    // Only load crawler management data if user is admin
    if (currentUserIsAdmin) {
        loadJobsTable(); 
        loadSatellitesTable(); 
        checkGlobalPauseStatus(); 
    }

    if (refreshInterval) {
        clearInterval(refreshInterval); // Clear any existing interval
    }
    refreshInterval = setInterval(() => {
        loadStats();
        // Only refresh crawler management data if user is admin
        if (currentUserIsAdmin) {
            loadJobsTable();
            loadSatellitesTable();
            checkGlobalPauseStatus();
        }
    }, 10000); // Refresh all data every 10 seconds
}

function showSection(sectionId) {
    // If trying to access crawler-management and not admin, redirect
    if (sectionId === 'crawler-management' && !currentUserIsAdmin) {
        alert("Access Denied: Admin privileges required to access Crawler Management.");
        showSection('dashboard'); // Redirect to dashboard
        return;
    }

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

    // Special handling for Crawler Management tab to load its tables
    if (sectionId === 'crawler-management') {
        loadJobsTable();
        loadSatellitesTable();
        checkGlobalPauseStatus();
    }
}
