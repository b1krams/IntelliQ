<script lang="ts">
  import { auth } from '../lib/auth.svelte';
  import { workflowStore } from '../lib/stores.svelte';

  function handleNewSession() {
    if (confirm('Start a new requirements session? A new 5-character Session ID will be generated.')) {
      workflowStore.resetToNewProject();
    }
  }
</script>

<header class="h-16 bg-black text-white px-6 flex items-center justify-between border-b-2 border-neutral-700 sticky top-0 z-40 shadow-md">
  <div class="flex items-center gap-4">
    <div class="flex items-center font-display tracking-tight text-xl font-extrabold select-none">
      <span>INTELLIQ</span>
      <span class="w-2.5 h-2.5 bg-[#86BC25] inline-block ml-1"></span>
    </div>
    <span class="text-neutral-500 text-sm hidden sm:inline" aria-hidden="true">|</span>
    <nav class="hidden md:flex items-center gap-2 text-xs font-display uppercase tracking-wider text-neutral-400">
      <span>Session</span>
      <span class="text-neutral-600">:</span>
      <span class="font-mono font-black text-[#86BC25] tracking-widest text-sm bg-neutral-900 px-2 py-0.5 border border-neutral-700">
        {workflowStore.state.workflow_id}
      </span>
      {#if workflowStore.state.brd?.title}
        <span class="text-neutral-600">/</span>
        <span class="text-neutral-200 font-bold truncate max-w-xs">{workflowStore.state.brd.title}</span>
      {/if}
    </nav>
  </div>

  <div class="flex items-center gap-3">
    <!-- Start New Session Button -->
    <button
      type="button"
      onclick={handleNewSession}
      class="px-3 py-1.5 bg-neutral-900 hover:bg-neutral-800 text-white text-xs font-black uppercase tracking-wider border-2 border-neutral-600 hover:border-neutral-400 transition-colors cursor-pointer flex items-center gap-1.5"
    >
      <span class="text-[#86BC25] font-black">+</span> New Session
    </button>

    <!-- Theme Toggle -->
    <button
      type="button"
      onclick={() => workflowStore.toggleTheme()}
      title="Toggle Light/Dark Theme"
      aria-label="Toggle Theme"
      class="w-9 h-9 flex items-center justify-center bg-neutral-900 hover:bg-neutral-800 text-white border-2 border-neutral-600 hover:border-neutral-400 transition-colors cursor-pointer"
    >
      {#if workflowStore.theme === 'dark'}
        <svg class="w-4 h-4 text-amber-300 fill-current" viewBox="0 0 20 20" aria-hidden="true">
          <path
            fill-rule="evenodd"
            d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
            clip-rule="evenodd"
          />
        </svg>
      {:else}
        <svg class="w-4 h-4 text-neutral-200 fill-current" viewBox="0 0 20 20" aria-hidden="true">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      {/if}
    </button>

    <!-- User Profile & Sign Out -->
    {#if auth.isAuthenticated}
      <div class="flex items-center gap-3 bg-neutral-900 border border-neutral-700 px-3 py-1.5 text-xs">
        <span class="w-2 h-2 bg-[#86BC25]"></span>
        <span class="text-neutral-200 font-medium truncate max-w-[160px]">{auth.user?.name || auth.user?.email}</span>
        <button
          type="button"
          onclick={() => auth.logout()}
          class="text-neutral-400 hover:text-white font-bold text-xs uppercase cursor-pointer border-l border-neutral-700 pl-2 ml-1"
        >
          Sign Out
        </button>
      </div>
    {/if}
  </div>
</header>
