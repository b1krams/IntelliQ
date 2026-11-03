<script lang="ts">
  import { api } from '../lib/api';
  import { workflowStore } from '../lib/stores.svelte';
  import type { Stage, WorkflowRequest } from '../lib/types';

  let userPrompt = $state('');
  let feedbackText = $state('');

  async function triggerAction(actionName: WorkflowRequest['action'], customPrompt?: string) {
    if (workflowStore.rateLimitCountdown > 0) {
      workflowStore.showToast(`Please wait ${workflowStore.rateLimitCountdown}s before next request.`, true);
      return;
    }

    workflowStore.isStreaming = true;
    workflowStore.streamingRawText = '';

    const req: WorkflowRequest = {
      workflow_id: workflowStore.state.workflow_id,
      action: actionName,
      stage: workflowStore.state.current_stage,
      user_prompt: customPrompt || userPrompt,
      feedback: feedbackText,
      attachments: workflowStore.stagedAttachments,
      model_preference: 'auto',
    };

    await api.streamWorkflow(req, {
      onToken: (delta) => {
        workflowStore.streamingRawText += delta;
      },
      onState: (updatedState) => {
        workflowStore.setState(updatedState);
      },
      onRateLimit: (seconds) => {
        workflowStore.startRateLimitCountdown(seconds);
        workflowStore.showToast(`System busy. Cooldown: ${seconds} seconds.`, true);
      },
      onError: (err) => {
        workflowStore.showToast(`Generation error: ${err.message}`, true);
        workflowStore.isStreaming = false;
      },
      onComplete: () => {
        workflowStore.isStreaming = false;
        feedbackText = '';
        const readable = actionName.replace('generate_', '').replace('refine_', '').replace('_', ' ').toUpperCase();
        workflowStore.showToast(`Generated ${readable} successfully.`);
      },
    });
  }

  function handleCancel() {
    api.cancelActiveStream();
    workflowStore.isStreaming = false;
    workflowStore.showToast('Generation cancelled.');
  }
</script>

<div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 space-y-5 shadow-xs">
  <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
    <h4 class="text-xs font-extrabold font-display uppercase tracking-wider text-neutral-950 dark:text-white flex items-center gap-2">
      <span class="w-2.5 h-2.5 bg-[#86BC25] inline-block"></span>
      Generate Requirements & Tests
    </h4>
  </div>

  <!-- Primary Project Context -->
  <div class="flex flex-col gap-1.5 w-full">
    <label for="project-context" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
      Project Scope & Requirements Context
    </label>
    <textarea
      id="project-context"
      rows="3"
      bind:value={userPrompt}
      placeholder="Describe your project, user needs, or paste discovery notes..."
      class="w-full p-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white focus:border-black dark:focus:border-[#86BC25]"
    ></textarea>
  </div>

  <!-- Primary Generation Buttons -->
  <div class="space-y-2">
    <span class="text-xs font-bold text-neutral-600 dark:text-neutral-400 uppercase block">
      Generation Steps
    </span>

    <div class="grid grid-cols-2 gap-2.5">
      <!-- 1. Generate BRD -->
      <button
        type="button"
        disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
        onclick={() => triggerAction('generate_brd')}
        class="py-3 px-3 bg-black text-white hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer border-2 border-black dark:border-white disabled:opacity-40"
      >
        {workflowStore.isStreaming ? 'Generating...' : '1. Generate Requirements'}
      </button>

      <!-- 2. Generate Epics -->
      <button
        type="button"
        disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
        onclick={() => triggerAction('generate_epics')}
        class="py-3 px-3 bg-white text-black hover:bg-neutral-100 border-2 border-neutral-800 dark:bg-neutral-950 dark:text-white dark:border-neutral-300 dark:hover:bg-neutral-800 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer disabled:opacity-40"
      >
        2. Generate Epics
      </button>

      <!-- 3. Generate Stories -->
      <button
        type="button"
        disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
        onclick={() => triggerAction('generate_stories')}
        class="py-3 px-3 bg-white text-black hover:bg-neutral-100 border-2 border-neutral-800 dark:bg-neutral-950 dark:text-white dark:border-neutral-300 dark:hover:bg-neutral-800 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer disabled:opacity-40"
      >
        3. User Stories
      </button>

      <!-- 4. Generate Test Cases -->
      <button
        type="button"
        disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
        onclick={() => triggerAction('generate_test_cases')}
        class="py-3 px-3 bg-[#86BC25] text-black hover:bg-[#72a11f] text-xs font-black uppercase tracking-wider transition-colors cursor-pointer border-2 border-black shadow-xs disabled:opacity-40"
      >
        4. Test Cases
      </button>
    </div>

    <!-- Active Generation Status / Cancel -->
    {#if workflowStore.isStreaming}
      <div class="flex items-center justify-between p-3 bg-neutral-100 dark:bg-neutral-950 border border-neutral-400 dark:border-neutral-700 mt-2">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25] animate-pulse"></span>
          <span class="text-xs font-bold text-neutral-900 dark:text-neutral-100">
            Generating content, please wait...
          </span>
        </div>
        <button
          type="button"
          onclick={handleCancel}
          class="px-2.5 py-1 bg-neutral-800 text-white hover:bg-black text-xs font-bold uppercase cursor-pointer"
        >
          Cancel
        </button>
      </div>
    {/if}

    <!-- Rate Limit Cooldown Notice -->
    {#if workflowStore.rateLimitCountdown > 0}
      <div class="p-3 bg-amber-50 dark:bg-neutral-950 border border-amber-500 text-xs flex items-center justify-between mt-2">
        <span class="text-amber-900 dark:text-amber-300 font-bold">
          ⏳ Please wait before generating again
        </span>
        <span class="font-bold text-amber-800 dark:text-amber-400">
          Cooldown: {workflowStore.rateLimitCountdown}s
        </span>
      </div>
    {/if}
  </div>

  <!-- Interactive Feedback Tuning Box -->
  <div class="flex flex-col gap-1.5 w-full pt-2 border-t border-neutral-200 dark:border-neutral-800">
    <label for="feedback-input" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200">
      Refine & Request Changes
    </label>
    <div class="flex gap-2">
      <input
        id="feedback-input"
        type="text"
        maxlength="500"
        bind:value={feedbackText}
        placeholder="e.g. 'Add a test case for invalid credit cards' or 'Break Story 101 into two stories'..."
        class="flex-1 px-3 py-2 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white focus:border-black dark:focus:border-[#86BC25]"
        onkeydown={(e) => {
          if (e.key === 'Enter' && feedbackText) {
            triggerAction(
              workflowStore.state.current_stage === 'epics'
                ? 'refine_epics'
                : workflowStore.state.current_stage === 'stories'
                ? 'refine_stories'
                : workflowStore.state.current_stage === 'test_cases'
                ? 'refine_test_cases'
                : 'refine_brd'
            );
          }
        }}
      />
      <button
        type="button"
        disabled={!feedbackText || workflowStore.isStreaming}
        onclick={() =>
          triggerAction(
            workflowStore.state.current_stage === 'epics'
              ? 'refine_epics'
              : workflowStore.state.current_stage === 'stories'
              ? 'refine_stories'
              : workflowStore.state.current_stage === 'test_cases'
              ? 'refine_test_cases'
              : 'refine_brd'
          )}
        class="px-4 py-2 bg-black text-white dark:bg-white dark:text-black text-xs font-black uppercase cursor-pointer hover:bg-neutral-800 dark:hover:bg-neutral-200 disabled:opacity-40"
      >
        Update
      </button>
    </div>
  </div>
</div>
