/**
 * Authentication utilities for frontend
 */

class AuthManager {
    constructor() {
        this.tokenKey = 'fuji_auth_token';
        this.userKey = 'fuji_user_info';
    }

    /**
     * Store JWT token and user info
     */
    login(token, user) {
        localStorage.setItem(this.tokenKey, token);
        localStorage.setItem(this.userKey, JSON.stringify(user));
        this.setAuthHeader(token);
        
        // Trigger login event for chatbox
        window.dispatchEvent(new CustomEvent('userLogin', { detail: { user } }));
    }

    /**
     * Remove JWT token and user info
     */
    logout() {
        // Only clear JWT-related data, not session data
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.userKey);
        sessionStorage.removeItem(this.tokenKey);
        sessionStorage.removeItem(this.userKey);
        this.clearAuthHeader();
        
        // Trigger logout event for chatbox
        window.dispatchEvent(new CustomEvent('userLogout'));
        
        // Call API logout if token exists
        this.apiLogout();
    }

    /**
     * Get stored JWT token
     */
    getToken() {
        return localStorage.getItem(this.tokenKey) || sessionStorage.getItem(this.tokenKey);
    }

    /**
     * Get stored user info
     */
    getUser() {
        const userStr = localStorage.getItem(this.userKey) || sessionStorage.getItem(this.userKey);
        return userStr ? JSON.parse(userStr) : null;
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.getToken();
    }

    /**
     * Set Authorization header for API requests
     */
    setAuthHeader(token) {
        if (typeof axios !== 'undefined') {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        }
        if (typeof fetch !== 'undefined') {
            // Store token for manual fetch requests
            window.authToken = token;
        }
    }

    /**
     * Clear Authorization header
     */
    clearAuthHeader() {
        if (typeof axios !== 'undefined') {
            delete axios.defaults.headers.common['Authorization'];
        }
        if (typeof window !== 'undefined') {
            delete window.authToken;
        }
    }

    /**
     * Call API logout endpoint
     */
    async apiLogout() {
        const token = this.getToken();
        if (!token) return;

        try {
            const response = await fetch('/api/v1/auth/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                console.warn('API logout failed:', response.statusText);
            }
        } catch (error) {
            console.warn('API logout error:', error);
        }
    }

    /**
     * Initialize auth manager
     */
    init() {
        const token = this.getToken();
        if (token) {
            this.setAuthHeader(token);
        }

        // Auto logout when session expires
        this.checkTokenExpiry();
    }

    /**
     * Check if token is expired
     */
    checkTokenExpiry() {
        const token = this.getToken();
        if (!token) return;

        try {
            // Decode JWT payload (simple base64 decode)
            const payload = JSON.parse(atob(token.split('.')[1]));
            const now = Date.now() / 1000;
            
            if (payload.exp && payload.exp < now) {
                console.log('Token expired, logging out...');
                this.logout();
                // Redirect to login if on a protected page
                if (window.location.pathname.includes('profile') || 
                    window.location.pathname.includes('order')) {
                    window.location.href = '/login';
                }
            }
        } catch (error) {
            console.warn('Token validation failed:', error);
            this.logout();
        }
    }
}

// Global auth manager instance
window.authManager = new AuthManager();

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    window.authManager.init();
});

// Enhanced logout function for web UI
function enhancedLogout() {
    // Clear client-side auth data
    window.authManager.logout();
    
    // Clear only auth-related session storage, not all session data
    sessionStorage.removeItem('fuji_auth_token');
    sessionStorage.removeItem('fuji_user_info');
    
    // Then do the regular server-side logout
    window.location.href = '/logout';
}

// Override any existing logout links
document.addEventListener('DOMContentLoaded', function() {
    const logoutLinks = document.querySelectorAll('a[href="/logout"], a[href*="logout"]');
    logoutLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            enhancedLogout();
        });
    });
});