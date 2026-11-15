/**
 * Lightweight Zero-SDK Cognito PKCE Auth Client with Svelte 5 Runes.
 * Enforces pre-stream token refresh within 5 minutes of expiration.
 */
import type { UserProfile } from './types';

interface AuthTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresAt: number;
}

/**
 * Browser-native Zero-SDK JWT claim parser for extracting Cognito ID token claims.
 */
export function parseJwtClaims(token: string): Record<string, any> {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return {};
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return {};
  }
}

class AuthStore {
  user = $state<UserProfile | null>(null);
  tokens = $state<AuthTokens | null>(null);
  isAuthenticated = $derived(!!this.user && !!this.tokens?.accessToken);
  authModalOpen = $state(false);

  constructor() {
    this.loadPersistedAuth();
  }

  private loadPersistedAuth() {
    try {
      const savedUser = localStorage.getItem('intelliq_user');
      const savedTokens = localStorage.getItem('intelliq_tokens');
      if (savedTokens) {
        this.tokens = JSON.parse(savedTokens);
        const claims = this.tokens?.idToken ? parseJwtClaims(this.tokens.idToken) : {};
        if (savedUser) {
          const parsedUser: UserProfile = JSON.parse(savedUser);
          const givenName = claims.given_name || parsedUser.given_name;
          this.user = {
            ...parsedUser,
            given_name: givenName,
            name: givenName || parsedUser.name || parsedUser.email,
          };
        }
      } else if (savedUser) {
        this.user = JSON.parse(savedUser);
      }
    } catch (e) {
      console.warn('Failed to load persisted auth:', e);
    }
  }

  setSession(tokens: AuthTokens, user: UserProfile) {
    const claims = tokens.idToken ? parseJwtClaims(tokens.idToken) : {};
    const givenName = claims.given_name || user.given_name;
    const resolvedUser: UserProfile = {
      ...user,
      given_name: givenName,
      name: givenName || user.name || user.email,
    };
    this.tokens = tokens;
    this.user = resolvedUser;
    localStorage.setItem('intelliq_user', JSON.stringify(resolvedUser));
    localStorage.setItem('intelliq_tokens', JSON.stringify(tokens));
  }

  logout() {
    this.user = null;
    this.tokens = null;
    localStorage.removeItem('intelliq_user');
    localStorage.removeItem('intelliq_tokens');
  }

  /**
   * Pre-Stream Token Refresh: verifies token is not within 5 minutes of expiration.
   */
  async getValidToken(): Promise<string> {
    if (!this.tokens) {
      return '';
    }

    const nowSeconds = Math.floor(Date.now() / 1000);
    const timeUntilExpiry = this.tokens.expiresAt - nowSeconds;

    // If within 5 minutes (300 seconds), trigger refresh
    if (timeUntilExpiry < 300 && this.tokens.refreshToken) {
      await this.refreshTokens();
    }

    return this.tokens.idToken || this.tokens.accessToken;
  }

  private async refreshTokens() {
    if (!this.tokens?.refreshToken) return;
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.tokens.refreshToken }),
      });
      if (res.ok) {
        const data = await res.json();
        this.tokens = {
          accessToken: data.access_token,
          idToken: data.id_token,
          refreshToken: data.refresh_token || this.tokens.refreshToken,
          expiresAt: Math.floor(Date.now() / 1000) + 3600,
        };
        localStorage.setItem('intelliq_tokens', JSON.stringify(this.tokens));
        if (this.user && data.id_token) {
          const claims = parseJwtClaims(data.id_token);
          if (claims.given_name) {
            this.user.given_name = claims.given_name;
            this.user.name = claims.given_name;
            localStorage.setItem('intelliq_user', JSON.stringify(this.user));
          }
        }
      }
    } catch (e) {
      console.warn('Silent token refresh failed:', e);
    }
  }

  async login(email: string, password: string): Promise<{ success: boolean; error?: string; challenge?: string; session?: string }> {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.error || 'Authentication failed' };
      }

      if (data.challenge === 'NEW_PASSWORD_REQUIRED') {
        return {
          success: false,
          challenge: 'NEW_PASSWORD_REQUIRED',
          session: data.session,
          error: data.message || 'Temporary password detected. You must set a new permanent password.',
        };
      }

      const claims = data.id_token ? parseJwtClaims(data.id_token) : {};
      const givenName = data.user?.given_name || claims.given_name;
      this.setSession(
        {
          accessToken: data.access_token,
          idToken: data.id_token,
          refreshToken: data.refresh_token,
          expiresAt: Math.floor(Date.now() / 1000) + (data.expires_in || 3600),
        },
        {
          user_id: data.user.sub,
          email: data.user.email,
          given_name: givenName,
          name: givenName || data.user.name || email.split('@')[0],
          created_at: new Date().toISOString(),
        }
      );
      this.authModalOpen = false;
      return { success: true };
    } catch (err: any) {
      console.error('Login error:', err);
      return { success: false, error: err.message || 'Network error contacting Cognito' };
    }
  }

  async completeNewPassword(email: string, newPassword: string, session: string): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await fetch('/api/auth/new-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), new_password: newPassword, session }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.error || 'Password update failed' };
      }
      const claims = data.id_token ? parseJwtClaims(data.id_token) : {};
      const givenName = data.user?.given_name || claims.given_name;
      this.setSession(
        {
          accessToken: data.access_token,
          idToken: data.id_token,
          refreshToken: data.refresh_token,
          expiresAt: Math.floor(Date.now() / 1000) + (data.expires_in || 3600),
        },
        {
          user_id: data.user.sub,
          email: data.user.email,
          given_name: givenName,
          name: givenName || data.user.name || email.split('@')[0],
          created_at: new Date().toISOString(),
        }
      );
      this.authModalOpen = false;
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.message || 'Failed to update permanent password' };
    }
  }

  async signUp(email: string, password: string, name?: string): Promise<{ success: boolean; error?: string; message?: string }> {
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password, name: name?.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.error || 'Registration failed' };
      }
      return { success: true, message: data.message || 'Verification code sent to your email.' };
    } catch (err: any) {
      return { success: false, error: err.message || 'Registration failed' };
    }
  }

  async confirmSignUp(email: string, code: string): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await fetch('/api/auth/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), code: code.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.error || 'Confirmation failed' };
      }
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.message || 'Confirmation failed' };
    }
  }
}

export const auth = new AuthStore();

