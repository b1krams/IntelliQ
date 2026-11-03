<script lang="ts">
  import { auth } from './lib/auth.svelte';
  import { workflowStore } from './lib/stores.svelte';
  import Header from './components/Header.svelte';
  import LoginPage from './components/LoginPage.svelte';
  import WorkflowStepper from './components/WorkflowStepper.svelte';
  import MetricsBar from './components/MetricsBar.svelte';
  import IntakeStage from './components/stages/IntakeStage.svelte';
  import BrdStage from './components/stages/BrdStage.svelte';
  import EpicsStage from './components/stages/EpicsStage.svelte';
  import StoriesStage from './components/stages/StoriesStage.svelte';
  import TestCasesStage from './components/stages/TestCasesStage.svelte';
  import AuditTrail from './components/AuditTrail.svelte';

  let showActivityDrawer = $state(false);
</script>

{#if !auth.isAuthenticated}
  <!-- DEDICATED FULL-PAGE LOGIN SCREEN -->
  <LoginPage />
{:else}
  <!-- MAIN WORKSPACE SCREEN -->
  <div class="min-h-screen flex flex-col font-sans bg-[#F4F4F6] dark:bg-[#0c0c0e] text-neutral-900 dark:text-neutral-100 transition-colors duration-200">
    <!-- Header Navigation -->
    <Header />

    <!-- Toast Notification Container -->
    <aside
      aria-live="polite"
      aria-atomic="true"
      class="fixed bottom-6 right-6 z-50 transition-all duration-200 pointer-events-none bg-neutral-950 text-white dark:bg-white dark:text-neutral-950 px-4 py-3 border-2 shadow-2xl flex items-center gap-3 text-xs font-bold {workflowStore.toast.visible
        ? 'translate-y-0 opacity-100'
        : 'translate-y-24 opacity-0'} {workflowStore.toast.isAlert
        ? 'border-red-600'
        : 'border-[#86BC25]'}"
    >
      <span class="w-2.5 h-2.5 {workflowStore.toast.isAlert ? 'bg-red-600' : 'bg-[#86BC25]'} shrink-0"></span>
      <span>{workflowStore.toast.message}</span>
    </aside>

    <!-- Main Workspace Canvas -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8 space-y-6">
      <!-- Top Metrics Summary (visible once artifacts start forming) -->
      {#if workflowStore.state.epics.length > 0 || workflowStore.state.stories.length > 0 || workflowStore.state.test_cases.length > 0}
        <MetricsBar />
      {/if}

      <!-- Step-by-Step Progress Stepper -->
      <WorkflowStepper />

      <!-- STAGE-SPECIFIC ACTIVE CANVAS -->
      {#if workflowStore.viewStage === 'intake'}
        <IntakeStage />
      {:else if workflowStore.viewStage === 'brd'}
        <BrdStage />
      {:else if workflowStore.viewStage === 'epics'}
        <EpicsStage />
      {:else if workflowStore.viewStage === 'stories'}
        <StoriesStage />
      {:else if workflowStore.viewStage === 'test_cases'}
        <TestCasesStage />
      {/if}
    </main>

    <!-- Floating Activity Log Button & Drawer -->
    <aside aria-label="Activity history" class="fixed bottom-5 left-6 z-30">
      <button
        type="button"
        onclick={() => (showActivityDrawer = !showActivityDrawer)}
        class="px-3 py-1.5 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-950 border-2 border-neutral-700 dark:border-neutral-300 text-[11px] font-black uppercase tracking-wider shadow-lg flex items-center gap-2 cursor-pointer hover:bg-black dark:hover:bg-white transition-colors"
      >
        <span class="w-2 h-2 bg-[#86BC25]"></span>
        <span>{showActivityDrawer ? 'Hide Activity Log' : 'View Activity Log'}</span>
      </button>

      {#if showActivityDrawer}
        <div class="absolute bottom-10 left-0 w-80 sm:w-96 shadow-2xl">
          <AuditTrail />
        </div>
      {/if}
    </aside>

    <!-- Simplified Footer -->
    <footer class="h-12 bg-black text-neutral-400 px-6 flex items-center justify-between text-xs border-t-2 border-neutral-800 mt-12 no-print">
      <div class="flex items-center gap-2">
        <span class="font-extrabold text-white">INTELLIQ<span class="text-[#86BC25]">.</span></span>
        <span class="text-neutral-400 hidden sm:inline">Requirements to Executable Test Cases</span>
      </div>
      <div class="text-[11px] text-neutral-500">
        Enterprise Platform
      </div>
    </footer>
  </div>
{/if}
