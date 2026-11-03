<script lang="ts">
  import { workflowStore } from '../../lib/stores.svelte';

  let showPreview = $state(true);
</script>

{#if workflowStore.isStreaming}
  <div class="bg-neutral-950 text-white border-2 border-neutral-700 p-4 space-y-3 shadow-lg">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="w-3 h-3 bg-[#86BC25] animate-pulse"></span>
        <div>
          <span class="font-extrabold font-display uppercase tracking-wider text-xs text-white">
            Synthesizing Specifications
          </span>
          <p class="text-[11px] text-neutral-400">
            Generating structured output conforming to enterprise quality standards...
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={() => (showPreview = !showPreview)}
          class="px-2.5 py-1 text-[11px] font-bold text-neutral-300 hover:text-white border border-neutral-700 hover:border-neutral-500 cursor-pointer"
        >
          {showPreview ? 'Hide Raw Stream' : 'View Raw Stream'}
        </button>
        <button
          type="button"
          onclick={() => workflowStore.cancelStreaming()}
          class="px-3 py-1 bg-red-950 hover:bg-red-900 text-red-200 border border-red-700 text-xs font-bold uppercase tracking-wider cursor-pointer"
        >
          Cancel
        </button>
      </div>
    </div>

    {#if showPreview && workflowStore.streamingRawText}
      <div class="p-3 bg-neutral-900 border border-neutral-800 font-mono text-[11px] text-[#86BC25] max-h-48 overflow-y-auto whitespace-pre-wrap">
        {workflowStore.streamingRawText}
      </div>
    {/if}
  </div>
{/if}

