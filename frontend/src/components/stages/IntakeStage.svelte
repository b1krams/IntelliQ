<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../../lib/api';
  import { auth } from '../../lib/auth.svelte';
  import { workflowStore } from '../../lib/stores.svelte';
  import type { Attachment } from '../../lib/types';
  import StreamingBanner from './StreamingBanner.svelte';

  let userPrompt = $state(workflowStore.state.user_prompt || '');
  let resumeSessionInput = $state('');
  let isUploading = $state(false);
  let uploadProgress = $state(0);
  let isDragOver = $state(false);
  let fileInputRef: HTMLInputElement | null = null;
  let recentSessions = $state<{ workflow_id: string; title: string; current_stage: string; updated_at?: number }[]>([]);
  let isLoadingRecent = $state(false);

  // Sync userPrompt if state already contains it
  $effect(() => {
    if (workflowStore.state.user_prompt && workflowStore.state.user_prompt !== userPrompt) {
      userPrompt = workflowStore.state.user_prompt;
    }
  });

  onMount(async () => {
    if (auth.isAuthenticated) {
      isLoadingRecent = true;
      try {
        const list = await api.listWorkflows();
        if (list && list.length > 0) {
          recentSessions = list.map((w: any) => ({
            workflow_id: w.workflow_id || (w.SK ? w.SK.replace('WORKFLOW#', '') : ''),
            title: w.title || 'Untitled Session',
            current_stage: w.current_stage || 'intake',
            updated_at: w.updated_at,
          })).filter((s) => s.workflow_id && s.workflow_id !== 'wf_sample_init');
        }
      } catch {
        // Soft fallback
      } finally {
        isLoadingRecent = false;
      }
    }
  });

  // Either prompt OR supporting documents is mandatory
  const hasValidInput = $derived(
    userPrompt.trim().length > 0 || workflowStore.stagedAttachments.length > 0
  );

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    if (!auth.isAuthenticated) {
      workflowStore.showToast('Please sign in to upload documents.', true);
      return;
    }

    const file = files[0];
    if (file.size > 50 * 1024 * 1024) {
      workflowStore.showToast('File exceeds 50MB size limit.', true);
      return;
    }

    isUploading = true;
    uploadProgress = 0;
    try {
      const att = await api.uploadFileToS3(file, workflowStore.state.workflow_id, (p) => {
        uploadProgress = p;
      });
      workflowStore.stagedAttachments = [...workflowStore.stagedAttachments, att];
      workflowStore.showToast(`Uploaded ${file.name}`);
    } catch (err: any) {
      workflowStore.showToast(`Upload failed: ${err.message}`, true);
    } finally {
      isUploading = false;
      uploadProgress = 0;
      if (fileInputRef) fileInputRef.value = '';
    }
  }

  function removeAttachment(id: string) {
    workflowStore.stagedAttachments = workflowStore.stagedAttachments.filter((a) => a.id !== id);
    workflowStore.showToast('Document removed.');
  }

  async function handleResumeSession(idToResume?: string) {
    const targetId = (idToResume || resumeSessionInput).trim().toUpperCase();
    if (!targetId) {
      workflowStore.showToast('Please enter a 5-character Session ID to resume.', true);
      return;
    }

    const success = await workflowStore.loadSession(targetId);
    if (success) {
      resumeSessionInput = '';
    }
  }

  async function handleSubmit() {
    if (!hasValidInput) {
      workflowStore.showToast('Please enter requirements notes OR attach a supporting document.', true);
      return;
    }
    workflowStore.state.user_prompt = userPrompt.trim();
    await workflowStore.triggerAction('generate_brd', {
      userPrompt: userPrompt.trim(),
    });
  }
</script>

