export interface User {
    id: string;
    email: string;
    username: string;
}

export const authState = $state<{
    user: User | null;
    token: string | null;
    isInitialized: boolean;
    serviceError: boolean;
}>({
    user: null,
    token: null,
    isInitialized: false,
    serviceError: false,
});

export function initializeAuth() {
    if (typeof window !== 'undefined') {
        const storedToken = localStorage.getItem('auth_token');
        if (storedToken) {
            authState.token = storedToken;
            fetchUser(storedToken);
        } else {
            authState.isInitialized = true;
        }
    }
}

async function fetchUser(token: string) {
    try {
        const response = await fetch('/api/v1/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            authState.user = await response.json();
            authState.serviceError = false;
        } else if (response.status === 401 || response.status === 403) {
            // Bad or expired token — clear it
            logout();
        } else {
            // 5xx or unexpected status: service is starting up, keep the token
            authState.serviceError = true;
        }
    } catch {
        // Network unreachable — keep the token so the user isn't logged out
        authState.serviceError = true;
    } finally {
        authState.isInitialized = true;
    }
}

export function login(token: string) {
    if (typeof window !== 'undefined') {
        localStorage.setItem('auth_token', token);
    }
    authState.token = token;
    authState.serviceError = false;
    fetchUser(token);
}

export function logout() {
    if (typeof window !== 'undefined') {
        const token = localStorage.getItem('auth_token');
        if (token) {
            fetch('/api/v1/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
            }).catch(() => {});
        }
        localStorage.removeItem('auth_token');
    }
    authState.token = null;
    authState.user = null;
    authState.serviceError = false;
}
