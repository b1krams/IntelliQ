<script lang="ts">
  import { api } from '../lib/api';
  import { workflowStore } from '../lib/stores.svelte';

  let searchQuery = $state('');
  let isExporting = $state(false);

  function switchTab(tab: 'brd' | 'epics' | 'stories' | 'test_cases') {
    workflowStore.activeTab = tab;
  }

  async function triggerExport() {
    isExporting = true;
    try {
      const res = await api.exportJiraExcel(workflowStore.state.workflow_id);
      workflowStore.showToast(`Exported JIRA package: ${res.filename}`);
    } catch (err: any) {
      workflowStore.showToast(`Export failed: ${err.message}`, true);
    } finally {
      isExporting = false;
    }
  }

  function handleSignOff() {
    workflowStore.showToast('Attestation signed and registered by Lead Engagement Partner.');
  }

  const filteredEpics = $derived(
    workflowStore.state.epics.filter(
      (e) =>
        e.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.summary.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  const filteredStories = $derived(
    workflowStore.state.stories.filter(
      (s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.epic_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.capability.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  const filteredTestCases = $derived(
    workflowStore.state.test_cases.filter(
      (t) =>
        t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.story_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.test_type.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );
</script>

<div class="space-y-6">
  <!-- Top Tab Navigation & Search Bar -->
  <div class="bg-white dark:bg-neutral-900 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs">
    <div class="px-6 pt-4 border-b-2 border-neutral-300 dark:border-neutral-700 flex flex-col md:flex-row md:items-center justify-between gap-4">
      <!-- Underline Tabs -->
      <div role="tablist" class="flex gap-6 overflow-x-auto">
        <button
          type="button"
          role="tab"
          onclick={() => switchTab('brd')}
          class="pb-3 text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer {workflowStore.activeTab === 'brd'
            ? 'text-neutral-950 dark:text-white border-b-4 border-[#86BC25]'
            : 'text-neutral-500 hover:text-neutral-950 dark:text-neutral-400 dark:hover:text-white border-b-4 border-transparent'}"
        >
          1. Requirements
        </button>

        <button
          type="button"
          role="tab"
          onclick={() => switchTab('epics')}
          class="pb-3 text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer {workflowStore.activeTab === 'epics'
            ? 'text-neutral-950 dark:text-white border-b-4 border-[#86BC25]'
            : 'text-neutral-500 hover:text-neutral-950 dark:text-neutral-400 dark:hover:text-white border-b-4 border-transparent'}"
        >
          2. Epics ({workflowStore.state.epics.length})
        </button>

        <button
          type="button"
          role="tab"
          onclick={() => switchTab('stories')}
          class="pb-3 text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer {workflowStore.activeTab === 'stories'
            ? 'text-neutral-950 dark:text-white border-b-4 border-[#86BC25]'
            : 'text-neutral-500 hover:text-neutral-950 dark:text-neutral-400 dark:hover:text-white border-b-4 border-transparent'}"
        >
          3. User Stories ({workflowStore.state.stories.length})
        </button>

        <button
          type="button"
          role="tab"
          onclick={() => switchTab('test_cases')}
          class="pb-3 text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer {workflowStore.activeTab === 'test_cases'
            ? 'text-neutral-950 dark:text-white border-b-4 border-[#86BC25]'
            : 'text-neutral-500 hover:text-neutral-950 dark:text-neutral-400 dark:hover:text-white border-b-4 border-transparent'}"
        >
          4. Test Cases ({workflowStore.state.test_cases.length})
        </button>
      </div>

      <!-- Action Search & Export Trigger -->
      <div class="flex items-center gap-2 pb-3">
        <input
          type="search"
          placeholder="Search..."
          bind:value={searchQuery}
          class="px-3 py-1.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-400 dark:border-neutral-600 text-xs font-semibold text-neutral-950 dark:text-white placeholder-neutral-500 focus:outline-hidden"
        />
        <button
          type="button"
          disabled={isExporting}
          onclick={triggerExport}
          class="px-4 py-1.5 bg-black text-white dark:bg-white dark:text-black text-xs font-black uppercase font-display tracking-wider cursor-pointer border border-black hover:bg-neutral-800 dark:hover:bg-neutral-200 transition-colors shrink-0 disabled:opacity-50"
        >
          {isExporting ? 'Exporting...' : '📥 Download Excel'}
        </button>
      </div>
    </div>

    <!-- Live Stream Output Mirror (when stream is active) -->
    {#if workflowStore.isStreaming && workflowStore.streamingRawText}
      <div class="p-4 bg-neutral-950 text-[#86BC25] font-mono text-xs overflow-x-auto max-h-48 border-b-2 border-neutral-700">
        <div class="flex items-center justify-between pb-1 border-b border-neutral-800 text-[10px] text-neutral-400 mb-2">
          <span>Live Generation Preview</span>
          <span>{workflowStore.streamingRawText.length} characters</span>
        </div>
        <pre class="whitespace-pre-wrap">{workflowStore.streamingRawText}</pre>
      </div>
    {/if}

    <!-- TAB 1: BRD DOCUMENT OVERVIEW -->
    {#if workflowStore.activeTab === 'brd'}
      <div class="p-6 space-y-6">
        <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-900 dark:border-neutral-100">
          <div>
            <h3 class="text-sm font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white">
              {workflowStore.state.brd?.title || workflowStore.state.title}
            </h3>
            <p class="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5">
              Version: {workflowStore.state.brd?.version || '1.0'} • Formal Business Requirements Document
            </p>
          </div>
          <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-100 text-emerald-950 border-2 border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-500 text-[10px] font-black uppercase tracking-wider">
            <span class="w-2 h-2 bg-[#86BC25]"></span> Audited
          </span>
        </div>

        <!-- Executive Summary -->
        <div class="p-4 bg-neutral-100 dark:bg-neutral-950 border-l-4 border-black dark:border-white space-y-1">
          <span class="text-[10px] font-extrabold uppercase font-display text-neutral-600 dark:text-neutral-400">Executive Summary</span>
          <p class="text-xs font-medium text-neutral-900 dark:text-neutral-100 leading-relaxed">
            {workflowStore.state.brd?.executive_summary || 'No executive summary generated yet. Click "1. Generate BRD" to synthesize.'}
          </p>
        </div>

        <!-- Objectives & Scope Split Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="p-4 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 space-y-2">
            <h5 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
              Business Objectives
            </h5>
            <ul class="space-y-1.5 text-xs text-neutral-800 dark:text-neutral-200 list-disc list-inside">
              {#each workflowStore.state.brd?.business_objectives || ['Scale-to-zero operational footprint', 'Zero-leak secret hygiene', 'Automated JIRA test case parity'] as obj}
                <li>{obj}</li>
              {/each}
            </ul>
          </div>

          <div class="p-4 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 space-y-2">
            <h5 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
              Scope Definition
            </h5>
            <div class="space-y-2 text-xs">
              <div>
                <span class="font-bold text-[#4c750b] dark:text-[#86BC25] block text-[11px] font-mono">IN-SCOPE:</span>
                <p class="text-neutral-700 dark:text-neutral-300">
                  {(workflowStore.state.brd?.in_scope || ['Serverless stream processing', 'Cognito Lite authentication', 'S3 direct upload presigning']).join(', ')}
                </p>
              </div>
              <div>
                <span class="font-bold text-neutral-500 block text-[11px] font-mono">OUT-OF-SCOPE:</span>
                <p class="text-neutral-700 dark:text-neutral-300">
                  {(workflowStore.state.brd?.out_of_scope || ['EC2 instances or fixed server clusters', 'Paid AWS Secrets Manager']).join(', ')}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Functional Requirements Dossier Table -->
        <div class="space-y-2">
          <span class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display block">
            Functional Requirements Breakdown
          </span>
          <div class="border-2 border-neutral-300 dark:border-neutral-700 overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-neutral-200 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-200 font-display uppercase tracking-wider text-[11px] border-b-2 border-neutral-300 dark:border-neutral-700">
                <tr>
                  <th class="py-3 px-4 font-extrabold">Req ID</th>
                  <th class="py-3 px-4 font-extrabold">Requirement Title</th>
                  <th class="py-3 px-4 font-extrabold">Specification Description</th>
                  <th class="py-3 px-4 font-extrabold">Priority</th>
                </tr>
              </thead>
              <tbody class="divide-y-2 divide-neutral-200 dark:divide-neutral-800">
                {#each workflowStore.state.brd?.functional_requirements || [] as req}
                  <tr class="hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
                    <td class="py-3 px-4 font-mono font-bold text-neutral-900 dark:text-neutral-100">{req.id}</td>
                    <td class="py-3 px-4 font-bold text-neutral-950 dark:text-white font-display">{req.title}</td>
                    <td class="py-3 px-4 text-neutral-700 dark:text-neutral-300">{req.description}</td>
                    <td class="py-3 px-4">
                      <span class="px-2 py-0.5 text-[10px] font-mono font-black border border-neutral-400 {req.priority === 'CRITICAL' ? 'bg-red-100 dark:bg-red-950 text-red-950 dark:text-red-200' : 'bg-neutral-100 dark:bg-neutral-800'}">
                        {req.priority}
                      </span>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    {/if}

    <!-- TAB 2: EPICS MATRIX -->
    {#if workflowStore.activeTab === 'epics'}
      <div class="p-6 space-y-4">
        <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-300 dark:border-neutral-700">
          <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            Agile Deliverable Epics ({filteredEpics.length})
          </h4>
          <span class="text-xs font-mono text-neutral-500">Target JIRA Issue Type: Epic</span>
        </div>

        <div class="border-2 border-neutral-300 dark:border-neutral-700 overflow-x-auto">
          <table class="w-full text-left text-xs font-sans">
            <thead class="bg-neutral-200 dark:bg-neutral-950 border-b-2 border-neutral-300 dark:border-neutral-700 text-neutral-900 dark:text-neutral-200 font-display uppercase tracking-wider text-[11px]">
              <tr>
                <th class="py-3.5 px-4 font-extrabold">Epic Key</th>
                <th class="py-3.5 px-4 font-extrabold">Summary</th>
                <th class="py-3.5 px-4 font-extrabold">Business Value / Narrative</th>
                <th class="py-3.5 px-4 font-extrabold">Acceptance Criteria</th>
              </tr>
            </thead>
            <tbody class="divide-y-2 divide-neutral-200 dark:divide-neutral-800">
              {#each filteredEpics as ep}
                <tr class="hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
                  <td class="py-4 px-4 font-mono text-[11px] font-bold text-neutral-900 dark:text-neutral-100">{ep.id}</td>
                  <td class="py-4 px-4 font-extrabold font-display text-neutral-950 dark:text-white">{ep.title}</td>
                  <td class="py-4 px-4 text-neutral-800 dark:text-neutral-200 font-medium">{ep.business_value || ep.summary}</td>
                  <td class="py-4 px-4 text-[11px] font-mono text-neutral-700 dark:text-neutral-300">
                    <ul class="list-disc list-inside space-y-0.5">
                      {#each ep.acceptance_criteria as ac}
                        <li>{ac}</li>
                      {/each}
                    </ul>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- TAB 3: USER STORIES (INVEST SPECIFICATION) -->
    {#if workflowStore.activeTab === 'stories'}
      <div class="p-6 space-y-4">
        <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-300 dark:border-neutral-700">
          <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            INVEST Backlog User Stories ({filteredStories.length})
          </h4>
          <span class="text-xs font-mono text-neutral-500">Format: Given-When-Then Gherkin</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          {#each filteredStories as st}
            <div class="bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 p-4 space-y-3 shadow-xs">
              <div class="flex items-start justify-between">
                <div>
                  <span class="font-mono text-[10px] font-bold px-1.5 py-0.5 bg-neutral-200 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200">
                    {st.id} • LINKED: {st.epic_id}
                  </span>
                  <h5 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display mt-1.5">
                    {st.title}
                  </h5>
                </div>
                <span class="px-2 py-0.5 bg-neutral-200 dark:bg-neutral-800 font-mono text-[10px] font-black">
                  {st.story_points} PTS
                </span>
              </div>

              <!-- Persona Narrative -->
              <p class="text-xs text-neutral-800 dark:text-neutral-200 font-medium leading-relaxed">
                <span class="font-bold">As a</span> {st.user_role},
                <span class="font-bold">I want to</span> {st.capability},
                <span class="font-bold">so that</span> {st.benefit}.
              </p>

              <!-- Gherkin Criteria -->
              <div class="p-2.5 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-800 space-y-1">
                <span class="text-[10px] font-mono font-bold text-neutral-500 uppercase block">Gherkin Criteria:</span>
                <ul class="text-[11px] font-mono text-neutral-700 dark:text-neutral-300 space-y-1 list-disc list-inside">
                  {#each st.acceptance_criteria_gherkin as crit}
                    <li>{crit}</li>
                  {/each}
                </ul>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- TAB 4: JIRA TEST CASES TABLE -->
    {#if workflowStore.activeTab === 'test_cases'}
      <div class="p-6 space-y-4">
        <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-300 dark:border-neutral-700">
          <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            JIRA-Compatible Test Case Matrix ({filteredTestCases.length})
          </h4>
          <span class="text-xs font-mono text-neutral-500">Compatible with Xray / Zephyr</span>
        </div>

        <div class="border-2 border-neutral-300 dark:border-neutral-700 overflow-x-auto">
          <table class="w-full text-left text-xs font-sans">
            <thead class="bg-neutral-200 dark:bg-neutral-950 border-b-2 border-neutral-300 dark:border-neutral-700 text-neutral-900 dark:text-neutral-200 font-display uppercase tracking-wider text-[11px]">
              <tr>
                <th class="py-3 px-3 font-extrabold">Test ID</th>
                <th class="py-3 px-3 font-extrabold">Story Ref</th>
                <th class="py-3 px-3 font-extrabold">Test Title</th>
                <th class="py-3 px-3 font-extrabold">Type</th>
                <th class="py-3 px-3 font-extrabold">Priority</th>
                <th class="py-3 px-3 font-extrabold">Steps & Expected Results</th>
              </tr>
            </thead>
            <tbody class="divide-y-2 divide-neutral-200 dark:divide-neutral-800">
              {#each filteredTestCases as tc}
                <tr class="hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
                  <td class="py-3 px-3 font-mono text-[11px] font-bold text-neutral-900 dark:text-neutral-100">{tc.id}</td>
                  <td class="py-3 px-3 font-mono text-[10px] text-neutral-600 dark:text-neutral-400">{tc.story_id}</td>
                  <td class="py-3 px-3 font-bold font-display text-neutral-950 dark:text-white">{tc.title}</td>
                  <td class="py-3 px-3">
                    <span class="px-2 py-0.5 text-[9px] font-mono font-black border border-neutral-400 {tc.test_type === 'NEGATIVE' ? 'bg-amber-100 text-amber-950' : tc.test_type === 'BOUNDARY' ? 'bg-purple-100 text-purple-950' : 'bg-emerald-100 text-emerald-950'}">
                      {tc.test_type}
                    </span>
                  </td>
                  <td class="py-3 px-3 font-mono text-[10px] font-bold">{tc.priority}</td>
                  <td class="py-3 px-3 text-[11px] font-mono">
                    <ol class="list-decimal list-inside space-y-1">
                      {#each tc.steps as step}
                        <li>
                          <span class="font-bold text-neutral-900 dark:text-neutral-100">{step.action}</span>
                          <span class="text-neutral-500 block pl-4">→ Expected: {step.expected_result}</span>
                        </li>
                      {/each}
                    </ol>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  </div>

  <!-- SECTION 10 & 11: GOVERNANCE & EMBEDDED AI CARDS -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <!-- Embedded AI Recommendation Card -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 border-t-4 border-t-[#86BC25] space-y-4 shadow-xs">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25]" aria-hidden="true"></span>
          <h5 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            AI Decision Support Insights
          </h5>
        </div>
        <span class="px-2 py-0.5 bg-neutral-100 dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 font-mono text-[10px] font-black text-[#628f14] dark:text-[#86BC25]">
          {(workflowStore.state.ai_insights.confidence_score * 100).toFixed(1)}% CONFIDENCE
        </span>
      </div>

      <div class="p-3 bg-neutral-100 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 space-y-1.5 text-xs">
        <p class="font-extrabold uppercase font-display text-[10px] text-neutral-600 dark:text-neutral-400">Analysis Rationale:</p>
        <ul class="space-y-1 text-neutral-700 dark:text-neutral-300 text-[11px] font-medium list-disc list-inside">
          {#each workflowStore.state.ai_insights.rationale_bullets as bullet}
            <li>{bullet}</li>
          {/each}
        </ul>
      </div>

      <div class="flex items-center gap-2 pt-1">
        <button
          type="button"
          onclick={() => workflowStore.showToast('AI recommendations accepted.')}
          class="flex-1 py-2 bg-neutral-900 hover:bg-black text-white dark:bg-white dark:text-neutral-950 text-xs font-black font-display uppercase tracking-wider cursor-pointer border border-black dark:border-white transition-colors"
        >
          Accept Recommendation
        </button>
        <button
          type="button"
          onclick={() => workflowStore.showToast('AI recommendation marked for manual override.')}
          class="px-3 py-2 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 hover:text-black dark:hover:text-white border border-neutral-300 dark:border-neutral-700 text-xs font-extrabold uppercase font-display cursor-pointer"
        >
          Override
        </button>
      </div>
    </div>

    <!-- Review & Sign-Off -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 space-y-4 shadow-xs">
      <div class="flex items-center justify-between pb-2 border-b border-neutral-200 dark:border-neutral-800">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25]" aria-hidden="true"></span>
          <h5 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            Project Sign-Off & Approval
          </h5>
        </div>
        <span class="text-xs font-bold text-[#4c750b] dark:text-[#86BC25]">READY FOR REVIEW</span>
      </div>

      <p class="text-xs text-neutral-700 dark:text-neutral-300 font-medium">
        All generated requirements, user stories, and test cases have been reviewed and mapped. Approve to finalize the project for export.
      </p>

      <div class="pt-1">
        <button
          type="button"
          onclick={handleSignOff}
          class="w-full py-2.5 bg-[#86BC25] hover:bg-[#72a11f] text-black font-display text-xs font-extrabold uppercase tracking-wider cursor-pointer border border-black shadow-xs transition-colors"
        >
          ✓ Approve & Finalize Requirements
        </button>
      </div>
    </div>
  </div>
</div>

