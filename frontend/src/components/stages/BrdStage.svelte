<script lang="ts">
  import { workflowStore } from '../../lib/stores.svelte';
  import StreamingBanner from './StreamingBanner.svelte';

  let feedbackText = $state('');

  const brd = $derived(workflowStore.state.brd);

  async function handleRevise() {
    if (!feedbackText.trim()) {
      workflowStore.showToast('Please enter your revision feedback.', true);
      return;
    }
    await workflowStore.triggerAction('refine_brd', { feedback: feedbackText });
    feedbackText = '';
  }

  async function handleApproveAndNext() {
    if (workflowStore.state.epics.length > 0) {
      workflowStore.setViewStage('epics');
    } else {
      await workflowStore.triggerAction('generate_epics');
      workflowStore.setViewStage('epics');
    }
  }

  function handleDownloadMarkdown() {
    if (!brd) {
      workflowStore.showToast('No BRD available to download.', true);
      return;
    }

    const lines: string[] = [];
    lines.push(`# ${brd.title || workflowStore.state.title || 'Business Requirements Document'}`);
    lines.push('');
    lines.push(`- **Document Version:** ${brd.version || '1.0'}`);
    lines.push(`- **Session ID:** ${workflowStore.state.workflow_id}`);
    lines.push(`- **Generated At:** ${new Date().toISOString()}`);
    lines.push('');
    lines.push('---');
    lines.push('');

    lines.push('## 1. Executive Summary');
    lines.push('');
    lines.push(brd.executive_summary || 'No executive summary provided.');
    lines.push('');

    if (brd.business_objectives && brd.business_objectives.length > 0) {
      lines.push('## 2. Business Objectives');
      lines.push('');
      for (const obj of brd.business_objectives) {
        lines.push(`- ${obj}`);
      }
      lines.push('');
    }

    if ((brd.in_scope && brd.in_scope.length > 0) || (brd.out_of_scope && brd.out_of_scope.length > 0)) {
      lines.push('## 3. Project Scope Boundary');
      lines.push('');
      if (brd.in_scope && brd.in_scope.length > 0) {
        lines.push('### 3.1 In-Scope');
        lines.push('');
        for (const item of brd.in_scope) {
          lines.push(`- ${item}`);
        }
        lines.push('');
      }
      if (brd.out_of_scope && brd.out_of_scope.length > 0) {
        lines.push('### 3.2 Out-of-Scope');
        lines.push('');
        for (const item of brd.out_of_scope) {
          lines.push(`- ${item}`);
        }
        lines.push('');
      }
    }

    if (brd.stakeholders && brd.stakeholders.length > 0) {
      lines.push('## 4. Key Stakeholders');
      lines.push('');
      lines.push('| Role | Name | Department / Focus |');
      lines.push('| :--- | :--- | :--- |');
      for (const sh of brd.stakeholders) {
        const role = (sh.role || 'Stakeholder').replace(/\|/g, '\\|');
        const name = (sh.name || '-').replace(/\|/g, '\\|');
        const dept = (sh.department || '-').replace(/\|/g, '\\|');
        lines.push(`| ${role} | ${name} | ${dept} |`);
      }
      lines.push('');
    }

    if (brd.functional_requirements && brd.functional_requirements.length > 0) {
      lines.push(`## 5. Functional Requirements Matrix (${brd.functional_requirements.length} Items)`);
      lines.push('');
      lines.push('| Req ID | Requirement Title | Detailed Specification | Priority |');
      lines.push('| :--- | :--- | :--- | :--- |');
      for (const req of brd.functional_requirements) {
        const id = (req.id || '').replace(/\|/g, '\\|');
        const title = (req.title || '').replace(/\|/g, '\\|');
        const desc = (req.description || '').replace(/\r?\n+/g, ' ').replace(/\|/g, '\\|');
        const priority = req.priority || 'MEDIUM';
        lines.push(`| **${id}** | ${title} | ${desc} | \`${priority}\` |`);
      }
      lines.push('');
    }

    if (brd.non_functional_requirements && brd.non_functional_requirements.length > 0) {
      lines.push('## 6. Non-Functional Requirements');
      lines.push('');
      lines.push('| Category | Specification |');
      lines.push('| :--- | :--- |');
      for (const nfr of brd.non_functional_requirements) {
        const cat = (nfr.category || 'General').replace(/\|/g, '\\|');
        const spec = (nfr.specification || '').replace(/\r?\n+/g, ' ').replace(/\|/g, '\\|');
        lines.push(`| **${cat}** | ${spec} |`);
      }
      lines.push('');
    }

    if (brd.assumptions_and_risks && brd.assumptions_and_risks.length > 0) {
      lines.push('## 7. Assumptions & Risks');
      lines.push('');
      lines.push('| Type | Description | Mitigation Strategy |');
      lines.push('| :--- | :--- | :--- |');
      for (const ar of brd.assumptions_and_risks) {
        const type = (ar.type || 'ASSUMPTION').replace(/\|/g, '\\|');
        const desc = (ar.description || '').replace(/\r?\n+/g, ' ').replace(/\|/g, '\\|');
        const mit = (ar.mitigation || 'N/A').replace(/\r?\n+/g, ' ').replace(/\|/g, '\\|');
        lines.push(`| **${type}** | ${desc} | ${mit} |`);
      }
      lines.push('');
    }

    if (brd.compliance_regulatory && brd.compliance_regulatory.length > 0) {
      lines.push('## 8. Compliance & Regulatory Standards');
      lines.push('');
      for (const comp of brd.compliance_regulatory) {
        lines.push(`- ${comp}`);
      }
      lines.push('');
    }

    const md = lines.join('\n');
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const baseName = (brd.title || workflowStore.state.title || `session_${workflowStore.state.workflow_id}`)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
    a.download = `${baseName || 'brd'}_requirements.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    workflowStore.showToast(`Downloaded ${a.download}`);
  }
</script>

<div class="space-y-6">
  <!-- Stage Banner -->
  <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 bg-[#86BC25]"></span>
        <h2 class="text-base font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white">
          Stage 2: Business Requirements Document (BRD)
        </h2>
      </div>
      <p class="text-xs text-neutral-600 dark:text-neutral-400 mt-1 max-w-3xl">
        Review your structured requirements specification. You can provide targeted revision feedback or approve to decompose into agile Epics.
      </p>
    </div>

    <!-- Top Action -->
    {#if brd}
      <div>
        <button
          type="button"
          onclick={handleDownloadMarkdown}
          class="px-4 py-2 bg-white hover:bg-neutral-100 dark:bg-neutral-900 dark:hover:bg-neutral-800 text-neutral-950 dark:text-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-300 cursor-pointer transition-colors flex items-center gap-1.5 shadow-2xs"
          title="Download Business Requirements Document as Markdown (.md)"
        >
          <svg class="w-3.5 h-3.5 text-[#4c750b] dark:text-[#86BC25]" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
          <span>Download BRD (.md)</span>
        </button>
      </div>
    {/if}
  </div>

  <StreamingBanner />

  {#if !brd}
    <div class="bg-white dark:bg-neutral-900 p-8 md:p-12 border-2 border-neutral-300 dark:border-neutral-700 text-center space-y-4">
      {#if workflowStore.state.status === 'error'}
        <div class="p-4 bg-red-100 dark:bg-red-950/60 border-2 border-red-600 text-red-950 dark:text-red-200 text-left space-y-1.5 max-w-2xl mx-auto">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 bg-red-600 shrink-0"></span>
            <span class="text-xs font-black font-display uppercase tracking-wider text-red-800 dark:text-red-300">
              Technical Generation Failure
            </span>
          </div>
          <p class="text-xs font-mono break-words text-red-900 dark:text-red-200">
            {workflowStore.state.ai_insights?.rationale_bullets?.[0] || 'Upstream LLM provider execution failed.'}
          </p>
          <p class="text-[11px] text-red-700 dark:text-red-400">
            Mock content generation is disabled. Please verify your GEMINI_API_KEY / GROQ_API_KEY in .env and retry.
          </p>
        </div>
      {/if}
      <p class="text-sm font-bold text-neutral-700 dark:text-neutral-300">
        No business requirements generated yet.
      </p>
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('intake')}
        class="px-4 py-2 bg-black text-white dark:bg-white dark:text-black text-xs font-bold uppercase cursor-pointer"
      >
        Go to Stage 1 (Intake)
      </button>
    </div>
  {:else}
    <!-- Main BRD Document Canvas -->
    <div class="bg-white dark:bg-neutral-900 p-6 md:p-8 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-6">
      <!-- Document Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b-2 border-neutral-900 dark:border-neutral-100 gap-2">
        <div>
          <h3 class="text-lg font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white">
            {brd.title || workflowStore.state.title}
          </h3>
          <p class="text-xs text-neutral-500 mt-0.5">
            Version {brd.version || '1.0'} • Formal Requirements Specification
          </p>
        </div>
        <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-100 text-emerald-950 border-2 border-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-500 text-xs font-black uppercase tracking-wider self-start md:self-auto">
          <span class="w-2 h-2 bg-[#86BC25]"></span> Ready for Decomposition
        </span>
      </div>

      <!-- Executive Summary -->
      <div class="p-5 bg-neutral-100 dark:bg-neutral-950 border-l-4 border-black dark:border-white space-y-1.5">
        <span class="text-[11px] font-black uppercase font-display text-neutral-600 dark:text-neutral-400">
          Executive Summary
        </span>
        <p class="text-xs font-medium text-neutral-900 dark:text-neutral-100 leading-relaxed">
          {brd.executive_summary}
        </p>
      </div>

      <!-- Objectives & Scope Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Objectives -->
        <div class="p-5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 space-y-3">
          <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            Business Objectives
          </h4>
          <ul class="space-y-2 text-xs text-neutral-800 dark:text-neutral-200 list-disc list-inside">
            {#each brd.business_objectives || [] as obj}
              <li>{obj}</li>
            {/each}
          </ul>
        </div>

        <!-- Scope Definition -->
        <div class="p-5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 space-y-3">
          <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            Scope Boundary
          </h4>
          <div class="space-y-2.5 text-xs">
            <div>
              <span class="font-bold text-[#4c750b] dark:text-[#86BC25] block text-[11px] font-mono">IN-SCOPE:</span>
              <ul class="list-disc list-inside space-y-1 text-neutral-700 dark:text-neutral-300 mt-1">
                {#each brd.in_scope || [] as item}
                  <li>{item}</li>
                {/each}
              </ul>
            </div>
            <div>
              <span class="font-bold text-neutral-500 block text-[11px] font-mono">OUT-OF-SCOPE:</span>
              <ul class="list-disc list-inside space-y-1 text-neutral-700 dark:text-neutral-300 mt-1">
                {#each brd.out_of_scope || [] as item}
                  <li>{item}</li>
                {/each}
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Functional Requirements Table -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            Functional Requirements Matrix ({brd.functional_requirements?.length || 0})
          </h4>
          <span class="text-[11px] font-mono text-neutral-500">Traceable to Epics & Stories</span>
        </div>

        <div class="border-2 border-neutral-300 dark:border-neutral-700 overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-neutral-200 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-200 font-display uppercase tracking-wider text-[11px] border-b-2 border-neutral-300 dark:border-neutral-700">
              <tr>
                <th class="py-3 px-4 font-extrabold w-24">Req ID</th>
                <th class="py-3 px-4 font-extrabold w-64">Requirement Title</th>
                <th class="py-3 px-4 font-extrabold">Detailed Specification</th>
                <th class="py-3 px-4 font-extrabold w-28">Priority</th>
              </tr>
            </thead>
            <tbody class="divide-y-2 divide-neutral-200 dark:divide-neutral-800">
              {#each brd.functional_requirements || [] as req}
                <tr class="hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
                  <td class="py-3.5 px-4 font-mono font-bold text-neutral-900 dark:text-neutral-100">{req.id}</td>
                  <td class="py-3.5 px-4 font-bold text-neutral-950 dark:text-white font-display">{req.title}</td>
                  <td class="py-3.5 px-4 text-neutral-700 dark:text-neutral-300 leading-relaxed">{req.description}</td>
                  <td class="py-3.5 px-4">
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

      <!-- Non-Functional & Risks -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
        {#if brd.non_functional_requirements?.length}
          <div class="p-4 bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 space-y-2">
            <h5 class="text-xs font-bold uppercase tracking-wider text-neutral-900 dark:text-neutral-100 font-display">
              Non-Functional Requirements
            </h5>
            <ul class="space-y-1.5 text-xs text-neutral-700 dark:text-neutral-300">
              {#each brd.non_functional_requirements as nfr}
                <li>
                  <span class="font-bold text-neutral-900 dark:text-neutral-100">[{nfr.category}]:</span> {nfr.specification}
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if brd.assumptions_and_risks?.length}
          <div class="p-4 bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 space-y-2">
            <h5 class="text-xs font-bold uppercase tracking-wider text-neutral-900 dark:text-neutral-100 font-display">
              Assumptions & Risks
            </h5>
            <ul class="space-y-1.5 text-xs text-neutral-700 dark:text-neutral-300">
              {#each brd.assumptions_and_risks as ar}
                <li>
                  <span class="font-bold text-neutral-900 dark:text-neutral-100">[{ar.type}]:</span> {ar.description}
                  {#if ar.mitigation}
                    <span class="text-neutral-500 block text-[11px] pl-2">Mitigation: {ar.mitigation}</span>
                  {/if}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    </div>

    <!-- Specific Revision & Feedback Card for Stage 2 -->
    <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-4">
      <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
        <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display flex items-center gap-2">
          <span class="w-2.5 h-2.5 bg-[#86BC25]"></span>
          Refine Requirements
        </h4>
        <span class="text-[11px] text-neutral-500 font-medium">Prompt-assisted revision</span>
      </div>

      <div class="flex flex-col md:flex-row gap-3">
        <textarea
          rows="2"
          bind:value={feedbackText}
          placeholder="Enter revision instructions (e.g. 'Add requirement for multi-currency payment checkout', 'Mark SMS notifications as out of scope')..."
          class="flex-1 p-3 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white focus:border-black dark:focus:border-[#86BC25]"
        ></textarea>
        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleRevise}
          class="px-5 py-3 bg-neutral-900 hover:bg-black text-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-white transition-colors cursor-pointer shrink-0 disabled:opacity-40"
        >
          🔄 Revise Requirements
        </button>
      </div>
    </div>

    <!-- Bottom Stage Navigation -->
    <div class="flex items-center justify-between pt-2 flex-wrap gap-3">
      <button
        type="button"
        onclick={() => workflowStore.setViewStage('intake')}
        class="px-5 py-2.5 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 text-xs font-black uppercase tracking-wider border-2 border-neutral-400 dark:border-neutral-600 cursor-pointer transition-colors"
      >
        ← Back to Scope
      </button>

      <div class="flex items-center gap-3">
        <button
          type="button"
          onclick={handleDownloadMarkdown}
          class="px-5 py-2.5 bg-white hover:bg-neutral-100 dark:bg-neutral-900 dark:hover:bg-neutral-800 text-neutral-950 dark:text-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-300 cursor-pointer transition-colors flex items-center gap-2 shadow-2xs"
          title="Download BRD as Markdown (.md)"
        >
          <svg class="w-3.5 h-3.5 text-[#4c750b] dark:text-[#86BC25]" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
          <span>Download BRD (.md)</span>
        </button>

        <button
          type="button"
          disabled={workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
          onclick={handleApproveAndNext}
          class="px-6 py-3 bg-[#86BC25] hover:bg-[#72a11f] text-black text-xs font-black uppercase tracking-wider border-2 border-black cursor-pointer shadow-md transition-colors flex items-center gap-2 disabled:opacity-40"
        >
          <span>{workflowStore.state.epics.length > 0 ? 'View Stage 3 (Epics)' : 'Approve & Generate Epics'}</span>
          <span>→</span>
        </button>
      </div>
    </div>
  {/if}
</div>

