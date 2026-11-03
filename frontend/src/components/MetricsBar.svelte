<script lang="ts">
  import { workflowStore } from '../lib/stores.svelte';

  const epicsCount = $derived(workflowStore.state.epics.length);
  const storiesCount = $derived(workflowStore.state.stories.length);
  const testsCount = $derived(workflowStore.state.test_cases.length);

  const coveragePercent = $derived(
    storiesCount === 0 ? 0 : Math.min(100, Math.round((testsCount / storiesCount) * 100))
  );
</script>

<div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
  <!-- Metric 1: Epics -->
  <div class="bg-white dark:bg-neutral-900 p-5 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs flex flex-col justify-between">
    <div>
      <span class="text-xs font-extrabold uppercase tracking-wider text-neutral-600 dark:text-neutral-400 font-display">
        Epics
      </span>
      <p class="text-3xl font-black tracking-tight text-neutral-950 dark:text-white mt-1 font-display">
        {epicsCount}
      </p>
    </div>
    <div class="mt-2 text-xs font-medium text-neutral-500 dark:text-neutral-400">
      Business capabilities
    </div>
  </div>

  <!-- Metric 2: User Stories -->
  <div class="bg-white dark:bg-neutral-900 p-5 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs flex flex-col justify-between">
    <div>
      <span class="text-xs font-extrabold uppercase tracking-wider text-neutral-600 dark:text-neutral-400 font-display">
        User Stories
      </span>
      <p class="text-3xl font-black tracking-tight text-neutral-950 dark:text-white mt-1 font-display">
        {storiesCount}
      </p>
    </div>
    <div class="mt-2 text-xs font-medium text-neutral-500 dark:text-neutral-400">
      Acceptance criteria ready
    </div>
  </div>

  <!-- Metric 3: Test Cases -->
  <div class="bg-white dark:bg-neutral-900 p-5 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs flex flex-col justify-between">
    <div>
      <span class="text-xs font-extrabold uppercase tracking-wider text-neutral-600 dark:text-neutral-400 font-display">
        Test Cases
      </span>
      <p class="text-3xl font-black tracking-tight text-neutral-950 dark:text-white mt-1 font-display">
        {testsCount}
      </p>
    </div>
    <div class="mt-2 text-xs font-medium text-neutral-500 dark:text-neutral-400">
      Step-by-step test steps
    </div>
  </div>

  <!-- Metric 4: Test Coverage -->
  <div class="bg-white dark:bg-neutral-900 p-5 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs space-y-2 flex flex-col justify-between">
    <div>
      <div class="flex justify-between items-center text-xs">
        <span class="font-extrabold uppercase tracking-wider text-neutral-600 dark:text-neutral-400 font-display">
          Story Coverage
        </span>
        <span class="font-black text-neutral-950 dark:text-white">{coveragePercent}%</span>
      </div>
      <div class="w-full h-2.5 bg-neutral-200 dark:bg-neutral-800 border border-neutral-400 dark:border-neutral-600 mt-2">
        <div class="bg-[#86BC25] h-full transition-all duration-300" style="width: {coveragePercent}%"></div>
      </div>
    </div>
    <span class="text-xs font-medium text-neutral-500 dark:text-neutral-400 block">
      {testsCount} tests mapped to stories
    </span>
  </div>
</div>
