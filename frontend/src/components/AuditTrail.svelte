<script lang="ts">
  import { workflowStore } from '../lib/stores.svelte';
</script>

<div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-4">
  <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
    <h4 class="text-xs font-black uppercase tracking-wider text-neutral-950 dark:text-white font-display flex items-center gap-2">
      <span class="w-2.5 h-2.5 bg-neutral-950 dark:bg-white inline-block"></span>
      Recent Activity
    </h4>
  </div>

  <ol class="relative border-l-2 border-neutral-300 dark:border-neutral-700 ml-2 space-y-4 my-1">
    {#each workflowStore.state.history as item}
      <li class="ml-4">
        <span
          class="absolute -left-[5px] mt-1.5 w-2.5 h-2.5 border-2 border-white dark:border-neutral-900 {item.actor === 'AGENT'
            ? 'bg-[#86BC25]'
            : 'bg-neutral-900 dark:bg-white'}"
          aria-hidden="true"
        ></span>
        <div class="flex items-center gap-2">
          <span
            class="px-1.5 py-0.5 text-[9px] font-black uppercase {item.actor === 'AGENT'
              ? 'bg-[#86BC25] text-black'
              : 'bg-black text-white dark:bg-white dark:text-black'}"
          >
            {item.actor === 'AGENT' ? 'AI' : 'USER'}
          </span>
          <time class="text-[10px] text-neutral-500 font-medium">{item.timestamp}</time>
        </div>
        <h6 class="text-xs font-bold text-neutral-950 dark:text-white mt-1">
          {item.action.replace('_', ' ').toUpperCase()}
        </h6>
        <p class="text-[11px] text-neutral-600 dark:text-neutral-400 mt-0.5">{item.details}</p>
      </li>
    {/each}
  </ol>
</div>
