const api = {
    baseUrl: '',

    getJwtPayload(token) {
        try {
            if (!token) return null;
            const parts = token.split('.');
            if (parts.length !== 3) return null;
            const base64Url = parts[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
            return JSON.parse(atob(padded));
        } catch (_) {
            return null;
        }
    },
    
    async request(endpoint, method = 'GET', body = null) {
        const token = localStorage.getItem('token');
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const options = { method, headers };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(`${this.baseUrl}${endpoint}`, options);

        if (response.status === 401) {
            this.logout();
            return;
        }

        if (response.status === 403) {
            alert("Security Alert: You do not have permission to access this data.");
            const payload = this.getJwtPayload(token);
            const role = (payload && payload.role) ? payload.role : localStorage.getItem('role');
            if (role === 'admin') window.location.href = '/admin/dashboard';
            else if (role === 'teacher') window.location.href = '/teacher/dashboard';
            else window.location.href = '/dashboard';
            return;
        }

        if (!response.ok) {
            const error = await response.json();
            throw error;
        }

        return response.json();
    },

    get(endpoint) { return this.request(endpoint, 'GET'); },
    post(endpoint, body) { return this.request(endpoint, 'POST', body); },
    put(endpoint, body) { return this.request(endpoint, 'PUT', body); },
    delete(endpoint) { return this.request(endpoint, 'DELETE'); },

    logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('displayName');
        window.location.href = '/';
    }
};
