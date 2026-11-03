<script lang="ts">
  import { api } from '../lib/api';
  import { workflowStore } from '../lib/stores.svelte';

  interface Props {
    open: boolean;
    onClose: () => void;
  }

  let { open = false, onClose }: Props = $props();
  let isExporting = $state(false);

  async function handleExcelDownload() {
    isExporting = true;
    try {
      const res = await api.exportJiraExcel(workflowStore.state.workflow_id);
      workflowStore.showToast(`Downloaded ${res.filename}`);
      onClose();
    } catch (e: any) {
      workflowStore.showToast(`Export error: ${e.message}`, true);
    } finally {
      isExporting = false;
    }
  }

  function handleMarkdownDownload() {
    const md = `# ${workflowStore.state.brd?.title || workflowStore.state.title}
## Executive Summary
${workflowStore.state.brd?.executive_summary || ''}

## Epics
${workflowStore.state.epics.map((e) => `### ${e.id}: ${e.title}\n${e.summary}\n`).join('\n')}

## User Stories
${workflowStore.state.stories.map((s) => `### ${s.id} (${s.epic_id}): ${s.title}\nAs a ${s.user_role}, I want to ${s.capability}, so that ${s.benefit}.\n`).join('\n')}

## Test Cases
${workflowStore.state.test_cases.map((t) => `### ${t.id} (${t.story_id}): ${t.title}\nType: ${t.test_type}\n`).join('\n')}
`;
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflowStore.state.title.toLowerCase().replace(/ /g, '_')}_spec.md`;
    a.click();
    URL.revokeObjectURL(url);
    workflowStore.showToast('Downloaded Markdown specification.');
    onClose();
  }
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
    <div class="bg-white dark:bg-neutral-900 border-2 border-black dark:border-white p-6 max-w-lg w-full shadow-2xl space-y-5">
      <div class="flex items-center justify-between pb-3 border-b-2 border-neutral-300 dark:border-neutral-700">
        <div class="flex items-center gap-2">
          <div class="w-3 h-3 bg-[#86BC25]"></div>
          <h3 class="text-sm font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display">
            Export JIRA Deliverables Package
          </h3>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="text-neutral-500 hover:text-black dark:hover:text-white font-mono font-bold text-sm cursor-pointer"
        >
          ✕
        </button>
      </div>

      <p class="text-xs text-neutral-600 dark:text-neutral-400">
        Generate compliant, import-ready workbooks mapped directly to standard JIRA, Xray, and Zephyr schemas.
      </p>

      <!-- Package Manifest Table -->
      <div class="border border-neutral-300 dark:border-neutral-700 p-3 bg-neutral-50 dark:bg-neutral-950 text-xs space-y-2">
        <span class="text-[10px] font-mono font-bold text-neutral-500 uppercase block">Workbook Contents Manifest:</span>
        <div class="grid grid-cols-2 gap-2 font-mono text-[11px]">
          <div class="p-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-800">
            <span class="text-neutral-500 block">Sheet 1: Summary</span>
            <span class="font-bold">Traceability Matrix</span>
          </div>
          <div class="p-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-800">
            <span class="text-neutral-500 block">Sheet 2: BRD</span>
            <span class="font-bold">Objectives & Scope</span>
          </div>
          <div class="p-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-800">
            <span class="text-neutral-500 block">Sheet 3: Epics</span>
            <span class="font-bold">{workflowStore.state.epics.length} Epics</span>
          </div>
          <div class="p-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-800">
            <span class="text-neutral-500 block">Sheet 4: Stories</span>
            <span class="font-bold">{workflowStore.state.stories.length} User Stories</span>
          </div>
          <div class="p-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-800 col-span-2">
            <span class="text-neutral-500 block">Sheet 5: Test Cases (Xray / Zephyr)</span>
            <span class="font-bold text-[#4c750b] dark:text-[#86BC25]">{workflowStore.state.test_cases.length} Step-by-Step Test Cases</span>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="pt-2 flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onclick={handleMarkdownDownload}
          class="flex-1 py-2.5 bg-neutral-200 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 text-xs font-bold font-display uppercase tracking-wider hover:bg-neutral-300 dark:hover:bg-neutral-700 cursor-pointer"
        >
          Download Markdown (.md)
        </button>
        <button
          type="button"
          disabled={isExporting}
          onclick={handleExcelDownload}
          class="flex-1 py-2.5 bg-[#86BC25] hover:bg-[#72a11f] text-black text-xs font-black font-display uppercase tracking-wider transition-colors cursor-pointer border border-black shadow-xs disabled:opacity-50"
        >
          {isExporting ? 'Generating XLSX...' : 'Download JIRA Excel (.xlsx)'}
        </button>
      </div>
    </div>
  </div>
{/if}

