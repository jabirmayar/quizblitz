window.Auth = (() => {
    if (document?.documentElement) {
        document.documentElement.style.visibility = 'hidden';
    }

    const parseJwt = (jwtToken) => {
        try {
            if (!jwtToken) return null;
            const parts = jwtToken.split('.');
            if (parts.length !== 3) return null;
            const base64Url = parts[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
            return JSON.parse(atob(padded));
        } catch (_) {
            return null;
        }
    };

    const isExpired = (payload) => {
        if (!payload) return true;
        const exp = payload.exp;
        const expSeconds = (typeof exp === 'number') ? exp : (typeof exp === 'string' ? Number(exp) : null);
        if (!expSeconds || Number.isNaN(expSeconds)) return true;
        return Date.now() >= expSeconds * 1000;
    };

    const roleHome = (role) => {
        if (role === 'admin') return '/admin/dashboard';
        if (role === 'teacher') return '/teacher/dashboard';
        if (role === 'student') return '/dashboard';
        return '/';
    };

    const clearAuth = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role'); // legacy
        localStorage.removeItem('displayName');
    };

    const reveal = () => {
        if (document?.documentElement) {
            document.documentElement.style.visibility = '';
        }
    };

    const requireAuth = ({ roles = null, redirectTo = "/" } = {}) => {
        const token = localStorage.getItem('token');
        if (!token) {
            clearAuth();
            window.location.replace(redirectTo);
            return;
        }

        const payload = parseJwt(token);
        if (!payload || isExpired(payload)) {
            clearAuth();
            window.location.replace(redirectTo);
            return;
        }

        const role = payload.role;
        if (Array.isArray(roles) && roles.length > 0 && !roles.includes(role)) {
            window.location.replace(roleHome(role));
            return;
        }

        reveal();
    };

    return { parseJwt, isExpired, requireAuth, clearAuth, roleHome };
})();
