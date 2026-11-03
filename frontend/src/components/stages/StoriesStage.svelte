<script lang="ts">
  import { workflowStore } from '../../lib/stores.svelte';
  import StreamingBanner from './StreamingBanner.svelte';

  let searchQuery = $state('');
  let feedbackText = $state('');
  let generatingStoryId = $state<string | null>(null);
  let expandedStoryTests = $state<Record<string, boolean>>({});
  let storyPrompts = $state<Record<string, string>>({});
  let allExpanded = $state(false);

  const filteredStories = $derived(
    workflowStore.state.stories.filter(
      (s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.epic_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.user_role.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.capability.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  function getStoryTestCases(storyId: string) {
    if (!storyId) return [];
    const cleanId = storyId.trim().toUpperCase();
    const cleanIdNorm = cleanId.replace(/[^A-Z0-9]/g, '');
    const cleanIdDigits = cleanId.replace(/\D/g, '');
    return (workflowStore.state.test_cases || []).filter((tc) => {
      if (!tc.story_id) return false;
      const tcStory = tc.story_id.trim().toUpperCase();
      const tcNorm = tcStory.replace(/[^A-Z0-9]/g, '');
      const tcDigits = tcStory.replace(/\D/g, '');
      return (
        tcStory === cleanId ||
        tcNorm === cleanIdNorm ||
        (cleanIdDigits.length > 0 &&
          tcDigits.length > 0 &&
          parseInt(cleanIdDigits, 10) === parseInt(tcDigits, 10))
      );
    });
  }

  function toggleExpandStory(storyId: string) {
    expandedStoryTests = { ...expandedStoryTests, [storyId]: !expandedStoryTests[storyId] };
  }

  function toggleExpandAll() {
    allExpanded = !allExpanded;
    const next: Record<string, boolean> = {};
    for (const st of workflowStore.state.stories) {
      next[st.id] = allExpanded;
    }
    expandedStoryTests = next;
  }

  async function handleGenerateTestsForStory(storyId: string) {
    generatingStoryId = storyId;
    const customPrompt = (storyPrompts[storyId] || '').trim();
    try {
      await workflowStore.triggerAction('generate_test_cases', {
        targetId: storyId,
        feedback: customPrompt || undefined,
      });
      expandedStoryTests = { ...expandedStoryTests, [storyId]: true };
      workflowStore.showToast(
        customPrompt
          ? `Regenerated test cases for ${storyId} with custom prompt`
          : `Generated test cases for ${storyId}`
      );
    } catch (e: any) {
      workflowStore.showToast(`Failed to generate test cases for ${storyId}: ${e.message}`, true);
    } finally {
      generatingStoryId = null;
    }
  }

  async function handleRevise() {
    if (!feedbackText.trim()) {
      workflowStore.showToast('Please enter your revision feedback.', true);
      return;
    }
    await workflowStore.triggerAction('refine_stories', { feedback: feedbackText });
    feedbackText = '';
  }

  async function handleApproveAndNext() {
    if (workflowStore.state.test_cases.length > 0) {
      workflowStore.setViewStage('test_cases');
    } else {
      await workflowStore.triggerAction('generate_test_cases');
      workflowStore.setViewStage('test_cases');
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
          Stage 4: User Stories & Acceptance Criteria ({workflowStore.state.stories.length})
        </h2>
      </div>
      <p class="text-xs text-neutral-600 dark:text-neutral-400 mt-1 max-w-3xl">
        INVEST-compliant user stories equipped with Gherkin acceptance criteria (Given / When / Then). Generate test cases per story with custom prompts or approve all.
      </p>
    </div>
  </div>

  <StreamingBanner />

  {#if workflowStore.state.stories.length === 0}
    <div class="bg-white dark:bg-neutral-900 p-12 border-2 border-neutral-300 dark:border-neutral-700 text-center space-y-4">
      <p class="text-sm font-bold text-neutral-700 dark:text-neutral-300">
        No user stories generated yet.
      </p>
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('epics')}
        class="px-4 py-2 bg-black text-white dark:bg-white dark:text-black text-xs font-bold uppercase cursor-pointer"
      >
        Go to Stage 3 (Epics)
      </button>
    </div>
  {:else}
    <!-- Stories Filter & Header Bar -->
    <div class="bg-white dark:bg-neutral-900 p-4 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div class="flex items-center gap-3 flex-wrap">
        <h3 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
          User Stories Matrix ({filteredStories.length} of {workflowStore.state.stories.length})
        </h3>
        {#if workflowStore.state.test_cases.length > 0}
          <span class="px-2 py-0.5 bg-emerald-100 text-emerald-950 border border-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-500 font-mono text-[10px] font-black uppercase">
            ✓ {workflowStore.state.test_cases.length} Total Test Cases Synthesized
          </span>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={toggleExpandAll}
          class="px-2.5 py-1.5 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 text-[10px] font-bold uppercase border border-neutral-300 dark:border-neutral-600 cursor-pointer whitespace-nowrap"
        >
          {allExpanded ? '▲ Collapse All' : '▼ Expand All'}
        </button>
        <input
          type="search"
          placeholder="Search stories by ID, persona, or capability..."
          bind:value={searchQuery}
          class="px-3 py-1.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white placeholder-neutral-500 focus:outline-hidden w-full sm:w-72"
        />
      </div>
    </div>

    <!-- Stories Cards Grid -->
    <div class="space-y-4">
      {#each filteredStories as st}
        {@const storyTestCases = getStoryTestCases(st.id)}
        <div class="bg-white dark:bg-neutral-900 border-2 border-neutral-300 dark:border-neutral-700 p-5 space-y-4 shadow-xs">
          <!-- Story Header & Metadata -->
          <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 border-b border-neutral-200 dark:border-neutral-800">
            <div class="space-y-1.5 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-mono text-[10px] font-bold px-2 py-0.5 bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 border border-neutral-300 dark:border-neutral-700">
                  {st.id} • {st.epic_id}
                </span>
                <span class="px-2 py-0.5 bg-neutral-100 dark:bg-neutral-800 font-mono text-[10px] font-black border border-neutral-400">
                  {st.story_points} PTS
                </span>
                <span class="px-2 py-0.5 font-mono text-[10px] font-bold border border-neutral-400 {st.priority === 'MUST_HAVE' ? 'bg-red-100 dark:bg-red-950 text-red-950 dark:text-red-200' : 'bg-neutral-100 dark:bg-neutral-800'}">
                  {st.priority}
                </span>
              </div>
              <h4 class="text-sm font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
                {st.title}
              </h4>
            </div>

            <!-- Story Test Controls -->
            <div class="flex flex-col sm:items-end gap-1.5 shrink-0">
              <div class="flex items-center gap-1.5">
                <button
                  type="button"
                  onclick={() => toggleExpandStory(st.id)}
                  class="text-[10px] font-bold text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white underline cursor-pointer"
                >
                  {expandedStoryTests[st.id]
                    ? (storyTestCases.length > 0 ? 'Hide Tests ▲' : 'Hide Prompt ▲')
                    : (storyTestCases.length > 0 ? 'View Tests ▼' : '+ Custom Prompt')}
                </button>
                {#if storyTestCases.length > 0}
                  <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-950 border border-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-500 font-mono text-[10px] font-black uppercase">
                    ✓ {storyTestCases.length} {storyTestCases.length === 1 ? 'Test' : 'Tests'}
                  </span>
                {/if}
              </div>
              <button
                type="button"
                disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
                onclick={() => handleGenerateTestsForStory(st.id)}
                class="px-3 py-1.5 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-[11px] font-black uppercase tracking-wider border border-neutral-700 dark:border-neutral-300 transition-colors cursor-pointer disabled:opacity-40 whitespace-nowrap shadow-2xs"
                title="Generate test cases specifically for {st.id}"
              >
                {generatingStoryId === st.id
                  ? '⏳ Generating...'
                  : storyTestCases.length > 0
                  ? '🔄 Regenerate Test Cases'
                  : '⚡ Generate Test Cases'}
              </button>
            </div>
          </div>

          <!-- User Persona Narrative -->
          <p class="text-xs text-neutral-800 dark:text-neutral-200 font-medium leading-relaxed p-3 bg-neutral-50 dark:bg-neutral-950 border-l-2 border-[#86BC25]">
            <span class="font-bold">As a</span> {st.user_role},
            <span class="font-bold">I want to</span> {st.capability},
            <span class="font-bold">so that</span> {st.benefit}.
          </p>

          <!-- Gherkin Acceptance Criteria -->
          <div class="p-3 bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 space-y-1.5">
            <span class="text-[10px] font-mono font-bold text-neutral-500 uppercase block">Gherkin Acceptance Criteria:</span>
            <ul class="text-[11px] font-mono text-neutral-700 dark:text-neutral-300 space-y-1 list-disc list-inside">
              {#each st.acceptance_criteria_gherkin as crit}
                <li>{crit}</li>
              {/each}
            </ul>
          </div>

          <!-- Expandable Section for Custom Prompt and Test Cases -->
          {#if expandedStoryTests[st.id]}
            <div class="pt-3 border-t-2 border-neutral-200 dark:border-neutral-800 space-y-3">
              <!-- Input area above 'Test Cases Generated for' pane -->
              <div class="border-2 border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-950 p-3.5 space-y-2 shadow-2xs">
                <div class="flex items-center justify-between">
                  <label
                    for={`story-prompt-${st.id}`}
                    class="text-[11px] font-black uppercase tracking-wider text-neutral-900 dark:text-neutral-100 font-display flex items-center gap-1.5"
                  >
                    <span class="w-2 h-2 bg-[#86BC25] inline-block"></span>
                    Custom Prompt for {st.id} Test Cases:
                  </label>
                  {#if storyPrompts[st.id]}
                    <button
                      type="button"
                      onclick={() => { storyPrompts[st.id] = ''; }}
                      class="text-[10px] text-neutral-500 hover:text-black dark:hover:text-white font-mono underline cursor-pointer"
                    >
                      Clear Prompt
                    </button>
                  {/if}
                </div>

                <div class="flex flex-col sm:flex-row gap-2">
                  <input
                    id={`story-prompt-${st.id}`}
                    type="text"
                    bind:value={storyPrompts[st.id]}
                    placeholder="Enter custom prompt / test focus for {st.id} (e.g. 'Focus on edge cases, negative scenarios, boundary limits, and security validation')..."
                    class="flex-1 px-3 py-2 bg-white dark:bg-neutral-900 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white placeholder:text-neutral-400 focus:outline-hidden focus:border-black dark:focus:border-[#86BC25]"
                    onkeydown={(e) => {
                      if (e.key === 'Enter') handleGenerateTestsForStory(st.id);
                    }}
                  />
                  <button
                    type="button"
                    disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
                    onclick={() => handleGenerateTestsForStory(st.id)}
                    class="px-4 py-2 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-200 transition-colors cursor-pointer shrink-0 disabled:opacity-40 flex items-center gap-1.5 shadow-2xs"
                  >
                    {generatingStoryId === st.id
                      ? '⏳ Generating...'
                      : storyTestCases.length > 0
                      ? '🔄 Regenerate Test Cases'
                      : '⚡ Generate Test Cases'}
                  </button>
                </div>
              </div>

              <!-- 'Test Cases Generated for' pane -->
              {#if storyTestCases.length > 0}
                <div class="border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4 space-y-3">
                  <div class="flex items-center justify-between pb-2 border-b border-neutral-200 dark:border-neutral-800">
                    <span class="text-[11px] font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
                      Test Cases Generated for {st.id} ({storyTestCases.length})
                    </span>
                    <span class="text-[10px] text-neutral-500 font-mono">JIRA / Xray Compliant</span>
                  </div>
                  <div class="space-y-3">
                    {#each storyTestCases as tc}
                      <div class="p-3 bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2">
                        <div class="flex flex-wrap items-center justify-between gap-1.5">
                          <div class="flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold text-[#4c750b] dark:text-[#86BC25]">{tc.id}</span>
                            <span class="px-1.5 py-0.5 text-[9px] font-mono font-black border border-neutral-400 {tc.test_type === 'NEGATIVE' ? 'bg-amber-100 text-amber-950 dark:bg-amber-950/60 dark:text-amber-200' : tc.test_type === 'BOUNDARY' ? 'bg-purple-100 text-purple-950 dark:bg-purple-950/60 dark:text-purple-200' : tc.test_type === 'SECURITY' ? 'bg-red-100 text-red-950 dark:bg-red-950/60 dark:text-red-200' : 'bg-emerald-100 text-emerald-950 dark:bg-emerald-950/60 dark:text-emerald-200'}">
                              {tc.test_type}
                            </span>
                            <span class="text-[9px] font-mono px-1.5 py-0.5 border border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800 font-bold text-neutral-700 dark:text-neutral-300">
                              {tc.priority}
                            </span>
                          </div>
                          <span class="text-[10px] font-mono text-neutral-500">{tc.epic_id}</span>
                        </div>
                        <h5 class="text-xs font-bold text-neutral-950 dark:text-white">{tc.title}</h5>
                        {#if tc.preconditions && tc.preconditions.length > 0}
                          <div class="text-[11px] text-neutral-600 dark:text-neutral-400 font-mono">
                            <span class="font-bold uppercase text-[9px] text-neutral-500">Preconditions:</span>
                            <span class="ml-1">{tc.preconditions.join('; ')}</span>
                          </div>
                        {/if}
                        {#if tc.steps && tc.steps.length > 0}
                          <div class="space-y-1 pt-1">
                            <span class="font-bold uppercase text-[9px] text-neutral-500 font-mono">Steps:</span>
                            <ol class="space-y-1 text-[11px] font-mono">
                              {#each tc.steps as step}
                                <li class="pl-2 border-l-2 border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300">
                                  {#if typeof step === 'string'}
                                    <span class="font-bold text-neutral-900 dark:text-neutral-100">{step}</span>
                                  {:else}
                                    <span class="font-bold text-neutral-900 dark:text-neutral-100">Step {step.step_number || ''}:</span> {step.action || ''}
                                    {#if step.expected_result}
                                      <div class="text-[10px] text-neutral-500 pl-2">➔ Expected: {step.expected_result}</div>
                                    {/if}
                                  {/if}
                                </li>
                              {/each}
                            </ol>
                          </div>
                        {/if}
                        {#if tc.test_data}
                          <div class="text-[11px] font-mono text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-900 p-2 border border-neutral-200 dark:border-neutral-800">
                            <span class="font-bold uppercase text-[9px] text-neutral-500 block mb-0.5">Test Data:</span>
                            <pre class="text-[10px] whitespace-pre-wrap font-mono overflow-x-auto">{tc.test_data}</pre>
                          </div>
                        {/if}
                        {#if tc.postconditions}
                          <div class="text-[11px] font-mono text-neutral-600 dark:text-neutral-400">
                            <span class="font-bold uppercase text-[9px] text-neutral-500">Postconditions:</span>
                            <span class="ml-1">{tc.postconditions}</span>
                          </div>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Specific Revision & Feedback Card for Stage 4 -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-4">
      <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
        <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25]"></span>
          Refine User Stories
        </h4>
        <span class="text-[11px] text-neutral-500 font-medium">Prompt-assisted revision</span>
      </div>

      <div class="flex flex-col md:flex-row gap-3">
        <textarea
          rows="2"
          bind:value={feedbackText}
          placeholder="Enter revision instructions for user stories (e.g. 'Add edge case scenario for card decline', 'Split story US-02 into separate tasks')..."
          class="flex-1 p-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white focus:border-black dark:focus:border-[#86BC25]"
        ></textarea>
        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleRevise}
          class="px-5 py-3 bg-neutral-900 hover:bg-black text-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-white transition-colors cursor-pointer shrink-0 disabled:opacity-40"
        >
          🔄 Revise Stories
        </button>
      </div>
    </div>

    <!-- Bottom Stage Navigation -->
    <div class="flex flex-wrap items-center justify-between gap-3 pt-2">
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('epics')}
        class="px-5 py-2.5 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-400 dark:border-neutral-600 cursor-pointer transition-colors"
      >
        ← Back to Epics
      </button>

      <div class="flex items-center gap-3">
        {#if workflowStore.state.test_cases.length > 0}
          <button
            type="button"
            disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
            onclick={async () => {
              await workflowStore.triggerAction('generate_test_cases');
              workflowStore.setViewStage('test_cases');
            }}
            class="px-5 py-2.5 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-200 transition-colors cursor-pointer disabled:opacity-40"
          >
            ⚡ Regenerate All Test Cases
          </button>
        {/if}

        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleApproveAndNext}
          class="px-6 py-3 bg-[#86BC25] hover:bg-[#72a11f] text-black text-xs font-black uppercase tracking-wider border-2 border-black cursor-pointer shadow-md transition-colors flex items-center gap-2 disabled:opacity-40"
        >
          <span>{workflowStore.state.test_cases.length > 0 ? 'View Stage 5 (Test Cases)' : 'Approve & Generate All Test Cases'}</span>
          <span>→</span>
        </button>
      </div>
    </div>
  {/if}
</div>
