/**
 * Zero-Dependency URL-State Hydration & Deep Linking (ADR-12).
 * Synchronizes active session IDs and view stages with the browser location
 * using native history APIs (pushState / replaceState) without routing bloat.
 */
import type { Stage } from './types';

export type ViewableStage = 'intake' | 'brd' | 'epics' | 'stories' | 'test_cases';

export const VALID_STAGES: readonly ViewableStage[] = ['intake', 'brd', 'epics', 'stories', 'test_cases'] as const;

export interface ParsedUrlState {
  sessionId?: string;
  stage?: ViewableStage;
}

/**
 * Extracts and sanitizes session and stage parameters from current browser URL.
 */
export function readUrlParams(urlSearch: string = window.location.search): ParsedUrlState {
  const params = new URLSearchParams(urlSearch);
  const rawSession = params.get('session');
  const rawStage = params.get('stage');

  const sessionId = rawSession ? rawSession.trim().toUpperCase() : undefined;
  const stage = rawStage && (VALID_STAGES as readonly string[]).includes(rawStage.toLowerCase())
    ? (rawStage.toLowerCase() as ViewableStage)
    : undefined;

  return { sessionId, stage };
}

/**
 * Synchronizes session and stage state to the browser address bar without reload.
 */
export function updateUrlParams(sessionId: string, stage: ViewableStage): void {
  if (typeof window === 'undefined') return;

  const currentParams = new URLSearchParams(window.location.search);
  let changed = false;

  if (sessionId && currentParams.get('session') !== sessionId) {
    currentParams.set('session', sessionId);
    changed = true;
  }

  if (stage && currentParams.get('stage') !== stage) {
    currentParams.set('stage', stage);
    changed = true;
  }

  if (changed) {
    const newQuery = currentParams.toString();
    const newRelativePathQuery = `${window.location.pathname}?${newQuery}${window.location.hash}`;
    window.history.replaceState({ sessionId, stage }, '', newRelativePathQuery);
  }
}

export interface SyncableStore {
  state: { workflow_id: string };
  viewStage: ViewableStage;
  setViewStage: (stage: ViewableStage) => void;
  loadSession: (sessionId: string) => Promise<boolean>;
  setSessionId: (newId: string) => void;
  showToast: (message: string, isAlert?: boolean) => void;
}

/**
 * Initializes bidirectional hydration between browser URL and WorkflowStore.
 */
export function initUrlSync(store: SyncableStore): () => void {
  if (typeof window === 'undefined') return () => {};

  // 1. Initial Mount Hydration
  const { sessionId, stage } = readUrlParams();
  if (sessionId) {
    if (sessionId !== store.state.workflow_id) {
      store.loadSession(sessionId).then((loaded) => {
        if (!loaded) {
          store.setSessionId(sessionId);
        }
        if (stage) {
          store.setViewStage(stage);
        }
      });
    } else if (stage) {
      store.setViewStage(stage);
    }
  } else if (stage) {
    store.setViewStage(stage);
  }

  // 2. Handle Browser Back / Forward Navigation (popstate)
  const handlePopState = () => {
    const { stage: popStage } = readUrlParams();
    if (popStage && popStage !== store.viewStage) {
      store.setViewStage(popStage);
    }
  };

  window.addEventListener('popstate', handlePopState);

  return () => {
    window.removeEventListener('popstate', handlePopState);
  };
}
