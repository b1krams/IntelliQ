<script lang="ts">
  import { workflowStore } from '../lib/stores.svelte';

  type StepperStage = 'intake' | 'brd' | 'epics' | 'stories' | 'test_cases';

  const stages: { id: StepperStage; label: string; num: string }[] = [
    { id: 'intake', label: '1. Scope & Intake', num: '01' },
    { id: 'brd', label: '2. Requirements', num: '02' },
    { id: 'epics', label: '3. Epics', num: '03' },
    { id: 'stories', label: '4. User Stories', num: '04' },
    { id: 'test_cases', label: '5. Test Cases & Export', num: '05' },
  ];

  const order: StepperStage[] = ['intake', 'brd', 'epics', 'stories', 'test_cases'];

  function isStageComplete(stageId: StepperStage): boolean {
    if (stageId === 'intake') {
      return !!workflowStore.state.brd || workflowStore.state.current_stage !== 'intake';
    }
    if (stageId === 'brd') {
      return !!workflowStore.state.brd && (workflowStore.state.epics.length > 0 || ['epics', 'stories', 'test_cases', 'export'].includes(workflowStore.state.current_stage));
    }
    if (stageId === 'epics') {
      return workflowStore.state.epics.length > 0 && (workflowStore.state.stories.length > 0 || ['stories', 'test_cases', 'export'].includes(workflowStore.state.current_stage));
    }
    if (stageId === 'stories') {
      return workflowStore.state.stories.length > 0 && (workflowStore.state.test_cases.length > 0 || ['test_cases', 'export'].includes(workflowStore.state.current_stage));
    }
    if (stageId === 'test_cases') {
      return workflowStore.state.test_cases.length > 0;
    }
    return false;
  }

  function canAccessStage(stageId: StepperStage): boolean {
    if (stageId === 'intake') return true;
    if (stageId === 'brd') return !!workflowStore.state.brd || workflowStore.state.current_stage !== 'intake';
    if (stageId === 'epics') return workflowStore.state.epics.length > 0 || ['epics', 'stories', 'test_cases', 'export'].includes(workflowStore.state.current_stage);
    if (stageId === 'stories') return workflowStore.state.stories.length > 0 || ['stories', 'test_cases', 'export'].includes(workflowStore.state.current_stage);
    if (stageId === 'test_cases') return workflowStore.state.test_cases.length > 0 || ['test_cases', 'export'].includes(workflowStore.state.current_stage);
    return false;
  }
</script>

<div class="space-y-2">
  <div class="flex justify-between items-center text-xs">
    <span class="font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
      Project Progression
    </span>
    <div class="flex items-center gap-3 text-xs font-bold text-neutral-600 dark:text-neutral-400">
      <span>
        Active View: <span class="text-neutral-950 dark:text-white uppercase font-black">{workflowStore.viewStage.replace('_', ' ')}</span>
      </span>
      <span>•</span>
      <span>
        Status: <span class="text-[#4c750b] dark:text-[#86BC25] uppercase font-black">{workflowStore.isStreaming ? 'GENERATING...' : workflowStore.state.status}</span>
      </span>
    </div>
  </div>

  <ol class="grid grid-cols-2 md:grid-cols-5 border-2 border-neutral-300 dark:border-neutral-700 divide-x-2 divide-neutral-300 dark:divide-neutral-700 text-xs shadow-xs">
    {#each stages as st}
      {@const complete = isStageComplete(st.id)}
      {@const viewing = workflowStore.viewStage === st.id}
      {@const accessible = canAccessStage(st.id)}

      <li class="h-full">
        <button
          type="button"
          disabled={!accessible}
          class="w-full h-full p-3 text-left transition-colors {accessible ? 'cursor-pointer hover:bg-neutral-100 dark:hover:bg-neutral-800/60' : 'cursor-not-allowed opacity-50'} {viewing
            ? 'border-t-4 border-black dark:border-white bg-white dark:bg-neutral-900 shadow-xs'
            : complete
            ? 'border-t-4 border-[#86BC25] bg-neutral-50 dark:bg-neutral-950'
            : 'border-t-4 border-neutral-300 dark:border-neutral-800 bg-neutral-200/40 dark:bg-neutral-950'}"
          onclick={() => {
            if (accessible) {
              workflowStore.setViewStage(st.id);
            }
          }}
        >
          <div class="flex items-center justify-between">
            <span
              class="text-[10px] font-mono font-bold block {complete
                ? 'text-[#4c750b] dark:text-[#86BC25]'
                : viewing
                ? 'text-neutral-950 dark:text-white'
                : 'text-neutral-500 dark:text-neutral-400'}"
            >
              {complete ? '✓ COMPLETED' : viewing ? 'VIEWING' : 'PENDING'}
            </span>
            <span class="text-[10px] font-mono text-neutral-400">{st.num}</span>
          </div>
          <span class="font-black text-neutral-950 dark:text-white block mt-1 truncate font-display text-xs">
            {st.label}
          </span>
        </button>
      </li>
    {/each}
  </ol>
</div>
