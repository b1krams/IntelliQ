/**
 * Reactive Application Store using Svelte 5 Runes ($state, $derived, $state.raw).
 * Avoids deep JavaScript proxy overhead on large artifact payloads.
 */
import { api } from './api';
import type { Attachment, Stage, WorkflowRequest, WorkflowState } from './types';

/**
 * Generate a 5-character uppercase alphanumeric Session ID.
 * Excludes easily confusable characters (0/O, 1/I).
 */
export function generateSessionId(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let result = '';
  for (let i = 0; i < 5; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export function createInitialWorkflowState(customId?: string): WorkflowState {
  const id = (customId || generateSessionId()).trim().toUpperCase();
  return {
    workflow_id: id,
    current_stage: 'intake',
    status: 'idle',
    title: `Session ${id}`,
    user_prompt: '',
    attachments: [],
    epics: [],
    stories: [],
    test_cases: [],
    ai_insights: {
      confidence_score: 1.0,
      rationale_bullets: [
        'Ready to analyze business requirements and specifications from your input notes or uploaded documents',
        'Transforms raw notes or documents into audit-ready Requirements, Epics, User Stories, and Executable Test Cases',
      ],
      ambiguities_flagged: [],
      suggested_actions: ['Enter your project scope or upload specification documents to get started'],
    },
    history: [
      {
        timestamp: new Date().toISOString(),
        actor: 'USER',
        action: 'PROJECT_INITIALIZED',
        details: `Session ${id} initialized for requirements intake.`,
      },
    ],
  };
}

export const INITIAL_WORKFLOW_STATE: WorkflowState = createInitialWorkflowState();

class WorkflowStore {
  state = $state.raw<WorkflowState>(INITIAL_WORKFLOW_STATE);
  viewStage = $state<'intake' | 'brd' | 'epics' | 'stories' | 'test_cases'>('intake');
  streamingRawText = $state<string>('');
  isStreaming = $state<boolean>(false);
  stagedAttachments = $state<Attachment[]>([]);
  activeTab = $state<'brd' | 'epics' | 'stories' | 'test_cases'>('brd');
  rateLimitCountdown = $state<number>(0);
  theme = $state<'dark' | 'light'>(
    typeof window !== 'undefined' && document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  );
  toast = $state<{ message: string; isAlert: boolean; visible: boolean }>({
    message: '',
    isAlert: false,
    visible: false,
  });

  private toastTimeout: any = null;

  setState(newState: WorkflowState, targetId?: string) {
    if (targetId) {
      const cleanTarget = targetId.trim().toUpperCase();
      const cleanTargetNorm = cleanTarget.replace(/[^A-Z0-9]/g, '');
      const cleanTargetDigits = cleanTarget.replace(/\D/g, '');

      const isStoryTarget =
        cleanTarget.startsWith('US') ||
        cleanTarget.startsWith('STORY') ||
        (this.state.stories || []).some((s) => {
          if (!s.id) return false;
          const sid = s.id.trim().toUpperCase();
          const sNorm = sid.replace(/[^A-Z0-9]/g, '');
          const sDigits = sid.replace(/\D/g, '');
          return (
            sid === cleanTarget ||
            sNorm === cleanTargetNorm ||
            (cleanTargetDigits.length > 0 &&
              sDigits.length > 0 &&
              parseInt(cleanTargetDigits, 10) === parseInt(sDigits, 10))
          );
        });

      if (isStoryTarget) {
        const matchesTargetStory = (storyId: string | undefined): boolean => {
          if (!storyId) return false;
          const tcUpper = storyId.trim().toUpperCase();
          const tcNorm = tcUpper.replace(/[^A-Z0-9]/g, '');
          const tcDigits = tcUpper.replace(/\D/g, '');
          return (
            tcUpper === cleanTarget ||
            tcNorm === cleanTargetNorm ||
            (cleanTargetDigits.length > 0 &&
              tcDigits.length > 0 &&
              parseInt(cleanTargetDigits, 10) === parseInt(tcDigits, 10))
          );
        };

        // Test cases from current client state belonging to other stories
        const existingOtherTestCases = (this.state.test_cases || []).filter(
          (tc) => !matchesTargetStory(tc.story_id)
        );

        // Test cases from incoming state belonging to the target story
        let incomingTargetTestCases = (newState.test_cases || [])
          .filter((tc) => matchesTargetStory(tc.story_id))
          .map((tc) => ({ ...tc, story_id: targetId }));

        // Fallback: if incoming has test cases but none matched strictly, assign them to targetId
        if (incomingTargetTestCases.length === 0 && (newState.test_cases || []).length > 0) {
          incomingTargetTestCases = (newState.test_cases || []).map((tc) => ({
            ...tc,
            story_id: tc.story_id || targetId,
          }));
        }

        if (incomingTargetTestCases.length > 0) {
          const merged = [...existingOtherTestCases, ...incomingTargetTestCases];
          const seen = new Set<string>();
          const uniqueTestCases = merged.filter((tc) => {
            if (!tc.id || seen.has(tc.id)) return false;
            seen.add(tc.id);
            return true;
          });
          newState = {
            ...newState,
            test_cases: uniqueTestCases,
            stories: this.state.stories || newState.stories || [],
            current_stage: this.viewStage === 'stories' ? 'stories' : newState.current_stage,
          };
        } else {
          // If incoming state does not yet contain test cases for target story, keep existing
          newState = {
            ...newState,
            test_cases: this.state.test_cases || [],
            stories: this.state.stories || newState.stories || [],
            current_stage: this.viewStage === 'stories' ? 'stories' : newState.current_stage,
          };
        }
      } else {
        // Target is an Epic (or default)
        const cleanTargetEpic = cleanTarget;
        const cleanTargetNorm = cleanTargetEpic.replace(/[^A-Z0-9]/g, '');
        const cleanTargetDigits = cleanTargetEpic.replace(/\D/g, '');

        const matchesTargetEpic = (epicId: string | undefined): boolean => {
          if (!epicId) return false;
          const sEpic = epicId.trim().toUpperCase();
          const sEpicNorm = sEpic.replace(/[^A-Z0-9]/g, '');
          const sEpicDigits = sEpic.replace(/\D/g, '');
          return (
            sEpic === cleanTargetEpic ||
            sEpicNorm === cleanTargetNorm ||
            (cleanTargetDigits.length > 0 &&
              sEpicDigits.length > 0 &&
              parseInt(cleanTargetDigits, 10) === parseInt(sEpicDigits, 10))
          );
        };

        // Stories from current client state belonging to other epics
        const existingOtherStories = (this.state.stories || []).filter(
          (s) => !matchesTargetEpic(s.epic_id)
        );

        // Stories from incoming state belonging to the target epic
        const incomingTargetStories = (newState.stories || []).filter(
          (s) => matchesTargetEpic(s.epic_id)
        );

        if (incomingTargetStories.length > 0) {
          const merged = [...existingOtherStories, ...incomingTargetStories];
          const seen = new Set<string>();
          const uniqueStories = merged.filter((s) => {
            if (!s.id || seen.has(s.id)) return false;
            seen.add(s.id);
            return true;
          });
          newState = {
            ...newState,
            stories: uniqueStories,
            current_stage: this.viewStage === 'epics' ? 'epics' : newState.current_stage,
          };
        } else {
          // If incoming state does not yet contain stories for the target epic (e.g. initial stream event),
          // keep our current stories completely intact. Never duplicate or discard!
          newState = {
            ...newState,
            stories: this.state.stories || [],
            current_stage: this.viewStage === 'epics' ? 'epics' : newState.current_stage,
          };
        }
      }
    } else if (newState.stories && newState.stories.length > 0) {
      // General deduplication by story ID across all stages
      const seen = new Set<string>();
      newState = {
        ...newState,
        stories: newState.stories.filter((s) => {
          if (!s.id || seen.has(s.id)) return false;
          seen.add(s.id);
          return true;
        }),
      };
    }

    if (newState.test_cases && newState.test_cases.length > 0) {
      const seenTc = new Set<string>();
      newState = {
        ...newState,
        test_cases: newState.test_cases.filter((tc) => {
          if (!tc.id || seenTc.has(tc.id)) return false;
          seenTc.add(tc.id);
          return true;
        }),
      };
    }

    this.state = newState;
    if (newState.attachments && newState.attachments.length > 0) {
      this.stagedAttachments = newState.attachments;
    }
    const stage = newState.current_stage === 'export' ? 'test_cases' : newState.current_stage;
    if (['intake', 'brd', 'epics', 'stories', 'test_cases'].includes(stage)) {
      this.viewStage = stage as any;
    }
    if (newState.current_stage === 'epics') this.activeTab = 'epics';
    else if (newState.current_stage === 'stories') this.activeTab = 'stories';
    else if (newState.current_stage === 'test_cases' || newState.current_stage === 'export') this.activeTab = 'test_cases';
    else if (newState.current_stage === 'brd') this.activeTab = 'brd';
  }

  setViewStage(stage: 'intake' | 'brd' | 'epics' | 'stories' | 'test_cases') {
    this.viewStage = stage;
    if (stage === 'brd' || stage === 'epics' || stage === 'stories' || stage === 'test_cases') {
      this.activeTab = stage;
    }
  }

  setSessionId(newId: string) {
    const formatted = newId.trim().toUpperCase();
    this.state = {
      ...this.state,
      workflow_id: formatted,
      title: this.state.title.startsWith('Session ') ? `Session ${formatted}` : this.state.title,
    };
  }

  async loadSession(sessionId: string): Promise<boolean> {
    const formatted = sessionId.trim().toUpperCase();
    if (!formatted) {
      this.showToast('Please enter a valid 5-character Session ID.', true);
      return false;
    }

    try {
      this.showToast(`Loading session ${formatted}...`);
      const res = await api.getWorkflow(formatted);
      if (res && res.workflow_id) {
        this.setState(res);
        this.showToast(`Resumed Session ${formatted} successfully.`);
        return true;
      }
      this.showToast(`Session ${formatted} not found.`, true);
      return false;
    } catch (err: any) {
      this.showToast(`Failed to load session ${formatted}: ${err.message}`, true);
      return false;
    }
  }

  resetToNewProject(customId?: string) {
    this.state = createInitialWorkflowState(customId);
    this.viewStage = 'intake';
    this.activeTab = 'brd';
    this.stagedAttachments = [];
    this.streamingRawText = '';
    this.isStreaming = false;
    this.showToast(`Started new session ${this.state.workflow_id}.`);
  }

  showToast(message: string, isAlert: boolean = false) {
    this.toast = { message, isAlert, visible: true };
    if (this.toastTimeout) clearTimeout(this.toastTimeout);
    this.toastTimeout = setTimeout(() => {
      this.toast.visible = false;
    }, 2800);
  }

  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    if (this.theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('theme', this.theme);
  }

  startRateLimitCountdown(seconds: number) {
    this.rateLimitCountdown = seconds;
    const interval = setInterval(() => {
      if (this.rateLimitCountdown <= 1) {
        this.rateLimitCountdown = 0;
        clearInterval(interval);
      } else {
        this.rateLimitCountdown -= 1;
      }
    }, 1000);
  }

  async triggerAction(
    actionName: WorkflowRequest['action'],
    params?: { userPrompt?: string; feedback?: string; targetId?: string }
  ) {
    if (this.rateLimitCountdown > 0) {
      this.showToast(`Please wait ${this.rateLimitCountdown}s before next request.`, true);
      return;
    }

    this.isStreaming = true;
    this.streamingRawText = '';

    const req: WorkflowRequest = {
      workflow_id: this.state.workflow_id,
      action: actionName,
      stage: this.state.current_stage,
      user_prompt: params?.userPrompt !== undefined ? params.userPrompt : (this.state.user_prompt || this.state.title),
      feedback: params?.feedback || '',
      target_id: params?.targetId,
      attachments: this.stagedAttachments,
      model_preference: 'auto',
    };

    await api.streamWorkflow(req, {
      onToken: (delta) => {
        this.streamingRawText += delta;
      },
      onState: (updatedState) => {
        this.setState(updatedState, params?.targetId);
      },
      onRateLimit: (seconds) => {
        this.startRateLimitCountdown(seconds);
        this.showToast(`System busy. Cooldown: ${seconds} seconds.`, true);
      },
      onError: (err) => {
        this.showToast(`Generation error: ${err.message}`, true);
        this.isStreaming = false;
      },
      onComplete: () => {
        this.isStreaming = false;
        if (this.state.status === 'error') {
          return;
        }
        const readable = actionName
          .replace('generate_', '')
          .replace('refine_', '')
          .replace('_', ' ')
          .toUpperCase();
        this.showToast(`Generated ${readable} successfully.`);
      },
    });
  }

  cancelStreaming() {
    api.cancelActiveStream();
    this.isStreaming = false;
    this.showToast('Generation cancelled.');
  }
}

export const workflowStore = new WorkflowStore();
