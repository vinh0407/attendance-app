/* =====================================================
   OpenCV AI Portal - Main JavaScript
   ===================================================== */

// =====================================================
// Utility Functions
// =====================================================

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: success, error, warning, info
 */
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastIcon = document.getElementById('toastIcon');
    const toastMessage = document.getElementById('toastMessage');

    if (!toast || !toastIcon || !toastMessage) return;

    const icons = {
        success: 'check_circle',
        error: 'error',
        warning: 'warning',
        info: 'info'
    };

    const colors = {
        success: 'text-green-400',
        error: 'text-red-400',
        warning: 'text-yellow-400',
        info: 'text-primary'
    };

    toastIcon.textContent = icons[type] || icons.info;
    toastIcon.className = `material-symbols-outlined ${colors[type] || colors.info}`;
    toastMessage.textContent = message;

    toast.classList.remove('translate-y-20', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');

    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
        toast.classList.remove('translate-y-0', 'opacity-100');
    }, 3000);
}

/**
 * Update current time display
 */
function updateTime() {
    const currentTimeEl = document.getElementById('currentTime');
    if (!currentTimeEl) return;

    const now = new Date();
    const timeStr = now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const dateStr = now.toLocaleDateString('vi-VN', { weekday: 'short', day: 'numeric', month: 'short' });
    currentTimeEl.textContent = `${timeStr} • ${dateStr}`;
}

/**
 * Update last sync time
 */
function updateLastSync() {
    const lastSyncEl = document.getElementById('lastSync');
    if (!lastSyncEl) return;

    const now = new Date();
    lastSyncEl.textContent = now.toLocaleTimeString('vi-VN', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
}

/**
 * Format number with leading zeros
 * @param {number} num - Number to format
 * @param {number} size - Desired size
 */
function padNumber(num, size = 2) {
    return String(num).padStart(size, '0');
}

/**
 * Fetch with error handling
 * @param {string} url - URL to fetch
 * @param {object} options - Fetch options
 */
async function safeFetch(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

/**
 * Get CSRF token from cookies
 */
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// =====================================================
// API Helper Functions
// =====================================================

/**
 * Record attendance via API
 * @param {string} studentId - Student ID
 * @param {number} confidence - Recognition confidence
 * @param {string} cameraId - Camera ID
 */
async function recordAttendance(studentId, confidence = 0, cameraId = '') {
    const csrfToken = getCsrfToken();
    
    try {
        const response = await safeFetch('/api/record-attendance/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                student_id: studentId,
                confidence: confidence,
                camera_id: cameraId
            })
        });

        if (response.success) {
            showToast(`Attendance recorded for ${response.data.student_name}`, 'success');
        } else {
            showToast(response.error || 'Failed to record attendance', 'error');
        }

        return response;
    } catch (error) {
        showToast('Failed to record attendance', 'error');
        throw error;
    }
}

/**
 * Fetch system stats
 */
async function fetchStats() {
    try {
        const response = await safeFetch('/api/stats/');
        return response.data;
    } catch (error) {
        console.error('Failed to fetch stats:', error);
        return null;
    }
}

/**
 * Fetch students list
 */
async function fetchStudents() {
    try {
        const response = await safeFetch('/api/students/');
        return response.data;
    } catch (error) {
        console.error('Failed to fetch students:', error);
        return [];
    }
}

/**
 * Fetch today's attendance
 */
async function fetchTodayAttendance() {
    try {
        const response = await safeFetch('/api/attendance/today/');
        return response.data;
    } catch (error) {
        console.error('Failed to fetch attendance:', error);
        return [];
    }
}

// =====================================================
// Initialize
// =====================================================

// Log initialization
console.log('🚀 OpenCV AI Portal JS loaded');

// Export functions for global use
window.showToast = showToast;
window.updateTime = updateTime;
window.updateLastSync = updateLastSync;
window.recordAttendance = recordAttendance;
window.fetchStats = fetchStats;
window.fetchStudents = fetchStudents;
window.fetchTodayAttendance = fetchTodayAttendance;
window.getCsrfToken = getCsrfToken;
