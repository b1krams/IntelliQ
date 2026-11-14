import { describe, expect, it, vi, beforeEach } from 'vitest';
import { readUrlParams, updateUrlParams, initUrlSync, type SyncableStore } from './url_sync';

describe('URL Synchronization & Hydration (ADR-12)', () => {
  it('parses valid session and stage parameters', () => {
    const parsed = readUrlParams('?session=ABC12&stage=stories');
    expect(parsed.sessionId).toBe('ABC12');
    expect(parsed.stage).toBe('stories');
  });

  it('normalizes session to uppercase and handles case-insensitive stages', () => {
    const parsed = readUrlParams('?session=xyz89&stage=EPICS');
    expect(parsed.sessionId).toBe('XYZ89');
    expect(parsed.stage).toBe('epics');
  });

  it('ignores invalid stages gracefully without crashing', () => {
    const parsed = readUrlParams('?session=ABC12&stage=invalid_stage_xyz');
    expect(parsed.sessionId).toBe('ABC12');
    expect(parsed.stage).toBeUndefined();
  });

  it('returns undefined when no query parameters are present', () => {
    const parsed = readUrlParams('');
    expect(parsed.sessionId).toBeUndefined();
    expect(parsed.stage).toBeUndefined();
  });

  it('updates browser URL parameters via replaceState', () => {
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState');
    updateUrlParams('NEW12', 'test_cases');

    expect(replaceStateSpy).toHaveBeenCalled();
    replaceStateSpy.mockRestore();
  });

  it('hydrates store on initial mount and registers popstate listener', async () => {
    const mockStore: SyncableStore = {
      state: { workflow_id: 'OLD01' },
      viewStage: 'intake',
      setViewStage: vi.fn(),
      loadSession: vi.fn().mockResolvedValue(true),
      setSessionId: vi.fn(),
      showToast: vi.fn(),
    };

    // Mock search params with session and stage
    const originalSearch = window.location.search;
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, search: '?session=SES99&stage=brd' },
    });

    const cleanup = initUrlSync(mockStore);
    expect(mockStore.loadSession).toHaveBeenCalledWith('SES99');

    // Wait for resolution
    await Promise.resolve();
    expect(mockStore.setViewStage).toHaveBeenCalledWith('brd');

    cleanup();
    window.location.search = originalSearch;
  });
});
