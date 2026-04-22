export interface User {
    id: string;
    email: string;
    username: string;
}

export const authState = $state<{
    user: User | null;
    token: string | null;
    isInitialized: boolean;
}>({
    user: null,
    token: null,
    isInitialized: false
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
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        if (response.ok) {
            authState.user = await response.json();
        } else {
            // Token invalid or expired
            logout();
        }
    } catch (e) {
        console.error("Failed to fetch user", e);
        logout();
    } finally {
        authState.isInitialized = true;
    }
}

export function login(token: string) {
    if (typeof window !== 'undefined') {
        localStorage.setItem('auth_token', token);
    }
    authState.token = token;
    fetchUser(token);
}

export function logout() {
    if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
    }
    authState.token = null;
    authState.user = null;
}
