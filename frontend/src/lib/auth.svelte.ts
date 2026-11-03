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
      if (savedUser && savedTokens) {
        this.user = JSON.parse(savedUser);
        this.tokens = JSON.parse(savedTokens);
      }
    } catch (e) {
      console.warn('Failed to load persisted auth:', e);
    }
  }

  setSession(tokens: AuthTokens, user: UserProfile) {
    this.tokens = tokens;
    this.user = user;
    localStorage.setItem('intelliq_user', JSON.stringify(user));
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
          name: data.user.name || email.split('@')[0],
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
          name: data.user.name || email.split('@')[0],
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