<div class="space-y-6">
  <!-- Stage 1 Banner with Resume Session Option -->
  <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <div class="flex items-center gap-2">
        <span class="w-3 h-3 bg-[#86BC25]"></span>
        <h2 class="text-base font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white">
          Stage 1: Requirements Scope & Intake
        </h2>
      </div>
      <p class="text-xs text-neutral-600 dark:text-neutral-400 mt-1 max-w-2xl">
        Provide either your requirements context or attach supporting documents (or both). All uploaded files, prompts, and generated artifacts are automatically linked to Session <span class="font-mono font-bold text-neutral-900 dark:text-white">{workflowStore.state.workflow_id}</span>.
      </p>
    </div>

    <!-- Resume Existing Session Input -->
    <div class="flex items-center gap-2 flex-wrap shrink-0">
      <span class="text-xs font-extrabold uppercase tracking-wider text-neutral-600 dark:text-neutral-400 font-display">
        Resume Session:
      </span>
      <div class="flex items-center gap-1.5">
        <input
          type="text"
          maxlength="12"
          placeholder="e.g. K9B2M"
          bind:value={resumeSessionInput}
          class="w-28 px-3 py-1.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-400 dark:border-neutral-600 font-mono font-black text-xs uppercase tracking-widest text-neutral-950 dark:text-white focus:outline-hidden"
          onkeydown={(e) => {
            if (e.key === 'Enter') handleResumeSession();
          }}
        />
        <button
          type="button"
          onclick={() => handleResumeSession()}
          class="px-4 py-1.5 bg-neutral-900 hover:bg-black text-white dark:bg-neutral-100 dark:text-black dark:hover:bg-white text-xs font-black uppercase tracking-wider border-2 border-neutral-800 dark:border-neutral-200 cursor-pointer transition-colors"
        >
          Load
        </button>
      </div>
    </div>
  </div>

  <!-- Recent Sessions Quick-Resume List (if any exist) -->
  {#if recentSessions.length > 0}
    <div class="bg-neutral-50 dark:bg-neutral-950 p-3.5 border-2 border-neutral-300 dark:border-neutral-800 flex items-center gap-2 overflow-x-auto">
      <span class="text-[11px] font-black uppercase font-display text-neutral-500 shrink-0">
        Recent Sessions:
      </span>
      <div class="flex items-center gap-2 flex-wrap">
        {#each recentSessions as sess}
          <button
            type="button"
            onclick={() => handleResumeSession(sess.workflow_id)}
            class="px-2.5 py-1 text-[11px] font-mono font-bold bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 hover:border-black dark:hover:border-[#86BC25] text-neutral-900 dark:text-neutral-100 cursor-pointer flex items-center gap-1.5"
            title="Stage: {sess.current_stage}"
          >
            <span class="font-black text-[#4c750b] dark:text-[#86BC25]">{sess.workflow_id}</span>
            <span class="text-neutral-500 font-sans truncate max-w-[120px]">({sess.title})</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}

  <StreamingBanner />

  <!-- Validation Status Notice -->
  {#if !hasValidInput}
    <div class="p-3.5 bg-amber-50 dark:bg-amber-950/40 border-2 border-amber-600 text-amber-950 dark:text-amber-200 text-xs font-bold flex items-center gap-2.5">
      <span class="text-base">⚠️</span>
      <span>
        Mandatory: Please provide either <strong>Requirements Scope & Context</strong> notes OR upload at least one <strong>Supporting Document</strong> to proceed.
      </span>
    </div>
  {/if}

  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
    <!-- Left Column: Scope & Requirements Context (7 cols) -->
    <div class="lg:col-span-7 space-y-5">
      <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 space-y-4 shadow-xs">
        <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
          <h3 class="text-xs font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white">
            Requirements Scope & Context
          </h3>
          <span class="text-[11px] font-bold text-neutral-500">
            {userPrompt.trim().length > 0 ? '✓ Context provided' : 'Optional if document attached'}
          </span>
        </div>

        <!-- Scope & Discovery Notes -->
        <div class="space-y-1.5">
          <label for="project-notes" class="text-xs font-extrabold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 font-display">
            Business Requirements, Rules & Workflows
          </label>
          <textarea
            id="project-notes"
            rows="8"
            bind:value={userPrompt}
            placeholder="Describe business goals, core user roles, functional capabilities, compliance needs, or paste your discovery transcript notes here..."
            class="w-full p-3.5 bg-neutral-50 dark:bg-neutral-950 border-2 border-neutral-300 dark:border-neutral-700 text-xs font-medium text-neutral-950 dark:text-white leading-relaxed focus:border-black dark:focus:border-[#86BC25]"
          ></textarea>
        </div>

        <!-- Primary Action Button -->
        <div class="pt-2">
          <button
            type="button"
            disabled={!hasValidInput || workflowStore.isStreaming || workflowStore.rateLimitCountdown > 0}
            onclick={handleSubmit}
            class="w-full py-3.5 px-6 bg-black text-white hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer border-2 border-black dark:border-white shadow-md flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {#if workflowStore.isStreaming}
              <span class="w-3 h-3 bg-[#86BC25] animate-pulse"></span>
              <span>Analyzing Requirements & Synthesizing...</span>
            {:else}
              <span>✨ Generate Business Requirements</span>
              <span class="text-neutral-400 dark:text-neutral-600">→</span>
            {/if}
          </button>
        </div>
      </div>
    </div>

    <!-- Right Column: Document Upload (5 cols) -->
    <div class="lg:col-span-5 space-y-5">
      <div class="bg-white dark:bg-neutral-900 p-6 border-2 border-neutral-300 dark:border-neutral-700 space-y-4 shadow-xs">
        <div class="flex items-center justify-between pb-2 border-b-2 border-neutral-200 dark:border-neutral-800">
          <h3 class="text-xs font-black font-display uppercase tracking-wider text-neutral-950 dark:text-white flex items-center gap-2">
            <span class="w-2.5 h-2.5 bg-neutral-950 dark:bg-white inline-block"></span>
            Supporting Documents
          </h3>
          <span class="text-[11px] font-bold text-neutral-500 font-mono">
            {workflowStore.stagedAttachments.length > 0 ? `✓ ${workflowStore.stagedAttachments.length} attached` : 'Optional if context entered'}
          </span>
        </div>

        <p class="text-xs text-neutral-600 dark:text-neutral-400">
          Upload specifications, transcripts, or architecture diagrams. Documents remain linked to Session <span class="font-mono font-bold">{workflowStore.state.workflow_id}</span> without re-uploading.
        </p>

        <!-- Dropzone -->
        <div
          role="button"
          tabindex="0"
          class="p-6 border-2 border-dashed {isDragOver
            ? 'border-[#86BC25] bg-emerald-50/20'
            : 'border-neutral-400 dark:border-neutral-600'} hover:border-black dark:hover:border-[#86BC25] bg-neutral-50 dark:bg-neutral-950 text-center transition-colors cursor-pointer select-none"
          ondragover={(e) => {
            e.preventDefault();
            isDragOver = true;
          }}
          ondragleave={() => (isDragOver = false)}
          ondrop={(e) => {
            e.preventDefault();
            isDragOver = false;
            handleFiles(e.dataTransfer?.files || null);
          }}
          onclick={() => fileInputRef?.click()}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') fileInputRef?.click();
          }}
        >
          <input
            type="file"
            bind:this={fileInputRef}
            class="hidden"
            accept=".txt,.vtt,.docx,.pdf,.png,.jpg,.jpeg,.csv"
            onchange={(e) => handleFiles((e.target as HTMLInputElement).files)}
          />
          <div class="text-2xl mb-1 text-neutral-700 dark:text-neutral-300 font-black">⬆</div>
          <p class="text-xs font-bold text-neutral-900 dark:text-neutral-100 font-display">
            Drag & drop files here, or <span class="text-[#4c750b] dark:text-[#86BC25] underline">browse files</span>
          </p>
          <p class="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            Supported: TXT, PDF, PNG, JPG, DOCX (Max 50MB)
          </p>
        </div>

        {#if isUploading}
          <div class="space-y-1 p-3 bg-neutral-100 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-700">
            <div class="flex justify-between text-xs font-bold">
              <span>Uploading to Session storage...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div class="w-full h-2 bg-neutral-300 dark:bg-neutral-700">
              <div class="bg-[#86BC25] h-full transition-all duration-150" style="width: {uploadProgress}%"></div>
            </div>
          </div>
        {/if}

        <!-- Uploaded Files List -->
        {#if workflowStore.stagedAttachments.length > 0}
          <div class="space-y-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
            <span class="text-[11px] font-bold text-neutral-600 dark:text-neutral-400 uppercase tracking-wider block font-display">
              Linked Session Documents ({workflowStore.stagedAttachments.length})
            </span>
            <ul class="space-y-1.5">
              {#each workflowStore.stagedAttachments as att}
                <li class="flex items-center justify-between p-2.5 bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-700 text-xs">
                  <div class="flex items-center gap-2 truncate pr-2">
                    <span class="w-2 h-2 bg-[#86BC25]"></span>
                    <span class="font-bold text-neutral-900 dark:text-neutral-100 truncate">{att.name}</span>
                    <span class="text-[10px] text-neutral-500 font-mono">({Math.round((att.size_bytes || 0) / 1024)} KB)</span>
                  </div>
                  <button
                    type="button"
                    onclick={() => removeAttachment(att.id)}
                    class="text-neutral-400 hover:text-red-600 dark:hover:text-red-400 font-bold px-1.5 cursor-pointer"
                    title="Remove attachment"
                  >
                    ✕
                  </button>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>
