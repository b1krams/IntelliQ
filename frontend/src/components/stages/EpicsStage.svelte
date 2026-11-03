<script lang="ts">
  import { workflowStore } from '../../lib/stores.svelte';
  import StreamingBanner from './StreamingBanner.svelte';

  let searchQuery = $state('');
  let feedbackText = $state('');
  let generatingEpicId = $state<string | null>(null);
  let expandedEpicStories = $state<Record<string, boolean>>({});
  let epicPrompts = $state<Record<string, string>>({});

  const filteredEpics = $derived(
    (workflowStore.state.epics || []).filter(
      (e) =>
        (e.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (e.id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (e.summary || '').toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  function getEpicStories(epicId: string) {
    if (!epicId) return [];
    const cleanId = epicId.trim().toUpperCase();
    const cleanIdNorm = cleanId.replace(/[^A-Z0-9]/g, '');
    const cleanIdDigits = cleanId.replace(/\D/g, '');
    return (workflowStore.state.stories || []).filter((s) => {
      if (!s.epic_id) return false;
      const sEpic = s.epic_id.trim().toUpperCase();
      const sEpicNorm = sEpic.replace(/[^A-Z0-9]/g, '');
      const sEpicDigits = sEpic.replace(/\D/g, '');
      return (
        sEpic === cleanId ||
        sEpicNorm === cleanIdNorm ||
        (cleanIdDigits.length > 0 &&
          sEpicDigits.length > 0 &&
          parseInt(cleanIdDigits, 10) === parseInt(sEpicDigits, 10))
      );
    });
  }

  function toggleExpandEpic(epicId: string) {
    expandedEpicStories = { ...expandedEpicStories, [epicId]: !expandedEpicStories[epicId] };
  }

  async function handleGenerateStoriesForEpic(epicId: string) {
    generatingEpicId = epicId;
    const customPrompt = (epicPrompts[epicId] || '').trim();
    try {
      await workflowStore.triggerAction('generate_stories', {
        targetId: epicId,
        feedback: customPrompt || undefined,
      });
      expandedEpicStories = { ...expandedEpicStories, [epicId]: true };
    } catch (e: any) {
      workflowStore.showToast(`Failed to generate stories for ${epicId}: ${e.message}`, true);
    } finally {
      generatingEpicId = null;
    }
  }

  async function handleRevise() {
    if (!feedbackText.trim()) {
      workflowStore.showToast('Please enter your revision feedback.', true);
      return;
    }
    await workflowStore.triggerAction('refine_epics', { feedback: feedbackText });
    feedbackText = '';
  }

  async function handleApproveAndNext() {
    if (workflowStore.state.stories.length > 0) {
      workflowStore.setViewStage('stories');
    } else {
      await workflowStore.triggerAction('generate_stories');
      workflowStore.setViewStage('stories');
    }
  }
</script>

<div class="space-y-6">
  <!-- Stage Banner -->
  <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs">
    <div>
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 bg-[#86BC25]"></span>
        <h2 class="text-base font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white">
          Stage 3: Architectural & Functional Epics ({workflowStore.state.epics.length})
        </h2>
      </div>
      <p class="text-xs text-neutral-600 dark:text-neutral-400 mt-1 max-w-3xl">
        High-level business capabilities decomposed from your approved requirements. Refine their boundaries or proceed to user stories.
      </p>
    </div>
  </div>

  <StreamingBanner />

  {#if workflowStore.state.epics.length === 0}
    <div class="bg-white dark:bg-neutral-900 p-12 border-2 border-neutral-300 dark:border-neutral-700 text-center space-y-4">
      <p class="text-sm font-bold text-neutral-700 dark:text-neutral-300">
        No epics generated yet.
      </p>
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('brd')}
        class="px-4 py-2 bg-black text-white dark:bg-white dark:text-black text-xs font-bold uppercase cursor-pointer"
      >
        Go to Stage 2 (Requirements)
      </button>
    </div>
  {:else}
    <!-- Epics Controls & Table -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b-2 border-neutral-200 dark:border-neutral-800">
        <h3 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
          Deliverable Epics Matrix
        </h3>
        <input
          type="search"
          placeholder="Search epics..."
          bind:value={searchQuery}
          class="px-3 py-1.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white placeholder-neutral-500 focus:outline-hidden w-full sm:w-64"
        />
      </div>

      <div class="border-2 border-neutral-300 dark:border-neutral-700 overflow-x-auto">
        <table class="w-full text-left text-xs font-sans">
          <thead class="bg-neutral-200 dark:bg-neutral-950 border-b-2 border-neutral-300 dark:border-neutral-700 text-neutral-900 dark:text-neutral-200 font-display uppercase tracking-wider text-[11px]">
            <tr>
              <th class="py-3 px-4 font-extrabold w-28">Epic Key</th>
              <th class="py-3 px-4 font-extrabold w-56">Epic Title</th>
              <th class="py-3 px-4 font-extrabold">Business Value / Narrative</th>
              <th class="py-3 px-4 font-extrabold">Acceptance Criteria</th>
              <th class="py-3 px-4 font-extrabold w-52 text-right">User Stories</th>
            </tr>
          </thead>
          <tbody class="divide-y-2 divide-neutral-200 dark:divide-neutral-800">
            {#each filteredEpics as ep}
              {@const epicStories = getEpicStories(ep.id)}
              <tr class="hover:bg-neutral-100 dark:hover:bg-neutral-800/60 transition-colors">
                <td class="py-4 px-4 font-mono text-[11px] font-bold text-neutral-900 dark:text-neutral-100 align-top">{ep.id}</td>
                <td class="py-4 px-4 font-extrabold font-display text-neutral-950 dark:text-white align-top">{ep.title}</td>
                <td class="py-4 px-4 text-neutral-800 dark:text-neutral-200 font-medium leading-relaxed align-top">{ep.business_value || ep.summary}</td>
                <td class="py-4 px-4 text-[11px] font-mono text-neutral-700 dark:text-neutral-300 align-top">
                  <ul class="list-disc list-inside space-y-1">
                    {#each ep.acceptance_criteria || [] as ac}
                      <li>{ac}</li>
                    {/each}
                  </ul>
                </td>
                <td class="py-4 px-4 text-right align-top">
                  <div class="flex flex-col items-end gap-1.5">
                    <div class="flex items-center gap-1.5">
                      <button
                        type="button"
                        onclick={() => toggleExpandEpic(ep.id)}
                        class="text-[10px] font-bold text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white underline cursor-pointer"
                      >
                        {expandedEpicStories[ep.id]
                          ? (epicStories.length > 0 ? 'Hide Stories ▲' : 'Hide Prompt ▲')
                          : (epicStories.length > 0 ? 'View Stories ▼' : '+ Custom Prompt')}
                      </button>
                      {#if epicStories.length > 0}
                        <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-950 border border-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-500 font-mono text-[10px] font-black uppercase">
                          ✓ {epicStories.length} {epicStories.length === 1 ? 'Story' : 'Stories'}
                        </span>
                      {/if}
                    </div>
                    <button
                      type="button"
                      disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
                      onclick={() => handleGenerateStoriesForEpic(ep.id)}
                      class="px-3 py-1.5 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-[11px] font-black uppercase tracking-wider border border-neutral-700 dark:border-neutral-300 transition-colors cursor-pointer disabled:opacity-40 whitespace-nowrap shadow-2xs"
                      title="Generate user stories specifically for {ep.id}"
                    >
                      {generatingEpicId === ep.id
                        ? '⏳ Generating...'
                        : epicStories.length > 0
                        ? '🔄 Regenerate Stories'
                        : '⚡ Generate User Stories'}
                    </button>
                  </div>
                </td>
              </tr>
              {#if expandedEpicStories[ep.id]}
                <tr class="bg-neutral-50 dark:bg-neutral-950 border-t border-neutral-200 dark:border-neutral-800">
                  <td colspan="5" class="p-4 space-y-3">
                    <!-- Input area above 'Stories Generated for' pane -->
                    <div class="border-2 border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-950 p-3.5 space-y-2 shadow-2xs">
                      <div class="flex items-center justify-between">
                        <label
                          for={`epic-prompt-${ep.id}`}
                          class="text-[11px] font-black uppercase tracking-wider text-neutral-900 dark:text-neutral-100 font-display flex items-center gap-1.5"
                        >
                          <span class="w-2 h-2 bg-[#86BC25] inline-block"></span>
                          Custom Prompt for {ep.id} Stories:
                        </label>
                        {#if epicPrompts[ep.id]}
                          <button
                            type="button"
                            onclick={() => { epicPrompts[ep.id] = ''; }}
                            class="text-[10px] text-neutral-500 hover:text-black dark:hover:text-white font-mono underline cursor-pointer"
                          >
                            Clear Prompt
                          </button>
                        {/if}
                      </div>

                      <div class="flex flex-col sm:flex-row gap-2">
                        <input
                          id={`epic-prompt-${ep.id}`}
                          type="text"
                          bind:value={epicPrompts[ep.id]}
                          placeholder="Enter custom prompt / instructions for {ep.id} stories (e.g. 'Focus on edge cases, retry logic, and strict security validation')..."
                          class="flex-1 px-3 py-2 bg-white dark:bg-neutral-900 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white placeholder:text-neutral-400 focus:outline-hidden focus:border-black dark:focus:border-[#86BC25]"
                          onkeydown={(e) => {
                            if (e.key === 'Enter') handleGenerateStoriesForEpic(ep.id);
                          }}
                        />
                        <button
                          type="button"
                          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
                          onclick={() => handleGenerateStoriesForEpic(ep.id)}
                          class="px-4 py-2 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-200 transition-colors cursor-pointer shrink-0 disabled:opacity-40 flex items-center gap-1.5 shadow-2xs"
                        >
                          {generatingEpicId === ep.id
                            ? '⏳ Generating...'
                            : epicStories.length > 0
                            ? '🔄 Regenerate Stories'
                            : '⚡ Generate User Stories'}
                        </button>
                      </div>
                    </div>

                    <!-- 'Stories Generated for' pane -->
                    {#if epicStories.length > 0}
                      <div class="border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4 space-y-3">
                        <div class="flex items-center justify-between pb-2 border-b border-neutral-200 dark:border-neutral-800">
                          <span class="text-[11px] font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
                            Stories Generated for {ep.id} ({epicStories.length})
                          </span>
                          <span class="text-[10px] text-neutral-500 font-mono">INVEST-Compliant</span>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {#each epicStories as st}
                            <div class="p-3 bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-1.5">
                              <div class="flex items-center justify-between">
                                <span class="font-mono text-[10px] font-bold text-[#4c750b] dark:text-[#86BC25]">{st.id}</span>
                                <span class="text-[9px] font-mono px-1.5 py-0.5 border border-neutral-400 bg-neutral-100 dark:bg-neutral-800 font-bold">{st.priority}</span>
                              </div>
                              <h5 class="text-xs font-bold text-neutral-950 dark:text-white">{st.title}</h5>
                              <p class="text-[11px] text-neutral-700 dark:text-neutral-300 leading-normal">
                                As a <strong class="text-neutral-900 dark:text-neutral-100">{st.user_role}</strong>, I want to {st.capability}, so that {st.benefit}.
                              </p>
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Specific Revision & Feedback Card for Stage 3 -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-4">
      <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
        <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25]"></span>
          Refine Epics
        </h4>
        <span class="text-[11px] text-neutral-500 font-medium">Prompt-assisted revision</span>
      </div>

      <div class="flex flex-col md:flex-row gap-3">
        <textarea
          rows="2"
          bind:value={feedbackText}
          placeholder="Enter revision instructions for epics (e.g. 'Split checkout into cart and payment gateway', 'Add separate audit & logging epic')..."
          class="flex-1 p-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white focus:border-black dark:focus:border-[#86BC25]"
        ></textarea>
        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleRevise}
          class="px-5 py-3 bg-neutral-900 hover:bg-black text-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-white transition-colors cursor-pointer shrink-0 disabled:opacity-40"
        >
          🔄 Revise Epics
        </button>
      </div>
    </div>

    <!-- Bottom Stage Navigation -->
    <div class="flex flex-wrap items-center justify-between gap-3 pt-2">
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('brd')}
        class="px-5 py-2.5 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-400 dark:border-neutral-600 cursor-pointer transition-colors"
      >
        ← Back to BRD
      </button>

      <div class="flex items-center gap-3">
        {#if workflowStore.state.stories.length > 0}
          <button
            type="button"
            disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
            onclick={async () => {
              await workflowStore.triggerAction('generate_stories');
              workflowStore.setViewStage('stories');
            }}
            class="px-5 py-2.5 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-200 transition-colors cursor-pointer disabled:opacity-40"
          >
            ⚡ Regenerate All Stories
          </button>
        {/if}

        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleApproveAndNext}
          class="px-6 py-3 bg-[#86BC25] hover:bg-[#72a11f] text-black text-xs font-black uppercase tracking-wider border-2 border-black cursor-pointer shadow-md transition-colors flex items-center gap-2 disabled:opacity-40"
        >
          <span>{workflowStore.state.stories.length > 0 ? `View Stage 4 (Stories: ${workflowStore.state.stories.length})` : 'Approve & Generate All Stories'}</span>
          <span>→</span>
        </button>
      </div>
    </div>
  {/if}
</div>

