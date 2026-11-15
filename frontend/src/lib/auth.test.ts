import { describe, expect, it, beforeEach } from 'vitest';
import { auth, parseJwtClaims } from './auth.svelte';

function createMockJwt(payload: Record<string, any>): string {
  const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const body = btoa(JSON.stringify(payload)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const sig = 'mock_signature';
  return `${header}.${body}.${sig}`;
}

describe('Auth Client & Cognito given_name (ADR-04 & ADR-07)', () => {
  beforeEach(() => {
    localStorage.clear();
    auth.logout();
  });

  it('correctly parses Cognito claims from ID token', () => {
    const token = createMockJwt({
      sub: 'usr_123',
      email: 'alex.smith@deloitte.com',
      given_name: 'Alex',
    });

    const claims = parseJwtClaims(token);
    expect(claims.sub).toBe('usr_123');
    expect(claims.email).toBe('alex.smith@deloitte.com');
    expect(claims.given_name).toBe('Alex');
  });

  it('returns empty object when token is malformed', () => {
    expect(parseJwtClaims('invalid.token')).toEqual({});
    expect(parseJwtClaims('')).toEqual({});
  });

  it('sets user name to given_name attribute when setSession is called', () => {
    const idToken = createMockJwt({
      sub: 'usr_abc',
      email: 'john.doe@deloitte.com',
      given_name: 'John',
    });

    auth.setSession(
      {
        accessToken: 'mock_access',
        idToken,
        refreshToken: 'mock_refresh',
        expiresAt: Math.floor(Date.now() / 1000) + 3600,
      },
      {
        user_id: 'usr_abc',
        email: 'john.doe@deloitte.com',
        name: 'john.doe',
        created_at: new Date().toISOString(),
      }
    );

    expect(auth.isAuthenticated).toBe(true);
    expect(auth.user?.given_name).toBe('John');
    expect(auth.user?.name).toBe('John');
  });

  it('persists and restores given_name across session reloads', () => {
    const idToken = createMockJwt({
      sub: 'usr_xyz',
      email: 'samantha.green@deloitte.com',
      given_name: 'Samantha',
    });

    localStorage.setItem(
      'intelliq_tokens',
      JSON.stringify({
        accessToken: 'access_xyz',
        idToken,
        refreshToken: 'refresh_xyz',
        expiresAt: Math.floor(Date.now() / 1000) + 3600,
      })
    );
    // Legacy user stored with email prefix in name
    localStorage.setItem(
      'intelliq_user',
      JSON.stringify({
        user_id: 'usr_xyz',
        email: 'samantha.green@deloitte.com',
        name: 'samantha.green',
        created_at: new Date().toISOString(),
      })
    );

    // Calling setSession or simulating reload
    auth.setSession(
      {
        accessToken: 'access_xyz',
        idToken,
        refreshToken: 'refresh_xyz',
        expiresAt: Math.floor(Date.now() / 1000) + 3600,
      },
      JSON.parse(localStorage.getItem('intelliq_user')!)
    );

    expect(auth.user?.given_name).toBe('Samantha');
    expect(auth.user?.name).toBe('Samantha');
  });
});
