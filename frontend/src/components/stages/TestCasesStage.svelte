<script lang="ts">
  import { api } from '../../lib/api';
  import { workflowStore } from '../../lib/stores.svelte';
  import StreamingBanner from './StreamingBanner.svelte';

  let feedbackText = $state('');
  let isExporting = $state(false);

  const testCases = $derived(workflowStore.state.test_cases || []);

  const positiveCount = $derived(testCases.filter((t) => t.test_type === 'POSITIVE').length);
  const negativeCount = $derived(testCases.filter((t) => t.test_type === 'NEGATIVE').length);
  const boundaryCount = $derived(testCases.filter((t) => t.test_type === 'BOUNDARY').length);
  const securityCount = $derived(testCases.filter((t) => t.test_type === 'SECURITY').length);

  async function handleExport() {
    isExporting = true;
    try {
      const res = await api.exportJiraExcel(workflowStore.state.workflow_id);
      workflowStore.showToast(`Exported JIRA Test Suite: ${res.filename}`);
    } catch (err: any) {
      workflowStore.showToast(`Export failed: ${err.message}`, true);
    } finally {
      isExporting = false;
    }
  }

  async function handleRevise() {
    if (!feedbackText.trim()) {
      workflowStore.showToast('Please enter your revision feedback.', true);
      return;
    }
    await workflowStore.triggerAction('refine_test_cases', { feedback: feedbackText });
    feedbackText = '';
  }

  function handleNewSession() {
    if (confirm(`Start a new requirements session? Current work is saved under Session ${workflowStore.state.workflow_id}.`)) {
      workflowStore.resetToNewProject();
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
          Stage 5: Test Suite Matrix & JIRA Export ({testCases.length})
        </h2>
      </div>
      <p class="text-xs text-neutral-600 dark:text-neutral-400 mt-1 max-w-3xl">
        Complete executable test cases generated from your business requirements. Traceable, audit-ready, and exportable directly into JIRA (Xray / Zephyr).
      </p>
    </div>
  </div>

  <StreamingBanner />

  {#if testCases.length === 0}
    <div class="bg-white dark:bg-neutral-900 p-12 border-2 border-neutral-300 dark:border-neutral-700 text-center space-y-4">
      <p class="text-sm font-bold text-neutral-700 dark:text-neutral-300">
        No test cases synthesized yet.
      </p>
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('stories')}
        class="px-4 py-2 bg-black text-white dark:bg-white dark:text-black text-xs font-bold uppercase cursor-pointer"
      >
        Go to Stage 4 (User Stories)
      </button>
    </div>
  {:else}
    <!-- Test Metric Breakdown -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
      <div class="bg-white dark:bg-neutral-900 p-4 border-2 border-neutral-300 dark:border-neutral-700 text-center">
        <span class="text-[10px] font-extrabold uppercase font-display text-neutral-500">Total Tests</span>
        <p class="text-2xl font-black text-neutral-950 dark:text-white mt-0.5">{testCases.length}</p>
      </div>
      <div class="bg-white dark:bg-neutral-900 p-4 border-2 border-neutral-300 dark:border-neutral-700 text-center">
        <span class="text-[10px] font-extrabold uppercase font-display text-neutral-500">Functional / Positive</span>
        <p class="text-2xl font-black text-emerald-600 dark:text-[#86BC25] mt-0.5">{positiveCount}</p>
      </div>
      <div class="bg-white dark:bg-neutral-900 p-4 border-2 border-neutral-300 dark:border-neutral-700 text-center">
        <span class="text-[10px] font-extrabold uppercase font-display text-neutral-500">Negative Path</span>
        <p class="text-2xl font-black text-amber-600 mt-0.5">{negativeCount}</p>
      </div>
      <div class="bg-white dark:bg-neutral-900 p-4 border-2 border-neutral-300 dark:border-neutral-700 text-center">
        <span class="text-[10px] font-extrabold uppercase font-display text-neutral-500">Boundary & Limit</span>
        <p class="text-2xl font-black text-purple-600 mt-0.5">{boundaryCount}</p>
      </div>
      <div class="bg-white dark:bg-neutral-900 p-4 border-2 border-neutral-300 dark:border-neutral-700 text-center">
        <span class="text-[10px] font-extrabold uppercase font-display text-neutral-500">Security & Auth</span>
        <p class="text-2xl font-black text-red-600 mt-0.5">{securityCount}</p>
      </div>
    </div>

    <!-- Test Cases Table -->
    <div class="bg-white dark:bg-neutral-900 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs overflow-x-auto">
      <table class="w-full text-left text-xs font-sans">
        <thead class="bg-neutral-200 dark:bg-neutral-950 border-b-2 border-neutral-300 dark:border-neutral-700 text-neutral-900 dark:text-neutral-200 font-display uppercase tracking-wider text-[11px]">
          <tr>
            <th class="py-3 px-4 font-extrabold w-24">Test ID</th>
            <th class="py-3 px-4 font-extrabold w-28">Story Key</th>
            <th class="py-3 px-4 font-extrabold w-64">Test Title</th>
            <th class="py-3 px-4 font-extrabold w-28">Test Type</th>
            <th class="py-3 px-4 font-extrabold w-24">Priority</th>
            <th class="py-3 px-4 font-extrabold">Pre-conditions & Execution Steps</th>
          </tr>
        </thead>
        <tbody class="divide-y-2 divide-neutral-200 dark:divide-neutral-800">
          {#each testCases as tc}
            <tr class="hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
              <td class="py-4 px-4 font-mono text-[11px] font-bold text-neutral-900 dark:text-neutral-100">{tc.id}</td>
              <td class="py-4 px-4 font-mono text-[11px] text-neutral-600 dark:text-neutral-400 font-bold">{tc.story_id}</td>
              <td class="py-4 px-4 font-bold font-display text-neutral-950 dark:text-white">{tc.title}</td>
              <td class="py-4 px-4">
                <span class="px-2 py-0.5 text-[9px] font-mono font-black border border-neutral-400 {tc.test_type === 'NEGATIVE' ? 'bg-amber-100 text-amber-950' : tc.test_type === 'BOUNDARY' ? 'bg-purple-100 text-purple-950' : tc.test_type === 'SECURITY' ? 'bg-red-100 text-red-950' : 'bg-emerald-100 text-emerald-950'}">
                  {tc.test_type}
                </span>
              </td>
              <td class="py-4 px-4 font-mono text-[10px] font-bold">{tc.priority}</td>
              <td class="py-4 px-4 text-xs font-mono space-y-2">
                {#if tc.preconditions && tc.preconditions.length > 0}
                  <div class="text-[10px] text-neutral-500 pb-1">
                    <span class="font-bold text-neutral-700 dark:text-neutral-300">PRE:</span> {tc.preconditions.join('; ')}
                  </div>
                {/if}
                <ol class="list-decimal list-inside space-y-1 text-neutral-800 dark:text-neutral-200">
                  {#each tc.steps || [] as step}
                    <li>
                      {#if typeof step === 'string'}
                        <span class="text-neutral-950 dark:text-white">{step}</span>
                      {:else}
                        <span class="font-bold text-neutral-950 dark:text-white">{step.action || step.step || ''}</span>
                        {#if step.expected_result}
                          <span class="text-neutral-500 dark:text-neutral-400 block pl-4">→ Expected: {step.expected_result}</span>
                        {/if}
                      {/if}
                    </li>
                  {/each}
                </ol>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Specific Revision & Feedback Card for Stage 5 -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-4">
      <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
        <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25]"></span>
          Refine Test Cases
        </h4>
        <span class="text-[11px] text-neutral-500 font-medium">Prompt-assisted revision</span>
      </div>

      <div class="flex flex-col md:flex-row gap-3">
        <textarea
          rows="2"
          bind:value={feedbackText}
          placeholder="Enter revision instructions for test cases (e.g. 'Add stress test for 10,000 concurrent cart updates', 'Add negative test for expired security token')..."
          class="flex-1 p-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white focus:border-black dark:focus:border-[#86BC25]"
        ></textarea>
        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleRevise}
          class="px-5 py-3 bg-neutral-900 hover:bg-black text-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-white transition-colors cursor-pointer shrink-0 disabled:opacity-40"
        >
          🔄 Revise Test Cases
        </button>
      </div>
    </div>

    <!-- Final Stage Actions Bar -->
    <div class="flex items-center justify-between pt-2">
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('stories')}
        class="px-5 py-2.5 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-400 dark:border-neutral-600 cursor-pointer transition-colors"
      >
        ← Back to User Stories
      </button>

      <div class="flex items-center gap-3">
        <button
          type="button"
          onclick={handleNewSession}
          class="px-5 py-2.5 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-200 cursor-pointer transition-colors"
        >
          ➕ Start New Session
        </button>

        <button
          type="button"
          disabled={isExporting}
          onclick={handleExport}
          class="px-6 py-3 bg-[#86BC25] hover:bg-[#72a11f] text-black text-xs font-black uppercase tracking-wider border-2 border-black cursor-pointer shadow-md transition-colors flex items-center gap-2 disabled:opacity-40"
        >
          <span>{isExporting ? 'Generating Excel...' : '📥 Download JIRA Excel (.xlsx)'}</span>
        </button>
      </div>
    </div>
  {/if}
</div>

